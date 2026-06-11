### Ejemplo Dafny experimental

Este directorio contiene un contrato SGDSL mínimo para probar el backend Dafny experimental.

Uso:

```bash
structguard formal examples/formal/dafny \
  --backend dafny \
  --dsl examples/formal/dafny/array_stack.sgdsl \
  --out-dir artifacts/formal-dafny
```

El comando genera:

```text
artifacts/formal-dafny/dafny/ArrayStackModel.dfy
artifacts/formal-dafny/dafny_manifest.json
```

El estado `GENERATED` significa que el modelo fue emitido. Solo `VERIFIED` significa que Dafny se ejecutó y verificó el modelo.
