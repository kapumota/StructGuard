### StructGuard

**StructGuard** es una plataforma de línea de comandos para revisar implementaciones de estructuras de datos mediante contratos, análisis acotado, evidencia reproducible y exportación formal experimental. Está pensada para apoyar cursos, proyectos académicos y librerías C++ propias donde se implementan pilas, colas, vectores, deques, árboles, heaps, hashing, grafos y estructuras similares.

StructGuard no está limitado a CC-232. CC-232 es el primer perfil académico. El motor puede analizar otras librerías C++, otros cursos y, progresivamente, otros lenguajes mediante perfiles, contratos, frontends y exportadores.

Su objetivo no es reemplazar al compilador ni demostrar matemáticamente todo un programa C++; su valor está en combinar análisis acotado, lint de contratos, documentación automática, señales de seguridad, perfiles de rendimiento y artefactos para CI.

#### Fase 0: reposicionamiento del producto

La Fase 0 separa el producto en cuatro conceptos:

```text
StructGuard Core     = motor general de análisis y evidencia
Profiles            = reglas, contratos y presets por dominio
CC-232 Profile       = perfil educativo inicial
Generic C++ Profile  = perfil general para librerías C++ propias
STL Adapters         = adaptadores para librerías externas
```

Documentación nueva de esta fase:

- `docs/PRODUCT_VISION.md`
- `docs/ARCHITECTURE.md`
- `docs/FORMAL_LIMITATIONS.md`
- `docs/PROFILE_MODEL.md`

Perfiles base agregados:

- `profiles/cc232/`
- `profiles/generic-cpp/`
- `profiles/stl-adapters/`
- `profiles/custom-template/`

#### Fase 1: sistema de perfiles real

La Fase 1 convierte esos perfiles en entradas reales de la CLI. Ahora se pueden listar, validar y aplicar perfiles de dominio sin pasar manualmente todos los contratos base.

```bash
structguard profiles list
structguard profiles validate profiles/generic-cpp/profile.yml
structguard scan examples/generic_cpp --profile generic-cpp
```

`scan` es un alias operativo de `analyze` orientado al flujo nuevo. Los comandos antiguos siguen disponibles para mantener compatibilidad.

#### Fase 2: SGDSL estable y ContractIR

La Fase 2 agrega un parser SGDSL estable, un AST explícito, ContractIR y validadores semánticos iniciales. El flujo nuevo permite validar contratos antes de conectarlos con analizadores, exportadores formales o perfiles de dominio.

```bash
structguard contract check profiles/generic-cpp/contracts/stack.sgdsl
structguard contract dump-ir profiles/generic-cpp/contracts/stack.sgdsl --json
```

Esta fase no enlaza todavía contratos con código C++ real. Ese enlace corresponde a la Fase 3 con BindingIR.

Documentación nueva de esta fase:

- `docs/SGDSL_SPEC.md`

Módulos nuevos:

- `src/structguard/sgdsl/`
- `src/structguard/ir/contract_ir.py`
- `src/structguard/ir/contract_validator.py`

#### Fase 3: binding entre contrato y código fuente

La Fase 3 agrega una validación explícita entre contratos externos SGDSL y símbolos reales del código fuente.

```bash
structguard contract bind examples/generic_cpp \
  --contract profiles/generic-cpp/contracts/stack.sgdsl
```

Esta fase introduce `BindingIR`, tabla de símbolos fuente, resolución de nombres y detección de contratos huérfanos. Si un contrato declara un método que ya no existe en el código, StructGuard emite `BINDING_ORPHAN_METHOD` en lugar de ignorarlo.

Documentación nueva de esta fase:

- `docs/CONTRACT_BINDING.md`

Módulos nuevos:

- `src/structguard/binding/`


#### Fase 4: frontend C++ canónico con Clang

La Fase 4 introduce `SourceIR` y un frontend C++ canónico basado en Clang. Clang pasa a ser la fuente principal de verdad para proyectos C++ cuando se usa `--language cpp` con `--compile-commands`.

```bash
structguard scan examples/cpp_projects \
  --language cpp \
  --compile-commands examples/cpp_projects/compile_commands.json \
  --profile generic-cpp
```

También se puede guardar la representación interna del código fuente:

```bash
structguard scan examples/cpp_projects \
  --language cpp \
  --compile-commands examples/cpp_projects/compile_commands.json \
  --profile generic-cpp \
  --source-ir-json artifacts/source-ir.json
```

El frontend ligero se conserva solo como modo rápido y fallback educativo. En CI se recomienda no permitir fallback para evitar resultados con garantías semánticas más débiles.

Documentación nueva de esta fase:

- `docs/CPP_FRONTEND.md`

Módulos nuevos:

- `src/structguard/frontend/cpp/`
- `src/structguard/ir/source_ir.py`

Ejemplo nuevo:

- `examples/cpp_projects/`

#### Fase 5: motor de análisis modular

La Fase 5 introduce un motor común para `scan`. El CLI deja de decidir directamente qué módulos ejecutar y pasa a delegar en `AnalysisEngine`, `AnalysisContext` y `PassManager`.

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

Los comandos antiguos siguen disponibles por compatibilidad, pero el flujo recomendado para nuevas fases es `scan --preset ...`. Si no se indica `--preset`, `scan` usa el modo `source` como exploración inicial no bloqueante.

Documentación nueva de esta fase:

- `docs/ANALYSIS_ENGINE.md`

Módulos nuevos:

- `src/structguard/core/analysis_engine.py`
- `src/structguard/core/analysis_context.py`
- `src/structguard/core/pass_manager.py`
- `src/structguard/core/capabilities.py`
- `src/structguard/core/result.py`

#### Fase 6: FindingIR y reportes desacoplados

La Fase 6 agrega un modelo común de hallazgos. Los analizadores pueden seguir emitiendo diagnósticos internos, pero los reportes nuevos consumen `FindingIR` como capa intermedia estable.

```bash
structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset ci \
  --contract profiles/generic-cpp/contracts/stack.sgdsl \
  --findings-json artifacts/findings.json
```

También se pueden generar reportes desacoplados en HTML, Markdown, JUnit y SARIF:

```bash
--findings-html artifacts/findings.html
--findings-md artifacts/findings.md
--findings-junit artifacts/findings.xml
--findings-sarif artifacts/findings.sarif
```

Documentación nueva de esta fase:

- `docs/FINDINGS_MODEL.md`

Módulos nuevos:

- `src/structguard/findings/`
- `src/structguard/reporters/json_reporter.py`
- `src/structguard/reporters/html_reporter.py`
- `src/structguard/reporters/markdown_reporter.py`
- `src/structguard/reporters/junit_reporter.py`
- `src/structguard/reporters/sarif_reporter.py`


#### Fase 7: política YAML validada

La Fase 7 agrega validación estricta para `structguard.yml`.

El objetivo de esta fase es evitar configuraciones ambiguas, claves mal escritas o campos ignorados silenciosamente. A partir de esta fase, StructGuard puede validar la política del proyecto antes de ejecutar análisis, reportes o flujos de CI.

#### Comando principal

```bash
structguard policy validate structguard.yml
```

#### Ejemplo de error esperado

```text
Política inválida: structguard.yml
[FAILED] POLICY_UNKNOWN_KEY deep-secuirty
  Clave desconocida: deep-secuirty. Quizá quiso decir deep-security.
```

#### Archivos principales

```text
src/structguard/policy/
schemas/structguard-policy.schema.json
docs/POLICY_REFERENCE.md
structguard.yml
```

#### Alcance

Esta fase no agrega nuevos analizadores. Su función es asegurar que la configuración usada por StructGuard sea explícita, validada y reproducible.

La validación de política es especialmente importante para fases posteriores, porque evita que presets, perfiles, contratos o reglas se ejecuten con opciones mal escritas o parcialmente ignoradas.

#### Resultado

Con esta fase, StructGuard diferencia entre:

```text
configuración válida
configuración inválida
claves desconocidas
valores fuera de esquema
opciones no soportadas
```

Esto reduce errores silenciosos y prepara el proyecto para flujos más reproducibles de benchmark, reportes, cache y CI.

#### Fase 8: modelo de memoria mínimo para C++

La Fase 8 agrega un modelo inicial de memoria para estructuras de datos C++. No intenta verificar todo C++, pero sí distingue patrones básicos de ownership manual.

El análisis reconoce:

```text
new / delete
new[] / delete[]
nullptr
campos puntero
arreglos dinámicos
capacidad lógica vs. capacidad física
riesgos simples de double delete y null dereference
```

El modelo se ejecuta desde presets que incluyen seguridad:

```bash
structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset security
```

También se ejecuta en:

```bash
structguard scan . --preset ci
structguard scan . --preset full
```

Documentación nueva de esta fase:

- `docs/MEMORY_MODEL.md`

Módulos nuevos:

- `src/structguard/memory/model.py`
- `src/structguard/memory/ownership.py`
- `src/structguard/memory/aliasing.py`
- `src/structguard/analyzers/memory_safety.py`

#### Fase 9: análisis estructural por contratos

La Fase 9 convierte reglas educativas en análisis estructural configurable. El objetivo es que las reglas iniciales tengan identificador estable, descripción, severidad por defecto, ejemplos, perfiles aplicables y CWE cuando corresponde.

Reglas iniciales:

```text
SG-CONTRACT-MISSING-PRECONDITION
SG-STACK-POP-EMPTY
SG-QUEUE-FIFO-VIOLATION
SG-BOUNDS-INDEX-RISK
SG-SIZE-NOT-UPDATED
SG-HEAP-PROPERTY-RISK
SG-BST-ORDER-RISK
SG-NULL-DEREFERENCE-RISK
SG-MEMORY-OWNERSHIP-RISK
```

Ejemplo:

```bash
structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset security
```

Documentación nueva de esta fase:

- `docs/RULES_REFERENCE.md`

Módulos nuevos o ampliados:

- `src/structguard/analyzers/contracts.py`
- `src/structguard/analyzers/bounds.py`
- `src/structguard/analyzers/structure_semantics.py`
- `src/structguard/analyzers/memory_safety.py`
- `src/structguard/analyzers/complexity_hints.py`

#### Fase 9.5: inventario de scripts y módulos heredados

La Fase 9.5 agrega una limpieza no destructiva antes de continuar con corpus, benchmark, reporte canónico, evidencia mínima y cache incremental. No elimina scripts ni módulos heredados, pero documenta cuáles siguen activos, cuáles son candidatos a migración y cuáles deben revisarse antes de retirarse.

Documentación nueva de esta fase:

- `docs/SCRIPTS_INVENTORY.md`
- `docs/LEGACY_MODULES.md`

Decisión principal:

```text
No se eliminan scripts ni módulos de src/structguard en esta fase.
Se documenta su estado para evitar romper CLI, pruebas o demos antes de migrarlos.
```

Esta fase prepara el camino para la Fase 10, donde el corpus y los benchmarks deben medir comandos y artefactos sin arrastrar ambigüedad sobre scripts antiguos.

#### Fase 9.6: niveles de garantía y semántica visual

La Fase 9.6 agrega una taxonomía explícita de garantías para evitar que resultados heurísticos o acotados se comuniquen como verificación formal.

StructGuard ahora distingue severidad y garantía:

```text
severidad = gravedad del hallazgo
garantía = tipo de evidencia que produjo el hallazgo
```

Niveles definidos:

```text
G1_HEURISTIC          = señal heurística
G2_STRUCTURAL         = regla estructural sobre IR o contratos
G3_BOUNDED            = chequeo acotado
G4_EXECUTED           = resultado observado por ejecución real
G5_FORMALLY_VERIFIED  = obligación descargada por backend formal soportado
```

Los reportes FindingIR, HTML, Markdown, JUnit, SARIF y la CLI muestran el nivel de garantía asociado a cada hallazgo.

Estados visibles nuevos:

```text
BOUNDED_VERIFIED -> BOUNDED_CHECK_PASSED
PROVED           -> FORMALLY_VERIFIED
```

Los nombres antiguos se conservan internamente solo como compatibilidad histórica. La interfaz debe evitar que un chequeo acotado parezca una prueba formal.

Documentación nueva de esta fase:

- `docs/GUARANTEE_LEVELS.md`
- `docs/V1_SUCCESS_CRITERIA.md`

Módulos nuevos:

- `src/structguard/findings/guarantee.py`
- `src/structguard/reporters/guarantee_badge.py`

Esta fase deja preparado el terreno para la Fase 10, donde el corpus y los benchmarks podrán medir resultados con niveles de garantía claros.

#### Comandos recomendados y comandos heredados

StructGuard conserva comandos heredados por compatibilidad, pero el flujo recomendado para nuevas fases es usar `scan --preset`.

El objetivo es evitar que el CLI crezca con comandos duplicados y reducir la deuda técnica de mantenimiento. Los comandos antiguos seguirán disponibles durante una etapa de transición, pero las nuevas funcionalidades deben integrarse primero en el motor modular y en los presets de `scan`.

#### Flujo recomendado

```bash
structguard scan . --preset source
structguard scan . --preset contracts
structguard scan . --preset security
structguard scan . --preset ci
structguard scan . --preset full
```

#### Tabla de migración

| Comando heredado | Reemplazo recomendado                        | Estado                 |
| ---------------- | -------------------------------------------- | ---------------------- |
| `analyze`        | `scan --preset contracts`                    | Compatibilidad         |
| `verify`         | `scan --preset contracts`                    | Compatibilidad         |
| `lint`           | `scan --preset contracts`                    | Compatibilidad         |
| `security`       | `scan --preset security`                     | Compatibilidad         |
| `ci`             | `scan --preset ci`                           | Compatibilidad         |
| `bench`          | Futuro `benchmark`                           | Pendiente de migración |
| `fuzz`           | `testgen`                                    | Deprecado              |
| `assist`         | Sin reemplazo directo                        | Legacy heurístico      |
| `advanced`       | Perfiles y contratos SGDSL                   | Legacy educativo       |
| `clang`          | `scan --language cpp --compile-commands ...` | Compatibilidad         |
| `formal`         | Exportadores formales futuros                | Experimental           |

#### Regla para nuevas fases

Las nuevas fases deben implementar primero sus capacidades en:

```text
AnalysisEngine
FindingIR
reporters
policy
scan --preset
```

Los comandos heredados solo deben actuar como envoltorios de compatibilidad cuando exista una traducción clara al flujo nuevo.

#### Política de deprecación del CLI

StructGuard mantiene comandos heredados para no romper flujos existentes, scripts de demo o pruebas históricas. Sin embargo, esos comandos no representan el diseño final del CLI.

La migración será gradual.

#### Etapas

| Etapa    | Decisión                                                               |
| -------- | ---------------------------------------------------------------------- |
| Fase 9.6 | Documentar comandos heredados y marcar `fuzz` como deprecado           |
| Fase 10  | Medir qué comandos se usan en benchmark, demos y documentación         |
| Fase 11  | Agregar advertencias de deprecación para comandos con reemplazo claro  |
| Fase 12  | Redirigir comandos simples hacia `scan --preset ...` cuando sea seguro |
| Fase 15  | Decidir qué comandos se mantienen, migran o eliminan                   |

#### Criterio de eliminación

Un comando heredado solo puede eliminarse si cumple estas condiciones:

```text
tiene reemplazo documentado
sus pruebas fueron migradas
no aparece en demos activas
no aparece en documentación principal
no es necesario para compatibilidad de una fase anterior
```

#### Ejemplo de transición

El comando:

```bash
structguard fuzz
```

queda reservado como alias heredado. El comando recomendado para generación abstracta de casos de prueba es:

```bash
structguard testgen
```

`fuzz` no debe presentarse como fuzzing nativo, porque no ejecuta binarios ni usa instrumentación como sanitizers, libFuzzer o AFL++.

#### Resultado esperado

El CLI debe converger gradualmente hacia un flujo más simple:

```text
scan
contract
profile
policy
report
benchmark
testgen
```

Esto permite mantener compatibilidad sin duplicar indefinidamente la lógica de análisis.

#### Clang opcional para análisis AST estricto

Si quieres usar el análisis basado en Clang, por ejemplo con `--strict-ast`, instala Clang antes de ejecutar StructGuard:

```bash
sudo apt update
sudo apt install clang
```


#### 1. Crear el entorno `struct_guard`

Se recomienda trabajar dentro de un entorno aislado llamado `struct_guard`.

#### Instalación con entorno virtual de Python

Desde la carpeta principal del proyecto:

```bash
python3 -m venv struct_guard
source struct_guard/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

En Windows PowerShell:

```powershell
python -m venv struct_guard
.\struct_guard\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

#### Instalación para desarrollo

Si quieres modificar StructGuard o ejecutar sus pruebas internas, instala el paquete en modo editable con las dependencias de desarrollo:

```bash
python -m pip install -e '.[dev]'
pytest -q
ruff check .
mypy
```

Esto instala StructGuard en modo editable y permite ejecutar las herramientas usadas durante el desarrollo:

- `pytest` para pruebas.
- `ruff` para lint.
- `mypy` para verificación básica de tipos.

#### Soporte opcional para SMT/Z3

Si quieres habilitar el backend SMT/Z3 para análisis formal o ejecución con solver:

```bash
python -m pip install -e '.[z3]'
```

También puedes instalar desarrollo y Z3 en un solo paso:

```bash
python -m pip install -e '.[dev,z3]'
```

Esta opción es útil para CI, validación completa o desarrollo con soporte formal habilitado.

#### Comprobar la instalación

Después de instalar StructGuard, verifica que el comando esté disponible:

```bash
structguard --version
structguard doctor .
```

También puedes generar un reporte JSON del estado del entorno:

```bash
mkdir -p report
structguard doctor . --json report/doctor.json
```

Una salida correcta debería mostrar `[OK]` en Python, árbol fuente y herramientas instaladas. Si aparece una advertencia sobre `clang`, instala Clang si deseas usar `--strict-ast`.

En Ubuntu/Debian:

```bash
sudo apt update
sudo apt install -y clang
```

#### GitHub Actions y reportes SARIF

StructGuard puede generar reportes SARIF para integrarse con GitHub Code Scanning. Sin embargo, GitHub solo permite subir SARIF a Code Scanning cuando esta función está habilitada en el repositorio.

En repositorios públicos de GitHub.com, Code Scanning está disponible. En repositorios privados o internos, puede requerir que GitHub Code Security esté habilitado.

##### Opción A: usar Code Scanning

Si quieres que los resultados SARIF aparezcan en la pestaña de seguridad de GitHub, activa Code Scanning:

1. Entra a tu repositorio en GitHub.
2. Ve a **Settings**.
3. Entra a **Code security** o **Security & analysis**.
4. Busca **Code scanning**.
5. Actívalo.

Luego usa estos permisos en el workflow:

```yaml
permissions:
  contents: read
  actions: read
  security-events: write
```

Y agrega el paso de subida SARIF:

```yaml
- name: Subir SARIF
  if: github.event_name == 'push' && hashFiles('report/structguard.sarif') != ''
  uses: github/codeql-action/upload-sarif@v4
  with:
    sarif_file: report/structguard.sarif
    category: structguard
```

Se recomienda ejecutar la subida SARIF solo en `push`, no en todos los `pull_request`, porque los pull requests desde forks pueden no tener permisos suficientes para publicar resultados de Code Scanning.

##### Opción B: guardar SARIF como artefacto sin activar Code Scanning

Si todavía no quieres activar Code Scanning, no uses `github/codeql-action/upload-sarif`. En su lugar, guarda los reportes como artefactos del workflow:

```yaml
- name: Subir reportes de StructGuard
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: structguard-reports
    path: report/
```

Así el archivo:

```text
report/structguard.sarif
```

queda disponible para descarga dentro de los artefactos del workflow, pero GitHub no intenta importarlo a Code Scanning.

##### Workflow recomendado sin Code Scanning activado

Esta es la opción más simple para proyectos en fase inicial o primeras publicaciones en GitHub:

```yaml
name: StructGuard CI

on:
  push:
  pull_request:

jobs:
  quality:
    runs-on: ubuntu-latest

    permissions:
      contents: read
      actions: read

    steps:
      - uses: actions/checkout@v4

      - name: Instalar dependencias del sistema
        run: |
          sudo apt update
          sudo apt install -y clang

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Actualizar pip
        run: python -m pip install --upgrade pip

      - name: Instalar paquete con herramientas de desarrollo y Z3
        run: python -m pip install -e '.[dev,z3]'

      - name: Verificar entorno
        run: |
          mkdir -p report
          structguard doctor . --json report/doctor.json

      - name: Compilar fuentes de Python
        run: python -m compileall -q src tests

      - name: Ejecutar pruebas
        run: pytest -q

      - name: Ejecutar lint crítico con Ruff
        run: ruff check .

      - name: Ejecutar verificación básica de tipos con mypy
        run: mypy

      - name: Ejecutar política de StructGuard y emitir artefactos
        run: |
          mkdir -p report
          structguard ci examples/stack_ok.h \
            --headers-only \
            --strict-ast \
            --deep-security \
            --html report/structguard-ci.html \
            --json report/structguard-ci.json \
            --junit report/structguard-junit.xml \
            --sarif report/structguard.sarif \
            --summary-md report/structguard-summary.md \
            --github-annotations

      - name: Validar salidas de reportes
        run: |
          python scripts/validate_outputs.py
          python scripts/validate_outputs.py --profile doctor

      - name: Subir reportes de StructGuard
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: structguard-reports
          path: report/
```

#### Workflow con Code Scanning activado

Cuando Code Scanning esté habilitado en el repositorio, cambia los permisos a:

```yaml
permissions:
  contents: read
  actions: read
  security-events: write
```

Y agrega al final:

```yaml
- name: Subir SARIF
  if: github.event_name == 'push' && hashFiles('report/structguard.sarif') != ''
  uses: github/codeql-action/upload-sarif@v4
  with:
    sarif_file: report/structguard.sarif
    category: structguard
```

Si aparece un error como:

```text
Code scanning is not enabled for this repository.
Please enable code scanning in the repository settings.
```

significa que el SARIF fue generado, pero GitHub no tiene Code Scanning habilitado para ese repositorio. En ese caso, activa Code Scanning o deja el SARIF únicamente como artefacto del workflow.

##### Limpieza de artefactos generados

Después de instalar en modo editable o ejecutar pruebas, pueden aparecer artefactos como:

```text
src/structguard.egg-info
.pytest_cache
 ```

 Estos archivos son generados automáticamente y se pueden eliminar sin afectar el código fuente principal:

```text
rm -rf src/structguard.egg-info .pytest_cache .mypy_cache .ruff_cache
 ```

 También se pueden limpiar caches de Python:

 ```python
find . -type d -name "__pycache__" -exec rm -rf {} +
 ```

Luego verifica nuevamente:

```
structguard doctor .
```

Es normal que esos artefactos vuelvan a aparecer si ejecutas otra vez `pip install -e .` o `pytest`.

#### 2. ¿Qué hace StructGuard?

StructGuard ejecuta varias capas de revisión sobre estructuras de datos:

| Comando | Propósito |
|---|---|
| `analyze` | Ejecuta verificación acotada de contratos y lint de contratos en una sola pasada. |
| `verify` | Evalúa contratos `requires`, `ensures` e `invariant` dentro del modelo acotado soportado. |
| `lint` | Detecta contratos faltantes, invariantes débiles, precondiciones ausentes y documentación incompleta. |
| `suggest` | Sugiere anotaciones `// invariant`, `// requires` y `// ensures` para cabeceras C++. |
| `docs` | Genera documentación automática de API, contratos, invariantes y costos esperados. |
| `security` | Busca riesgos heurísticos: índices fuera de rango, underflow, overflow, memoria manual, inicialización y precondiciones débiles. |
| `perf` | Genera perfiles estáticos de rendimiento, modelos de crecimiento y arneses de benchmark. |
| `testgen` / `fuzz` | Genera secuencias abstractas, contraejemplos candidatos y pruebas de regresión. |
| `ci` / `ci-init` | Integra StructGuard con compuertas de CI, reportes HTML/JSON/JUnit/SARIF y anotaciones de GitHub Actions. |
| `clang` / `--strict-ast` | Usa Clang como compuerta de parseo real de C++ antes de confiar en diagnósticos acotados o heurísticos. |
| `formal` / `pipeline-formal` | Exporta artefactos SMT-LIB/Viper experimentales. La interfaz muestra `FORMALLY_VERIFIED` solo si un backend formal soportado descarga la obligación. |
| `rust` / `python` | Frontends iniciales para analizar contratos simples en Rust y Python. |
| `assist` / `advanced` | Genera recomendaciones heurísticas y plantillas para estructuras avanzadas. |


#### 3. Flujo interno del proyecto

El flujo conceptual de StructGuard es:

```text
Cabeceras .h / .hpp
        |
        v
Fast-scan educativo / Clang canónico
        |
        v
Extracción de estructuras, métodos, campos y contratos
        |
        v
DSL de contratos opcional (.sgdsl)
        |
        v
Análisis por módulos
  - bounded checking con garantía G3
  - contract lint con garantía G2
  - security heuristics con garantía G1
  - testgen abstracto con garantía G1
  - documentación
  - rendimiento
        |
        v
Reportes y artefactos
  - consola
  - HTML
  - JSON
  - Markdown
  - JUnit
  - SARIF
  - harness C++
```

La arquitectura está separada en módulos dentro de `src/structguard/`:

| Módulo | Rol principal |
|---|---|
| `cli.py` | Define la interfaz de línea de comandos. |
| `frontend.py`, `cppscan.py`, `clang_frontend.py` | Extraen información desde C++ y, opcionalmente, desde Clang. |
| `dsl.py` | Carga contratos externos `.sgdsl`. |
| `verifier.py`, `formal.py`, `pipeline.py` | Construyen y evalúan obligaciones de verificación acotada o formal experimental. |
| `lint.py`, `security.py`, `performance.py` | Ejecutan análisis especializados. |
| `docs.py`, `report.py`, `ci_outputs.py` | Generan reportes legibles por humanos y por herramientas de CI. |
| `fuzz.py`, `counterexample.py`, `trace.py` | Producen secuencias abstractas, trazas y contraejemplos candidatos. El comando `fuzz` queda como alias heredado de `testgen`, no como fuzzing nativo. |
| `standard_contracts.py`, `profiles/`, `policy/` | Definen contratos, perfiles y políticas de ejecución. |


#### 4. Primer objetivo recomendado con perfiles

Empieza por una ejecución simple sobre el perfil que corresponda. Para CC-232 puedes usar el contrato movido al perfil dedicado:

```bash
structguard scan ../Libreria_cc232/Semana2/include --profile cc232
```

Este comando sirve para comprobar rápidamente si StructGuard puede leer las cabeceras, aplicar contratos base del perfil y emitir diagnósticos útiles. Para una librería C++ propia, usa `--profile generic-cpp` o crea un perfil nuevo desde `profiles/custom-template/`.

Para guardar resultados en archivos:

```bash
mkdir -p report
structguard scan ../Libreria_cc232/Semana2/include \
  --profile cc232 \
  --html report/cc232_analysis.html \
  --json report/cc232_analysis.json
```

Si tienes Clang instalado y quieres exigir que las cabeceras sean parseables por un frontend real de C++, añade `--strict-ast`:

```bash
structguard scan ../Libreria_cc232/Semana2/include \
  --profile cc232 \
  --strict-ast \
  --std c++17
```

`--strict-ast` no prueba los contratos; actúa como una compuerta de confianza. Si Clang no puede parsear una cabecera, StructGuard evita presentar resultados heurísticos como si fueran confiables.


#### 5. Flujo recomendado para CC-232

Este flujo genera documentación, seguridad y rendimiento para `Libreria_cc232`:

```bash
mkdir -p report

structguard docs ../Libreria_cc232/Semana2/include \
  --headers-only \
  --dsl contracts/cc232_core.sgdsl \
  --docs-html report/cc232_docs.html \
  --markdown-dir report/cc232_md \
  --docs-json report/cc232_docs.json

structguard security ../Libreria_cc232/Semana2/include \
  --headers-only \
  --deep \
  --html report/cc232_security.html \
  --security-json report/cc232_security.json

structguard perf ../Libreria_cc232/Semana2/include \
  --headers-only \
  --perf-html report/cc232_perf.html \
  --perf-json report/cc232_perf.json \
  --perf-md report/cc232_perf.md \
  --growth-json report/cc232_growth.json \
  --harness report/cc232_perf_harness.cpp
```

También puedes ejecutar el script incluido:

```bash
bash scripts/final_demo_cc232.sh ../Libreria_cc232/Semana2/include
```

Ese script genera artefactos en `report/demo_cc232/`, incluyendo análisis, documentación, seguridad, testgen abstracto, rendimiento y CI.


#### 6. Demostración completa del proyecto

##### 6.1 Revisar que el entorno esté listo

```bash
structguard doctor .
```

##### 6.2 Analizar una pila correcta

```bash
structguard analyze examples/stack_ok.h --headers-only --strict-ast --std c++17
```

##### 6.3 Detectar un bug intencional

```bash
structguard analyze examples/stack_bug.h --headers-only --strict-ast --std c++17
```

`examples/stack_bug.h` está incluido deliberadamente para demostrar detección de fallos. Por eso no debe presentarse todo `examples/` como una suite que tenga que pasar limpia.

##### 6.4 Generar reportes HTML y JSON

```bash
mkdir -p report
structguard analyze examples/stack_ok.h \
  --headers-only \
  --strict-ast \
  --std c++17 \
  --html report/examples_analysis.html \
  --json report/examples_analysis.json
```

##### 6.5 Generar documentación automática

```bash
structguard docs examples \
  --headers-only \
  --docs-html report/examples_docs.html \
  --markdown-dir report/examples_md \
  --docs-json report/examples_docs.json
```

##### 6.6 Ejecutar revisión de seguridad

```bash
structguard security examples \
  --headers-only \
  --deep \
  --html report/examples_security.html \
  --security-json report/examples_security.json
```

##### 6.7 Generar testgen abstracto y pruebas candidatas

```bash
structguard testgen examples \
  --headers-only \
  --seeds 20 \
  --steps 50 \
  --fuzz-html report/examples_fuzz.html \
  --fuzz-json report/examples_fuzz.json \
  --replay report/examples_replay.py \
  --emit-tests \
  --test-dir report/generated_tests
```

##### 6.8 Generar perfil de rendimiento

```bash
structguard perf examples \
  --headers-only \
  --perf-html report/examples_perf.html \
  --perf-json report/examples_perf.json \
  --perf-md report/examples_perf.md \
  --growth-json report/examples_growth.json \
  --harness report/examples_perf_harness.cpp
```

##### 6.9 Ejecutar compuerta CI local

```bash
structguard ci examples/stack_ok.h \
  --headers-only \
  --strict-ast \
  --policy structguard.yml \
  --deep-security \
  --html report/structguard-ci.html \
  --json report/structguard-ci.json \
  --junit report/structguard-junit.xml \
  --sarif report/structguard.sarif \
  --summary-md report/structguard-summary.md \
  --github-annotations
```

##### 6.10 Scripts de demostración incluidos

```bash
bash scripts/demo_clean_ci.sh       # debe pasar
bash scripts/demo_bug_detection.sh  # debe fallar de forma esperada y validada
bash scripts/final_demo.sh          # ejecuta ambas rutas
```

#### 7. Uso de contratos DSL

Los contratos externos se escriben en archivos `.sgdsl`. El paquete incluye `contracts/cc232_core.sgdsl`, orientado a estructuras base de CC-232.

Ejemplo simplificado:

```text
package cc232;

structure ArrayStack {
  invariant n >= 0;
  invariant n <= capacity();
  method add { requires 0 <= i && i <= n; ensures n == old(n) + 1; }
  method remove { requires 0 <= i && i < n; ensures n == old(n) - 1; }
}
```

Valida un archivo DSL con:

```bash
structguard dsl contracts/cc232_core.sgdsl --html report/cc232_dsl.html --dsl-json report/cc232_dsl.json
```

Usa `--dsl` en `analyze`, `docs`, `security`, `perf`, `ci`, `testgen` y otros comandos que aceptan rutas C++:

```bash
structguard analyze <ruta> --headers-only --dsl contracts/cc232_core.sgdsl
```

#### 8. Limitaciones importantes

StructGuard es una herramienta auxiliar de revisión. No reemplaza:

- compilación real con Clang/GCC,
- sanitizers como AddressSanitizer, UndefinedBehaviorSanitizer o ThreadSanitizer,
- pruebas unitarias,
- fuzzing nativo,
- revisión humana,
- verificación formal completa.

Sus principales límites son:

- El análisis acotado trabaja con dominios pequeños y estados simplificados.
- El frontend ligero no entiende todo C++ moderno.
- Las macros, templates complejos, sobrecarga avanzada, aliasing, iteradores y memoria dinámica pueden reducir la precisión.
- El modo `security` es heurístico: prioriza señales útiles, no pruebas definitivas.
- El modo `perf` estima perfiles y crecimiento esperado; no sustituye benchmarks reales.
- El modo formal es experimental y depende de la calidad del modelo exportado.


#### 9. Falsos positivos y falsos negativos

#### Falsos positivos

Un falso positivo ocurre cuando StructGuard advierte un problema aunque el código real sea seguro. Puede pasar si:

- una macro garantiza una condición que el analizador no expande,
- una función auxiliar valida índices antes de llamar al método analizado,
- un wrapper externo garantiza una precondición,
- un template genera código válido, pero el frontend ligero no reconstruye bien el caso,
- una rama compleja protege una operación, pero el modelo no la representa con suficiente precisión.

#### Falsos negativos

Un falso negativo ocurre cuando StructGuard no reporta un problema que sí existe. Puede pasar si:

- el bug solo aparece con tamaños mayores que el dominio acotado,
- hay overflow real fuera del rango modelado,
- el fallo depende de aliasing, iteradores inválidos o memoria dinámica,
- el error requiere una secuencia larga de operaciones,
- la precondición faltante no coincide con los patrones conocidos,
- el comportamiento depende de efectos laterales no modelados.

Por eso un resultado visible `BOUNDED_CHECK_PASSED` debe leerse como: "no se encontró contraejemplo dentro del modelo acotado", no como "el programa es correcto para todos los casos".


#### 10. CI/CD

Crea una política inicial y un workflow de GitHub Actions:

```bash
structguard ci-init . --project-path Libreria_cc232 --force
```

Ejecuta un gate local sobre CC-232:

```bash
structguard ci ../Libreria_cc232/Semana2/include \
  --headers-only \
  --policy structguard.yml \
  --deep-security \
  --html report/structguard-ci.html \
  --json report/structguard-ci.json \
  --junit report/structguard-junit.xml \
  --sarif report/structguard.sarif \
  --summary-md report/structguard-summary.md \
  --github-annotations
```

Si quieres hacer fallar el pipeline ante advertencias:

```bash
structguard ci ../Libreria_cc232/Semana2/include \
  --headers-only \
  --policy structguard.yml \
  --deep-security \
  --fail-on-warnings
```

#### 11. Contenido del paquete

```text
StructGuard/
├── contracts/              # Contratos DSL heredados
├── docs/                   # Visión de producto, arquitectura y limitaciones
├── profiles/               # Perfiles de dominio y contratos por perfil
├── examples/               # Ejemplos C++, Rust y Python
├── scripts/                # Demos, pruebas de humo y validación de release
├── src/structguard/        # Código fuente principal
├── tests/                  # Pruebas automatizadas
├── .github/workflows/      # Workflow de GitHub Actions
├── pyproject.toml          # Metadatos del paquete Python
├── structguard.yml         # Política inicial de StructGuard
├── CHANGELOG.md
├── LICENSE
└── README.md
```

#### 12. Validación de release

Para validar el paquete localmente:

```bash
bash scripts/validate_release.sh
```

Para hacer que herramientas de desarrollo ausentes como `ruff` o `mypy` sean un fallo duro:

```bash
STRUCTGUARD_STRICT_DEV=1 bash scripts/validate_release.sh
```
#### 13. Resumen operativo

Para un uso típico con `Libreria_cc232`, el flujo mínimo recomendado es:

```bash
conda activate struct_guard
mkdir -p report

structguard analyze ../Libreria_cc232/Semana2/include --headers-only --dsl profiles/cc232/contracts/cc232_core.sgdsl
structguard docs ../Libreria_cc232/Semana2/include --headers-only --dsl profiles/cc232/contracts/cc232_core.sgdsl --docs-html report/cc232_docs.html --markdown-dir report/cc232_md --docs-json report/cc232_docs.json
structguard security ../Libreria_cc232/Semana2/include --headers-only --deep --html report/cc232_security.html --security-json report/cc232_security.json
structguard perf ../Libreria_cc232/Semana2/include --headers-only --perf-html report/cc232_perf.html --perf-json report/cc232_perf.json --perf-md report/cc232_perf.md --growth-json report/cc232_growth.json --harness report/cc232_perf_harness.cpp
```

Si el proyecto ya compila correctamente con Clang, añade `--strict-ast --std c++17` a los comandos críticos de análisis y CI.

#### 14. Alcance explícito de contratos en scan

Cuando un perfil incluye varios contratos, `scan --preset ci` los valida todos.
Para analizar un ejemplo parcial o una sola estructura, use `--contract`:

```bash
structguard scan examples/generic_cpp \
  --profile generic-cpp \
  --preset ci \
  --contract profiles/generic-cpp/contracts/stack.sgdsl
```

El perfil sigue definiendo la configuración de dominio, pero el alcance contractual queda limitado al archivo indicado.
