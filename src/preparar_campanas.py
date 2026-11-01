"""Agrega los datos de campaña del SIF a nivel municipio.

Genera, para 2021 y 2024:

- Conteo de eventos de campaña realizados (públicos, privados, onerosos).
- Eventos por partido / coalición.
- Eventos por cada 1,000 personas en lista nominal.
- Un resumen de gasto de campaña por entidad federativa.

Los archivos de entrada viven en ``DatosAbiertos/Campanas`` y los productos en
``DatosAbiertos/processed``.

Uso:
    python src/preparar_campanas.py
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "DatosAbiertos"
CAMP_DIR = DATA_DIR / "Campanas"
PROCESSED_DIR = DATA_DIR / "processed"

EVENT_FILES = {
    2024: [
        CAMP_DIR / "PREFO_23-24_CAM_AE_240624.csv",
        *sorted((CAMP_DIR / "Eventos_2024_Local" / "Eventos_csv_24062024").glob("*.csv")),
    ],
    2021: [CAMP_DIR / "Eventos_2021_Federal" / "PEFO_20-21_CAMPAÑA_EVENTOS_210622.csv"],
}

PARTY_PATTERNS = {
    "morena": r"\bMORENA\b",
    "pan": r"\bPAN\b",
    "pri": r"\bPRI\b",
    "prd": r"\bPRD\b",
    "pvem": r"\bPVEM\b|\bVERDE\b",
    "pt": r"\bPT\b",
    "mc": r"\bMC\b|MOVIMIENTO CIUDADANO",
}

BAD_EVENT_NAMES = {"", "SIN EVENTO", "SIN AGENDA", "NO HAY AGENDA", "N/A", "NA"}


def norm(text) -> str:
    """Normaliza nombres para cruzar entidades y municipios."""
    if pd.isna(text):
        return ""
    text = unicodedata.normalize("NFKD", str(text))
    text = text.encode("ascii", "ignore").decode("ascii").upper().strip()
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_municipio(value) -> tuple[float, str]:
    """Separa ``"3-CALVILLO"`` en clave y nombre."""
    if pd.isna(value):
        return np.nan, ""
    text = str(value).strip()
    match = re.match(r"^(\d+)\s*-\s*(.+)$", text)
    if match:
        return float(match.group(1)), match.group(2).strip()
    return np.nan, text


def cargar_catalogo() -> pd.DataFrame:
    """Catálogo de municipios con lista nominal de 2021 y 2024."""
    panel_path = PROCESSED_DIR / "panel_secciones_2009_2024.parquet"
    if panel_path.exists():
        panel = pd.read_parquet(
            panel_path,
            columns=["EDOCVE", "EDONOM", "MPIOCVE", "MPIONOM", "LN_2021", "LN_2024"],
        )
        catalog = (
            panel.groupby(["EDOCVE", "EDONOM", "MPIOCVE", "MPIONOM"], as_index=False)
            .agg(LN_2021=("LN_2021", "sum"), LN_2024=("LN_2024", "sum"))
        )
    else:
        print("Panel no encontrado; leyendo el catálogo desde los CSV de 2024.")
        files = sorted(
            (DATA_DIR / "DatosAbiertos_DECEyEC_ConteosCensales2024").glob("*.csv")
        )
        frames = [
            pd.read_csv(
                f,
                encoding="utf-8-sig",
                usecols=["EDOCVE", "EDONOM", "MPIOCVE", "MPIONOM", "LN"],
            )
            for f in files
        ]
        raw = pd.concat(frames, ignore_index=True)
        catalog = (
            raw.groupby(["EDOCVE", "EDONOM", "MPIOCVE", "MPIONOM"], as_index=False)
            .agg(LN_2024=("LN", "sum"))
        )
        catalog["LN_2021"] = np.nan

    catalog["ent_norm"] = catalog["EDONOM"].map(norm)
    catalog["mun_norm"] = catalog["MPIONOM"].map(norm)
    return catalog


def leer_eventos(year: int) -> pd.DataFrame:
    frames = []
    for file in EVENT_FILES[year]:
        if not file.exists():
            print(f"  Aviso: no existe {file}")
            continue
        encoding = "latin-1" if year == 2021 else "utf-8-sig"
        frame = pd.read_csv(file, encoding=encoding, low_memory=False)
        frame["archivo_origen"] = file.name
        frames.append(frame)
        print(f"  Leído {file.name}: {len(frame):,} filas")
    if not frames:
        raise FileNotFoundError(f"No hay archivos de eventos para {year}")
    return pd.concat(frames, ignore_index=True)


def limpiar_eventos(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.copy()
    raw["ENTIDAD_NORM"] = raw["ENTIDAD"].map(norm)
    parsed = raw["MUNICIPIO"].apply(lambda x: pd.Series(parse_municipio(x)))
    parsed.columns = ["mun_cve", "mun_nom"]
    raw = pd.concat([raw.reset_index(drop=True), parsed.reset_index(drop=True)], axis=1)
    raw["mun_norm"] = raw["mun_nom"].map(norm)

    raw["fecha_evento"] = pd.to_datetime(
        raw["FECHA DEL EVENTO"], dayfirst=True, errors="coerce"
    )

    nombre = raw["NOMBRE"].fillna("").str.upper().str.strip()
    descripcion = raw["DESCRIPCION"].fillna("").str.upper().str.strip()
    raw["evento_util"] = ~nombre.isin(BAD_EVENT_NAMES) & ~descripcion.isin(BAD_EVENT_NAMES)

    raw["realizado"] = raw["ESTATUS EVENTO"].eq("REALIZADO")
    raw["publico"] = raw["TIPO EVENTO"].eq("PUBLICO")
    raw["oneroso"] = raw["EVENTO"].eq("ONEROSO")
    raw["federal"] = raw["AMBITO"].eq("FEDERAL")
    raw["local"] = raw["AMBITO"].eq("LOCAL")
    raw["federal_publico"] = raw["federal"] & raw["publico"]
    raw["local_publico"] = raw["local"] & raw["publico"]
    raw["sin_siglas"] = raw["SIGLAS"].isna() | raw["SIGLAS"].astype(str).str.strip().eq("")
    siglas = raw["SIGLAS"].fillna("").astype(str).str.upper()
    for party, pattern in PARTY_PATTERNS.items():
        raw[f"partido_{party}"] = siglas.str.contains(pattern, regex=True)
    return raw


def agregar_eventos(raw: pd.DataFrame, catalog: pd.DataFrame, year: int) -> pd.DataFrame:
    util = raw[raw["realizado"] & raw["evento_util"] & raw["MUNICIPIO"].notna()].copy()

    keys = ["ENTIDAD_NORM", "mun_norm"]
    counts = (
        util.groupby(keys, as_index=False)
        .agg(
            eventos=("IDENTIFICADOR", "size"),
            eventos_publicos=("publico", "sum"),
            eventos_privados=("publico", lambda s: int((~s).sum())),
            eventos_onerosos=("oneroso", "sum"),
            eventos_federal=("federal", "sum"),
            eventos_local=("local", "sum"),
            eventos_federal_publicos=("federal_publico", "sum"),
            eventos_local_publicos=("local_publico", "sum"),
            eventos_sin_siglas=("sin_siglas", "sum"),
            **{f"eventos_{p}": (f"partido_{p}", "sum") for p in PARTY_PATTERNS},
        )
    )

    merged = catalog.merge(
        counts,
        left_on=["ent_norm", "mun_norm"],
        right_on=["ENTIDAD_NORM", "mun_norm"],
        how="left",
    )
    count_cols = [c for c in merged.columns if c.startswith("eventos")]
    merged[count_cols] = merged[count_cols].fillna(0).astype(int)

    merged["year"] = year
    ln_col = "LN_2021" if year == 2021 else "LN_2024"
    merged["lista_nominal"] = merged[ln_col].fillna(merged["LN_2024"])
    merged["eventos_por_1000_ln"] = np.where(
        merged["lista_nominal"] > 0, merged["eventos"] / merged["lista_nominal"] * 1000, np.nan
    )
    merged["eventos_publicos_por_1000_ln"] = np.where(
        merged["lista_nominal"] > 0,
        merged["eventos_publicos"] / merged["lista_nominal"] * 1000,
        np.nan,
    )
    for col in ("eventos_federal", "eventos_local", "eventos_federal_publicos"):
        merged[f"{col}_por_1000_ln"] = np.where(
            merged["lista_nominal"] > 0,
            merged[col] / merged["lista_nominal"] * 1000,
            np.nan,
        )
    merged["cobertura"] = merged["eventos"] > 0

    matched = int((merged["eventos"] > 0).sum())
    total = len(merged)
    print(
        f"  {year}: {int(merged['eventos'].sum()):,} eventos asignados a "
        f"{matched:,}/{total:,} municipios ({matched / total:.1%})"
    )
    return merged[
        [
            "EDOCVE", "EDONOM", "MPIOCVE", "MPIONOM", "year", "lista_nominal",
            "eventos", "eventos_publicos", "eventos_privados", "eventos_onerosos",
            "eventos_federal", "eventos_local",
            "eventos_federal_publicos", "eventos_local_publicos",
            "eventos_sin_siglas",
            *[f"eventos_{p}" for p in PARTY_PATTERNS],
            "eventos_por_1000_ln", "eventos_publicos_por_1000_ln",
            "eventos_federal_por_1000_ln", "eventos_local_por_1000_ln",
            "eventos_federal_publicos_por_1000_ln", "cobertura",
        ]
    ]


def resumir_gastos(year: int) -> pd.DataFrame | None:
    """Resume el gasto de campaña por entidad federativa."""
    if year == 2024:
        files = [
            CAMP_DIR / "PREFO_23-24_CAM_GxR_240624.csv",
            CAMP_DIR / "PREFO_23-24_CAM_OYG_240624.csv",
        ]
    else:
        files = [
            CAMP_DIR / "PEFO_20-21_CAMPANA_G_RUBRO.csv",
            CAMP_DIR / "PEFO_20-21_CAMPANA_OYG.csv",
        ]

    frames = []
    for file in files:
        if not file.exists():
            continue
        encoding = "latin-1" if year == 2021 else "utf-8-sig"
        frame = pd.read_csv(file, encoding=encoding, low_memory=False)
        if "TOTAL GASTOS" not in frame.columns:
            continue
        frame["gasto"] = (
            frame["TOTAL GASTOS"]
            .astype(str)
            .str.replace(r"[$,()\s]", "", regex=True)
            .str.replace(r"^-$", "0", regex=True)
            .replace({"": np.nan, "nan": np.nan})
            .pipe(pd.to_numeric, errors="coerce")
        )
        frame["entidad_norm"] = frame["ESTADO ELECCION"].map(norm)
        frames.append(
            frame.groupby("entidad_norm", as_index=False).agg(
                gasto_total=("gasto", "sum"), candidaturas=("gasto", "size")
            )
        )

    if not frames:
        return None

    result = pd.concat(frames, ignore_index=True).groupby("entidad_norm", as_index=False).agg(
        gasto_total=("gasto_total", "sum"), candidaturas=("candidaturas", "sum")
    )
    result["year"] = year
    print(f"  Gasto {year}: {len(result)} entidades, ${result['gasto_total'].sum():,.0f}")
    return result


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    catalog = cargar_catalogo()
    print(f"Catálogo: {len(catalog):,} municipios")

    resumen = {}
    for year in (2021, 2024):
        print(f"Procesando eventos {year}...")
        raw = limpiar_eventos(leer_eventos(year))
        municipios = agregar_eventos(raw, catalog, year)
        output = PROCESSED_DIR / f"eventos_municipio_{year}.csv"
        municipios.to_csv(output, index=False)
        print(f"  Guardado {output} ({len(municipios):,} filas)")

        resumen[str(year)] = {
            "filas_crudas": int(len(raw)),
            "eventos_realizados": int(raw["realizado"].sum()),
            "eventos_utiles": int((raw["realizado"] & raw["evento_util"] & raw["MUNICIPIO"].notna()).sum()),
            "municipios_con_eventos": int((municipios["eventos"] > 0).sum()),
            "municipios_catalogo": int(len(municipios)),
            "eventos_asignados": int(municipios["eventos"].sum()),
        }

    gastos = [g for g in (resumir_gastos(2021), resumir_gastos(2024)) if g is not None]
    if gastos:
        gastos_df = pd.concat(gastos, ignore_index=True)
        gastos_df.to_csv(PROCESSED_DIR / "gastos_entidad_campana.csv", index=False)
        print(f"Guardado {PROCESSED_DIR / 'gastos_entidad_campana.csv'}")

    with open(PROCESSED_DIR / "campanas_resumen.json", "w", encoding="utf-8") as fh:
        json.dump(resumen, fh, ensure_ascii=False, indent=2)
    print(f"Guardado {PROCESSED_DIR / 'campanas_resumen.json'}")


if __name__ == "__main__":
    main()
