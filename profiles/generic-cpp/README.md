### Generic C++ Profile

#### Propósito

Perfil general para librerías C++ propias que implementan estructuras de datos fuera de CC-232.

#### Estado

Este perfil es la ruta canónica para ejemplos C++ genéricos.

#### Uso esperado

```bash
structguard scan include \
  --profile generic-cpp \
  --preset contracts \
  --headers-only \
  --contract profiles/generic-cpp/contracts/stack.sgdsl
```
