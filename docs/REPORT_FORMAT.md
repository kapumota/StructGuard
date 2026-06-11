### Formato de reporte canónico

#### Objetivo

`report.json` es la fuente canónica de verdad para una ejecución de StructGuard.

La Fase 11 evita que cada formato de salida tenga su propia interpretación de los hallazgos. A partir de esta fase, los reportes secundarios deben poder derivarse desde `report.json`.

#### Archivo principal

```text
artifacts/report.json
```

#### Estructura mínima

```text
schema_version
  versión del formato canónico

tool
  nombre y versión de StructGuard

run
  raíz analizada, perfil, preset, lenguaje y metadatos mínimos de ejecución

summary
  conteos por severidad, conteos por garantía y total de hallazgos

rules
  reglas únicas activadas por la ejecución

findings
  hallazgos normalizados con ubicación, severidad, garantía, evidencia y remediación

legacy_diagnostics
  diagnósticos originales preservados por compatibilidad
```

#### Ejecución recomendada

```bash
structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset security \
  --report-json artifacts/report.json \
  --lockfile artifacts/structguard.lock
```

#### Derivar reportes secundarios

```bash
structguard report derive artifacts/report.json \
  --html artifacts/report.html \
  --sarif artifacts/report.sarif \
  --junit artifacts/junit.xml \
  --markdown artifacts/report.md
```

#### Regla de diseño

`report.json` debe ser suficiente para reconstruir reportes secundarios sin volver a ejecutar el análisis.

Esto no significa que todos los reportes secundarios sean obligatorios. En una ejecución mínima solo se necesita:

```text
artifacts/report.json
artifacts/structguard.lock
```

#### Relación con FindingIR

`report.json` conserva hallazgos normalizados derivados de FindingIR. Cada hallazgo incluye:

```text
rule_id
message
severity
guarantee
location
symbol
evidence
remediation
cwe
tags
```

#### Relación con niveles de garantía

Cada hallazgo mantiene su nivel de garantía:

```text
G1_HEURISTIC
G2_STRUCTURAL
G3_BOUNDED
G4_EXECUTED
G5_FORMALLY_VERIFIED
```

Esto evita que un reporte derivado pierda la diferencia entre una señal heurística, una regla estructural y una verificación formal real.
