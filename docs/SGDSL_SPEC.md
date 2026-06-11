### SGDSL estable

#### Propósito

SGDSL es el lenguaje de contratos de StructGuard. En la fase 2 deja de ser solo texto auxiliar y pasa a tener un flujo explícito:

```text
.sgdsl
  |
  v
Parser
  |
  v
SGDSL AST
  |
  v
ContractIR
  |
  v
Validators / Exporters / Analyzers
```

El objetivo es que cada contrato pueda validarse antes de conectarse con analizadores, exportadores formales o perfiles de dominio.

#### Forma mínima

```text
package generic.cpp;

structure Stack {
  invariant n >= 0;
  method push { ensures n == old(n) + 1; }
  method pop { requires n > 0; ensures n == old(n) - 1; }
  method top requires n > 0;
}
```

#### Campos

Los campos son opcionales en esta fase para mantener compatibilidad con contratos antiguos. Cuando se declaran, el validador puede detectar referencias a campos o parámetros inexistentes.

```text
structure Stack {
  field n: int;
  invariant n >= 0;
}
```

#### Métodos con parámetros

El parser estable acepta parámetros tipados o sin tipo.

```text
structure Vector {
  field n: int;
  method get(i: int) requires 0 <= i && i < n;
  method set(i: int, value: int) requires 0 <= i && i < n;
}
```

#### Contratos soportados

```text
invariant expresión;
requires expresión;
ensures expresión;
```

Los contratos pueden escribirse dentro de un bloque de método:

```text
method pop {
  requires n > 0;
  ensures n == old(n) - 1;
}
```

O en forma compacta:

```text
method top requires n > 0;
```

#### Validaciones iniciales

El comando `structguard contract check` detecta:

```text
estructuras duplicadas
campos duplicados
métodos duplicados
contratos duplicados
expresiones vacías
paréntesis sin balancear
operadores incompletos
caracteres no admitidos
campos o parámetros inexistentes cuando hay campos declarados
llamadas a métodos no declarados dentro del contrato
comparaciones numéricas sobre campos booleanos
métodos declarados sin requires ni ensures
```

#### Comandos

Validar un contrato:

```bash
structguard contract check profiles/generic-cpp/contracts/stack.sgdsl
```

Emitir ContractIR en JSON:

```bash
structguard contract dump-ir profiles/generic-cpp/contracts/stack.sgdsl --json
```

Escribir ContractIR en archivo:

```bash
structguard contract dump-ir profiles/generic-cpp/contracts/stack.sgdsl --output artifacts/contract-ir.json
```

#### Limitación importante

La fase 2 todavía no enlaza el contrato con el código C++ real. Por eso la detección de métodos inexistentes en el código fuente completo queda para la fase 3, donde se agregará BindingIR.

En esta fase, StructGuard valida la consistencia interna del contrato y prepara una IR estable para que las siguientes fases no dependan de texto crudo.
