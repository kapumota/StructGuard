### Changelog

#### 4.6.1 Professional ES

- Added `structguard doctor` for environment and source-tree checks.
- Added confidence/evidence/remediation metadata to JSON, HTML, JUnit and SARIF-oriented outputs.
- Added realistic example corpus for template stack/vector and circular queue plus an indexed vector bug sample.
- Tightened release validation with doctor output validation and Python compile checks.
- Fixed duplicate Clang `--std` parser registration.
- Kept Clang/SMT support explicitly bounded and experimental where applicable.

#### 4.5.5-es-stable

- `report/` queda documentado como evidencia generada para presentación. Para una entrega fuente pura puede eliminarse y regenerarse.
- `scripts/validate_outputs.py` acepta `--profile ci|demo-clean|demo-bug` y `--dir`, por lo que ya no está amarrado a rutas fijas.
- `scripts/validate_release.sh` ejecuta `compileall`, tests, generación de outputs CI, validación de outputs y demos separadas.
- `ruff` y `mypy` se ejecutan cuando están instalados; `STRUCTGUARD_STRICT_DEV=1` los exige como fallo duro.
- La documentación de demo aclara la dependencia opcional de Clang para `--strict-ast`.
- La documentación explica que señales `SEC_*` de nivel `INFO` son revisión heurística y no fallos de contrato.
- La documentación refuerza que el modo formal es experimental y que `PROVED` aplica solo a obligaciones SMT/Viper generadas.

#### 4.5.4-es-stable

- Se separaron las demos en una ruta limpia (`scripts/demo_clean_ci.sh`) y una ruta de bug intencional (`scripts/demo_bug_detection.sh`).
- `scripts/validate_release.sh` ya no depende de comandos ocultados con `|| true`; valida explícitamente el fallo esperado de `BuggyStack::pop`.
- El SMT-LIB generado ya no incluye `(get-model)` en el artefacto principal, el modelo se solicita solo cuando Z3 devuelve `sat`.
- El módulo `assist` se presenta como recomendaciones heurísticas, sin afirmar uso de IA generativa.
- Se añadió `DEMO.md` con comandos exactos y rutas de reportes HTML.
- Se limpia `src/structguard.egg-info` desde la fuente.

#### Registro de cambios

#### 4.5.3-estable

- Reposiciona el alcance real como bounded checking, heuristic analysis y contract lint.
- Añade niveles de confianza explícitos: `PROVED`, `BOUNDED_VERIFIED`, `HEURISTIC`, `UNKNOWN`, además de `FAILED`, `WARNING` e `INFO`.
- Añade `--strict-ast` en `verify`, `analyze` y `ci` para exigir parseo real con Clang.
- Añade pruebas adversariales para límites del modelo y fallos de Clang.
- Actualiza CI para ejecutar `pytest`, `ruff`, `mypy` y validación de artefactos HTML/JSON/JUnit/SARIF.
- Separa artefactos generados de los reportes principales de desarrollo.
- Documenta falsos positivos y falsos negativos con ejemplos.

#### 4.5.1-estable

Versión estable entregable.

- Consolida todos los módulos v4.5 en un paquete pulido.
- Añade README estable, instalación, inicio rápido, arquitectura, limitaciones, referencia de comandos y documentación de la demostración final.
- Añade scripts de prueba de humo, demostración final, demostración CC-232 y validación de la versión.
- Regenera los informes de demostración fuera del código fuente principal.
- Elimina archivos de caché transitorios del paquete de la versión.
- Mantiene todas las capacidades v4.5: verificación, análisis estático, informes, documentación, seguridad, CI, fuzz/generación de pruebas, ingeniería de rendimiento, DSL, frontends, artefactos formales y plantillas avanzadas.

#### 4.5.0

- Añadidos perfiles de ingeniería de rendimiento.
- Añadidos planes de carga, sugerencias de contadores, curvas de crecimiento empírico, verificaciones de regresión y generación de arneses en C++.

#### 4.4.0

- Añadido Fuzz/TestGen con scripts de reproducción, corpus de semillas y candidatos de pruebas generados en C++.

#### 4.3.0

- Añadidas compuertas de política de CI/CD, JUnit, SARIF, resúmenes en Markdown e integración con GitHub Actions.

#### 4.2.0

- Añadido análisis de seguridad defensivo profundo para estructuras de datos en C++.

#### 4.1.0

- Añadida generación automática de documentación.

#### 4.0.0

- Añadido pipeline experimental Clang AST ->CFG/SSA ->SMT/Viper, frontends de Rust/Python, recomendaciones heurísticas y estructuras avanzadas.
