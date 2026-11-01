"""Entrena y compara modelos de riesgo de abstención por sección electoral.

El objetivo es la abstención observada en 2024. Se comparan cinco enfoques:

1. Línea base: usar directamente la abstención de 2021.
2. Ridge con la historia 2009-2021.
3. HistGradientBoosting con la historia 2009-2021.
4. HistGradientBoosting + contexto espacial (municipio/entidad).
5. HistGradientBoosting + contexto espacial + eventos de campaña del SIF.

La validación reserva municipios completos y se repite con varias semillas para
reportar media y desviación estándar. El modelo final se ajusta con todas las
secciones modelables y genera el índice de riesgo, los escenarios X1/X2 y las
tablas de métricas e importancia de variables.

Uso:
    python src/entrenar_modelo.py
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

warnings.filterwarnings("ignore", category=FutureWarning)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "DatosAbiertos"
PROCESSED_DIR = DATA_DIR / "processed"
PANEL_PATH = PROCESSED_DIR / "panel_secciones_2009_2024.parquet"

YEARS = [2009, 2012, 2015, 2018, 2021, 2024]
HIST_YEARS = YEARS[:-1]
KEYS = ["EDOCVE", "MPIOCVE", "SECCION"]
EPS = 1e-4
SEEDS = [42, 7, 2024]
TEST_SIZE = 0.20
TARGET = "abstencion_2024"

HIST_NUMERIC = [
    "tasa_abstencion", "tasa_participacion", "ns_ratio", "LN",
    "prop_18_29", "prop_30_59", "prop_60_mas",
    "prop_hombres", "prop_mujeres", "prop_no_binario",
]
HIST_CATEGORICAL = ["TIPOSEC"]
TIPOSEC_MAP = {"R": 0, "M": 1, "U": 2}


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def inv_logit(x):
    return 1 / (1 + np.exp(-x))


def load_panel() -> pd.DataFrame:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(
            f"No existe {PANEL_PATH}. Ejecuta primero: python src/preparar_datos.py"
        )
    panel = pd.read_parquet(PANEL_PATH)
    for col in ("EDOCVE", "MPIOCVE", "SECCION"):
        panel[col] = pd.to_numeric(panel[col], errors="coerce").fillna(-1).astype(int)
    return panel


def add_missing_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    abst_cols = [f"tasa_abstencion_{y}" for y in HIST_YEARS]
    df["n_anios_historia"] = df[abst_cols].notna().sum(axis=1)
    df["historia_completa"] = (df["n_anios_historia"] == len(HIST_YEARS)).astype(int)
    df["tiene_2021"] = df["tasa_abstencion_2021"].notna().astype(int)
    for year in HIST_YEARS:
        df[f"falta_{year}"] = df[f"tasa_abstencion_{year}"].isna().astype(int)
    return df


def add_spatial_features(df: pd.DataFrame) -> pd.DataFrame:
    """Variables de contexto municipal y estatal construidas solo con 2021."""
    df = df.copy()
    mun = ["EDOCVE", "MPIOCVE"]
    state = ["EDOCVE"]

    def add_group_stats(frame, group, prefix, value_col):
        grouped = frame.groupby(group, dropna=False)[value_col]
        frame[f"{prefix}_mean"] = grouped.transform("mean")
        frame[f"{prefix}_std"] = grouped.transform("std")
        # Leave-one-out: evita que la propia sección domine el promedio.
        total = grouped.transform("sum")
        count = grouped.transform("count")
        frame[f"{prefix}_loo"] = (total - frame[value_col]) / (count - 1).replace(0, np.nan)

    add_group_stats(df, mun, "mun_abst_2021", "tasa_abstencion_2021")
    add_group_stats(df, mun, "mun_part_2021", "tasa_participacion_2021")
    add_group_stats(df, state, "ent_abst_2021", "tasa_abstencion_2021")
    add_group_stats(df, state, "ent_part_2021", "tasa_participacion_2021")

    df["mun_desv_2021"] = df["tasa_abstencion_2021"] - df["mun_abst_2021_mean"]
    df["mun_ln_2021"] = df.groupby(mun, dropna=False)["LN_2021"].transform("sum")
    df["ent_ln_2021"] = df.groupby(state, dropna=False)["LN_2021"].transform("sum")
    df["n_secciones_municipio"] = df.groupby(mun, dropna=False)["SECCION"].transform("size")

    # Tendencias y volatilidad.
    df["tendencia_seccion_18_21"] = (
        df["tasa_abstencion_2021"] - df["tasa_abstencion_2018"]
    )
    df["tendencia_mun_18_21"] = df.groupby(mun, dropna=False)[
        "tendencia_seccion_18_21"
    ].transform("mean")
    df["tendencia_ent_18_21"] = df.groupby(state, dropna=False)[
        "tendencia_seccion_18_21"
    ].transform("mean")

    abst_cols = [f"tasa_abstencion_{y}" for y in HIST_YEARS]
    df["volatilidad_seccion"] = df[abst_cols].std(axis=1, skipna=True)
    df["volatilidad_mun"] = df.groupby(mun, dropna=False)["volatilidad_seccion"].transform("mean")

    # Posición relativa dentro de la entidad.
    df["rank_mun_en_entidad"] = df.groupby(state, dropna=False)[
        "mun_abst_2021_mean"
    ].rank(pct=True)

    # Crecimiento de la lista nominal (información disponible antes de la jornada).
    df["crec_ln_18_21"] = df["LN_2021"] / df["LN_2018"].replace(0, np.nan) - 1
    df["crec_ln_21_24"] = df["LN_2024"] / df["LN_2021"].replace(0, np.nan) - 1
    df["crec_ln_mun_21_24"] = df.groupby(mun, dropna=False)["crec_ln_21_24"].transform("mean")

    # Composición sociodemográfica municipal.
    for col in ("prop_18_29", "prop_60_mas", "prop_mujeres"):
        df[f"mun_{col}_2021"] = df.groupby(mun, dropna=False)[f"{col}_2021"].transform("mean")

    return df


def load_campaign_features() -> pd.DataFrame:
    """Carga y combina los eventos de campaña 2021 y 2024 por municipio."""
    frames = []
    for year in (2021, 2024):
        path = PROCESSED_DIR / f"eventos_municipio_{year}.csv"
        if not path.exists():
            print(f"Aviso: no existe {path}; se omite el bloque de campaña.")
            return pd.DataFrame()
        frame = pd.read_csv(path)
        drop = {"EDONOM", "MPIONOM", "lista_nominal"}
        keep = [c for c in frame.columns if c not in drop]
        frames.append(frame[keep])

    long = pd.concat(frames, ignore_index=True)
    wide = long.pivot_table(
        index=["EDOCVE", "MPIOCVE"], columns="year", aggfunc="first"
    )
    wide.columns = [f"camp_{name}_{year}" for name, year in wide.columns]
    wide = wide.reset_index()

    # Cambios 2021 -> 2024 comparando el mismo ámbito (federal con federal).
    wide["camp_delta_eventos_federal_1000"] = (
        wide.get("camp_eventos_federal_por_1000_ln_2024", np.nan)
        - wide.get("camp_eventos_federal_por_1000_ln_2021", np.nan)
    )
    wide["camp_delta_publicos_federal_1000"] = (
        wide.get("camp_eventos_federal_publicos_por_1000_ln_2024", np.nan)
        - wide.get("camp_eventos_federal_publicos_por_1000_ln_2021", np.nan)
    )
    wide["camp_ratio_eventos_federal"] = (
        wide.get("camp_eventos_federal_2024", np.nan) + 1
    ) / (wide.get("camp_eventos_federal_2021", np.nan) + 1)
    wide["camp_cobertura_2024"] = wide.get("camp_cobertura_2024", 0).fillna(0).astype(int)
    return wide


def build_dataset() -> tuple[pd.DataFrame, list[str], list[str], list[str], list[str]]:
    panel = load_panel()
    data = add_spatial_features(add_missing_flags(panel))

    numeric_hist = [f"{col}_{y}" for y in HIST_YEARS for col in HIST_NUMERIC]
    categorical_hist = [f"TIPOSEC_{y}" for y in HIST_YEARS]
    missing = [
        "n_anios_historia", "historia_completa", "tiene_2021",
        *[f"falta_{y}" for y in HIST_YEARS],
    ]
    spatial = [
        "mun_abst_2021_mean", "mun_abst_2021_std", "mun_abst_2021_loo",
        "mun_part_2021_mean", "mun_part_2021_std", "mun_part_2021_loo",
        "ent_abst_2021_mean", "ent_abst_2021_std", "ent_abst_2021_loo",
        "ent_part_2021_mean", "ent_part_2021_std", "ent_part_2021_loo",
        "mun_desv_2021", "mun_ln_2021", "ent_ln_2021", "n_secciones_municipio",
        "tendencia_seccion_18_21", "tendencia_mun_18_21", "tendencia_ent_18_21",
        "volatilidad_seccion", "volatilidad_mun", "rank_mun_en_entidad",
        "crec_ln_18_21", "crec_ln_21_24", "crec_ln_mun_21_24",
        "mun_prop_18_29_2021", "mun_prop_60_mas_2021", "mun_prop_mujeres_2021",
    ]

    campaign = load_campaign_features()
    campaign_features: list[str] = []
    if not campaign.empty:
        data = data.merge(campaign, on=["EDOCVE", "MPIOCVE"], how="left")
        campaign_features = [
            c for c in campaign.columns if c not in ("EDOCVE", "MPIOCVE")
        ]

    # Categóricas: entidad + tipo de sección de cada año.
    for col in categorical_hist:
        data[col] = data[col].astype("object").fillna("NA")
    data["EDOCVE_CAT"] = data["EDOCVE"].astype(str)

    hist_numeric = numeric_hist + missing
    hist_categorical = categorical_hist + ["EDOCVE_CAT"]
    return data, hist_numeric, hist_categorical, spatial, campaign_features


def make_pipeline(kind: str, numeric: list[str], categorical: list[str]) -> Pipeline:
    if kind == "ridge":
        num_pipe = Pipeline(
            [("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]
        )
        cat_pipe = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
            ]
        )
    else:
        num_pipe = "passthrough"
        cat_pipe = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="most_frequent")),
                (
                    "ordinal",
                    OrdinalEncoder(
                        handle_unknown="use_encoded_value", unknown_value=-1
                    ),
                ),
            ]
        )

    preprocessor = ColumnTransformer(
        [("num", num_pipe, numeric), ("cat", cat_pipe, categorical)]
    )
    if kind == "ridge":
        regressor = Ridge(alpha=10.0, random_state=42)
    else:
        regressor = HistGradientBoostingRegressor(
            max_iter=300,
            learning_rate=0.04,
            max_leaf_nodes=15,
            min_samples_leaf=40,
            l2_regularization=1.0,
            random_state=42,
        )
    return Pipeline([("prep", preprocessor), ("model", regressor)])


def baseline_prediction(df: pd.DataFrame) -> np.ndarray:
    base = df["tasa_abstencion_2021"].copy()
    base = base.fillna(df["tasa_abstencion_2021"].median())
    return base.clip(0, 1).to_numpy()


def evaluate_models(data: pd.DataFrame, feature_sets: dict[str, tuple[list[str], list[str]]]):
    modelable = data[data["seccion_valida_2024"]].copy()
    modelable["objetivo_logit"] = logit(modelable[TARGET])
    groups = (modelable["EDOCVE"].astype(str) + "_" + modelable["MPIOCVE"].astype(str)).to_numpy()

    detail_rows = []
    for seed in SEEDS:
        splitter = GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE, random_state=seed)
        train_idx, test_idx = next(splitter.split(modelable, groups=groups))
        train = modelable.iloc[train_idx]
        test = modelable.iloc[test_idx]
        y_test = test[TARGET].to_numpy()

        # Línea base.
        pred = baseline_prediction(test)
        detail_rows.append(
            _metric_row("baseline_2021", seed, y_test, pred, len(train), len(test))
        )

        for name, (numeric, categorical) in feature_sets.items():
            kind = "ridge" if name.startswith("ridge") else "hgb"
            features = numeric + categorical
            pipeline = make_pipeline(kind, numeric, categorical)
            pipeline.fit(train[features], train["objetivo_logit"])
            pred = np.clip(inv_logit(pipeline.predict(test[features])), 0, 1)
            detail_rows.append(
                _metric_row(name, seed, y_test, pred, len(train), len(test))
            )
            print(f"  semilla {seed}: {name} listo")

    detail = pd.DataFrame(detail_rows)
    summary = (
        detail.groupby("modelo", as_index=False)
        .agg(
            mae_media=("MAE", "mean"), mae_sd=("MAE", "std"),
            rmse_media=("RMSE", "mean"), rmse_sd=("RMSE", "std"),
            r2_media=("R2", "mean"), r2_sd=("R2", "std"),
            n_entrenamiento=("n_entrenamiento", "mean"),
            n_prueba=("n_prueba", "mean"),
        )
        .sort_values("mae_media")
    )
    return detail, summary, modelable


def _metric_row(model: str, seed: int, y_true, y_pred, n_train: int, n_test: int) -> dict:
    return {
        "modelo": model,
        "semilla": seed,
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": mean_squared_error(y_true, y_pred) ** 0.5,
        "R2": r2_score(y_true, y_pred),
        "n_entrenamiento": n_train,
        "n_prueba": n_test,
    }


def permutation_table(pipeline, test: pd.DataFrame, features: list[str], seed: int = 42) -> pd.DataFrame:
    sample = test.sample(min(len(test), 8_000), random_state=seed)
    result = permutation_importance(
        pipeline,
        sample[features],
        sample[TARGET],
        scoring="neg_mean_absolute_error",
        n_repeats=3,
        random_state=seed,
        n_jobs=-1,
    )
    table = pd.DataFrame(
        {
            "variable": features,
            "importancia_media": result.importances_mean,
            "importancia_sd": result.importances_std,
        }
    ).sort_values("importancia_media", ascending=False)
    return table.reset_index(drop=True)


def shap_table(pipeline, test: pd.DataFrame, features: list[str], seed: int = 42) -> pd.DataFrame | None:
    try:
        import shap
    except ImportError:
        return None
    model = pipeline.named_steps["model"]
    if not isinstance(model, HistGradientBoostingRegressor):
        return None
    prep = pipeline.named_steps["prep"]
    sample = test.sample(min(len(test), 2_000), random_state=seed)
    transformed = prep.transform(sample[features])
    names = prep.get_feature_names_out()
    explainer = shap.TreeExplainer(model)
    values = explainer.shap_values(transformed)
    table = pd.DataFrame(
        {"variable": names, "shap_abs_medio": np.abs(values).mean(axis=0)}
    ).sort_values("shap_abs_medio", ascending=False)
    return table.reset_index(drop=True)


def assign_levels(risk: pd.Series) -> pd.Series:
    levels = pd.cut(
        risk * 100,
        bins=[-np.inf, 35, 50, 65, np.inf],
        labels=["Bajo", "Medio", "Alto", "Muy alto"],
    )
    return pd.Categorical(
        levels,
        categories=["Bajo", "Medio", "Alto", "Muy alto", "Sin dato"],
        ordered=True,
    )


def main() -> None:
    print("Cargando panel y construyendo variables...")
    data, hist_numeric, hist_categorical, spatial, campaign = build_dataset()
    print(f"Secciones 2024: {len(data):,}")
    print(f"Modelables: {int(data['seccion_valida_2024'].sum()):,}")
    print(f"Con historia 2021: {int(data['tiene_historia_2021'].sum()):,}")
    print(f"Con historia completa 2009-2021: {int(data['historia_completa'].sum()):,}")

    feature_sets = {
        "ridge_historia": (hist_numeric, hist_categorical),
        "hgb_historia": (hist_numeric, hist_categorical),
        "hgb_espacial": (hist_numeric + spatial, hist_categorical),
    }
    if campaign:
        feature_sets["hgb_espacial_campana"] = (
            hist_numeric + spatial + campaign,
            hist_categorical,
        )

    print("\nEvaluando modelos con validación por municipio...")
    detail, summary, modelable = evaluate_models(data, feature_sets)
    print("\nResumen de métricas (media de 3 particiones):")
    print(summary.to_string(index=False))

    best_name = summary.iloc[0]["modelo"]
    print(f"\nMejor modelo: {best_name}")

    numeric, categorical = feature_sets[best_name]
    features = numeric + categorical
    pipeline = make_pipeline(
        "ridge" if best_name.startswith("ridge") else "hgb", numeric, categorical
    )
    pipeline.fit(modelable[features], modelable["objetivo_logit"])

    # Importancia de variables sobre una partición de validación.
    splitter = GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE, random_state=42)
    groups = (modelable["EDOCVE"].astype(str) + "_" + modelable["MPIOCVE"].astype(str)).to_numpy()
    _, test_idx = next(splitter.split(modelable, groups=groups))
    test = modelable.iloc[test_idx]
    importance = permutation_table(pipeline, test, features)
    shap_importance = shap_table(pipeline, test, features)

    # Predicción final para todas las secciones.
    data["riesgo_modelo"] = np.nan
    valid = data["seccion_valida_2024"]
    data.loc[valid, "riesgo_modelo"] = np.clip(
        inv_logit(pipeline.predict(data.loc[valid, features])), 0, 1
    )
    data["riesgo"] = (data["riesgo_modelo"] * 100).round(2)
    data["nivel_riesgo"] = assign_levels(data["riesgo_modelo"])
    data.loc[~valid, "nivel_riesgo"] = "Sin dato"
    data["abstencion_esperada_personas"] = data["riesgo_modelo"] * data["LN_2024"]
    data["prioridad"] = data["abstencion_esperada_personas"]

    intervencion = data["nivel_riesgo"].isin(["Alto", "Muy alto"])
    for name, reduction in (("X1_informativa", 0.03), ("X2_intensiva", 0.07)):
        tasa = data["riesgo_modelo"].where(~intervencion, (data["riesgo_modelo"] - reduction).clip(lower=0))
        data[name] = tasa
        data[f"personas_movilizables_{name}"] = (data["riesgo_modelo"] - tasa) * data["LN_2024"]

    scenarios = pd.DataFrame(
        {
            "escenario": ["Sin intervención", "X1 informativa", "X2 intensiva"],
            "reduccion_aplicada": ["0 puntos", "3 puntos", "7 puntos"],
            "personas_potencialmente_movilizables": [
                0,
                data["personas_movilizables_X1_informativa"].sum(),
                data["personas_movilizables_X2_intensiva"].sum(),
            ],
            "abstencion_promedio_escenario": [
                data["riesgo_modelo"].mean(),
                data["X1_informativa"].mean(),
                data["X2_intensiva"].mean(),
            ],
            "secciones_intervenidas": [
                0,
                int(intervencion.sum()),
                int(intervencion.sum()),
            ],
        }
    )

    levels = (
        data.groupby("nivel_riesgo", observed=False)
        .agg(
            secciones=("nivel_riesgo", "size"),
            lista_nominal=("LN_2024", "sum"),
            abstencion_esperada=("abstencion_esperada_personas", "sum"),
            riesgo_promedio=("riesgo", "mean"),
        )
        .reset_index()
    )
    levels["nivel_riesgo"] = pd.Categorical(
        levels["nivel_riesgo"],
        categories=["Bajo", "Medio", "Alto", "Muy alto", "Sin dato"],
        ordered=True,
    )
    levels = levels.sort_values("nivel_riesgo")

    entities = (
        data.groupby("EDONOM", as_index=False)
        .agg(
            secciones=("SECCION", "size"),
            secciones_modeladas=("seccion_valida_2024", "sum"),
            lista_nominal=("LN_2024", "sum"),
            riesgo_promedio=("riesgo_modelo", "mean"),
            alto_muy_alto=("nivel_riesgo", lambda s: int(s.isin(["Alto", "Muy alto"]).sum())),
        )
        .sort_values("riesgo_promedio", ascending=False)
    )

    # Salidas.
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    detail.to_csv(PROCESSED_DIR / "metricas_por_semilla.csv", index=False)
    summary.to_csv(PROCESSED_DIR / "metricas_modelos.csv", index=False)
    importance.to_csv(PROCESSED_DIR / "importancia_permutacion.csv", index=False)
    if shap_importance is not None:
        shap_importance.to_csv(PROCESSED_DIR / "importancia_shap.csv", index=False)
    scenarios.to_csv(BASE_DIR / "escenarios_modelo_riesgo_2024.csv", index=False)
    levels.to_csv(PROCESSED_DIR / "resumen_niveles_riesgo.csv", index=False)
    entities.to_csv(PROCESSED_DIR / "resumen_entidades.csv", index=False)
    joblib.dump(
        {"pipeline": pipeline, "features": features, "modelo": best_name},
        PROCESSED_DIR / "modelo_riesgo.joblib",
    )

    output_cols = [
        *KEYS, "EDONOM", "MPIONOM", "TIPOSEC_2024", "DEF", "DEL",
        "LN_2024", "SV_2024", "NV_2024", "abstencion_2024",
        "riesgo_modelo", "riesgo", "nivel_riesgo", "prioridad",
        "abstencion_esperada_personas",
        "X1_informativa", "X2_intensiva",
        "personas_movilizables_X1_informativa", "personas_movilizables_X2_intensiva",
        "seccion_valida_2024", "tiene_historia_2021", "historia_completa",
    ]
    result = data[output_cols].sort_values(
        ["nivel_riesgo", "prioridad"], ascending=[True, False]
    ).copy()
    for col in ("DEF", "DEL"):
        result[col] = pd.to_numeric(result[col], errors="coerce").astype("Int64")
    result.to_csv(BASE_DIR / "resultado_modelo_riesgo_2024.csv", index=False)

    metadata = {
        "modelo_seleccionado": best_name,
        "secciones_totales": int(len(data)),
        "secciones_modeladas": int(valid.sum()),
        "secciones_sin_dato": int((~valid).sum()),
        "semillas": SEEDS,
        "test_size": TEST_SIZE,
        "variables": features,
        "metricas": summary.to_dict(orient="records"),
    }
    with open(PROCESSED_DIR / "modelo_metadata.json", "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, ensure_ascii=False, indent=2)

    print("\nResumen por nivel de riesgo:")
    print(levels.to_string(index=False))
    print("\nEscenarios:")
    print(scenarios.to_string(index=False))
    print(f"\nResultado: {BASE_DIR / 'resultado_modelo_riesgo_2024.csv'}")
    print(f"Métricas: {PROCESSED_DIR / 'metricas_modelos.csv'}")


if __name__ == "__main__":
    main()
