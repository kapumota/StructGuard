### Frontend C++ canónico con Clang

#### Propósito

El frontend C++ de StructGuard usa Clang como fuente principal de verdad para proyectos C++. Esta fase corrige el problema de tener un frontend ligero y un frontend Clang sin una representación común.

El resultado del frontend canónico es `SourceIR`, una representación interna de archivos, estructuras, campos, métodos, namespaces, includes y diagnósticos de parseo.

```text
C++ source
  |
  v
Clang AST JSON
  |
  v
SourceIR
  |
  v
BindingIR / ContractIR / AnalysisEngine
```

#### Relación con el frontend ligero

El frontend ligero se conserva por compatibilidad, demos rápidas y entornos educativos sin Clang.

No debe interpretarse como fuente semántica completa. Su rol correcto es:

```text
fast-scan
fallback educativo
modo sin garantías semánticas completas
```

En CI se recomienda no permitir fallback:

```yaml
frontend:
  cpp:
    primary: clang
    fallback: lightweight
    fallback_allowed: false
```

#### Uso con compile_commands.json

Ejemplo:

```bash
structguard scan examples/cpp_projects \
  --language cpp \
  --compile-commands examples/cpp_projects/build/compile_commands.json \
  --profile generic-cpp
```

Para guardar SourceIR:

```bash
structguard scan examples/cpp_projects \
  --language cpp \
  --compile-commands examples/cpp_projects/build/compile_commands.json \
  --profile generic-cpp \
  --source-ir-json artifacts/source-ir.json
```

#### Uso con binding de contratos

```bash
structguard contract bind examples/cpp_projects \
  --contract profiles/generic-cpp/contracts/stack.sgdsl \
  --language cpp \
  --compile-commands examples/cpp_projects/build/compile_commands.json
```

#### Fallback explícito

Si el entorno no tiene Clang, se puede permitir fallback de forma explícita:

```bash
structguard scan examples/cpp_projects \
  --language cpp \
  --frontend clang \
  --fallback-allowed \
  --profile generic-cpp
```

Si Clang falla y `--fallback-allowed` no está activo, StructGuard emite un diagnóstico `CPP_CLANG_PARSE_FAILED`.

#### Alcance inicial

Esta fase soporta:

```text
headers .h / .hpp
C++17/C++20 mediante --std
namespaces
clases
structs
métodos
campos
templates simples
múltiples archivos
compile_commands.json
includes del proyecto
```

#### Limitaciones

Esta fase no intenta verificar todavía la semántica completa del cuerpo de los métodos. Tampoco resuelve macros complejas, especializaciones avanzadas de templates ni aliasing de memoria.

Esas capacidades deben aparecer en fases posteriores mediante BindingIR, modelo de memoria, análisis estructural y exportadores formales.
