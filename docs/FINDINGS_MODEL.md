### Modelo FindingIR

#### Objetivo

FindingIR es el modelo común de hallazgos de StructGuard. Su propósito es separar la lógica de análisis de los formatos de salida.

Antes de esta fase, los diagnósticos podían llegar directamente a reportes JSON, HTML, JUnit o SARIF. Eso hacía que cada formato conociera detalles internos de los analizadores.

Desde esta fase, el flujo recomendado es:

```text
Analyzer
  |
  v
Diagnostic
  |
  v
FindingIR
  |
  v
Reporters
```

#### Modelo

Cada hallazgo se representa con estos campos:

```python
Finding(
    rule_id: str,
    title: str,
    message: str,
    severity: str,
    confidence: str,
    location: Location,
    symbol: str,
    evidence: list[str],
    remediation: str,
    cwe: str | None,
    tags: list[str],
)
```

#### Severidad

FindingIR usa severidades estables para reportes externos:

```text
error
warning
note
info
```

La conversión inicial desde niveles internos es:

```text
FAILED           -> error
WARNING          -> warning
UNKNOWN          -> warning
HEURISTIC        -> note
BOUNDED_VERIFIED -> note
PROVED           -> note
INFO             -> info
```

#### Reporters

Los reporters consumen `ProjectReport` y convierten sus diagnósticos a FindingIR. Agregar un nuevo reporter no debe modificar el motor de análisis.

Reporters agregados:

```text
src/structguard/reporters/json_reporter.py
src/structguard/reporters/html_reporter.py
src/structguard/reporters/markdown_reporter.py
src/structguard/reporters/junit_reporter.py
src/structguard/reporters/sarif_reporter.py
```

#### CLI

Los comandos que usan las opciones comunes pueden escribir FindingIR con:

```bash
structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset ci \
  --contract profiles/generic-cpp/contracts/stack.sgdsl \
  --findings-json artifacts/findings.json
```

Otros formatos:

```bash
--findings-html artifacts/findings.html
--findings-md artifacts/findings.md
--findings-junit artifacts/findings.xml
--findings-sarif artifacts/findings.sarif
```

#### Alcance actual

Esta fase no elimina los reportes heredados. Los deja funcionando para compatibilidad.

El cambio importante es que los nuevos reportes quedan desacoplados del motor y consumen FindingIR como modelo intermedio.
