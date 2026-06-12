### Layout canónico de contratos

#### Regla principal

La ubicación canónica de contratos en StructGuard es:

```text
profiles/<perfil>/contracts/
```

Cada perfil debe conservar sus contratos cerca de su configuración, documentación y fixtures. Esto evita ambigüedad entre contratos globales, contratos de curso y contratos experimentales.

#### Contratos activos

| Ruta canónica | Perfil | Estado |
|---|---|---|
| `profiles/cc232/contracts/cc232_core.sgdsl` | `cc232` | Activo |
| `profiles/generic-cpp/contracts/stack.sgdsl` | `generic-cpp` | Activo |
| `profiles/generic-cpp/contracts/queue.sgdsl` | `generic-cpp` | Activo |
| `profiles/generic-cpp/contracts/vector.sgdsl` | `generic-cpp` | Activo |
| `profiles/advanced-structures/contracts/advanced_structures.sgdsl` | `advanced-structures` | Experimental |

#### Rutas relativas dentro de perfiles

Dentro de `profile.yml`, las rutas listadas en la clave `contracts` se resuelven de forma relativa al directorio del perfil.

Por ejemplo, el perfil `cc232` puede declarar su contrato con una ruta local al perfil, pero la ruta pública y canónica del archivo es:

```text
profiles/cc232/contracts/cc232_core.sgdsl
```

De forma equivalente, el perfil `advanced-structures` conserva su contrato avanzado en:

```text
profiles/advanced-structures/contracts/advanced_structures.sgdsl
```

#### Decisión de Fase 19

La carpeta raíz `contracts/` fue retirada como ubicación activa. Los contratos pasan a vivir dentro de `profiles/*/contracts/`.

Esta fase no elimina el soporte para rutas relativas dentro de `profile.yml`. Solo elimina la ambigüedad de mantener contratos activos fuera de sus perfiles.

#### Fase posterior

Si se requiere compatibilidad histórica con rutas antiguas, debe implementarse como alias explícito, advertencia documentada o migración asistida. No debe volver a introducirse una carpeta global de contratos activos.
