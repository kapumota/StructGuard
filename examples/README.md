# Ejemplos

Este directorio mezcla ejemplos limpios y un ejemplo con bug intencional.

## Ejemplo limpio

```bash
structguard analyze examples/stack_ok.h --headers-only --strict-ast --std c++17
```

Debe terminar sin `FAILED`. Los resultados `BOUNDED_VERIFIED` significan evidencia acotada, no prueba formal universal.

## Bug intencional

```bash
structguard analyze examples/stack_bug.h --headers-only --strict-ast --std c++17
```

`stack_bug.h` contiene deliberadamente `BuggyStack::pop`, que puede violar el invariante `size_ >= 0`. Esta demo debe fallar y sirve para mostrar detección de bugs.

## No usar `examples/` como demo limpia

```bash
structguard analyze examples --headers-only --strict-ast
```

Ese comando analiza también `stack_bug.h`, por lo que es normal observar algo como:

```text
BOUNDED_VERIFIED=14, FAILED=1, INFO=9, WARNING=1
```

El `FAILED=1` esperado corresponde al bug intencional de `BuggyStack::pop`.
