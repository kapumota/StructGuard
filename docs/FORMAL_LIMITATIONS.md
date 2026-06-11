### Formal Limitations

#### Proposito

Este documento define lo que StructGuard puede y no puede afirmar sobre correccion, analisis acotado y exportacion formal.

#### Analisis acotado

Cuando StructGuard reporta `BOUNDED_VERIFIED`, el significado correcto es:

```text
No se encontro una violacion dentro del modelo acotado usado por StructGuard.
```

No significa:

```text
El programa C++ es correcto para todos los casos posibles.
```

#### Cotas que deben documentarse en fases posteriores

Las fases siguientes deben hacer explicitas estas cotas:

- tamano maximo de secuencias de operaciones
- rango de enteros modelado
- profundidad maxima de llamadas o trazas
- numero maximo de archivos analizados
- operaciones soportadas por estructura
- restricciones del frontend usado

#### Clang y confianza sintactica

El modo estricto basado en Clang debe entenderse como compuerta de confianza sintactica y estructural. Si Clang no puede parsear el codigo, StructGuard no debe presentar resultados heurisiticos como si fueran equivalentes a un AST real de C++.

#### Exportacion formal

La exportacion formal debe reportar estados honestos:

```text
UNSUPPORTED
GENERATED
PARSED
CHECKED
VERIFIED
UNKNOWN
FAILED
```

Un archivo generado para Dafny, Prusti, Why3 o Viper no debe considerarse verificado hasta que el backend correspondiente lo confirme.

#### Z3 y solvers opcionales

Si un solver opcional no esta instalado, StructGuard debe emitir un estado `UNKNOWN` o `UNSUPPORTED`, no un resultado ambiguo.

#### Frase recomendada

StructGuard exporta modelos verificables para subconjuntos soportados.

#### Frase que debe evitarse

StructGuard verifica formalmente cualquier codigo C++.

#### Relacion con otras herramientas

StructGuard no reemplaza:

- compiladores C++
- sanitizers
- pruebas unitarias
- fuzzing nativo
- verificadores deductivos
- analizadores estaticos industriales

StructGuard puede complementar esas herramientas al organizar contratos, evidencia y reportes en un flujo reproducible.
