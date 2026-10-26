# Reto2_INE

## 🎯 Contexto y objetivo general

El objetivo del reto es anticipar el comportamiento
futuro de la abstención:

> **¿Qué zonas podrían presentar mayor abstención en el futuro si no se interviene?**

Para responderlo, se busca construir un **modelo simple de riesgo** a partir de
las **tendencias históricas de participación** y de **variables
sociodemográficas**, con el fin de simular escenarios de acción y traducirlos a
un **esquema fácil de interpretar**.

## Preguntas de investigación

1. ¿Qué zonas podrían presentar mayor abstención en futuras elecciones si no se
   interviene?
2. ¿Qué información histórica y/o característica nos sirve para entender y
   predecir la abstención?
3. Si hacemos una acción X, ¿podremos ayudar a prevenir la abstención? ¿Qué
   acción podría ser X?

## Propuesta del trabajo 

### Fase 1 — Comprensión de la información

- Revisar los metadatos oficiales de los archivos del INE.
- Explorar la estructura de los conteos: entidad federativa, municipio, sección
  electoral, tipo de sección, sexo y edad, y los indicadores de participación
  (`LN`, `SV`, `NV`, `NS`).

### Fase 2 — Preparación de los datos

- Cargar los CSV de cada entidad federativa.
- Unificar criterios de agregación (entidad → municipio → sección → tipo de
  sección).
- Derivar indicadores de abstención / participación por zona.

### Fase 3 — Modelo de riesgo

- Analizar tendencias históricas de participación.
- Identificar variables sociodemográficas asociadas a mayor riesgo.
- Ajustar el modelo simple de riesgo.

### Fase 4 — Simulación de escenarios

- Definir 2 acciones hipotéticas (X1 y X2).
- Simular su efecto sobre la abstención esperada.
- Comparar escenarios.

### Fase 5 — Visualización e interpretación

- Traducir los escenarios a un esquema fácil de interpretar.
- Generar conclusiones y entregables.

## 📊 Datos

**Fuente:** INE — Datos Abiertos. Conteos Censales de Participación 2024
(`AELEC`). 
Se recuperan de: https://ine.mx/transparencia/datos-abiertos/visualizacion-datos/conteos-censales-participacion/#seccion-federales

Carpeta local: `DatosAbiertos_DECEyEC_ConteosCensales2024/` (descargada desde el
portal de datos abiertos del INE; **no se versiona en el repositorio**).

Archivos:

- `datosabiertos_deceyec_conteoscensales2024_<entidad>.csv`: uno por entidad
  federativa (32 archivos, incluido el Distrito Federal / Ciudad de México).
- `01_descripcioncampos_conteoscensales2024.txt`: metadatos de los campos.

Variables principales:

| Variable   | Descripción                                                        |
| ---------- | ------------------------------------------------------------------ |
| `AELEC`    | Año de elección (2009, 2012, 2015, 2018, 2021 y 2024)              |
| `FELECCION`| Fecha de la jornada electoral (formato: DD/MM/AAAA)                |
| `EDOCVE`   | Clave INE de la entidad federativa                                 |
| `EDONOM`   | Nombre de la entidad federativa                                   |
| `MPIOCVE`  | Clave INE del municipio                                            |
| `MPIONOM`  | Nombre del municipio                                               |
| `SECCION`  | Sección electoral en el año correspondiente                      |
| `TIPOSEC`  | Tipo de sección: U Urbana; M Mixta; R Rural                      |
| `DEF`      | Distrito Electoral Federal (DERFE 2023)                          |
| `DEL`      | Distrito Electoral Local (DERFE 2023)                            |
| `SEXO`     | Sexo de las personas: 0 Hombres; 1 Mujeres; 2 No binario         |
| `EDAD`     | Años de edad cumplidos al día de la elección                    |
| `LN`       | Lista nominal de los cuadernillos para todas las casillas       |
| `SV`       | Registros con marca de voto                                       |
| `NV`       | Registros sin marca de voto                                       |
| `NS`       | Registros no especificados en participación                     |

**Nota:** la participación se reporta por cuadernillo/casilla mediante las marcas
`SV` / `NV` sobre la lista nominal `LN`; no se contempla la participación de
personas que votaron en casillas especiales ni la de mexicanos residentes en el
extranjero.


## 📁 Estructura del repositorio

```
Reto2_INE/
├── README.md
├── notebooks/
│   ├── exploracion_datos.ipynb
│   └── preparacion_datos.ipynb
└── DatosAbiertos_DECEyEC_ConteosCensales2024/   # ignorado en .gitignore
    ├── 01_descripcioncampos_conteoscensales2024.txt
    └── datosabiertos_deceyec_conteoscensales2024_*.csv
```

- `README.md`: documentación del reto, objetivos y estado del proyecto.
- `notebooks/exploracion_datos.ipynb`: Fase 1 — metadatos, carga y calidad de los datos (ejecutado).
- `notebooks/preparacion_datos.ipynb`: Fase 2 — limpieza y preparación de los datos (en ejecución).
- `DatosAbiertos_DECEyEC_ConteosCensales2024/`: datos abiertos descargados del
  INE (tamaño considerable; se excluyen del control de versiones mediante
  `.gitignore`).

## ✅ Estado del proyecto

- [ ] Definir preguntas de investigación y criterios de éxito.
- [x] Explorar la información (Fase 1 — `notebooks/exploracion_datos.ipynb`). ✅ *(por Marcos)*
- [x] Preparar los datos para el modelo (Fase 2 — `notebooks/preparacion_datos.ipynb`). ✅ *(por Marcos)*
- [ ] Construir modelo de riesgo.
- [ ] Simular escenarios de acción.
- [ ] Generar esquema interpretable.


---
