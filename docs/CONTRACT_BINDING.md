### Contract Binding

#### Propósito

Contract Binding conecta contratos externos SGDSL con símbolos reales del código fuente. Esta fase evita que un contrato obsoleto siga apareciendo como válido cuando el código cambió.

El modelo objetivo es:

```text
SourceIR + ContractIR + resolución de símbolos = BindingIR
```

En esta fase, `SourceIR` se construye con el frontend ligero existente. La Fase 4 reemplazará esa fuente por un frontend C++ canónico basado en Clang.

#### Problema que resuelve

Un contrato puede quedar separado del código cuando alguien renombra un método, elimina un campo o cambia una estructura. Antes de esta fase, un contrato podía pasar validación SGDSL aunque ya no correspondiera al código fuente.

Ejemplo de contrato obsoleto:

```text
structure ArrayStack {
  field n: int;
  method add { ensures n == old(n) + 1; }
}
```

Código real:

```cpp
class ArrayStack {
public:
    void push(int value);
private:
    int n;
};
```

Resultado esperado:

```text
FAIL: contrato huérfano
```

#### Componentes

```text
src/structguard/binding/symbol_table.py
src/structguard/binding/name_resolution.py
src/structguard/binding/binder.py
src/structguard/binding/contract_matcher.py
```

#### Flujo

```text
Código C++
  |
  v
SourceSymbolTable
  |
  v
ContractIR
  |
  v
BindingIR
  |
  v
Diagnósticos de binding
```

#### Comando

```bash
structguard contract bind examples/generic_cpp \
  --contract profiles/generic-cpp/contracts/stack.sgdsl
```

Para escribir el BindingIR:

```bash
structguard contract bind examples/generic_cpp \
  --contract profiles/generic-cpp/contracts/stack.sgdsl \
  --output artifacts/binding-ir.json
```

Para salida JSON completa:

```bash
structguard contract bind examples/generic_cpp \
  --contract profiles/generic-cpp/contracts/stack.sgdsl \
  --json
```

#### Contratos inline

StructGuard mantiene contratos externos `.sgdsl` y reconoce contratos inline cercanos a métodos C++.

Formato con dos puntos:

```cpp
// requires: size() > 0
// ensures: result == old(top())
int pop();
```

Formato sin dos puntos:

```cpp
// requires size() > 0
// ensures result == old(top())
int pop();
```

Los contratos inline no reemplazan al SGDSL externo. Sirven como información local que puede compararse con el contrato externo en fases posteriores.

#### Diagnósticos principales

```text
BINDING_ORPHAN_STRUCTURE
BINDING_ORPHAN_FIELD
BINDING_ORPHAN_METHOD
BINDING_CONTRACTS_MATCH_SOURCE
```

#### Alcance actual

Esta fase valida existencia de estructuras, campos y métodos. Todavía no prueba equivalencia semántica entre el cuerpo C++ y las expresiones SGDSL.

No promete:

```text
verificación formal completa
resolución completa de templates
análisis robusto de macros
modelo de memoria C++ completo
```

Eso corresponde a fases posteriores.

#### Criterio de aceptación

Un contrato externo que declare un método inexistente debe fallar con `BINDING_ORPHAN_METHOD`. El contrato no debe ser ignorado silenciosamente.
