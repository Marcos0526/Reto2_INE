# Reto2_INE — Índice territorial de riesgo de abstención

## 🎯 Resumen ejecutivo

Este proyecto construye un **índice territorial de riesgo de abstención por sección
electoral** a partir de los Conteos Censales de Participación del INE de 2009,
2012, 2015, 2018, 2021 y 2024. El modelo combina la historia electoral de cada
sección con variables sociodemográficas y con **contexto espacial municipal y
estatal** (promedios, dispersión, tendencias y posición relativa).

El objetivo es responder:

> **¿Qué zonas podrían presentar mayor abstención si no se interviene y qué
> información ayuda a priorizar acciones?**

Resultados principales de la ejecución actual:

| Indicador | Valor |
|---|---:|
| Secciones electorales en 2024 | **70,751** |
| Secciones con tasa de abstención válida | **68,651** |
| Secciones sin dato 2024 (`SV + NV = 0`) | **2,100** (1.59 millones de lista nominal, 1.62%) |
| MAE del modelo final (validación por municipio, 3 semillas) | **0.0323 ± 0.0018** |
| MAE de la línea base (abstención 2021) | **0.0974 ± 0.0038** |
| Reducción del MAE frente a la línea base | **≈ 66.9%** |
| R² del modelo final | **0.784 ± 0.011** |
| Secciones en riesgo alto o muy alto | **9,641** |
| Personas potencialmente movilizables con X1 (3 puntos) | **477,315** |
| Personas potencialmente movilizables con X2 (7 puntos) | **1,113,735** |

El índice es **territorial, no individual**, y los escenarios X1/X2 son análisis
de sensibilidad, **no efectos causales estimados**.

---

## ❓ Preguntas de investigación

1. ¿Qué zonas podrían presentar mayor abstención en futuras elecciones si no se
   interviene?
2. ¿Qué información histórica, sociodemográfica y territorial ayuda a explicar y
   predecir la abstención?
3. Si se aplica una acción X, ¿cuántas personas podrían movilizarse y qué
   acción tiene más sentido priorizar?

> **Alcance temporal:** el modelo es un pronóstico supervisado: usa únicamente
> información hasta 2021 para predecir la abstención de 2024. Como 2024 ya
> ocurrió, las puntuaciones finales son un pronóstico retrospectivo
> (*nowcast*) y no una proyección a 2027. Para prospectiva se actualizan las
> variables con 2024 y se reestima el modelo.

---

## 📊 Datos

### Fuentes

- **Conteos Censales de Participación 2009–2024** del INE:
  <https://ine.mx/transparencia/datos-abiertos/visualizacion-datos/conteos-censales-participacion/#seccion-federales>
- **Manual metodológico 2009–2024**:
  <https://ine.mx/wp-content/uploads/2025/06/Manual-Conteos-Censales-2009-2024.pdf>
- **Sistema Integral de Fiscalización (SIF)** para eventos y gastos de campaña:
  <https://fiscalizacion.ine.mx/web/portalsif/descarga-de-reportes>

> El sitio HTML del INE está protegido por un WAF, pero los ZIP, PDF y archivos
> del SIF son accesibles directamente. El script `src/descargar_datos.py`
> concentra las URLs utilizadas.

### Inventario descargado

| Dataset | Periodo | Archivos | Filas / tamaño | Uso |
|---|---|---|---:|---|
| Conteos Censales de Participación | 2009, 2012, 2015, 2018, 2021, 2024 | 32 CSV por año (192) | ~54.9 millones de filas; ~3.5 GB | Base del panel seccional |
| Conteos de prisión preventiva | 2024 | 1 CSV | 1 archivo | Cobertura especial |
| Conteos de voto anticipado | 2024 | 1 CSV | 1 archivo | Cobertura especial |
| Conteos del Poder Judicial | 2024–2025 | 31 CSV | ~602 MB | Análisis exploratorio adicional |
| Manual de Conteos Censales | 2009–2024 | 1 PDF | 2.6 MB | Metodología y diccionario |
| Agenda de eventos federales | 2024 | 1 CSV | 354,811 filas | Variable de campaña |
| Agenda de eventos locales | 2024 | 2 CSV | 1,304,225 filas | Variable de campaña |
| Agenda de eventos federales | 2021 | 1 CSV | 200,242 filas | Comparación de campaña |
| Gastos e ingresos de campaña | 2021, 2024 | 6 CSV | — | Análisis complementario |

Los datos se organizan así:

```
DatosAbiertos/
├── DatosAbiertos_DECEyEC_ConteosCensales2009/
├── DatosAbiertos_DECEyEC_ConteosCensales2012/
├── DatosAbiertos_DECEyEC_ConteosCensales2015/
├── DatosAbiertos_DECEyEC_ConteosCensales2018/
├── DatosAbiertos_DECEyEC_ConteosCensales2021/
├── DatosAbiertos_DECEyEC_ConteosCensales2024/
├── DatosAbiertos_DECEyEC_ConteosCensales_PrisionPreventiva2024/
├── DatosAbiertos_DECEyEC_ConteosCensales_VotoAnticipado2024/
├── DatosAbiertos_DECEyEC_ConteosCensalesPJ2025/
├── Campanas/
│   ├── PREFO_23-24_CAM_AE_240624.csv
│   ├── Eventos_2024_Local/Eventos_csv_24062024/
│   ├── Eventos_2021_Federal/
│   └── ... reportes de gasto e ingreso
├── processed/                    # panel y tablas derivadas (generado)
└── Manual-Conteos-Censales-2009-2024.pdf
```

`DatosAbiertos*/` está en `.gitignore`: son datos pesados y reproducibles con
`src/descargar_datos.py`.

### Variables originales

| Variable | Descripción |
|---|---|
| `AELEC` | Año de elección |
| `FELECCION` | Fecha de la jornada electoral |
| `EDOCVE`, `EDONOM` | Clave y nombre de la entidad federativa |
| `MPIOCVE`, `MPIONOM` | Clave y nombre del municipio |
| `SECCION` | Sección electoral en el año correspondiente |
| `TIPOSEC` | Tipo de sección: `U` urbana, `M` mixta, `R` rural |
| `DEF`, `DEL` | Distrito electoral federal y local |
| `SEXO` | 0 hombres, 1 mujeres, 2 no binario |
| `EDAD` | Años cumplidos al día de la elección |
| `LN` | Lista nominal de los cuadernillos |
| `SV` | Registros con marca de voto |
| `NV` | Registros sin marca de voto |
| `NS` | Registros no especificados en participación |

La abstención se calcula como `NV / (SV + NV)`. **`NS` no es abstención**: es un
indicador de calidad del registro y se usa como variable auxiliar.

### Cobertura y calidad

| Año | Secciones | Lista nominal | Abstención agregada | Secciones sin tasa |
|---|---:|---:|---:|---:|
| 2009 | 64,934 | 77,481,831 | 55.94% | 1,004 |
| 2012 | 65,599 | 76,490,962 | 37.92% | 82 |
| 2015 | 68,362 | 83,563,462 | 52.93% | 2,042 |
| 2018 | 68,408 | 89,123,997 | 37.63% | 2,517 |
| 2021 | 68,812 | 93,532,133 | 48.16% | 1,693 |
| 2024 | 70,751 | 98,330,348 | 40.33% | 2,100 |

- **68,651** secciones 2024 tienen tasa válida y son modelables.
- **66,138** tienen historia de 2021; **4,375** son modelables pero no tienen
  2021. El modelo las conserva, imputa con mediana y agrega banderas de faltante.
- **56,111** tienen historia completa 2009–2021.
- Las 2,100 secciones sin tasa 2024 se concentran en Sinaloa (350), Chihuahua
  (281), Coahuila (158), Michoacán (109) y Sonora (100). **No se eliminan del
  entregable**: se reportan como `Sin dato`.
- No se dispone de una tabla oficial de equivalencias seccionales entre años. El
  cruce usa `(EDOCVE, MPIOCVE, SECCION)` y puede perder historia cuando una
  sección fue dividida, fusionada o renumerada.

---

## 🧪 Metodología

### Pipeline reproducible

```bash
python src/descargar_datos.py      # descarga y extrae INE + SIF
python src/preparar_datos.py       # panel seccional 2009–2024 en Parquet
python src/preparar_campanas.py    # eventos y gastos de campaña por municipio
python src/entrenar_modelo.py      # comparación, modelo final y entregables
```

### Variables del modelo

El modelo final usa **92 variables**:

1. **Historia electoral (50 variables):** abstención, participación, proporción
   `NS`, lista nominal, composición por edad (18–29, 30–59, 60+) y por sexo para
   cada elección de 2009 a 2021.
2. **Tipo de sección (5 variables):** `TIPOSEC` de cada año.
3. **Faltantes explícitos (8 variables):** número de años con historia, bandera
   de historia completa, bandera de 2021 y una bandera por año faltante.
4. **Contexto espacial (28 variables):** promedios, desviaciones y promedios
   *leave-one-out* municipal y estatal de abstención/participación 2021;
   desviación de la sección respecto a su municipio; tendencia 2018–2021 de la
   sección, municipio y entidad; volatilidad histórica; crecimiento de la lista
   nominal; rango del municipio dentro de la entidad; composición
   sociodemográfica municipal y número de secciones del municipio.
5. **Entidad federativa:** codificada como variable categórica.

El objetivo se transforma con logit: `log(p / (1 - p))`, con `p` acotada a
`[0.0001, 0.9999]`. Las predicciones se devuelven a probabilidad con la inversa
del logit.

### Validación

- **GroupShuffleSplit** con 80% de municipios para entrenamiento y 20% para
  prueba. Ninguna sección de un municipio de prueba aparece en entrenamiento.
- **Tres semillas** (42, 7 y 2024) para reportar media y desviación estándar.
- Métricas en escala de probabilidad: MAE, RMSE y R².
- Línea base: usar directamente la abstención de 2021 (mediana si falta).

Las métricas reportadas son **fuera de muestra**. Las puntuaciones finales se
generan reajustando el modelo con todas las secciones modelables; por tanto, son
ajustadas (*in-sample*) y deben leerse como índice de priorización, no como una
segunda validación.

### Modelos comparados

| Modelo | Variables |
|---|---|
| `baseline_2021` | Abstención observada 2021 |
| `ridge_historia` | Historia 2009–2021 + tipo de sección + entidad |
| `hgb_historia` | Historia 2009–2021 + tipo de sección + entidad |
| `hgb_espacial` | Historia + contexto espacial municipal/estatal |
| `hgb_espacial_campana` | Historia + contexto espacial + eventos de campaña |

El modelo final se elige por **menor MAE medio** en validación. En esta ejecución
ganó `hgb_espacial`; los eventos de campaña **no mejoraron** la generalización
(ver más abajo) y se excluyeron del modelo final.

---

## 📈 Resultados

### Métricas de validación

| Modelo | MAE | RMSE | R² |
|---|---:|---:|---:|
| **`hgb_espacial` (final)** | **0.0323 ± 0.0018** | **0.0473 ± 0.0023** | **0.784 ± 0.011** |
| `hgb_espacial_campana` | 0.0328 ± 0.0018 | 0.0477 ± 0.0024 | 0.780 ± 0.011 |
| `hgb_historia` | 0.0335 ± 0.0016 | 0.0492 ± 0.0021 | 0.766 ± 0.008 |
| `ridge_historia` | 0.0350 ± 0.0020 | 0.0509 ± 0.0023 | 0.750 ± 0.012 |
| `baseline_2021` | 0.0974 ± 0.0038 | 0.1173 ± 0.0036 | −0.337 ± 0.145 |

La mejora del modelo final frente a la línea base es de **≈ 66.9% en MAE**. El
contexto espacial reduce el MAE de 0.0335 a 0.0323 frente al modelo solo
histórico.

### Distribución del riesgo

| Nivel | Secciones | Lista nominal | Abstención esperada | Riesgo medio |
|---|---:|---:|---:|---:|
| Bajo (< 35) | 22,979 | 29,014,613 | 8,464,047 | 28.86% |
| Medio (35–50) | 36,031 | 51,816,586 | 21,797,617 | 41.92% |
| Alto (50–65) | 9,344 | 15,422,746 | 8,407,422 | 54.31% |
| Muy alto (> 65) | 297 | 487,761 | 333,314 | 69.17% |
| Sin dato | 2,100 | 1,588,642 | — | — |

Las entidades con mayor riesgo promedio son **Baja California (51.66%)**,
**Sonora (47.29%)**, **Chihuahua (46.75%)**, **Durango (45.52%)**, **Baja
California Sur (45.21%)** y **Michoacán (44.91%)**. El ranking debe combinarse
con el tamaño de la lista nominal y la capacidad local de intervención.

> La abstención agregada de 2024 (40.33%) pondera por votos; el riesgo promedio
> del índice (39.35%) es el promedio simple entre secciones. Son métricas
> distintas y no deben compararse como si fueran la misma.

### Escenarios de acción

| Escenario | Reducción hipotética | Abstención promedio | Personas potencialmente movilizables |
|---|---:|---:|---:|
| Sin intervención | 0 puntos | 39.35% | 0 |
| X1 informativa | 3 puntos en alto/muy alto | 38.93% | **477,315** |
| X2 intensiva | 7 puntos en alto/muy alto | 38.37% | **1,113,735** |

- **X1 informativa:** mensajes claros y neutrales sobre cuándo, dónde y cómo
  votar; materiales impresos y difusión local.
- **X2 intensiva:** acompañamiento territorial, visitas comunitarias, módulos de
  orientación y seguimiento de barreras.

Ambos escenarios son **sensibilidad**, no impacto causal. Una intervención real
requiere medición antes/después, grupo de comparación o prueba controlada.

La cifra de personas es una **cota mecánica** (`reducción de la tasa × lista
nominal`). No estima cuántas personas son contactables, ni la respuesta
diferencial por sección, ni el costo de la intervención.

### Importancia de variables

Las variables más importantes según permutación son:

1. `tasa_participacion_2021`
2. `tasa_abstencion_2021`
3. `tendencia_ent_18_21` (tendencia estatal 2018–2021)
4. `tasa_abstencion_2018`
5. `tasa_participacion_2018`
6. `mun_abst_2021_mean` (promedio municipal 2021)
7. `mun_part_2021_mean`
8. `mun_ln_2021` (tamaño del municipio)
9. `ent_abst_2021_std`
10. `tasa_abstencion_2012`

La importancia SHAP coincide en colocar la historia reciente, la tendencia
estatal y el contexto municipal entre las señales principales. Los archivos
completos están en `DatosAbiertos/processed/importancia_permutacion.csv` e
`importancia_shap.csv`.

### ¿Qué pasó con los datos de campaña?

Se descargaron y procesaron **134,115 eventos federales de 2021** y **958,999
eventos de 2024** (115,104 federales + 843,895 locales), además de los reportes
de gasto. Los eventos se agregaron por municipio y se calcularon tasas por 1,000
personas en lista nominal.

Hallazgos:

- La cobertura es alta: 2,256/2,477 municipios en 2021 y 2,467/2,477 en 2024.
- La asociación simple entre eventos por 1,000 habitantes y cambio de abstención
  es prácticamente nula.
- Agregar las variables de campaña al modelo **no mejora** la validación: el MAE
  sube de 0.0323 a 0.0328.
- Los eventos son **auto-reportados**, están a nivel municipio (no sección), la
  cobertura por partido es muy desigual y las campañas eligen dónde competir
  (endogeneidad). 2021 además fue un contexto atípico por COVID-19.

Por eso los eventos **no se usan en el modelo final**. Quedan documentados como
fuente para un diseño cuasi-experimental futuro (panel municipal con efectos
fijos, event study, control sintético o variables instrumentales).

---

## 📁 Estructura del repositorio

```
Reto2_INE/
├── README.md
├── requirements.txt
├── .gitignore
├── src/
│   ├── descargar_datos.py       # descarga INE + SIF
│   ├── preparar_datos.py        # panel seccional 2009–2024
│   ├── preparar_campanas.py     # eventos/gastos por municipio
│   └── entrenar_modelo.py       # comparación, modelo final y salidas
├── notebooks/
│   ├── exploracion_datos.ipynb
│   ├── preparacion_datos.ipynb
│   └── modelo_riesgo.ipynb
├── infografia_resultados.html
├── resultado_modelo_riesgo_2024.csv
├── escenarios_modelo_riesgo_2024.csv
└── DatosAbiertos/               # ignorado en git; se genera con el pipeline
```

### Entregables

- `resultado_modelo_riesgo_2024.csv`: **70,751 secciones**, incluidas las 2,100
  marcadas como `Sin dato`. Columnas principales: `riesgo_modelo`, `riesgo`,
  `nivel_riesgo`, `prioridad`, `abstencion_esperada_personas`, escenarios X1/X2
  y banderas de cobertura histórica.
- `escenarios_modelo_riesgo_2024.csv`: comparación de X1/X2.
- `infografia_resultados.html`: resumen ejecutivo autocontenido.
- `DatosAbiertos/processed/`: panel Parquet, métricas, importancia de variables,
  resúmenes por entidad y metadatos del modelo.

---

## 🔁 Reproducibilidad

### Requisitos

- Python 3.11+ (probado con Python 3.12).
- ~5 GB de disco para datos y derivados.
- `7z` instalado para extraer los archivos de eventos de campaña.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Ejecución completa

```bash
python src/descargar_datos.py
python src/preparar_datos.py
python src/preparar_campanas.py
python src/entrenar_modelo.py
```

Tiempos aproximados en una laptop: descarga 5–15 min; panel 3–6 min; campañas
1–3 min; entrenamiento 2–5 min. El panel queda en
`DatosAbiertos/processed/panel_secciones_2009_2024.parquet`.

### Semillas y configuración

- Semillas de validación: `42`, `7`, `2024`.
- `test_size = 0.20`, agrupado por municipio.
- Modelo final: `HistGradientBoostingRegressor(max_iter=300, learning_rate=0.04,
  max_leaf_nodes=15, min_samples_leaf=40, l2_regularization=1.0)`.
- Objetivo: logit de la abstención 2024.

---

## ⚠️ Limitaciones

1. **No es un modelo causal.** El índice identifica territorios con mayor
   propensión observada; no estima el efecto de una intervención.
2. **Es territorial, no individual.** No predice la conducta de personas
   concretas ni debe usarse para etiquetarlas.
3. **El objetivo es 2024 observado.** El modelo es un *nowcast* calibrado contra
   2024; para prospectiva futura debe reentrenarse con datos posteriores.
4. **Cambios cartográficos.** Sin tabla de equivalencias seccionales, algunas
   secciones pierden historia cuando cambian claves o fronteras.
5. **Secciones sin dato.** 2,100 secciones (1.62% de la lista nominal) no tienen
   tasa válida 2024; se reportan como `Sin dato` y quedan fuera de escenarios.
6. **`NS` no es abstención.** Es un indicador de calidad y se trata como tal.
7. **Campañas auto-reportadas.** Los eventos del SIF no son intervenciones del
   INE, no miden contacto puerta a puerta y tienen cobertura desigual por partido.
8. **Una sola familia de modelos.** Se compararon Ridge y Gradient Boosting; no
   se exploraron modelos espaciales jerárquicos ni series de tiempo seccionales.
9. **Sin validación externa.** No se probó contra una elección distinta a 2024.

---

## 🚀 Trabajo futuro

- Construir una tabla de equivalencias seccionales 2009–2024 para recuperar
  historia perdida.
- Panel municipal 2021–2024 con efectos fijos de municipio y año para estimar
  asociaciones de campaña con pre-tendencias.
- Event study o control sintético para municipios de alta/baja intensidad de
  campaña.
- Variables instrumentales (topes de gasto, choques climáticos en días de evento).
- Modelos espaciales jerárquicos (BYM) o de vecindad entre secciones.
- Calibración y validación contra elecciones locales y la elección judicial
  2024–2025.
- Tablero interactivo con filtros por entidad, municipio y nivel de riesgo.

---

## ✅ Estado del proyecto

- [x] Descargar y organizar todos los Conteos Censales 2009–2024.
- [x] Descargar conteos especiales y manual metodológico.
- [x] Descargar eventos y gastos de campaña del SIF.
- [x] Construir panel seccional 2009–2024.
- [x] Agregar eventos de campaña por municipio.
- [x] Comparar modelos con validación territorial y tres semillas.
- [x] Incorporar contexto espacial y manejo explícito de faltantes.
- [x] Generar índice, niveles de riesgo y escenarios X1/X2.
- [x] Documentar resultados, límites y reproducibilidad.
- [x] Actualizar infografía y README.

---

## 📚 Fuentes y referencias

- INE, *Conteos Censales de Participación 2009–2024*.
- INE, *Manual de uso de la plataforma de Conteos Censales 2009–2024*.
- INE, *Sistema Integral de Fiscalización — descarga de reportes*.
- Código y cálculos: `src/` y `notebooks/`.
