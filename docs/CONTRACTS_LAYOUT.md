### Layout de contratos de StructGuard

#### Propósito

Este documento separa contratos canónicos por perfil de contratos conservados por compatibilidad.

La decisión principal de Fase 18 es no borrar la carpeta raíz `contracts/` todavía. Esa carpeta sigue apareciendo en documentación, demos heredadas y flujos CC-232.

#### Layout actual

| Ruta | Estado | Decisión |
|---|---|---|
| `contracts/cc232_core.sgdsl` | Compatibilidad CC-232 | Mantener temporalmente |
| `contracts/advanced_structures.sgdsl` | Ejemplo avanzado | Candidato a migrar |
| `profiles/cc232/contracts/cc232_core.sgdsl` | Perfil CC-232 | Ruta objetivo para migración gradual |
| `profiles/generic-cpp/contracts/stack.sgdsl` | Perfil canónico generic-cpp | Mantener |
| `profiles/generic-cpp/contracts/queue.sgdsl` | Perfil canónico generic-cpp | Mantener |
| `profiles/generic-cpp/contracts/vector.sgdsl` | Perfil canónico generic-cpp | Mantener |

#### Decisión

No ejecutar todavía:

```bash
git rm -r contracts
```

Antes de eliminar `contracts/` raíz se debe migrar toda referencia hacia `profiles/*/contracts/`.

#### Migración futura sugerida

```text
contracts/cc232_core.sgdsl -> profiles/cc232/contracts/cc232_core.sgdsl
contracts/advanced_structures.sgdsl -> profiles/advanced-structures/contracts/advanced_structures.sgdsl
```

Después de migrar se deben actualizar:

```text
README.md
docs/
profiles/cc232/profile.yml
scripts/final_demo_cc232.sh
tests/
```

#### Criterio de eliminación futura

La carpeta raíz `contracts/` puede retirarse solo si:

```text
no aparece en README.md
no aparece en docs/
no aparece en scripts/
no aparece en tests/
no aparece en profiles/
pytest, ruff y mypy pasan
```
