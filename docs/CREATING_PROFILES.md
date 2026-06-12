### Creación de perfiles en StructGuard

#### Propósito

Un perfil define cómo StructGuard debe analizar una familia de estructuras, una librería o un curso. La regla central es simple:

```text
StructGuard no valida una librería porque sí.
StructGuard valida código contra contratos explícitos definidos por un perfil.
```

Esto permite separar el motor general de análisis de las reglas específicas de un dominio.

#### Estructura recomendada

Cada perfil debe vivir bajo `profiles/` y tener esta forma:

```text
profiles/mi-perfil/
  profile.yml
  README.md
  contracts/
    estructura.sgdsl
```

#### Archivo profile.yml

Un perfil mínimo se ve así:

```yaml
name: mi-perfil
display_name: Mi Perfil
description: Perfil de ejemplo para una librería propia.
language: cpp
status: draft
contracts:
  - contracts/estructura.sgdsl
analysis:
  headers_only: true
  strict_ast: false
  bounded: true
outputs:
  html: true
  json: true
  sarif: true
```

#### Campos principales

| Campo | Uso |
| - | - |
| `name` | Identificador usado por la CLI. |
| `display_name` | Nombre legible del perfil. |
| `description` | Descripción breve del dominio analizado. |
| `language` | Lenguaje principal. Valores iniciales: `cpp`, `rust`, `python`, `multi`. |
| `status` | Estado del perfil. Valores iniciales: `draft`, `stable`, `experimental`, `template`. |
| `contracts` | Lista de contratos `.sgdsl` relativos al directorio del perfil. |
| `analysis` | Opciones de análisis que el perfil activa. |
| `outputs` | Salidas recomendadas para reportes. |

#### Validación de perfiles

Para listar perfiles disponibles:

```bash
structguard profiles list
```

Para validar un perfil:

```bash
structguard profiles validate profiles/generic-cpp/profile.yml
```

También puedes validar pasando el directorio del perfil:

```bash
structguard profiles validate profiles/generic-cpp
```

#### Uso de un perfil

Ejemplo con el perfil académico CC-232:

```bash
structguard scan ../Libreria_cc232/Semana2/include --profile cc232
```

Ejemplo con una librería C++ propia:

```bash
structguard scan external/my-containers/include --profile generic-cpp
```

Ejemplo con adaptadores STL:

```bash
structguard scan examples/external_libraries/stl --profile stl-adapters
```

#### Contratos adicionales

Un perfil puede declarar contratos base. Si el usuario necesita acotar el análisis a un contrato específico, puede usar una ruta canónica bajo `profiles/<perfil>/contracts/`:

```bash
structguard scan include --profile generic-cpp --contract profiles/my-profile/contracts/ring_buffer.sgdsl
```

StructGuard usa los contratos del perfil y permite acotar el alcance con `--contract` cuando el análisis debe enfocarse en una estructura concreta.

#### Recomendaciones

Mantén los contratos cerca del perfil, no dentro del motor.

Usa `profiles/custom-template/` como punto de partida para perfiles nuevos.

No declares que un perfil verifica formalmente una librería completa si solo ejecuta análisis acotado o heurístico.

Documenta las estructuras soportadas y las limitaciones del perfil en su `README.md`.
