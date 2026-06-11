### Referencia de reglas estructurales

#### Propósito

Esta referencia documenta las primeras reglas estructurales configurables de StructGuard. La meta de la Fase 9 es dejar de depender solo de advertencias heurísticas dispersas y expresar las reglas con metadatos estables.

Cada regla debe tener:

```text
rule_id
descripción
severidad por defecto
ejemplo correcto
ejemplo incorrecto
perfil donde aplica
posible CWE si corresponde
```

#### Flujo dentro del motor

```text
SourceIR o escaneo C++ ligero
  |
  v
ContractIR y BindingIR cuando están disponibles
  |
  v
Analizadores estructurales
  |
  v
FindingIR y reportes desacoplados
```

En esta fase las reglas se ejecutan desde el motor modular para los presets que corresponden:

```text
contracts
security
ci
full
```

#### SG-CONTRACT-MISSING-PRECONDITION

| Campo | Valor |
| --- | --- |
| rule_id | SG-CONTRACT-MISSING-PRECONDITION |
| descripción | Método sensible sin precondición explícita ni guarda local clara. |
| severidad por defecto | warning |
| perfiles | cc232, generic-cpp, stl-adapters |
| CWE | CWE-20 |

Ejemplo correcto:

```cpp
// requires n > 0
int pop();
```

Ejemplo incorrecto:

```cpp
int pop() {
    return data[--n];
}
```

#### SG-STACK-POP-EMPTY

| Campo | Valor |
| --- | --- |
| rule_id | SG-STACK-POP-EMPTY |
| descripción | Operación de pila que puede leer o eliminar desde una pila vacía. |
| severidad por defecto | error |
| perfiles | cc232, generic-cpp |
| CWE | CWE-787 |

Ejemplo correcto:

```cpp
// requires n > 0
int pop();
```

Ejemplo incorrecto:

```cpp
int pop() {
    return data[--n];
}
```

#### SG-QUEUE-FIFO-VIOLATION

| Campo | Valor |
| --- | --- |
| rule_id | SG-QUEUE-FIFO-VIOLATION |
| descripción | Operación de cola que parece retirar desde el extremo equivocado. |
| severidad por defecto | warning |
| perfiles | cc232, generic-cpp, stl-adapters |
| CWE | no aplica |

Ejemplo correcto:

```cpp
int dequeue() {
    return data[head++];
}
```

Ejemplo incorrecto:

```cpp
int dequeue() {
    return data[--tail];
}
```

#### SG-BOUNDS-INDEX-RISK

| Campo | Valor |
| --- | --- |
| rule_id | SG-BOUNDS-INDEX-RISK |
| descripción | Acceso indexado sin guarda local o precondición de límites visible. |
| severidad por defecto | warning |
| perfiles | cc232, generic-cpp, stl-adapters |
| CWE | CWE-125 |

Ejemplo correcto:

```cpp
// requires 0 <= i && i < size
int at(int i) const {
    return data[i];
}
```

Ejemplo incorrecto:

```cpp
int at(int i) const {
    return data[i];
}
```

#### SG-SIZE-NOT-UPDATED

| Campo | Valor |
| --- | --- |
| rule_id | SG-SIZE-NOT-UPDATED |
| descripción | Método mutador que no actualiza un campo de tamaño visible. |
| severidad por defecto | warning |
| perfiles | cc232, generic-cpp |
| CWE | no aplica |

Ejemplo correcto:

```cpp
void push(int value) {
    data[n] = value;
    n += 1;
}
```

Ejemplo incorrecto:

```cpp
void push(int value) {
    data[n] = value;
}
```

#### SG-HEAP-PROPERTY-RISK

| Campo | Valor |
| --- | --- |
| rule_id | SG-HEAP-PROPERTY-RISK |
| descripción | Método de heap que no muestra restauración de propiedad heap. |
| severidad por defecto | warning |
| perfiles | cc232, generic-cpp |
| CWE | no aplica |

Ejemplo correcto:

```cpp
void push(int value) {
    data[n] = value;
    bubbleUp(n);
    n += 1;
}
```

Ejemplo incorrecto:

```cpp
void push(int value) {
    data[n] = value;
    n += 1;
}
```

#### SG-BST-ORDER-RISK

| Campo | Valor |
| --- | --- |
| rule_id | SG-BST-ORDER-RISK |
| descripción | Método de BST que no muestra comparación de orden durante inserción o búsqueda. |
| severidad por defecto | warning |
| perfiles | cc232, generic-cpp |
| CWE | no aplica |

Ejemplo correcto:

```cpp
if (x < node->key) {
    node = node->left;
}
```

Ejemplo incorrecto:

```cpp
root = new Node(x);
```

#### SG-NULL-DEREFERENCE-RISK

| Campo | Valor |
| --- | --- |
| rule_id | SG-NULL-DEREFERENCE-RISK |
| descripción | Uso de puntero que puede ser nulo sin guarda local visible. |
| severidad por defecto | warning |
| perfiles | cc232, generic-cpp |
| CWE | CWE-476 |

Ejemplo correcto:

```cpp
if (node != nullptr) {
    return node->value;
}
```

Ejemplo incorrecto:

```cpp
return node->value;
```

#### SG-MEMORY-OWNERSHIP-RISK

| Campo | Valor |
| --- | --- |
| rule_id | SG-MEMORY-OWNERSHIP-RISK |
| descripción | Reserva manual sin ownership y liberación compatibles. |
| severidad por defecto | error |
| perfiles | cc232, generic-cpp |
| CWE | CWE-401 |

Ejemplo correcto:

```cpp
Vector(int n) {
    data = new int[n];
}

~Vector() {
    delete[] data;
}
```

Ejemplo incorrecto:

```cpp
Vector(int n) {
    data = new int[n];
}

~Vector() {
    delete data;
}
```

#### SG-COMPLEXITY-DEQUEUE-LINEAR-RISK

| Campo | Valor |
| --- | --- |
| rule_id | SG-COMPLEXITY-DEQUEUE-LINEAR-RISK |
| descripción | Operación dequeue parece desplazar elementos y puede ser O(n). |
| severidad por defecto | warning |
| perfiles | cc232, generic-cpp |
| CWE | no aplica |

Ejemplo correcto:

```cpp
int dequeue() {
    return data[head++];
}
```

Ejemplo incorrecto:

```cpp
int dequeue() {
    int value = data[0];
    for (int i = 1; i < n; ++i) {
        data[i - 1] = data[i];
    }
    n -= 1;
    return value;
}
```

#### Limitaciones

Estas reglas son conservadoras. No sustituyen a Clang, sanitizers, fuzzing nativo ni verificación formal. Sirven como capa estructural inicial para convertir patrones educativos en diagnósticos configurables y auditables.
