"""Prepara el panel de secciones electorales 2009-2024.

Lee los CSV originales del INE (DatosAbiertos/), agrega la información de
casillas a nivel de sección y construye un panel ancho con las variables
históricas que usa el modelo de riesgo.

Uso:
    python src/preparar_datos.py
    python src/preparar_datos.py --force
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "DatosAbiertos"
PROCESSED_DIR = DATA_DIR / "processed"

YEARS = [2009, 2012, 2015, 2018, 2021, 2024]
KEYS = ["EDOCVE", "MPIOCVE", "SECCION"]
RAW_USECOLS = [
    "EDOCVE", "EDONOM", "MPIOCVE", "MPIONOM", "SECCION", "TIPOSEC",
    "DEF", "DEL", "SEXO", "EDAD", "LN", "SV", "NV", "NS",
]
NUMERIC_COLS = [
    "EDOCVE", "MPIOCVE", "SECCION", "DEF", "DEL", "SEXO", "EDAD",
    "LN", "SV", "NV", "NS",
]
AGE_BINS = [17, 29, 59, np.inf]
AGE_LABELS = ["18_29", "30_59", "60_mas"]
SEXO_MAP = {0: "hombres", 1: "mujeres", 2: "no_binario"}
CHUNK_SIZE = 250_000

FIRST_COLS = ["TIPOSEC", "EDONOM", "MPIONOM", "DEF", "DEL"]


def _first_non_null(series: pd.Series):
    series = series.dropna()
    return series.iloc[0] if len(series) else np.nan


def _read_chunks(file: Path):
    return pd.read_csv(
        file, encoding="utf-8-sig", usecols=RAW_USECOLS, chunksize=CHUNK_SIZE
    )


def _prepare_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    chunk.columns = [str(c).replace("\ufeff", "").strip() for c in chunk.columns]
    for col in NUMERIC_COLS:
        chunk[col] = pd.to_numeric(chunk[col], errors="coerce").fillna(0)
    for col in ("LN", "SV", "NV", "NS"):
        chunk[col] = chunk[col].clip(lower=0)

    chunk["TIPOSEC"] = chunk["TIPOSEC"].astype(str).str.strip().str.upper()
    chunk["EDONOM"] = chunk["EDONOM"].astype(str).str.strip()
    chunk["MPIONOM"] = chunk["MPIONOM"].astype(str).str.strip()

    chunk["edad_grupo"] = (
        pd.cut(chunk["EDAD"], bins=AGE_BINS, labels=AGE_LABELS)
        .astype("object")
        .fillna("sin_dato")
    )
    chunk["sexo_grupo"] = chunk["SEXO"].map(SEXO_MAP).fillna("sin_dato")
    return chunk


def _aggregate_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
    """Agrega un chunk a nivel sección con desgloses de edad y sexo."""
    base = chunk.groupby(KEYS, as_index=False, dropna=False).agg(
        LN=("LN", "sum"),
        SV=("SV", "sum"),
        NV=("NV", "sum"),
        NS=("NS", "sum"),
        TIPOSEC=("TIPOSEC", _first_non_null),
        EDONOM=("EDONOM", _first_non_null),
        MPIONOM=("MPIONOM", _first_non_null),
        DEF=("DEF", _first_non_null),
        DEL=("DEL", _first_non_null),
    )

    edad = (
        chunk.groupby(KEYS + ["edad_grupo"], dropna=False)["LN"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )
    edad.columns.name = None
    edad = edad.rename(
        columns={name: f"edad_{name}" for name in edad.columns if name not in KEYS}
    )

    sexo = (
        chunk.groupby(KEYS + ["sexo_grupo"], dropna=False)["LN"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )
    sexo.columns.name = None
    sexo = sexo.rename(
        columns={name: f"sexo_{name}" for name in sexo.columns if name not in KEYS}
    )

    return base.merge(edad, on=KEYS, how="left").merge(sexo, on=KEYS, how="left")


def aggregate_election(year: int) -> pd.DataFrame:
    """Agrega los 32 CSV de una elección a nivel de sección."""
    data_dir = DATA_DIR / f"DatosAbiertos_DECEyEC_ConteosCensales{year}"
    files = sorted(data_dir.glob(f"datosabiertos_deceyec_conteoscensales{year}_*.csv"))
    if len(files) != 32:
        raise FileNotFoundError(
            f"Se esperaban 32 archivos para {year} en {data_dir}, se encontraron {len(files)}. "
            "Ejecuta primero: python src/descargar_datos.py"
        )

    partials: list[pd.DataFrame] = []
    for file in files:
        for chunk in _read_chunks(file):
            partials.append(_aggregate_chunk(_prepare_chunk(chunk)))

    result = pd.concat(partials, ignore_index=True)

    # Columnas de desglose: garantizar que existan todas.
    for name in AGE_LABELS + ["sin_dato"]:
        col = f"edad_{name}"
        if col not in result.columns:
            result[col] = 0
    for name in list(SEXO_MAP.values()) + ["sin_dato"]:
        col = f"sexo_{name}"
        if col not in result.columns:
            result[col] = 0

    agg = {
        "LN": "sum", "SV": "sum", "NV": "sum", "NS": "sum",
        **{f"edad_{n}": "sum" for n in AGE_LABELS + ["sin_dato"]},
        **{f"sexo_{n}": "sum" for n in list(SEXO_MAP.values()) + ["sin_dato"]},
        **{c: _first_non_null for c in FIRST_COLS},
    }
    result = result.groupby(KEYS, as_index=False, dropna=False).agg(agg)

    total = (result["SV"] + result["NV"]).replace(0, np.nan)
    nominal = result["LN"].replace(0, np.nan)
    result["tasa_abstencion"] = result["NV"] / total
    result["tasa_participacion"] = result["SV"] / total
    result["ns_ratio"] = result["NS"] / nominal

    for name in AGE_LABELS:
        result[f"prop_{name}"] = result[f"edad_{name}"] / nominal
    for name in SEXO_MAP.values():
        result[f"prop_{name}"] = result[f"sexo_{name}"] / nominal

    result["year"] = year
    return result


def build_panel(force: bool = False) -> pd.DataFrame:
    """Construye el panel ancho 2009-2024 y lo guarda en Parquet."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    panel_path = PROCESSED_DIR / "panel_secciones_2009_2024.parquet"
    if panel_path.exists() and not force:
        print(f"Panel ya existe: {panel_path}")
        return pd.read_parquet(panel_path)

    elections: dict[int, pd.DataFrame] = {}
    summary_rows = []
    for year in YEARS:
        print(f"Agregando {year}...")
        frame = aggregate_election(year)
        elections[year] = frame
        frame.to_parquet(PROCESSED_DIR / f"secciones_{year}.parquet", index=False)
        validos = (frame["SV"] + frame["NV"]).sum()
        summary_rows.append(
            {
                "year": year,
                "secciones": len(frame),
                "lista_nominal": frame["LN"].sum(),
                "si_votaron": frame["SV"].sum(),
                "no_votaron": frame["NV"].sum(),
                "no_especificados": frame["NS"].sum(),
                "tasa_abstencion": frame["NV"].sum() / validos if validos else np.nan,
                "secciones_sin_tasa": int(frame["tasa_abstencion"].isna().sum()),
            }
        )
        print(f"  {len(frame):,} secciones")

    feature_cols = [
        "tasa_abstencion", "tasa_participacion", "ns_ratio", "LN",
        "prop_18_29", "prop_30_59", "prop_60_mas",
        "prop_hombres", "prop_mujeres", "prop_no_binario",
    ]
    base = elections[2024][
        KEYS + ["EDONOM", "MPIONOM", "TIPOSEC", "DEF", "DEL", "LN", "SV", "NV", "NS",
                "tasa_abstencion", "tasa_participacion", "ns_ratio"]
    ].rename(
        columns={
            "LN": "LN_2024", "SV": "SV_2024", "NV": "NV_2024", "NS": "NS_2024",
            "tasa_abstencion": "abstencion_2024",
            "tasa_participacion": "participacion_2024",
            "ns_ratio": "ns_ratio_2024", "TIPOSEC": "TIPOSEC_2024",
        }
    )

    for year in YEARS[:-1]:
        frame = elections[year][KEYS + feature_cols + ["TIPOSEC"]].rename(
            columns={c: f"{c}_{year}" for c in feature_cols + ["TIPOSEC"]}
        )
        base = base.merge(frame, on=KEYS, how="left")

    base["seccion_valida_2024"] = base["abstencion_2024"].notna()
    base["tiene_historia_2021"] = base["tasa_abstencion_2021"].notna()
    base["tiene_historia_completa"] = base[
        [f"tasa_abstencion_{y}" for y in YEARS[:-1]]
    ].notna().all(axis=1)

    base.to_parquet(panel_path, index=False)
    pd.DataFrame(summary_rows).to_csv(PROCESSED_DIR / "resumen_conteos.csv", index=False)
    print(f"Panel guardado: {panel_path} ({len(base):,} secciones)")
    return base


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepara el panel de secciones 2009-2024.")
    parser.add_argument("--force", action="store_true", help="Recalcula aunque exista el panel.")
    args = parser.parse_args()
    build_panel(force=args.force)


if __name__ == "__main__":
    main()
