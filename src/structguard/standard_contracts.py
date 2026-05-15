from __future__ import annotations

from dataclasses import dataclass
import re

from .model import ClassModel, Contract, MethodModel


@dataclass(frozen=True)
class StandardContractRule:
    structure: str
    method_pattern: str
    kind: str
    expression_template: str
    source: str = "standard-library"


STACK_NAMES = {"stack", "pila", "arraystack", "linkedstack", "buggystack", "realisticstack", "branchstack"}
QUEUE_NAMES = {"queue", "cola", "arrayqueue", "circularqueue", "linkedqueue"}
VECTOR_NAMES = {"vector", "arraylist", "list", "dynamicarray", "array", "sequence"}


def _size_symbol(cls: ClassModel) -> str | None:
    for cand in ("size_", "n", "n_", "_size", "count", "count_", "length_"):
        if cand in cls.fields:
            return cand
    return None


def _capacity_symbol(cls: ClassModel) -> str | None:
    for cand in ("capacity_", "cap", "cap_", "_capacity", "max_size_"):
        if cand in cls.fields:
            return cand
    if "data_" in cls.fields or "a" in cls.fields:
        return "capacity_"
    return None


def structure_kind(cls: ClassModel) -> str:
    name = cls.name.split("::")[-1].lower()
    fields = {f.lower() for f in cls.fields}
    methods = {m.name.lower() for m in cls.methods}
    if name in STACK_NAMES or {"push", "pop", "top"} & methods:
        return "stack"
    if name in QUEUE_NAMES or {"enqueue", "dequeue", "front"} & methods or {"head_", "tail_"} & fields:
        return "queue"
    if name in VECTOR_NAMES or {"operator[]", "at", "push_back", "capacity"} & methods:
        return "vector"
    if any("vector" in f for f in fields) or any("data" in f for f in fields):
        return "vector"
    return "unknown"


def _has_contract(contracts: list[Contract], expr: str) -> bool:
    return any(c.expression == expr for c in contracts)


def standard_invariants(cls: ClassModel) -> list[Contract]:
    out: list[Contract] = []
    seen = {c.expression for c in cls.invariants}
    sz = _size_symbol(cls)
    cap = _capacity_symbol(cls)
    def add(expr: str) -> None:
        if expr and expr not in seen:
            out.append(Contract(kind="invariant", expression=expr, line=cls.start_line, source="standard-library"))
            seen.add(expr)
    if sz:
        add(f"{sz} >= 0")
    if cap:
        add(f"{cap} >= 0")
    if sz and cap:
        add(f"{sz} <= {cap}")
    if structure_kind(cls) == "queue":
        for cand in ("head_", "front_", "tail_", "rear_", "back_"):
            if cand in cls.fields:
                add(f"{cand} >= 0")
                if cap:
                    add(f"{cand} < {cap}")
    return out


def standard_requires(cls: ClassModel, method: MethodModel) -> list[Contract]:
    out: list[Contract] = []
    seen = {c.expression for c in method.requires}
    sz = _size_symbol(cls)
    cap = _capacity_symbol(cls)
    name = method.name.lower()
    body = method.body or ""
    def add(expr: str) -> None:
        if expr and expr not in seen:
            out.append(Contract(kind="requires", expression=expr, line=method.start_line, source="standard-library"))
            seen.add(expr)
    if sz and name in {"pop", "top", "peek", "front", "back", "dequeue", "remove", "removefirst", "operator[]", "at"}:
        if name in {"operator[]", "at"}:
            # No hay modelo de parámetros todavía; se conserva como señal contractual si el usuario usa index/i.
            if re.search(r"\b(index|idx|i)\b", method.signature):
                add(f"{sz} > 0")
        else:
            add(f"{sz} > 0")
    if sz and cap and name in {"push", "push_back", "enqueue", "insert", "add"}:
        if not re.search(rf"\b{re.escape(sz)}\s*<\s*{re.escape(cap)}\b", body):
            add(f"{sz} < {cap}")
    if name == "operator[]":
        # Los contratos paramétricos se representan como una heurística porque el motor acotado rastrea campos, no argumentos.
        if not any("index" in c.expression or "i" in c.expression for c in method.requires):
            out.append(Contract(kind="requires", expression="index >= 0", line=method.start_line, source="standard-library-parametric"))
            out.append(Contract(kind="requires", expression=f"index < {sz or 'size_'}", line=method.start_line, source="standard-library-parametric"))
    return out


def standard_ensures(cls: ClassModel, method: MethodModel) -> list[Contract]:
    out: list[Contract] = []
    seen = {c.expression for c in method.ensures}
    sz = _size_symbol(cls)
    cap = _capacity_symbol(cls)
    name = method.name.lower()
    body = method.body or ""
    def add(expr: str) -> None:
        if expr and expr not in seen:
            out.append(Contract(kind="ensures", expression=expr, line=method.start_line, source="standard-library"))
            seen.add(expr)
    if sz:
        if name in {"size", "length"} and re.search(rf"return\s+{re.escape(sz)}\s*;", body):
            add(f"result == {sz}")
        if name in {"empty", "isempty"}:
            add(f"result == ({sz} == 0)")
        # Solo inferimos cambios incondicionales cuando no hay if. Los cambios guardados quedan en el executor.
        if "if" not in body:
            if name in {"push", "push_back", "enqueue", "insert", "add"} and re.search(rf"\b{re.escape(sz)}\s*(\+\+|\+=\s*1|=\s*{re.escape(sz)}\s*\+\s*1)", body):
                add(f"{sz} == old({sz}) + 1")
            if name in {"pop", "dequeue", "remove", "removefirst"} and re.search(rf"\b{re.escape(sz)}\s*(--|-=\s*1|=\s*{re.escape(sz)}\s*-\s*1)", body):
                add(f"{sz} == old({sz}) - 1")
    if cap and name == "capacity":
        add(f"result == {cap}")
    return out
