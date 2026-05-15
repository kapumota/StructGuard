from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .cppscan import scan_project
from .model import Diagnostic, ProjectReport


@dataclass
class TraceEvent:
    step: int
    event: str
    symbol: str | None = None
    value: Any | None = None
    state: dict[str, Any] | None = None
    note: str | None = None


def _parse_ops(ops: str | None) -> list[tuple[str, str | None]]:
    if not ops:
        return []
    out: list[tuple[str, str | None]] = []
    for raw in re.split(r"[,;\n]+", ops):
        raw = raw.strip()
        if not raw:
            continue
        if ":" in raw:
            a, b = raw.split(":", 1)
            out.append((a.strip(), b.strip()))
        else:
            out.append((raw, None))
    return out


def abstract_trace(ops: str | None = None, structure: str = "stack") -> list[TraceEvent]:
    parsed = _parse_ops(ops) or [("push", "1"), ("push", "2"), ("pop", None), ("top", None)]
    size = 0
    capacity = 4
    data: list[Any] = []
    events: list[TraceEvent] = []
    for idx, (op, val) in enumerate(parsed, start=1):
        op_l = op.lower()
        note = None
        if op_l in {"push", "add", "enqueue", "insert"}:
            if size >= capacity:
                old_cap = capacity
                capacity *= 2
                note = f"redimensionamiento {old_cap}->{capacity}"
            data.append(val)
            size += 1
            event = "insert"
        elif op_l in {"pop", "remove", "dequeue"}:
            if size == 0:
                note = "violación de precondición: remove/pop sobre estructura vacía"
                event = "precondition_failure"
            else:
                if data:
                    data.pop()
                size -= 1
                event = "remove"
        elif op_l in {"top", "front", "back", "peek"}:
            event = "access"
            if size == 0:
                note = f"violación de precondición: {op} sobre estructura vacía"
        elif op_l in {"clear"}:
            data.clear(); size = 0; event = "clear"
        else:
            event = "operation"
            note = "operación desconocida trazada como no-op"
        events.append(TraceEvent(step=idx, event=event, symbol=op, value=val, state={"size": size, "capacity": capacity, "sample": list(data[-5:])}, note=note))
    return events


def source_trace_project(root: Path, headers_only: bool = False) -> ProjectReport:
    report = ProjectReport(root=str(root))
    classes = scan_project(root, headers_only=headers_only)
    count = 0
    for cls in classes:
        for m in cls.methods:
            if not m.body:
                continue
            body = m.body
            patterns: list[str] = []
            if re.search(r"\bresize\s*\(", body): patterns.append("resize")
            if re.search(r"rotate(Left|Right)|\brotate_", body): patterns.append("rotación de árbol")
            if re.search(r"\bfor\b|\bwhile\b", body): patterns.append("recorrido de bucle")
            if re.search(r"\bassert\s*\(", body): patterns.append("assert de precondición")
            if re.search(r"\bfind\s*\(|parent\s*\[", body): patterns.append("camino parent/find")
            if patterns:
                count += 1
                report.diagnostics.append(Diagnostic(
                    level="INFO",
                    code="TRACE_POINT",
                    message=f"{m.qualified_name} contiene eventos trazables: {', '.join(patterns)}.",
                    file=str(cls.file),
                    line=m.start_line,
                    symbol=m.qualified_name,
                    details={"events": patterns},
                ))
    if count == 0:
        report.diagnostics.append(Diagnostic(level="WARNING", code="NO_TRACE_POINTS", message="No se detectaron eventos fuente trazables.", file=str(root)))
    return report


def trace_project(root: Path, headers_only: bool = False, ops: str | None = None, structure: str = "stack") -> ProjectReport:
    report = source_trace_project(root, headers_only=headers_only)
    events = abstract_trace(ops, structure=structure)
    report.diagnostics.insert(0, Diagnostic(
        level="INFO",
        code="ABSTRACT_TRACE",
        message=f"Se generaron {len(events)} eventos abstractos para {structure}.",
        file=str(root),
        details={"events": [asdict(e) for e in events]},
    ))
    if any(e.event == "precondition_failure" for e in events):
        report.diagnostics.insert(1, Diagnostic(level="WARNING", code="TRACE_PRECONDITION_FAILURE", message="La secuencia de operaciones contiene una violación de precondición.", file=str(root)))
    return report


def write_trace_json(events: list[TraceEvent], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(e) for e in events], indent=2, ensure_ascii=False), encoding="utf-8")
    return path
