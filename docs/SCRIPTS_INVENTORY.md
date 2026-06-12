### Inventario de scripts de StructGuard

#### Propósito

Este documento clasifica los scripts ubicados en `scripts/` para evitar limpieza destructiva y para que el release tenga una ruta reproducible.

#### Estado recomendado

```text
Mantener          = usado por flujos actuales, validación o demostraciones vigentes
Revisar           = puede ser útil, pero necesita confirmación antes de conservarlo
Retirado          = script histórico eliminado después de validar que no estaba en rutas activas
```

#### Scripts activos

| Script | Estado | Motivo |
|---|---|---|
| `scripts/check_benchmark_thresholds.py` | Mantener | Valida umbrales del benchmark de regresión. |
| `scripts/demo.sh` | Mantener | Demo general del proyecto. |
| `scripts/demo_bug_detection.sh` | Mantener | Demo enfocada en detección de errores. |
| `scripts/demo_clean_ci.sh` | Mantener | Flujo de demostración para CI limpio. |
| `scripts/demo_full.sh` | Mantener | Demo amplia que todavía usa comandos especializados. |
| `scripts/smoke_new_user.sh` | Mantener | Smoke test de usuario nuevo agregado en Fase 18. |
| `scripts/smoke_test.sh` | Mantener | Validación rápida del proyecto. |
| `scripts/validate_outputs.py` | Mantener | Validación de salidas generadas. |
| `scripts/validate_release.sh` | Mantener | Validación de release. |

#### Scripts en revisión

| Script | Estado | Motivo |
|---|---|---|
| `scripts/final_demo.sh` | Revisar | Usado por Makefile; no retirar sin reemplazar el target. |
| `scripts/final_demo_cc232.sh` | Mantener | Demo CC-232 migrada a `scan --preset`, `report derive` y `testgen`. |

#### Scripts retirados en Fase 18

| Script | Estado | Motivo |
|---|---|---|
| `scripts/demo_v4_4.sh` | Retirado | Demo asociada a versión anterior y fuera del flujo activo. |
| `scripts/demo_v4_5.sh` | Retirado | Demo asociada a versión anterior y fuera del flujo activo. |

#### Política de limpieza

No se deben eliminar scripts solo porque no cambiaron desde el primer commit. Primero se debe comprobar si están referenciados por README, CI, Makefile, documentación o pruebas.

Comandos sugeridos:

```bash
grep -R "demo_v4_4\|demo_v4_5\|final_demo" -n README.md docs scripts .github Makefile tests \
  --exclude-dir=__pycache__
```

```bash
pytest -q
ruff check .
mypy
```

#### Decisión de Fase 18

La Fase 18 retira solo demos de versión anterior que no forman parte del flujo activo. No se elimina `final_demo.sh`, porque está referenciado por Makefile. No se elimina `final_demo_cc232.sh`, porque fue migrado al flujo canónico de Fase 19.
