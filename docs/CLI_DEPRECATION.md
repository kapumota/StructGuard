### Deprecación controlada del CLI

#### Objetivo

La Fase 15 centraliza la política de comandos heredados de StructGuard.

El objetivo no es eliminar comandos de inmediato. La meta es reducir deuda técnica del CLI sin romper usuarios actuales, scripts docentes, demos históricas o workflows existentes.

Esta fase define para cada comando heredado una decisión explícita:

```text
mantener
migrar
deprecar
eliminar después
```

#### Principio de migración

Las nuevas capacidades deben integrarse primero en los flujos canónicos:

```text
scan --preset
policy
report
testgen
benchmark de regresión
```

Los comandos heredados pueden seguir existiendo como alias temporales, pero deben mostrar un aviso claro cuando exista un reemplazo recomendado.

#### Comandos revisados

```text
verify
lint
security
perf
ci
bench
assist
advanced
clang
formal
fuzz
```

#### Tabla de decisiones

| Comando | Decisión | Reemplazo o estado recomendado | Criterio de retiro |
|---|---|---|---|
| `verify` | migrar | `scan --preset contracts` | Después de migrar pruebas, ejemplos y documentación activa |
| `lint` | migrar | `scan --preset contracts` | Después de migrar pruebas, ejemplos y documentación activa |
| `security` | migrar | `scan --preset security` | Después de validar equivalencia de reportes de seguridad |
| `perf` | mantener | Mantener como reporte especializado de rendimiento | Sin eliminación programada |
| `ci` | migrar | `scan --preset ci` y workflows de CI | Después de migrar gates locales y documentación principal |
| `bench` | migrar | `python benchmarks/run_benchmark.py` | Después de estabilizar un comando `benchmark` canónico |
| `assist` | deprecar | Reportes canónicos y futuras recomendaciones derivadas de FindingIR | Después de retirar referencias en demos y README |
| `advanced` | deprecar | Perfiles y contratos SGDSL documentados | Después de migrar plantillas útiles a `profiles/` y `docs/` |
| `clang` | migrar | `scan --language cpp --frontend clang --compile-commands ...` | Después de validar el frontend Clang dentro de `scan` |
| `formal` | mantener | Mantener como backend formal experimental | Sin eliminación programada antes de estabilizar exportadores formales |
| `fuzz` | deprecar | `testgen` | Después de retirar referencias activas a `fuzz` como flujo principal |

#### Comandos que migran hacia scan

Los siguientes comandos deben converger hacia `scan`:

```text
verify
lint
security
ci
clang
```

Equivalencias recomendadas:

```text
verify   -> scan --preset contracts
lint     -> scan --preset contracts
security -> scan --preset security
ci       -> scan --preset ci
clang    -> scan --language cpp --frontend clang --compile-commands ...
```

La migración debe hacerse sin eliminar los comandos históricos hasta que sus pruebas, ejemplos y referencias activas hayan sido actualizadas.

#### Comandos que se mantienen temporalmente

Los siguientes comandos se mantienen porque todavía representan capacidades especializadas o experimentales:

```text
perf
formal
```

`perf` conserva reportes y harnesses de rendimiento que aún no pertenecen al benchmark de regresión.

`formal` se mantiene como flujo experimental para exportadores formales. No debe comunicar `FORMALLY_VERIFIED` salvo que un backend formal soportado descargue efectivamente una obligación.

#### Comandos deprecados

Los siguientes comandos deben considerarse deprecados:

```text
assist
advanced
fuzz
```

`assist` y `advanced` pertenecen a una etapa histórica de recomendaciones y plantillas heurísticas.

`fuzz` no debe presentarse como fuzzing nativo. En StructGuard, el flujo correcto para generación abstracta de casos de prueba es:

```bash
structguard testgen ...
```

#### Diferencia entre testgen y fuzzing nativo

`testgen` significa generación abstracta o guiada por contratos.

Puede usar contratos, reglas, perfiles, hallazgos y modelos internos para proponer casos candidatos.

No ejecuta binarios reales.

No usa sanitizers.

No instrumenta código.

No integra motores como libFuzzer o AFL++.

Por eso el término `fuzz` queda reservado para compatibilidad histórica y no debe usarse como nombre principal del flujo nuevo.

#### Comando de inspección

La tabla de decisiones debe poder consultarse desde la CLI:

```bash
structguard legacy list
```

La salida debe mostrar, como mínimo:

```text
comando
decisión
reemplazo
criterio de retiro
```

#### Política de avisos

Los comandos heredados deben mostrar un aviso cuando se ejecutan.

El aviso debe indicar:

```text
comando heredado
decisión
reemplazo o estado recomendado
criterio de retiro
```

Ejemplo esperado para `fuzz`:

```text
Advertencia legacy: el comando 'fuzz' tiene decisión 'deprecar'. Reemplazo o estado recomendado: testgen.
```

#### Criterio para eliminar un comando heredado

Un comando heredado solo puede eliminarse cuando se cumplan todas estas condiciones:

```text
tiene reemplazo documentado
sus pruebas fueron migradas
no aparece en demos activas
no aparece en documentación principal
no rompe workflows de CI
no es necesario para reproducir fases anteriores
```

#### Relación con fases anteriores

La Fase 15 depende de decisiones tomadas antes:

```text
Fase 5  - scan --preset como flujo modular
Fase 6  - FindingIR como modelo común de hallazgos
Fase 9.6 - niveles de garantía para evitar falsas promesas
Fase 10 - benchmark de regresión
Fase 11 - report.json como fuente canónica
Fase 13 - testgen como reemplazo correcto de fuzz
Fase 14 - CI con gates medibles
```

#### Alcance de esta fase

Esta fase no elimina comandos.

Esta fase no cambia la semántica de los analizadores.

Esta fase no agrega fuzzing nativo.

Esta fase agrega:

```text
registro de decisiones legacy
avisos de compatibilidad
documentación de reemplazos
base para migración futura
```

#### Resultado esperado

Al final de la Fase 15, cada comando heredado debe tener una decisión explícita y verificable.

El CLI puede seguir siendo compatible con usuarios actuales, pero la evolución futura debe ocurrir sobre los flujos canónicos.
