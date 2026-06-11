### Modelo de cache incremental

#### Propósito

La cache incremental de StructGuard evita repetir trabajo cuando se ejecuta `scan` sobre un proyecto donde la mayoría de archivos no cambió.

La Fase 12 introduce una cache local por archivo. El objetivo no es distribuir resultados entre máquinas ni reemplazar el Evidence Pack. El objetivo es reducir trabajo repetido en ejecuciones locales y en flujos de desarrollo.

#### Problema que corrige

Antes de esta fase, una ejecución de `scan` analizaba nuevamente todos los archivos aunque solo hubiera cambiado uno.

Eso dificulta usar StructGuard en proyectos medianos, porque cada cambio pequeño fuerza a repetir análisis sobre archivos sin modificaciones.

#### Uso

```bash
structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset security \
  --cache \
  --cache-dir .structguard/cache
```

Para limpiar la cache antes de ejecutar:

```bash
structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset security \
  --cache \
  --cache-clear
```

#### Entradas de la clave

Cada entrada de cache se identifica con una huella estable que incluye:

```text
hash SHA-256 del archivo
hashes SHA-256 de contratos SGDSL
perfil activo
perfil de dominio
preset
flags principales
versión de StructGuard
capacidades del preset
```

Si cualquiera de esas entradas cambia, la clave cambia y el archivo se recalcula.

#### Archivos cacheables

La cache trabaja sobre archivos C++ detectados por StructGuard:

```text
.h
.hh
.hpp
.hxx
.cpp
.cc
.cxx
```

Cuando se usa `--headers-only`, solo se consideran cabeceras.

#### Comportamiento esperado

Primera ejecución:

```text
hits = 0
misses = cantidad de archivos cacheables
```

Segunda ejecución sin cambios:

```text
hits = cantidad de archivos cacheables
misses = 0
```

Si solo cambia un archivo:

```text
hits = archivos no modificados
misses = 1
```

#### Relación con report.json

La cache no reemplaza `report.json`. La cache acelera el análisis. `report.json` sigue siendo la fuente canónica de verdad para la ejecución.

Un flujo razonable es:

```bash
structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset security \
  --cache \
  --report-json artifacts/report.json \
  --lockfile artifacts/structguard.lock
```

#### Límites actuales

Esta fase no implementa invalidación por `#include`.

Eso significa que, si cambia un archivo incluido indirectamente por otros, la cache puede no invalidar automáticamente todos los consumidores. Esa mejora requiere modelar dependencias de inclusión y queda para una fase posterior.

#### Regla de versionamiento

La cache local no debe versionarse.

La ruta recomendada es:

```text
.structguard/cache/
```

Esa ruta está ignorada por Git.
