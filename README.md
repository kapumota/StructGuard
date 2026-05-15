### StructGuard 4.6.1 ES

**StructGuard** es una herramienta de línea de comandos para revisar implementaciones de estructuras de datos, principalmente en cabeceras C++17 (`.h`, `.hh`, `.hpp`, `.hxx`). Está pensada para apoyar cursos y proyectos donde se implementan pilas, colas, vectores, deques, árboles, heaps, hashing, grafos y estructuras similares.

Esta versión está diseñada especialmente para cabeceras `.h` como las de `Libreria_cc232`. Su objetivo no es reemplazar al compilador ni demostrar matemáticamente todo un programa C++; su valor está en combinar análisis acotado, lint de contratos, documentación automática, señales de seguridad, perfiles de rendimiento y artefactos para CI.


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
| `fuzz` / `testgen` | Genera secuencias abstractas, contraejemplos candidatos y pruebas de regresión. |
| `ci` / `ci-init` | Integra StructGuard con compuertas de CI, reportes HTML/JSON/JUnit/SARIF y anotaciones de GitHub Actions. |
| `clang` / `--strict-ast` | Usa Clang como compuerta de parseo real de C++ antes de confiar en diagnósticos acotados o heurísticos. |
| `formal` / `pipeline-formal` | Exporta artefactos SMT-LIB/Viper experimentales. Solo reporta `PROVED` si un backend externo descarga la obligación. |
| `rust` / `python` | Frontends iniciales para analizar contratos simples en Rust y Python. |
| `assist` / `advanced` | Genera recomendaciones heurísticas y plantillas para estructuras avanzadas. |


#### 3. Flujo interno del proyecto

El flujo conceptual de StructGuard es:

```text
Cabeceras .h / .hpp
        |
        v
Frontend ligero de C++ / Clang opcional
        |
        v
Extracción de estructuras, métodos, campos y contratos
        |
        v
DSL de contratos opcional (.sgdsl)
        |
        v
Análisis por módulos
  - bounded checking
  - contract lint
  - security heuristics
  - fuzzing abstracto
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
| `fuzz.py`, `counterexample.py`, `trace.py` | Producen secuencias abstractas, trazas y contraejemplos candidatos. |
| `standard_contracts.py`, `profiles.py`, `policy.py` | Definen contratos, perfiles y políticas de ejecución. |


#### 4. Primer objetivo recomendado con `Libreria_cc232`

Empieza por una ejecución simple sobre las cabeceras de la semana que quieras revisar:

```bash
structguard analyze ../Libreria_cc232/Semana2/include --headers-only --dsl contracts/cc232_core.sgdsl
```

Este comando sirve para comprobar rápidamente si StructGuard puede leer las cabeceras, aplicar contratos base y emitir diagnósticos útiles.

Para guardar resultados en archivos:

```bash
mkdir -p report
structguard analyze ../Libreria_cc232/Semana2/include \
  --headers-only \
  --dsl contracts/cc232_core.sgdsl \
  --html report/cc232_analysis.html \
  --json report/cc232_analysis.json
```

Si tienes Clang instalado y quieres exigir que las cabeceras sean parseables por un frontend real de C++, añade `--strict-ast`:

```bash
structguard analyze ../Libreria_cc232/Semana2/include \
  --headers-only \
  --strict-ast \
  --std c++17 \
  --dsl contracts/cc232_core.sgdsl
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

Ese script genera artefactos en `report/demo_cc232/`, incluyendo análisis, documentación, seguridad, fuzzing, rendimiento y CI.


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

##### 6.7 Generar fuzzing abstracto y pruebas candidatas

```bash
structguard fuzz examples \
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

#### 7. Lectura de resultados

StructGuard separa el diagnóstico operativo del nivel de confianza.

| Resultado | Interpretación |
|---|---|
| `FAILED` | Hay una violación, contraejemplo, fallo de política o error de parseo en el modelo soportado. Debe revisarse. |
| `UNKNOWN` | El método, contrato o patrón requiere un modelo más fuerte. No debe leerse como correcto ni como incorrecto. |
| `WARNING` | Hay riesgo, ausencia de contrato o práctica que conviene revisar. Puede no ser un bug real. |
| `INFO` | Señal auxiliar, resumen o recomendación. |
| `BOUNDED_VERIFIED` | No se encontró violación dentro de los límites del modelo acotado. No es una prueba universal. |
| `HEURISTIC` | Resultado basado en patrones o inferencias. Sirve para revisión, no para una conclusión formal. |
| `PROVED` | Una obligación formal generada fue descargada por un backend externo. No significa que todo el programa C++ esté probado. |

Regla práctica:

- Un diagnóstico `FAILED` indica una violación o contraejemplo dentro del modelo soportado.
- Un diagnóstico `UNKNOWN` indica que el método o patrón requiere un modelo más fuerte.
- Un diagnóstico `WARNING` indica riesgo, ausencia de contrato o práctica que conviene revisar.


#### 8. Uso de contratos DSL

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

Usa `--dsl` en `analyze`, `docs`, `security`, `perf`, `ci`, `fuzz` y otros comandos que aceptan rutas C++:

```bash
structguard analyze <ruta> --headers-only --dsl contracts/cc232_core.sgdsl
```

#### 9. Consejos prácticos para CC-232

Anota primero estructuras simples como `ArrayStack`, `ArrayQueue`, `ArrayDeque` y `DengVector`. Luego avanza hacia árboles, heaps, hashing, grafos y estructuras avanzadas.

Orden recomendado:

1. Ejecuta `analyze` sin `--strict-ast` para detectar problemas rápidos de contratos y patrones.
2. Corrige errores obvios de precondiciones, índices e invariantes.
3. Ejecuta `docs` para revisar qué API detectó StructGuard.
4. Ejecuta `security --deep` para buscar riesgos de límites, underflow, overflow e inicialización.
5. Ejecuta `perf` para obtener una lectura inicial de complejidad esperada y generar un harness.
6. Añade `--strict-ast` cuando las cabeceras ya compilen o cuando quieras usar Clang como compuerta estricta.
7. Integra `ci` cuando el flujo local sea estable.


#### 10. Limitaciones importantes

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


#### 11. Falsos positivos y falsos negativos

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

Por eso un resultado `BOUNDED_VERIFIED` debe leerse como: "no se encontró contraejemplo dentro del modelo acotado", no como "el programa es correcto para todos los casos".


#### 12. CI/CD

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

#### 13. Contenido del paquete

```text
StructGuard-4.6.1-es/
├── contracts/              # Contratos DSL, incluido cc232_core.sgdsl
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

#### 14. Validación de release

Para validar el paquete localmente:

```bash
bash scripts/validate_release.sh
```

Para hacer que herramientas de desarrollo ausentes como `ruff` o `mypy` sean un fallo duro:

```bash
STRUCTGUARD_STRICT_DEV=1 bash scripts/validate_release.sh
```
#### 15. Resumen operativo

Para un uso típico con `Libreria_cc232`, el flujo mínimo recomendado es:

```bash
conda activate struct_guard
mkdir -p report

structguard analyze ../Libreria_cc232/Semana2/include --headers-only --dsl contracts/cc232_core.sgdsl
structguard docs ../Libreria_cc232/Semana2/include --headers-only --dsl contracts/cc232_core.sgdsl --docs-html report/cc232_docs.html --markdown-dir report/cc232_md --docs-json report/cc232_docs.json
structguard security ../Libreria_cc232/Semana2/include --headers-only --deep --html report/cc232_security.html --security-json report/cc232_security.json
structguard perf ../Libreria_cc232/Semana2/include --headers-only --perf-html report/cc232_perf.html --perf-json report/cc232_perf.json --perf-md report/cc232_perf.md --growth-json report/cc232_growth.json --harness report/cc232_perf_harness.cpp
```

Si el proyecto ya compila correctamente con Clang, añade `--strict-ast --std c++17` a los comandos críticos de análisis y CI.
