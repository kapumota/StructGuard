### CI/CD con gates medibles

#### Objetivo

La Fase 14 integra pruebas unitarias, lint, tipos, validación de política, benchmark de regresión y reportes al flujo de CI.

El objetivo es que el CI no solo responda si el código compila o si pasan las pruebas unitarias, sino también si la calidad del análisis se mantiene dentro de umbrales definidos.

#### Workflows

StructGuard define dos workflows principales:

```text
.github/workflows/ci.yml
.github/workflows/benchmark.yml
```

`ci.yml` ejecuta las compuertas generales del proyecto:

```text
compileall
structguard policy validate
pytest
ruff
mypy
report.json
structguard.lock
report.sarif
```

`benchmark.yml` ejecuta el benchmark de regresión:

```bash
python benchmarks/run_benchmark.py \
  --output artifacts/benchmark-report.json \
  --thresholds benchmarks/thresholds.yml \
  --fail-on-threshold
```

Luego valida el reporte con:

```bash
python scripts/check_benchmark_thresholds.py artifacts/benchmark-report.json
```

#### Gates obligatorios

El CI debe fallar si ocurre cualquiera de estos casos:

```text
pytest falla
ruff falla
mypy falla
policy validate falla
benchmark cae por debajo del umbral definido
```

#### Umbrales

Los umbrales iniciales se definen en:

```text
benchmarks/thresholds.yml
```

Las métricas principales son:

```text
precision
recall
false_positive_rate
analysis_time_ms_per_file
mutation_detection_rate
```

Para métricas como `precision`, `recall` y `mutation_detection_rate`, el valor real debe ser mayor o igual al umbral.

Para métricas como `false_positive_rate` y `analysis_time_ms_per_file`, el valor real debe ser menor o igual al umbral.

#### Artefactos

Los workflows suben artefactos para inspección posterior:

```text
artifacts/benchmark-report.json
artifacts/report.json
artifacts/structguard.lock
artifacts/report.sarif
```

`benchmark-report.json` permite auditar qué casos pasaron, qué reglas se activaron y qué umbrales se cumplieron.

`report.sarif` es un derivado opcional desde `report.json` y puede usarse posteriormente con Code Scanning si el repositorio lo habilita.

#### Alcance

Esta fase no cambia los analizadores ni los umbrales por sí sola. Su función es convertir el benchmark y la política en compuertas automáticas.

La integración con Code Scanning puede activarse después, cuando el repositorio tenga esa opción habilitada.
