### STL Adapters Profile

#### Proposito

Perfil para adaptar expectativas de estructuras de datos comunes de STL a contratos de StructGuard.

#### Alcance

Este perfil no intenta verificar internamente la implementacion de STL. Define contratos de uso y envolturas esperadas para codigo cliente o adaptadores propios.

#### Uso esperado

```bash
structguard analyze examples/external_libraries/stl   --headers-only   --dsl profiles/stl-adapters/contracts/stl_containers.sgdsl
```
