### Motor de análisis modular

#### Objetivo

El motor de análisis modular separa la lógica de análisis del CLI. El comando `structguard scan` deja de ser una combinación directa de comandos internos y pasa a ejecutar un pipeline controlado por presets.

La pieza central es:

```text
AnalysisContext -> AnalysisEngine -> PassManager -> AnalysisEngineResult
```

#### Componentes

```text
src/structguard/core/analysis_context.py
src/structguard/core/analysis_engine.py
src/structguard/core/pass_manager.py
src/structguard/core/capabilities.py
src/structguard/core/result.py
```

#### Flujo conceptual

```text
LoadProfile
BuildSourceIR
BuildContractIR
BindContracts
RunBoundedContracts
RunLint
RunSecurity
RunFormal
```

No todos los pasos se ejecutan siempre. El preset decide qué capacidades se activan. Si no se indica `--preset`, `scan` usa `source` para evitar que una exploración inicial falle por contratos de dominio todavía no vinculados al código analizado.

#### Presets

```text
source     = construye SourceIR y diagnósticos del frontend
contracts  = valida contratos, binding, verificación acotada y lint
security   = ejecuta seguridad estructural usando el motor común
ci         = ejecuta contratos, lint y seguridad para integración continua
full       = ejecuta el conjunto más amplio disponible
```

#### Comandos

```bash
structguard scan examples/cpp_projects \
  --language cpp \
  --compile-commands examples/cpp_projects/compile_commands.json \
  --profile generic-cpp \
  --preset source
```

```bash
structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset contracts
```

```bash
structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset security
```

```bash
structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset ci
```

#### Compatibilidad

Los comandos antiguos siguen disponibles:

```text
verify
lint
security
perf
ci
fuzz
```

Sin embargo, el flujo nuevo recomendado es usar `scan --preset ...`. En fases posteriores, esos comandos pueden quedar como alias o presets más delgados sobre el motor.

#### Estado actual

Esta fase introduce el motor común y conecta `scan` con presets. No elimina todavía los comandos antiguos para evitar romper flujos existentes.

#### Limitaciones

El motor todavía reutiliza analizadores existentes como `verify_project`, `lint_project` y `security_project`. La separación completa de reglas, findings y reportes corresponde a las fases siguientes.

### Alcance explícito de contratos

Cuando un perfil contiene varios contratos, `scan --preset ci` valida todos los contratos del perfil.
Esto es correcto para un proyecto completo, pero puede ser demasiado estricto para ejemplos parciales.

Para analizar solo una estructura, se puede delimitar el alcance con `--contract`:

```bash
structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset ci \
  --contract profiles/generic-cpp/contracts/stack.sgdsl
```

En este modo, el perfil sigue aportando configuración de dominio, pero los contratos cargados son solo los indicados explícitamente.
Esto evita que un ejemplo parcial de `Stack` falle por contratos de `Queue` o `Vector` que pertenecen al mismo perfil general.
