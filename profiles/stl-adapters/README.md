### STL Adapters Profile

#### Propósito

Perfil para adaptar expectativas de estructuras de datos comunes de STL a contratos de StructGuard.

#### Alcance

Este perfil no intenta verificar internamente la implementación de STL. Define contratos de uso y envolturas esperadas para código cliente o adaptadores propios.

#### Uso esperado

```bash
structguard scan examples/external_libraries/stl \
  --profile stl-adapters \
  --preset contracts \
  --headers-only
```
