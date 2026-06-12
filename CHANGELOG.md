### Changelog

#### 4.6.1 - Fases 0 a 19

##### Arquitectura

```text
Fases 0 a 3: identidad del proyecto, perfiles, SGDSL y binding contrato-código
Fases 4 a 6: frontend C++ con Clang, motor modular y FindingIR
Fases 7 a 9.6: política YAML, modelo de memoria, análisis estructural y garantías G1-G5
Fase 10: corpus mínimo y benchmark de regresión
Fase 11: reporte canónico y Evidence Pack mínimo
Fase 12: cache incremental
Fase 13: testgen guiado por contratos
Fase 14: CI con gates medibles
Fase 15: deprecación controlada del CLI heredado
Fase 16: backend Dafny experimental
Fase 17: alineación pública de CLI, CI, README y CHANGELOG
Fase 18: hardening de release, smoke test, benchmark e inventario legacy
Fase 19: migración de contratos raíz hacia profiles/*/contracts/
```

##### CLI

```text
CLI canónico: scan --preset
Reportes derivados: report derive
Pruebas abstractas: testgen
Backend formal: Dafny experimental
Comandos heredados: documentados con structguard legacy list
```

##### Release hardening

```text
Smoke test de usuario nuevo: scripts/smoke_new_user.sh
Benchmark de regresión: .github/workflows/benchmark.yml
Inventario de módulos legacy: docs/LEGACY_MODULES.md
Layout de contratos: docs/CONTRACTS_LAYOUT.md
Inventario de scripts: docs/SCRIPTS_INVENTORY.md
```

##### Layout de contratos

```text
Ruta canónica CC-232: profiles/cc232/contracts/cc232_core.sgdsl
Ruta canónica avanzada: profiles/advanced-structures/contracts/advanced_structures.sgdsl
Carpeta contracts/ raíz: retirada después de migrar referencias activas
```

##### Métricas de referencia

Las métricas de benchmark deben tomarse del reporte generado por:

```bash
python benchmarks/run_benchmark.py \
  --thresholds benchmarks/thresholds.yml \
  --fail-on-threshold
```

No se registran valores fijos en este changelog si no provienen del reporte generado en CI.

##### Próximo release

La Fase 20 debe crear el tag anotado `v1.0.0`, publicar GitHub Release, validar badges públicos y cerrar el primer ciclo estable del proyecto.
