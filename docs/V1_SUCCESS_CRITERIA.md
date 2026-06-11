### Criterios de éxito para StructGuard v1.x

#### Propósito

Este documento define cuándo StructGuard v1.x puede considerarse estable como herramienta educativa robusta con núcleo de análisis serio.

#### Criterios para v1.0

StructGuard v1.0 se considera exitoso cuando cumple estos criterios:

```text
1. Todo finding muestra nivel de garantía en CLI, JSON, HTML, Markdown y SARIF.
2. El estado BOUNDED_CHECK_PASSED no se comunica como verificación formal.
3. El reporte canónico puede incluir guarantee_counts por ejecución.
4. El corpus de benchmark existe y reporta precision >= 0.80 y recall >= 0.85.
5. El CI ejecuta tests, lint, typing, policy validate y benchmark report.
6. Los comandos heredados están inventariados o muestran advertencias de compatibilidad.
7. Los reportes derivados no pierden información de garantía.
```

#### Criterios para v1.1

StructGuard v1.1 debe agregar criterios de eficiencia y utilidad:

```text
1. El cache incremental reduce el tiempo de análisis en >= 50% para cambios menores.
2. El cache documenta su política de invalidación por archivo, contrato, perfil y flags.
3. testgen genera pruebas que detectan >= 70% de bugs del corpus diseñado para generación.
4. benchmark gate bloquea regresiones bajo thresholds.yml cuando el baseline esté estabilizado.
5. El backend Dafny experimental verifica modelos abstractos simples definidos en su matriz de soporte.
```

#### Fuera de alcance para v1.x

Estos objetivos quedan diferidos para v2.x o investigación posterior:

```text
fuzzing nativo real con libFuzzer o AFL++
verificación formal de C++ arbitrario
soporte multi-lenguaje de producción
modelos completos de STL
análisis interprocedural profundo
varios backends formales simultáneos
```

#### Principio operativo

La evolución de StructGuard debe priorizar:

```text
medición antes que nuevas features
niveles de garantía antes que lenguaje visual optimista
un backend formal bien soportado antes que varios backends incompletos
report.json canónico antes que evidence packs grandes
```
