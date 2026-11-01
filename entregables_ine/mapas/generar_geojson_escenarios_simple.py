#!/usr/bin/env python3
"""
Generador simple de GeoJSON sin dependencias externas.
Lee CSV con csv module y produce FeatureCollection con propiedades.
"""
import argparse
import csv
import json
from pathlib import Path

def read_csv_header(path):
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)

def main():
    parser = argparse.ArgumentParser(description="Genera GeoJSON simple")
    parser.add_argument("--input", required=True)
    parser.add_argument("--escenarios", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    header, rows = read_csv_header(args.input)

    # Columnas deseadas
    wanted = [
        "EDOCVE","MPIOCVE","SECCION","EDONOM","MPIONOM",
        "LN_2024","abstencion_2024",
        "riesgo_modelo","riesgo","nivel_riesgo",
        "riesgo_p10","riesgo_p90","intervalo_ancho",
        "X1_informativa","X2_intensiva",
        "personas_movilizables_X1_informativa","personas_movilizables_X2_intensiva",
        "seccion_valida_2024","tiene_historia_2021","historia_completa","n_anios_historia"
    ]
    cols = [c for c in wanted if c in header]

    # Leer escenarios
    esc_header, esc_rows = read_csv_header(args.escenarios)
    esc_dict = {}
    for r in esc_rows:
        key = r.get('escenario')
        if key:
            esc_dict[key] = {k: r[k] for k in esc_header}

    features = []
    for row in rows:
        props = {}
        for c in cols:
            v = row.get(c, "")
            # Convertir números
            if v == "" or v is None:
                props[c] = None
            else:
                # Intentar int/float
                try:
                    if '.' in v:
                        props[c] = float(v)
                    else:
                        props[c] = int(v)
                except:
                    props[c] = v
        features.append({
            "type": "Feature",
            "geometry": None,
            "properties": props
        })

    geojson = {
        "type": "FeatureCollection",
        "name": "escenarios_riesgo_2024",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": features,
        "metadata": {
            "fuente": "Reto 2 INE - Índice Territorial de Riesgo de Abstención",
            "fecha_generacion": "2026-10-31",
            "escenarios": esc_dict,
            "columnas": cols,
            "nota": "Geometría vacía. Unir con capa de secciones electorales."
        }
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)

    print(f"GeoJSON generado: {out_path}")
    print(f"Características: {len(features)}")

if __name__ == "__main__":
    main()
