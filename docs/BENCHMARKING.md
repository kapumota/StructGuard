### Benchmarking de StructGuard

#### Propósito

La Fase 10 introduce un corpus mínimo y un benchmark de regresión para medir si StructGuard mejora o empeora entre fases.

El objetivo no es cubrir todos los casos posibles de C++. El objetivo es tener una base pequeña, reproducible y versionada que mida:

```text
precision
recall
false_positive_count
false_negative_count
analysis_time
rules_triggered
mutation_detection_rate
```

#### Estructura

```text
benchmarks/
├── corpus/
│   ├── correct/
│   └── buggy/
├── mutations/
├── ground_truth.yaml
├── thresholds.yml
└── run_benchmark.py
```

`benchmarks/corpus/correct/` contiene casos que no deberían activar reglas rastreadas. Incluye casos simples y casos de desafío que son correctos, pero usan helpers o patrones que pueden producir falsos positivos.

`benchmarks/corpus/buggy/` contiene casos con defectos intencionales y hallazgos esperados. Incluye casos simples y casos de desafío que ayudan a exponer falsos negativos conocidos.

`benchmarks/mutations/` contiene mutadores deterministas para generar casos defectuosos desde ejemplos correctos.

`benchmarks/ground_truth.yaml` define las reglas rastreadas, los casos manuales y las mutaciones esperadas.

`benchmarks/thresholds.yml` define umbrales iniciales conservadores para CI futuro.

#### Comando reproducible

Desde la raíz del repositorio:

```bash
python benchmarks/run_benchmark.py
```

Salida esperada:

```text
Benchmark de regresión StructGuard
Casos evaluados: ...
Precision: ...
Recall: ...
Falsos positivos: ...
Falsos negativos: ...
Mutation detection rate: ...
Reporte escrito en: artifacts/benchmark-report.json
```

#### Entorno recomendado

```bash
python3 -m venv struct_guard
source struct_guard/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install -e '.[dev]'
python benchmarks/run_benchmark.py
```

#### Métricas

#### Precision

Proporción de hallazgos reportados que estaban en el ground truth.

```text
precision = true_positive_count / (true_positive_count + false_positive_count)
```

#### Recall

Proporción de hallazgos esperados que StructGuard detectó.

```text
recall = true_positive_count / (true_positive_count + false_negative_count)
```

#### False positive count

Cantidad de reglas rastreadas que StructGuard reportó, pero que no estaban esperadas para el caso.

#### False negative count

Cantidad de reglas esperadas que StructGuard no reportó.

#### Analysis time

Tiempo aproximado de análisis por archivo y total de la corrida.

#### Rules triggered

Conteo por `rule_id` rastreado.

#### Mutation detection rate

Proporción de mutaciones generadas que activan al menos una regla esperada.

#### Mutaciones iniciales

La Fase 10 incluye mutaciones pequeñas y deterministas:

```text
remove_empty_guard_from_stack_pop
omit_size_increment
wrong_queue_end
remove_capacity_guard_from_stack_push
omit_queue_size_decrement
```

Estas mutaciones no intentan transformar C++ general. Solo generan variantes controladas para medir regresiones sobre estructuras de datos conocidas.

#### Casos de desafío

El corpus no debe estar ajustado para producir resultados perfectos. Por eso incluye casos de desafío:

```text
challenge_correct = código correcto que puede activar falsos positivos
challenge_buggy   = código defectuoso que puede exponer falsos negativos
```

Estos casos hacen visible el estado real del analizador. Si aparecen falsos positivos o falsos negativos, el benchmark no debe ocultarlos. El objetivo de la Fase 10 es medir, no maquillar resultados.

#### Umbrales iniciales

`benchmarks/thresholds.yml` define valores conservadores:

```yaml
precision: 0.80
recall: 0.85
false_positive_rate: 0.20
analysis_time_ms_per_file: 5000
mutation_detection_rate: 0.60
```

Por defecto, el benchmark solo reporta esos umbrales. Para hacer que el comando falle si no se alcanzan, usa:

```bash
python benchmarks/run_benchmark.py --fail-on-threshold
```

#### Resultados no perfectos

Un resultado `precision = 1.0` y `recall = 1.0` puede ser válido para un corpus muy pequeño, pero no es una señal suficiente de robustez. El benchmark inicial debe incluir casos que permitan observar limitaciones actuales.

La línea base esperada puede tener algunos falsos positivos o falsos negativos. Eso es aceptable si quedan registrados en `artifacts/benchmark-report.json` y si el proyecto puede comparar fases futuras contra esa línea base.

#### Criterio de aceptación de la Fase 10

La fase queda completa si:

```text
existe un corpus correcto y uno defectuoso
existen casos de desafío para falsos positivos y falsos negativos
existe ground_truth.yaml
existe un runner reproducible
se genera artifacts/benchmark-report.json
se calculan precision, recall, falsos positivos, falsos negativos y mutation_detection_rate
la corrida puede ejecutarse dentro del entorno struct_guard
```

#### Limitaciones

El benchmark inicial es pequeño. No debe interpretarse como evaluación completa del analizador.

Limitaciones conocidas:

```text
el corpus está orientado a estructuras de datos pequeñas
las mutaciones son textuales y controladas
no mide cobertura de ramas C++ real
no ejecuta binarios
no reemplaza fuzzing nativo ni sanitizers
```

La cobertura de ejecución real queda para fases posteriores.
