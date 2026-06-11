### Generic C++ Profile

#### Proposito

Perfil general para librerias C++ propias que implementan estructuras de datos fuera de CC-232.

#### Estado

Este perfil es una base de Fase 0. En Fase 1 debe conectarse al cargador real de perfiles.

#### Uso esperado

```bash
structguard analyze include   --headers-only   --dsl profiles/generic-cpp/contracts/stack.sgdsl   --dsl profiles/generic-cpp/contracts/queue.sgdsl
```
