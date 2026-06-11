### Backend Dafny experimental

#### Objetivo

La Fase 16 agrega un backend formal único experimental basado en Dafny.

El objetivo es evitar intentar mantener muchos backends formales al mismo tiempo. StructGuard empieza con un solo backend inicial y limita explícitamente su alcance.

#### Alcance soportado

El backend Dafny trabaja sobre modelos abstractos simples derivados de contratos SGDSL.

Estructuras iniciales soportadas:

```text
ArrayStack
ArrayQueue
ArrayVector
DisjointSet
```

El backend no traduce C++ real con punteros, memoria manual, aliasing, iteradores, templates complejos ni llamadas arbitrarias.

#### Uso recomendado

Ejemplo:

```bash
structguard formal examples/formal/dafny \
  --backend dafny \
  --dsl examples/formal/dafny/array_stack.sgdsl \
  --out-dir artifacts/formal-dafny
```

Salida esperada:

```text
artifacts/formal-dafny/dafny/ArrayStackModel.dfy
artifacts/formal-dafny/dafny_manifest.json
```

#### Estados del backend

El backend comunica estados explícitos:

```text
GENERATED
PARSED
VERIFIED
FAILED
UNKNOWN
UNSUPPORTED
```

Interpretación:

| Estado | Significado |
|---|---|
| `GENERATED` | El modelo Dafny fue generado, pero no se ejecutó Dafny. |
| `PARSED` | Reservado para una validación sintáctica futura. |
| `VERIFIED` | Dafny verificó el modelo generado. Solo puede emitirse si Dafny se ejecutó correctamente. |
| `FAILED` | Dafny rechazó el modelo o encontró una obligación no verificada. |
| `UNKNOWN` | No se pudo ejecutar Dafny o el resultado no fue concluyente. |
| `UNSUPPORTED` | La estructura o expresión queda fuera del subconjunto soportado. |

#### Garantía formal

StructGuard no debe comunicar `FORMALLY_VERIFIED` si el estado no es `VERIFIED`.

Un archivo con estado `GENERATED` solo significa que existe un modelo Dafny. No significa que el contrato haya sido probado.

#### Modelo generado

El backend genera un `trait` Dafny con campos `ghost`, un predicado `Valid()` y métodos abstractos con `requires` y `ensures`.

Ejemplo simplificado:

```dafny
trait ArrayStackModel {
  ghost var n: int
  ghost var capacity: int

  predicate Valid()
    reads this
  {
    n >= 0 &&
    n <= capacity
  }

  method add(i: int)
    requires Valid()
    requires 0 <= i && i <= n
    ensures Valid()
    ensures n == old(n) + 1
}
```

#### Lo que no soporta esta fase

Esta fase no soporta:

```text
traducción de C++ real
punteros
new/delete
aliasing
memoria manual
templates complejos
iteradores
verificación de cuerpos C++
generación de pruebas nativas
```

#### Relación con fases anteriores

La Fase 16 se apoya en:

```text
Fase 2  - SGDSL y ContractIR
Fase 9.6 - niveles de garantía
Fase 11 - report.json como fuente canónica
Fase 15 - formal como comando legacy experimental documentado
```

#### Criterio de aceptación

La fase queda aceptada si:

```text
existe un backend Dafny único experimental
exporta modelos para estructuras soportadas
marca estructuras no soportadas como UNSUPPORTED
no traduce C++ real con punteros
usa estados honestos
no comunica verificación formal sin ejecutar Dafny
```
