### StructGuard Architecture

#### Vista general

La arquitectura objetivo separa entrada, contratos, analisis, evidencia y exportacion formal.

```text
C++ / Rust / Python / SGDSL / contratos inline
        |
        v
Frontend por lenguaje
        |
        v
SourceIR
        |
        v
ContractIR
        |
        v
BindingIR
        |
        v
AnalysisEngine
        |
        v
Findings normalizados
        |
        v
Reporters / Evidence Pack / Exporters formales
```

#### Estado actual

En la version actual, StructGuard ya incluye CLI, parser heuristico, soporte Clang opcional, DSL de contratos, reportes, CI, seguridad heuristica, fuzzing abstracto y exportacion formal experimental.

La Fase 0 no reescribe esos modulos. Solo documenta la arquitectura objetivo y crea una estructura de perfiles para evitar que CC-232 sea tratado como el limite del producto.

#### Componentes objetivo

#### StructGuard Core

El nucleo debe contener el motor general de analisis. En fases posteriores debe concentrar:

- carga de configuracion
- carga de perfiles
- construccion de SourceIR
- construccion de ContractIR
- resolucion de BindingIR
- ejecucion de analizadores
- emision de Findings
- generacion de evidencia

#### Profiles

Los perfiles definen el dominio de analisis. Un perfil puede representar un curso, una libreria, una familia de estructuras o un conjunto de reglas de CI.

Ejemplos iniciales:

```text
profiles/cc232/
profiles/generic-cpp/
profiles/stl-adapters/
profiles/custom-template/
```

#### Frontends

Los frontends extraen informacion del codigo fuente. C++ sigue siendo el primer lenguaje de entrada.

El objetivo de fases posteriores es que Clang sea el frontend canonico para C++ y que el parser ligero quede como modo rapido o educativo.

#### ContractIR

ContractIR debe representar contratos de manera independiente del formato original. Puede venir de archivos `.sgdsl`, contratos inline o adaptadores.

#### BindingIR

BindingIR debe unir SourceIR y ContractIR. Su responsabilidad es detectar contratos huerfanos, metodos sin contrato, simbolos inexistentes y cambios de nombre no sincronizados.

#### Findings

Todos los modulos deben emitir hallazgos con un modelo comun. Esto evita que JSON, HTML, Markdown, JUnit y SARIF dependan directamente de cada analizador.

#### Backends formales

Dafny debe ser el primer backend formal recomendado. Prusti, Why3 y Viper deben tratarse como backends experimentales o de investigacion hasta que tengan validacion reproducible.

#### Regla de diseno

El CLI no debe ser el centro de la arquitectura. El CLI debe ser una capa fina que invoca el motor, los perfiles, los analizadores y los reporters.
