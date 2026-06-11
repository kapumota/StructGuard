### Inventario de scripts de StructGuard

#### Propósito

Este documento clasifica los scripts ubicados en `scripts/` para evitar limpieza destructiva antes de la Fase 10. La Fase 10 generará evidence packs, comandos ejecutados y artefactos reproducibles, por lo que es importante saber qué scripts siguen activos y cuáles son candidatos a migración o retiro.

#### Estado recomendado

```text
Mantener          = usado por flujos actuales, validación o demostraciones vigentes
Revisar           = puede ser útil, pero necesita confirmación antes de conservarlo
Candidato legacy  = script histórico o de versión anterior que debe migrarse o retirarse luego
```

#### Scripts activos

| Script | Estado | Motivo |
|---|---|---|
| `scripts/demo.sh` | Mantener | Demo general del proyecto. |
| `scripts/demo_bug_detection.sh` | Mantener | Demo enfocada en detección de errores. |
| `scripts/demo_clean_ci.sh` | Mantener | Flujo de demostración para CI limpio. |
| `scripts/demo_full.sh` | Mantener | Demo amplia que todavía usa comandos como `bench`. |
| `scripts/smoke_test.sh` | Mantener | Validación rápida del proyecto. |
| `scripts/validate_outputs.py` | Mantener | Validación de salidas generadas. |
| `scripts/validate_release.sh` | Mantener | Validación de release. |

#### Scripts candidatos a legacy

| Script | Estado | Motivo |
|---|---|---|
| `scripts/demo_v4_4.sh` | Candidato legacy | Script asociado a una versión anterior. |
| `scripts/demo_v4_5.sh` | Candidato legacy | Script asociado a una versión anterior. |
| `scripts/final_demo.sh` | Revisar | Puede estar duplicando demos actuales. |
| `scripts/final_demo_cc232.sh` | Revisar | Puede seguir siendo útil para el perfil CC-232, pero no debe ser la ruta principal del producto. |

#### Política de limpieza

No se deben eliminar scripts solo porque no cambiaron desde el primer commit. Primero se debe comprobar si están referenciados por README, CI, Makefile, documentación o pruebas.

Comandos sugeridos:

```bash
grep -R "demo_v4_4\|demo_v4_5\|final_demo" -n README.md docs scripts .github Makefile \
  --exclude-dir=__pycache__
```

```bash
pytest -q
ruff check .
mypy
```

#### Decisión para Fase 9.5

Esta fase no elimina scripts. Solo documenta su estado para que la Fase 10 pueda trabajar con evidencia reproducible sin mezclar cambios de arquitectura con limpieza destructiva.

#### Decisión futura

La eliminación real debe hacerse en una fase posterior, cuando existan reemplazos claros mediante:

```text
structguard scan
structguard contract
structguard policy
structguard report
structguard doctor
```
