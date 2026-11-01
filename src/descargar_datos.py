"""Descarga los datos abiertos del INE usados en el proyecto.

Incluye:

- Conteos Censales de Participación 2009, 2012, 2015, 2018, 2021 y 2024.
- Conteos especiales: prisión preventiva 2024, voto anticipado 2024 y PJ 2025.
- Manual metodológico 2009-2024.
- Agenda de eventos y reportes de gasto/ingreso de campaña del SIF (2021 y 2024).

Los archivos se guardan en ``DatosAbiertos/`` y se extraen automáticamente.
Los ZIP y 7z se descargan de los servidores estáticos del INE; el sitio HTML
tiene un WAF, pero los archivos no.

Uso:
    python src/descargar_datos.py
    python src/descargar_datos.py --force
    python src/descargar_datos.py --solo-conteos
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "DatosAbiertos"
CAMP_DIR = DATA_DIR / "Campanas"

CONTEOS_BASE = "https://ine.mx/wp-content/uploads"
FISCALIZACION = "https://fiscalizacion.ine.mx/documents/82565"

CONTEOS = [
    (2009, f"{CONTEOS_BASE}/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2009.zip"),
    (2012, f"{CONTEOS_BASE}/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2012.zip"),
    (2015, f"{CONTEOS_BASE}/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2015.zip"),
    (2018, f"{CONTEOS_BASE}/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2018.zip"),
    (2021, f"{CONTEOS_BASE}/2022/04/DatosAbiertos_DECEyEC_ConteosCensales2021.zip"),
    (2024, f"{CONTEOS_BASE}/2025/08/DatosAbiertos_DECEyEC_ConteosCensales2024.zip"),
]

ESPECIALES = [
    ("DatosAbiertos_DECEyEC_ConteosCensales_PrisionPreventiva2024", f"{CONTEOS_BASE}/2025/08/DatosAbiertos_DECEyEC_ConteosCensales_PrisionPreventiva2024.zip"),
    ("DatosAbiertos_DECEyEC_ConteosCensales_VotoAnticipado2024", f"{CONTEOS_BASE}/2025/08/DatosAbiertos_DECEyEC_ConteosCensales_VotoAnticipado2024.zip"),
    ("DatosAbiertos_DECEyEC_ConteosCensalesPJ2025", f"{CONTEOS_BASE}/2026/09/DatosAbiertos_DECEyEC_ConteosCensalesPJ2025.zip"),
]

MANUAL = f"{CONTEOS_BASE}/2025/06/Manual-Conteos-Censales-2009-2024.pdf"

CAMPANAS_2024 = f"{FISCALIZACION}/1268544"
CAMPANAS_2021 = f"{FISCALIZACION}/1140143"

CAMPANAS_CSV = [
    ("PREFO_23-24_CAM_AE_240624.csv", f"{CAMPANAS_2024}/PREFO_23-24_CAM_AE_240624.csv"),
    ("PREFO_23-24_CAM_GxR_240624.csv", f"{CAMPANAS_2024}/PREFO_23-24_CAM_GxR_240624.csv"),
    ("PREFO_23-24_CAM_OYG_240624.csv", f"{CAMPANAS_2024}/PREFO_23-24_CAM_OYG_240624.csv"),
    ("PREFO_23-24_CAM_YxR_240624.csv", f"{CAMPANAS_2024}/PREFO_23-24_CAM_YxR_240624.csv"),
    ("PEFO_20-21_CAMPANA_G_RUBRO.csv", f"{CAMPANAS_2021}/PEFO_20-21_CAMPA%C3%91A_G_RUBRO.csv"),
    ("PEFO_20-21_CAMPANA_OYG.csv", f"{CAMPANAS_2021}/PEFO_20-21_CAMPA%C3%91A_OYG.csv"),
    ("PEFO_20-21_CAMPANA_Y_RUBRO.csv", f"{CAMPANAS_2021}/PEFO_20-21_CAMPA%C3%91A_Y_RUBRO.csv"),
]

CAMPANAS_7Z = [
    (
        "Eventos_csv_24062024.7z",
        f"{FISCALIZACION}/1268556/Eventos_csv_24062024.7z",
        CAMP_DIR / "Eventos_2024_Local",
    ),
    (
        "PEFO_20-21_CAMPANA_EVENTOS_210622.7z",
        f"{FISCALIZACION}/883128/PEFO_20-21_CAMPA%C3%91A_EVENTOS_210622+CSV.7z",
        CAMP_DIR / "Eventos_2021_Federal",
    ),
]


def download(url: str, destination: Path, force: bool = False) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not force:
        print(f"  Ya existe: {destination.name}")
        return destination

    print(f"  Descargando {destination.name}...")
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    temp = destination.with_suffix(destination.suffix + ".part")
    with urllib.request.urlopen(request, timeout=120) as response, open(temp, "wb") as fh:
        shutil.copyfileobj(response, fh, length=1024 * 1024)
    temp.replace(destination)
    size_mb = destination.stat().st_size / (1024 * 1024)
    print(f"  Listo ({size_mb:.1f} MB)")
    return destination


def extract_zip(path: Path, destination: Path, force: bool = False) -> None:
    if destination.exists() and not force:
        print(f"  Carpeta ya extraída: {destination.name}")
        return
    print(f"  Extrayendo {path.name}...")
    with zipfile.ZipFile(path) as archive:
        archive.extractall(destination.parent)


def extract_7z(path: Path, destination: Path, force: bool = False) -> None:
    if destination.exists() and any(destination.iterdir()) and not force:
        print(f"  Carpeta ya extraída: {destination.name}")
        return
    if shutil.which("7z") is None:
        print(f"  Aviso: 7z no está instalado; extrae manualmente {path}", file=sys.stderr)
        return
    print(f"  Extrayendo {path.name}...")
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(["7z", "x", "-y", str(path), f"-o{destination}"], check=True,
                   stdout=subprocess.DEVNULL)


def main() -> None:
    parser = argparse.ArgumentParser(description="Descarga los datos abiertos del INE.")
    parser.add_argument("--force", action="store_true", help="Vuelve a descargar y extraer.")
    parser.add_argument("--solo-conteos", action="store_true", help="Omite los datos de campaña.")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Conteos Censales de Participación")
    for year, url in CONTEOS:
        archive = download(url, DATA_DIR / f"Conteos{year}.zip", args.force)
        extract_zip(archive, DATA_DIR / f"DatosAbiertos_DECEyEC_ConteosCensales{year}", args.force)

    print("\nConteos especiales")
    for folder, url in ESPECIALES:
        archive = download(url, DATA_DIR / f"{folder}.zip", args.force)
        extract_zip(archive, DATA_DIR / folder, args.force)

    print("\nManual metodológico")
    download(MANUAL, DATA_DIR / "Manual-Conteos-Censales-2009-2024.pdf", args.force)

    if args.solo_conteos:
        print("\nDatos de campaña omitidos (--solo-conteos).")
        return

    print("\nDatos de campaña del SIF")
    CAMP_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in CAMPANAS_CSV:
        download(url, CAMP_DIR / name, args.force)
    for name, url, destination in CAMPANAS_7Z:
        archive = download(url, CAMP_DIR / name, args.force)
        extract_7z(archive, destination, args.force)

    print("\nDescarga completa. Siguiente paso:")
    print("  python src/preparar_datos.py")
    print("  python src/preparar_campanas.py")
    print("  python src/entrenar_modelo.py")


if __name__ == "__main__":
    main()
