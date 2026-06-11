from __future__ import annotations

import re
from pathlib import Path

from structguard.analyzers.contracts import RuleDefinition, has_explicit_precondition, has_local_guard, method_changes_size
from structguard.cppscan import scan_project
from structguard.model import ClassModel, Diagnostic, MethodModel, ProjectReport


STRUCTURE_RULES: dict[str, RuleDefinition] = {
    "SG-STACK-POP-EMPTY": RuleDefinition(
        rule_id="SG-STACK-POP-EMPTY",
        description="Operación de pila que puede leer o eliminar desde una pila vacía.",
        default_severity="error",
        good_example="// requires n > 0\nT pop();",
        bad_example="T pop() { return data[--n]; }",
        profiles=("cc232", "generic-cpp"),
        cwe="CWE-787",
        tags=("stack", "contracts", "cpp"),
    ),
    "SG-QUEUE-FIFO-VIOLATION": RuleDefinition(
        rule_id="SG-QUEUE-FIFO-VIOLATION",
        description="Operación de cola que parece retirar desde el extremo equivocado.",
        default_severity="warning",
        good_example="return data[head++];",
        bad_example="return data[--tail];",
        profiles=("cc232", "generic-cpp", "stl-adapters"),
        cwe=None,
        tags=("queue", "semantics", "cpp"),
    ),
    "SG-SIZE-NOT-UPDATED": RuleDefinition(
        rule_id="SG-SIZE-NOT-UPDATED",
        description="Método mutador que no actualiza un campo de tamaño visible.",
        default_severity="warning",
        good_example="data[n] = value; n += 1;",
        bad_example="data[n] = value;",
        profiles=("cc232", "generic-cpp"),
        cwe=None,
        tags=("size", "invariant", "cpp"),
    ),
    "SG-HEAP-PROPERTY-RISK": RuleDefinition(
        rule_id="SG-HEAP-PROPERTY-RISK",
        description="Método de heap que no muestra restauración de propiedad heap.",
        default_severity="warning",
        good_example="push(value); bubbleUp(index);",
        bad_example="data[n++] = value;",
        profiles=("cc232", "generic-cpp"),
        cwe=None,
        tags=("heap", "semantics", "cpp"),
    ),
    "SG-BST-ORDER-RISK": RuleDefinition(
        rule_id="SG-BST-ORDER-RISK",
        description="Método de BST que no muestra comparación de orden durante inserción o búsqueda.",
        default_severity="warning",
        good_example="if (x < node->key) node = node->left;",
        bad_example="root = new Node(x);",
        profiles=("cc232", "generic-cpp"),
        cwe=None,
        tags=("bst", "semantics", "cpp"),
    ),
    "SG-NULL-DEREFERENCE-RISK": RuleDefinition(
        rule_id="SG-NULL-DEREFERENCE-RISK",
        description="Uso de puntero que puede ser nulo sin guarda local visible.",
        default_severity="warning",
        good_example="if (node != nullptr) return node->value;",
        bad_example="return node->value;",
        profiles=("cc232", "generic-cpp"),
        cwe="CWE-476",
        tags=("null", "memory", "cpp"),
    ),
}

_MUTATING_METHODS = {"push", "pop", "enqueue", "dequeue", "insert", "remove", "erase", "add", "delete", "extract_min", "extract_max"}
_SIZE_FIELD_HINTS = {"n", "size", "size_", "count", "count_", "length", "length_"}


def analyze_structure_semantics_project(root: Path, headers_only: bool = False) -> ProjectReport:
    classes = scan_project(root, headers_only=headers_only)
    report = ProjectReport(root=str(root), diagnostics=[])
    report.diagnostics.append(
        Diagnostic(
            level="INFO",
            code="SG_STRUCTURE_RULES_SUMMARY",
            message=f"Reglas estructurales evaluadas: {len(classes)} clases analizadas.",
            file=str(root),
            details={"tags": ["structure", "rules"], "rules": [rule.as_dict() for rule in STRUCTURE_RULES.values()]},
        )
    )
    for cls in classes:
        for method in cls.methods:
            _check_stack_empty(report, cls, method)
            _check_queue_fifo(report, cls, method)
            _check_size_update(report, cls, method)
            _check_heap_property(report, cls, method)
            _check_bst_order(report, cls, method)
            _check_null_deref(report, cls, method)
    return report


def _check_stack_empty(report: ProjectReport, cls: ClassModel, method: MethodModel) -> None:
    if "stack" not in cls.name.lower() or method.name.lower() not in {"pop", "top", "peek"}:
        return
    if has_explicit_precondition(method) or has_local_guard(method):
        return
    body = (method.body or "").replace(" ", "")
    if method.name.lower() == "peek" and "top(" in body:
        return
    _add(report, cls, method, "SG-STACK-POP-EMPTY", f"{method.qualified_name} puede operar sobre pila vacía.", method.signature)


def _check_queue_fifo(report: ProjectReport, cls: ClassModel, method: MethodModel) -> None:
    if "queue" not in cls.name.lower() or method.name.lower() not in {"dequeue", "pop", "front"}:
        return
    body = (method.body or "").lower().replace(" ", "")
    if not body:
        return
    suspicious = ("--tail" in body or "tail--" in body or "back" in body or "data[size" in body or "data[n" in body)
    healthy = ("head" in body or "front" in body)
    if suspicious and not healthy:
        _add(report, cls, method, "SG-QUEUE-FIFO-VIOLATION", f"{method.qualified_name} parece retirar desde el extremo posterior.", method.body or method.signature)


def _check_size_update(report: ProjectReport, cls: ClassModel, method: MethodModel) -> None:
    name = method.name.lower().strip("~")
    if name not in _MUTATING_METHODS:
        return
    body = method.body or ""
    if not body:
        return
    size_fields = cls.fields & _SIZE_FIELD_HINTS
    if not size_fields and not any(token in body for token in _SIZE_FIELD_HINTS):
        return
    if method_changes_size(method, cls.fields):
        return
    _add(report, cls, method, "SG-SIZE-NOT-UPDATED", f"{method.qualified_name} parece mutar la estructura sin actualizar el tamaño lógico.", method.signature)


def _check_heap_property(report: ProjectReport, cls: ClassModel, method: MethodModel) -> None:
    if "heap" not in cls.name.lower() or method.name.lower() not in {"push", "insert", "pop", "extract_min", "extract_max"}:
        return
    body = (method.body or "").lower()
    if not body:
        return
    if any(token in body for token in ("heapify", "bubble", "sift", "percolate", "pushdown", "bubbleup")):
        return
    _add(report, cls, method, "SG-HEAP-PROPERTY-RISK", f"{method.qualified_name} no muestra restauración de propiedad heap.", method.signature)


def _check_bst_order(report: ProjectReport, cls: ClassModel, method: MethodModel) -> None:
    class_name = cls.name.lower()
    if not any(token in class_name for token in ("bst", "binarysearchtree")):
        return
    if method.name.lower() not in {"insert", "contains", "find", "remove", "erase"}:
        return
    body = method.body or ""
    if not body:
        return
    if re.search(r"(<|>|compare|less|greater)", body):
        return
    _add(report, cls, method, "SG-BST-ORDER-RISK", f"{method.qualified_name} no muestra comparación de orden BST.", method.signature)


def _check_null_deref(report: ProjectReport, cls: ClassModel, method: MethodModel) -> None:
    body = method.body or ""
    if not body or has_local_guard(method):
        return
    matches = re.findall(r"\b([A-Za-z_]\w*)\s*->", body)
    if not matches:
        return
    pointer_fields = {field for field in cls.fields if field.lower() in {"root", "head", "tail", "node", "current"} or field.lower().endswith(("ptr", "_ptr"))}
    for target in sorted(set(matches)):
        if pointer_fields and target not in pointer_fields:
            continue
        _add(report, cls, method, "SG-NULL-DEREFERENCE-RISK", f"{method.qualified_name} usa {target}-> sin guarda de nulidad visible.", f"{target}->")
        break


def _add(report: ProjectReport, cls: ClassModel, method: MethodModel, rule_id: str, message: str, evidence: str) -> None:
    rule = STRUCTURE_RULES[rule_id]
    level = "FAILED" if rule.default_severity == "error" else "WARNING"
    report.diagnostics.append(
        Diagnostic(
            level=level,
            code=rule.rule_id,
            message=message,
            file=str(cls.file),
            line=method.start_line,
            symbol=method.qualified_name,
            details={
                "title": rule.description,
                "confidence": "medium",
                "evidence": evidence,
                "remediation": "Agrega contrato explícito, guarda local o restaura el invariante estructural correspondiente.",
                "cwe": rule.cwe,
                "tags": list(rule.tags),
                "rule": rule.as_dict(),
            },
        )
    )
