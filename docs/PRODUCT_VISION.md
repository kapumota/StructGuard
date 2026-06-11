### StructGuard Product Vision

#### Identidad

StructGuard es una plataforma extensible de contratos, analisis, evidencia y exportacion formal para implementaciones de estructuras de datos.

El proyecto no esta limitado a CC-232. CC-232 es el primer perfil academico y el primer banco de pruebas. El nucleo debe poder trabajar con otras librerias C++, otros cursos y, de forma progresiva, otros lenguajes mediante perfiles, contratos, frontends y exportadores.

#### Separacion conceptual

```text
StructGuard Core     = motor general de analisis y evidencia
Profiles            = reglas, contratos y presets por dominio
CC-232 Profile       = perfil educativo inicial
Generic C++ Profile  = perfil general para librerias C++ propias
STL Adapters         = adaptadores para librerias externas
```

#### Alcance de la Fase 0

La Fase 0 no cambia el motor de analisis. Su objetivo es reposicionar el producto y preparar la estructura de carpetas para fases posteriores.

El resultado esperado es que el repositorio deje de parecer una herramienta exclusiva para `Libreria_cc232` y empiece a presentarse como una plataforma general.

#### Promesa correcta

StructGuard analiza implementaciones de estructuras de datos contra contratos explicitos, genera evidencia reproducible y puede exportar modelos hacia backends formales para subconjuntos soportados.

#### Promesa que debe evitarse

StructGuard no debe prometer que verifica formalmente cualquier programa C++ ni que reemplaza al compilador, sanitizers, pruebas unitarias, fuzzing nativo o verificadores formales especializados.

#### Usuarios objetivo

- Docentes que necesitan revisar implementaciones de estructuras de datos.
- Estudiantes que necesitan retroalimentacion sobre invariantes, precondiciones y errores estructurales.
- Desarrolladores que quieren validar librerias C++ propias contra contratos explicitos.
- Investigadores que quieren explorar exportacion hacia Dafny, Prusti, Why3 o Viper.

#### Evolucion esperada

```text
Fase 0  - Reposicionamiento del producto
Fase 1  - Sistema de perfiles real
Fase 2  - SGDSL estable y ContractIR
Fase 3  - Binding codigo-contrato
Fase 4  - Frontend C++ canonico con Clang
Fase 5  - Motor de analisis modular
```
