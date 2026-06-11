### Evidence Pack mínimo

#### Objetivo

La Fase 11 define un Evidence Pack mínimo. El objetivo no es generar muchos archivos por cada ejecución, sino conservar la información necesaria para reproducir y auditar un análisis.

#### Archivos mínimos

```text
artifacts/report.json
artifacts/structguard.lock
```

#### `report.json`

Contiene la fuente canónica de verdad:

```text
hallazgos
reglas activadas
perfil
preset
resumen
niveles de garantía
diagnósticos heredados
```

#### `structguard.lock`

Contiene metadatos mínimos de reproducibilidad:

```text
versión de StructGuard
hashes SHA-256 de entradas
flags principales
perfil
preset
lenguaje
versión de Python
plataforma
```

#### Reportes opcionales

Los siguientes archivos son derivados. No son obligatorios para cada ejecución:

```text
artifacts/report.html
artifacts/report.sarif
artifacts/junit.xml
artifacts/report.md
```

Se generan desde `report.json` con:

```bash
structguard report derive artifacts/report.json \
  --html artifacts/report.html \
  --sarif artifacts/report.sarif \
  --junit artifacts/junit.xml \
  --markdown artifacts/report.md
```

#### Criterio de diseño

El Evidence Pack mínimo debe evitar una estructura burocrática. No se deben exigir nueve archivos por ejecución si dos archivos bastan para conservar evidencia reproducible.

#### Qué no resuelve esta fase

Esta fase no implementa cache incremental. Tampoco define políticas de retención de artefactos ni integración completa con auditorías externas.

La cache incremental corresponde a una fase posterior.
