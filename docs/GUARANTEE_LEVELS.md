### Niveles de garantía de StructGuard

#### Propósito

StructGuard distingue severidad y garantía.

La severidad responde a la pregunta:

```text
¿Qué tan grave es el hallazgo?
```

El nivel de garantía responde a la pregunta:

```text
¿Qué tipo de evidencia produjo este hallazgo?
```

Esta separación evita que un resultado heurístico, estructural o acotado se comunique como verificación formal.

#### G1 - Heurístico

Resultado basado en patrones, nombres, tokens, convenciones o señales incompletas.

Ejemplos:

```text
señales de seguridad aproximadas
generación abstracta de secuencias testgen
sugerencias de documentación o asistencia
pistas de rendimiento estático
```

Un hallazgo G1 puede ser útil, pero no prueba que el programa sea correcto o incorrecto.

#### G2 - Estructural

Resultado derivado de una representación estructural del código o de contratos.

Ejemplos:

```text
SourceIR
ContractIR
BindingIR
reglas SG-* documentadas
validación de política YAML
binding entre contrato y símbolo fuente
```

Un hallazgo G2 es más estable que una señal heurística, pero sigue dependiendo de la cobertura del frontend y del modelo estructural usado.

#### G3 - Acotado

Resultado obtenido dentro de límites finitos.

Ejemplos:

```text
búsqueda acotada de contraejemplos
chequeo finito de precondiciones
chequeo finito de postcondiciones
chequeo finito de invariantes
```

El estado visible para un chequeo acotado exitoso es:

```text
BOUNDED_CHECK_PASSED
```

Eso significa que StructGuard no encontró un contraejemplo dentro de los límites configurados. No equivale a prueba formal para todas las ejecuciones C++.

#### G4 - Ejecutado

Resultado observado mediante ejecución real.

Ejemplos futuros:

```text
tests generados y compilados
harness C++ ejecutado
fuzzing nativo con sanitizers
replay reproducible de una falla ejecutada
```

StructGuard reserva este nivel para ejecuciones reales. La generación abstracta de secuencias no debe llamarse fuzzing nativo.

#### G5 - Formalmente verificado

Resultado descargado por un backend formal soportado sobre un modelo explícito.

Ejemplos futuros o experimentales:

```text
Dafny
Why3
Viper
Prusti
SMT sobre modelo soportado
```

El estado visible asociado es:

```text
FORMALLY_VERIFIED
```

Este nivel no significa que StructGuard verificó cualquier programa C++ arbitrario. Solo significa que el backend formal descargó una obligación sobre el modelo generado y dentro del subconjunto soportado.

#### Regla de comunicación

StructGuard no debe usar palabras como:

```text
verified
proved
formalmente verificado
```

para resultados heurísticos, estructurales o acotados.

La regla práctica es:

```text
G1, G2 y G3 pueden orientar decisiones.
G4 puede reportar comportamiento observado.
G5 puede comunicar verificación formal del modelo soportado.
```

#### Estados internos y estados visibles

Por compatibilidad histórica, algunos módulos pueden conservar estados internos antiguos.

La interfaz debe mostrar:

```text
BOUNDED_VERIFIED -> BOUNDED_CHECK_PASSED
PROVED -> FORMALLY_VERIFIED
```

El objetivo es preservar compatibilidad de datos mientras se evita falsa confianza en CLI, HTML, Markdown, SARIF y FindingIR.

#### Reportes

Todo FindingIR debe incluir:

```json
{
  "guarantee": {
    "level": "G2_STRUCTURAL",
    "label": "Estructural",
    "description": "Resultado derivado de SourceIR, ContractIR, BindingIR o reglas estructurales documentadas."
  }
}
```

Los reportes deben mostrar resumen por nivel de garantía, por ejemplo:

```text
G1_HEURISTIC: 2
G2_STRUCTURAL: 5
G3_BOUNDED: 1
G4_EXECUTED: 0
G5_FORMALLY_VERIFIED: 0
```
