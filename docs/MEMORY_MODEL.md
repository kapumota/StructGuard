### Modelo de memoria mínimo para C++

#### Objetivo

El modelo de memoria de StructGuard no intenta verificar todo C++. Su objetivo inicial es reconocer patrones de memoria manual que aparecen en implementaciones de estructuras de datos.

La fase cubre casos frecuentes en arreglos dinámicos, listas, árboles y contenedores educativos:

```text
new / delete
new[] / delete[]
nullptr
ownership simple
aliasing local básico
campos puntero
arreglos dinámicos
capacidad lógica vs. capacidad física
move/copy básico como inventario inicial
```

#### Flujo

```text
Código C++
  |
  v
cppscan
  |
  v
ClassModel
  |
  v
MemoryModel
  |
  v
MemorySafetyAnalyzer
  |
  v
Diagnostics / FindingIR / Reporters
```

#### Módulos

```text
src/structguard/memory/model.py
src/structguard/memory/ownership.py
src/structguard/memory/aliasing.py
src/structguard/analyzers/memory_safety.py
```

#### Qué representa el modelo

El modelo identifica:

```text
campos puntero
reservas con new y new[]
liberaciones con delete y delete[]
asignaciones a nullptr
desreferencias de punteros
relaciones simples entre size y capacity
```

#### Reglas iniciales

| Regla | Nivel | Descripción |
| --- | --- | --- |
| `MEM_ARRAY_OWNERSHIP_OK` | INFO | `new[]` tiene `delete[]` compatible visible. |
| `MEM_SINGLE_OWNERSHIP_OK` | INFO | `new` tiene `delete` compatible visible. |
| `MEM_ARRAY_NEW_WITHOUT_DELETE_ARRAY` | WARNING | `new[]` no tiene `delete[]` visible. |
| `MEM_NEW_WITHOUT_DELETE` | WARNING | `new` no tiene `delete` visible. |
| `MEM_DELETE_KIND_MISMATCH` | FAILED | Se usa `delete` para memoria reservada con `new[]`, o `delete[]` para memoria reservada con `new`. |
| `MEM_DOUBLE_DELETE` | FAILED | El mismo recurso se libera más de una vez en el mismo método. |
| `MEM_NULL_DEREF_RISK` | WARNING | Un puntero posiblemente nulo se desreferencia sin guarda visible. |
| `MEM_CAPACITY_SIZE_MISMATCH` | FAILED | `size` puede quedar por encima de `capacity`. |

#### Uso desde scan

El modelo de memoria se ejecuta desde los presets que incluyen seguridad:

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

#### Ejemplo de uso correcto

```cpp
class CorrectArray {
    int* data;
    int size_;
    int capacity_;
public:
    CorrectArray(int capacity) : data(new int[capacity]), size_(0), capacity_(capacity) {}
    ~CorrectArray() { delete[] data; data = nullptr; }
};
```

Este patrón produce evidencia informativa de ownership compatible.

#### Ejemplo de riesgo

```cpp
class MissingDelete {
    int* data;
public:
    MissingDelete(int capacity) : data(new int[capacity]) {}
};
```

Este patrón produce `MEM_ARRAY_NEW_WITHOUT_DELETE_ARRAY`.

#### Limitaciones

Esta fase es deliberadamente conservadora. No modela todavía:

```text
control de flujo completo
destructores virtuales complejos
RAII avanzado
aliasing interprocedural
plantillas complejas
macros
move/copy con semántica completa
ownership compartido
```

#### Relación con fases futuras

Esta fase prepara el camino para analizar estructuras con punteros:

```text
LinkedList
DoublyLinkedList
BST
AVL
Treap
Graph
HashTable con encadenamiento
```

El objetivo posterior es conectar este modelo con BindingIR, políticas YAML estrictas y reglas estructurales más precisas.
