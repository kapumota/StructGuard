### Inventario de módulos heredados de StructGuard

#### Propósito

Este documento clasifica módulos históricos de `src/structguard/` que todavía existen junto al nuevo flujo modular introducido entre las fases 5 y 9.

El objetivo no es borrar código de inmediato, sino evitar eliminaciones prematuras. Algunos módulos parecen antiguos por nombre o por historial de Git, pero todavía están conectados a CLI, pruebas o módulos internos.

#### Módulos revisados

```text
src/structguard/advanced.py
src/structguard/assist.py
src/structguard/bench.py
src/structguard/ci.py
src/structguard/clang_bridge.py
src/structguard/clang_frontend.py
```

#### Clasificación

| Módulo | Estado | Referencias actuales | Decisión |
|---|---|---|---|
| `advanced.py` | Activo por compatibilidad | `cli.py`, pruebas históricas | Mantener hasta migrar `advanced` a presets o plantillas nuevas. |
| `assist.py` | Activo por compatibilidad | `cli.py`, pruebas históricas | Mantener hasta migrar recomendaciones a un analizador o comando nuevo. |
| `bench.py` | Activo | `cli.py`, `performance.py`, `scripts/demo_full.sh`, pruebas | Mantener. Es usado por benchmark y rendimiento. |
| `ci.py` | Activo por compatibilidad | CLI y flujos antiguos | Mantener mientras `scan --preset ci` termina de reemplazarlo. |
| `clang_bridge.py` | Activo | `verifier.py`, pruebas | Mantener hasta que `SourceIR` cubra completamente el puente anterior. |
| `clang_frontend.py` | Activo | `cli.py`, `pipeline.py`, `ci.py`, pruebas | Mantener hasta completar la migración al frontend C++ canónico nuevo. |

#### Motivo de no eliminación

Estos módulos todavía aparecen en imports de CLI, tests o módulos del motor heredado. Eliminarlos antes de migrar sus responsabilidades puede romper:

```text
comandos antiguos mantenidos por compatibilidad
pruebas existentes
flujos de demo
benchmark estático
strict AST anterior
verificación acotada con puente Clang heredado
```

#### Ruta de migración recomendada

La limpieza debe hacerse en tres pasos:

```text
1. Documentar el módulo y su uso actual.
2. Migrar la funcionalidad hacia AnalysisEngine, SourceIR, FindingIR o presets.
3. Retirar el módulo cuando no tenga imports, pruebas ni comandos activos.
```

#### Comandos de auditoría

Para revisar referencias antes de retirar un módulo:

```bash
grep -R "advanced\|assist\|bench\|clang_bridge\|clang_frontend" -n pyproject.toml .github scripts src tests docs \
  --exclude-dir=__pycache__
```

Para revisar si hay referencias a archivos concretos:

```bash
grep -R "advanced.py\|assist.py\|bench.py\|ci.py\|clang_bridge.py\|clang_frontend.py" -n . \
  --exclude-dir=.git \
  --exclude-dir=.pytest_cache \
  --exclude-dir=.ruff_cache \
  --exclude-dir=.mypy_cache \
  --exclude-dir=struct_guard \
  --exclude-dir=__pycache__
```

#### Decisión para Fase 9.5

No se elimina ningún módulo de `src/structguard/` en esta fase.

La fase deja documentado qué módulos son activos por compatibilidad y cuáles deben migrarse después de la Fase 10. Esto reduce el riesgo de mezclar limpieza destructiva con evidencia reproducible, cache incremental o cambios del motor.

#### Criterio para eliminación futura

Un módulo puede eliminarse solo si cumple todas estas condiciones:

```text
no aparece en imports de src/
no aparece en tests/
no aparece en scripts/
no aparece en README ni docs activas
su funcionalidad ya existe en el flujo nuevo
pytest, ruff y mypy pasan después de retirarlo
```
