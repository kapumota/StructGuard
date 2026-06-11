### Política YAML validada

#### Propósito

`structguard.yml` define cómo se ejecuta StructGuard en un repositorio. A partir de la Fase 7, la política tiene un esquema estricto: las claves desconocidas fallan durante la validación.

Esto evita errores silenciosos. Por ejemplo, una clave mal escrita como `deep-secuirty` ya no se ignora.

#### Comando principal

```bash
structguard policy validate structguard.yml
```

Salida esperada para una política válida:

```text
Política válida: structguard.yml
```

Salida esperada para una clave desconocida:

```text
Política inválida: structguard.yml
[FAILED] POLICY_UNKNOWN_KEY deep-secuirty
  Clave desconocida: deep-secuirty. Quizá quiso decir deep-security.
```

#### Ejemplo mínimo recomendado

```yaml
version: 1

profile: generic-cpp

frontend:
  cpp:
    primary: clang
    fallback_allowed: false

rules:
  SG-CONTRACT-MISSING-PRECONDITION:
    severity: error
  SG-BOUNDS-POSSIBLE-OVERFLOW:
    severity: warning

outputs:
  sarif: true
  junit: true
  html: true
```

#### Claves principales

```text
version
project
profile
paths
scan
frontend
verification
lint
security
fuzz
thresholds
clang
ci
report
outputs
rules
dsl
formal
pipeline
frontends
assist
advanced
docs
```

#### Frontend C++

```yaml
frontend:
  cpp:
    primary: clang
    fallback: lightweight
    fallback_allowed: false
    std: c++17
```

En CI se recomienda:

```yaml
fallback_allowed: false
```

De esa manera, el frontend ligero no reemplaza silenciosamente a Clang.

#### Reglas

La sección `rules` permite configurar reglas por identificador:

```yaml
rules:
  SG-CONTRACT-MISSING-PRECONDITION:
    severity: error
    enabled: true
  SG-BOUNDS-POSSIBLE-OVERFLOW:
    severity: warning
```

Cada regla puede usar:

```text
severity
confidence
enabled
cwe
tags
remediation
description
```

#### Salidas

La sección `outputs` controla reportes nuevos o integraciones:

```yaml
outputs:
  sarif: true
  junit: true
  html: true
  json: true
  markdown: false
```

#### Relación con la política heredada

StructGuard conserva compatibilidad con la política heredada usada por `structguard ci`. La validación estricta agrega una capa previa para detectar claves mal escritas antes de ejecutar el análisis.

#### Limitaciones actuales

Esta fase valida la estructura de claves. No valida todavía todos los tipos profundos ni reglas de consistencia entre secciones. Esas comprobaciones pueden incorporarse en fases posteriores.
