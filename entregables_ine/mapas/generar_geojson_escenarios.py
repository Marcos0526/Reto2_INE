#!/usr/bin/env python3
"""
Generador de GeoJSON para escenarios de riesgo de abstención.
Procesa resultado_modelo_riesgo_2024.csv y escenarios_modelo_riesgo_2024.csv
para producir geojson con puntajes de riesgo, intervalos y escenarios X1/X2.

Uso:
    python generar_geojson_escenarios.py \
        --input /path/resultado_modelo_riesgo_2024.csv \
        --escenarios /path/escenarios_modelo_riesgo_2024.csv \
        --output /path/escenarios_riesgo_2024.geojson

Requiere que el CSV incluya columnas de geometría o que existan geometrías
auxiliares para cada sección. En este script se genera un GeoJSON con
propiedades y geometría vacía, listo para enriquecer con capa SIG.
"""
import argparse
import json
import pandas as pd
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Genera GeoJSON de escenarios de riesgo")
    parser.add_argument("--input", required=True, help="CSV resultado modelo riesgo")
    parser.add_argument("--escenarios", required=True, help="CSV escenarios")
    parser.add_argument("--output", required=True, help="GeoJSON de salida")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    esc = pd.read_csv(args.escenarios)

    # Seleccionar columnas relevantes
    cols = [
        "EDOCVE","MPIOCVE","SECCION","EDONOM","MPIONOM",
        "LN_2024","abstencion_2024",
        "riesgo_modelo","riesgo","nivel_riesgo",
        "riesgo_p10","riesgo_p90","intervalo_ancho",
        "X1_informativa","X2_intensiva",
        "personas_movilizables_X1_informativa","personas_movilizables_X2_intensiva",
        "seccion_valida_2024","tiene_historia_2021","historia_completa","n_anios_historia"
    ]
    cols = [c for c in cols if c in df.columns]
    df_sel = df[cols].copy()

    # Agregar resumen de escenarios
    esc_dict = esc.set_index("escenario").to_dict(orient="index")

    features = []
    for _, row in df_sel.iterrows():
        props = row.to_dict()
        # Formatear numéricos
        for k, v in props.items():
            if isinstance(v, float) and pd.isna(v):
                props[k] = None
        features.append({
            "type": "Feature",
            "geometry": None,  # Llenar con geometría real en SIG
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
            "nota": "Geometría vacía. Unir con capa de secciones electorales por EDOCVE,MPIOCVE,SECCION."
        }
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)

    print(f"GeoJSON generado: {out_path}")
    print(f"Características: {len(features)}")
    print("Columnas incluidas:", cols)

if __name__ == "__main__":
    main()
