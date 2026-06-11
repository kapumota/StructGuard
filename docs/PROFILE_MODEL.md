### Profile Model

#### Objetivo

Un perfil define como StructGuard interpreta un dominio de estructuras de datos.

CC-232 debe ser solo un perfil inicial. El nucleo debe seguir siendo general.

#### Estructura de un perfil

```text
profiles/<nombre>/
  profile.yml
  README.md
  contracts/
```

#### Campos iniciales de `profile.yml`

```yaml
name: generic-cpp
display_name: Generic C++ Profile
description: Perfil general para librerias C++ propias.
language: cpp
status: draft
contracts:
  - contracts/stack.sgdsl
  - contracts/queue.sgdsl
analysis:
  headers_only: true
  strict_ast: false
```

#### Perfiles iniciales

#### cc232

Perfil educativo inicial. Contiene contratos e invariantes usados para estructuras de datos de cursos basados en arreglos, pilas, colas, deques, heaps, arboles y grafos.

#### generic-cpp

Perfil general para librerias C++ propias. Sirve como punto de partida para proyectos que no pertenecen a CC-232.

#### stl-adapters

Perfil para adaptadores de STL. No intenta verificar internamente `std::vector`, `std::queue` o `std::priority_queue`. Define contratos de uso, envolturas y expectativas semanticas.

#### custom-template

Plantilla para crear perfiles nuevos.

#### Regla central

StructGuard no valida una libreria porque si. La valida contra un contrato explicito y un perfil de dominio.

#### Ejemplos de uso esperado

```bash
structguard analyze include/Stack.hpp   --headers-only   --dsl profiles/generic-cpp/contracts/stack.sgdsl
```

```bash
structguard analyze ../Libreria_cc232/Semana2/include   --headers-only   --dsl profiles/cc232/contracts/cc232_core.sgdsl
```

#### Evolucion en fases posteriores

La Fase 1 debe convertir estos perfiles de documentacion en perfiles ejecutables cargados por el CLI y por el motor de analisis.
