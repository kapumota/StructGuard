from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MutationResult:
    name: str
    source_name: str
    content: str
    changed: bool
    expected_findings: list[str]


# Cada mutador es deliberadamente pequeño y determinista. La Fase 10 no intenta
# hacer mutación C++ general; solo genera variantes controladas para medir
# regresiones del analizador.
def apply_mutation(source_name: str, content: str, mutation_name: str, expected_findings: list[str]) -> MutationResult:
    if mutation_name == "remove_empty_guard_from_stack_pop":
        mutated = _remove_empty_guard_from_stack_pop(content)
    elif mutation_name == "omit_size_increment":
        mutated = _omit_size_increment(content)
    elif mutation_name == "wrong_queue_end":
        mutated = _wrong_queue_end(content)
    elif mutation_name == "remove_capacity_guard_from_stack_push":
        mutated = _remove_capacity_guard_from_stack_push(content)
    elif mutation_name == "omit_queue_size_decrement":
        mutated = _omit_queue_size_decrement(content)
    else:
        raise ValueError(f"Mutación no soportada: {mutation_name}")
    return MutationResult(
        name=mutation_name,
        source_name=source_name,
        content=mutated,
        changed=mutated != content,
        expected_findings=list(expected_findings),
    )


def available_mutations() -> list[str]:
    return [
        "remove_empty_guard_from_stack_pop",
        "omit_size_increment",
        "wrong_queue_end",
        "remove_capacity_guard_from_stack_push",
        "omit_queue_size_decrement",
    ]


def _remove_empty_guard_from_stack_pop(content: str) -> str:
    old = '''    int pop() {
        if (n <= 0) {
            throw std::out_of_range("pila vacía");
        }
        n -= 1;
        return data[n];
    }
'''
    new = '''    int pop() {
        return data[--n];
    }
'''
    if old in content:
        return content.replace(old, new)
    return content.replace('''    int pop() {
        if (n <= 0) {
            throw std::out_of_range("pila vacía");
        }
        n -= 1;
        return data[n];
    }
''', new)


def _omit_size_increment(content: str) -> str:
    return content.replace("        n += 1;\n", "        // Mutación: no se actualiza el tamaño lógico.\n", 1)


def _wrong_queue_end(content: str) -> str:
    old = '''    int dequeue() {
        if (n <= 0) {
            throw std::out_of_range("cola vacía");
        }
        int value = data[head];
        head = (head + 1) % 16;
        n -= 1;
        return value;
    }
'''
    new = '''    int dequeue() {
        if (n <= 0) {
            throw std::out_of_range("cola vacía");
        }
        n -= 1;
        return data[--tail];
    }
'''
    return content.replace(old, new)


def _remove_capacity_guard_from_stack_push(content: str) -> str:
    old = '    void push(int value) {\n        if (n >= 16) {\n            throw std::out_of_range("capacidad agotada");\n        }\n        data[n] = value;\n        n += 1;\n    }\n'
    new = '    void push(int value) {\n        data[n] = value;\n        n += 1;\n    }\n'
    return content.replace(old, new)


def _omit_queue_size_decrement(content: str) -> str:
    return content.replace("        n -= 1;\n", "        // Mutación: no se actualiza el tamaño lógico.\n", 1)
