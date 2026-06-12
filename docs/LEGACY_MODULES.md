### Inventario de módulos heredados de StructGuard

#### Propósito

Este documento clasifica módulos históricos de `src/structguard/` que todavía existen junto al flujo canónico basado en `scan --preset`, `report derive` y `testgen`.

El objetivo no es borrar código de inmediato. El objetivo es indicar qué módulos son activos, cuáles son wrappers de compatibilidad y cuál es el reemplazo canónico para nuevas contribuciones.

#### Criterios de estado

```text
Activo              = forma parte de la ruta actual del producto
Compatibilidad      = se conserva para comandos o pruebas heredadas
Legacy wrapper      = adapta una ruta antigua hacia componentes nuevos
Especializado       = comando todavía útil, pero no es el flujo principal
Deprecado           = se mantiene solo como transición documentada
Experimental        = puede usarse, pero no debe presentarse como garantía completa
```

#### Tabla de módulos

| Módulo | Rol histórico | Estado | Reemplazo canónico |
|---|---|---|---|
| `src/structguard/frontend.py` | Extracción C++ inicial | Legacy wrapper | `src/structguard/frontend/cpp/` y `scan --language cpp` |
| `src/structguard/cppscan.py` | Parser ligero educativo | Compatibilidad | `scan --frontend lightweight` |
| `src/structguard/clang_frontend.py` | Frontend Clang histórico | Legacy wrapper | `scan --language cpp --frontend clang --compile-commands ...` |
| `src/structguard/dsl.py` | Carga SGDSL inicial | Compatibilidad | `src/structguard/sgdsl/` y perfiles en `profiles/*/contracts/` |
| `src/structguard/verifier.py` | Verificación acotada inicial | Compatibilidad | `AnalysisEngine` y `scan --preset contracts` |
| `src/structguard/formal.py` | Backend formal experimental | Experimental | Backend Dafny experimental y `structguard formal` |
| `src/structguard/pipeline.py` | Orquestación histórica | Compatibilidad | `AnalysisEngine`, `FindingIR` y presets |
| `src/structguard/lint.py` | Reglas iniciales de calidad | Compatibilidad | `scan --preset contracts` |
| `src/structguard/security.py` | Revisión de seguridad histórica | Especializado | `scan --preset security` |
| `src/structguard/performance.py` | Revisión de rendimiento | Especializado | comando `perf` conservado |
| `src/structguard/docs.py` | Documentación derivada | Especializado | comando `docs` conservado |
| `src/structguard/report.py` | Reportes históricos | Compatibilidad | `report derive` desde `report.json` |
| `src/structguard/ci_outputs.py` | Emisión de artefactos CI | Compatibilidad | `report derive` y workflow canónico |
| `src/structguard/fuzz.py` | Generación abstracta previa | Deprecado | `testgen` |
| `src/structguard/counterexample.py` | Contraejemplos históricos | Compatibilidad | FindingIR, TestGen y reportes derivados |
| `src/structguard/trace.py` | Trazas internas | Compatibilidad | Evidence Pack y reporte canónico |

#### Reglas para nuevas contribuciones

Para código nuevo use primero estas rutas:

```text
scan --preset contracts
scan --preset security
scan --preset ci
scan --language cpp --frontend clang
report derive
testgen
```

Evite agregar funcionalidad nueva directamente sobre módulos marcados como `Deprecado` o `Legacy wrapper`, salvo que sea un arreglo de compatibilidad.

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

#### Decisión de Fase 18

La Fase 18 no elimina módulos de `src/structguard/`. Solo documenta su estado y evita que un contribuidor nuevo edite un archivo equivocado.
