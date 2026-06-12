### TestGen guiado por contratos

StructGuard usa `testgen` como nombre principal para la generación abstracta de casos de prueba.

Esta fase corrige la ambigüedad de llamar `fuzz` a un flujo que no ejecuta binarios, no instrumenta el programa y no usa motores como libFuzzer o AFL++.

#### Objetivo

`testgen` genera candidatos de pruebas a partir de:

```text
contratos SGDSL
secuencias abstractas de operaciones
métodos detectados en estructuras C++
fallos candidatos de precondición
```

El resultado es útil para crear pruebas de regresión, pero no debe presentarse como fuzzing nativo.

#### Comando principal

```bash
structguard testgen examples/generic_cpp \
  --profile generic-cpp \
  --contract profiles/generic-cpp/contracts/stack.sgdsl \
  --output artifacts/testgen-cases.json \
  --test-dir generated_tests
```

#### Salida JSON

El archivo JSON generado por `--output` incluye:

```text
schema_version
root
generation_mode
summary
cases
```

Cada caso contiene:

```text
structure
seed
operations
failure
final_state
target_method
minimized_operations
generation_mode
utility_score
classification
contract_hint
```

#### Métrica de utilidad

`utility_score` resume qué tan útil parece un caso candidato.

La puntuación sube cuando el caso:

```text
tiene fallo candidato
incluye reproductor minimizado
está asociado a un contrato
cubre métodos con requires o ensures
apunta a un método presente en el contrato
```

Esta métrica no prueba que el caso sea correcto. Sirve para priorizar revisión humana y pruebas de regresión.

#### Relación con fuzz

El comando heredado:

```bash
structguard testgen ...
```

queda como alias de compatibilidad y debe mostrar advertencia de deprecación.

El comando recomendado es:

```bash
structguard testgen ...
```

#### Alcance

Esta fase no implementa ejecución real de binarios, sanitizers ni fuzzing nativo.

El flujo correcto es:

```text
testgen = generación abstracta o guiada por contratos
fuzzing nativo = ejecución real futura con instrumentación
```
