### CC-232 Profile

#### Proposito

Perfil educativo inicial de StructGuard para estructuras de datos usadas en cursos como CC-232.

#### Estado

Este perfil conserva compatibilidad con los contratos actuales de `contracts/cc232_core.sgdsl` y prepara la separacion entre el nucleo general y las reglas academicas.

#### Uso esperado

```bash
structguard analyze ../Libreria_cc232/Semana2/include   --headers-only   --dsl profiles/cc232/contracts/cc232_core.sgdsl
```
