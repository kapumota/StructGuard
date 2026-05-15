from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .cppscan import scan_project
from .model import Diagnostic, ProjectReport, MethodModel, ClassModel


@dataclass
class BenchMetric:
    class_name: str
    method: str
    file: str
    line: int
    source_lines: int
    loops: int
    branches: int
    assignments: int
    returns: int
    asserts: int
    raw_index_ops: int
    pointer_ops: int
    estimated_cost: str
    workload_hint: str
    score: int


def _body(m: MethodModel) -> str:
    return m.body or ""


def _estimated_cost(cls: ClassModel, m: MethodModel, body: str) -> str:
    lname = cls.name.lower()
    mn = m.name.lower()
    loops = len(re.findall(r"\b(for|while)\b", body))

    if any(x in lname for x in ["avl", "bst", "tree", "heap", "btree", "skiplist"]):
        if mn in {"add", "insert", "remove", "delete", "find", "search", "get", "set"}:
            return "O(log n) esperado si se mantiene el invariante estructural"

    if any(x in lname for x in ["hash", "table", "dictionary"]):
        if mn in {"add", "insert", "remove", "find", "search", "get", "set"}:
            return "O(1) promedio esperado; revisar rehash y colisiones"

    if any(x in lname for x in ["array", "stack", "queue", "deque", "list"]):
        if mn in {"push", "pop", "top", "front", "back", "size", "empty", "add", "remove"} and loops == 0:
            return "O(1) u O(1) amortizado esperado"
        if loops >= 1:
            return "probablemente O(n) por bucle, desplazamiento o copia"

    if loops >= 2:
        return "probablemente O(n^2) o recorrido anidado"
    if loops == 1:
        return "probablemente O(n)"
    return "probablemente O(1) por cuerpo lineal"


def _workload_hint(cls: ClassModel, m: MethodModel) -> str:
    mn = m.name.lower()
    lname = cls.name.lower()

    if mn in {"add", "insert", "push", "enqueue"}:
        return "inserciones secuenciales; inserciones aleatorias, inserciones en límite de capacidad"
    if mn in {"remove", "pop", "dequeue"}:
        return "eliminación en estados vacío/no vacío, alternancia insertar/eliminar"
    if mn in {"get", "set", "find", "search", "contains"}:
        return "búsquedas con acierto/fallo; índices primero/medio/último, consultas aleatorias"
    if any(x in lname for x in ["heap", "priority"]):
        return "push-pop aleatorio; push-pop ordenado; duplicados adversariales"
    if any(x in lname for x in ["tree", "avl", "bst", "btree"]):
        return "claves aleatorias; claves ordenadas; claves duplicadas, carga intensiva de eliminaciones"
    if any(x in lname for x in ["hash"]):
        return "claves uniformes; claves con muchas colisiones; estrés de rehash"
    return "construcción básica y carga mínima de operaciones"


def collect_bench_metrics(root: Path, headers_only: bool = False) -> list[BenchMetric]:
    metrics: list[BenchMetric] = []
    classes = scan_project(root, headers_only=headers_only)
    for cls in classes:
        for m in cls.methods:
            if m.body is None or m.name.startswith("~"):
                continue
            body = _body(m)
            sloc = len([ln for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("//")])
            loops = len(re.findall(r"\b(for|while)\b", body))
            branches = len(re.findall(r"\b(if|else if|switch)\b", body))
            assignments = len(re.findall(r"(?<![=!<>])=(?!=)|\+=|-=|\+\+|--", body))
            returns = len(re.findall(r"\breturn\b", body))
            asserts = len(re.findall(r"\bassert\s*\(", body))
            raw_index_ops = len(re.findall(r"\[[^\]]+\]", body))
            pointer_ops = len(re.findall(r"->|\bnew\b|\bdelete\b|\*\s*[A-Za-z_]", body))
            score = sloc + loops * 8 + branches * 4 + raw_index_ops * 2 + pointer_ops * 3
            metrics.append(BenchMetric(
                class_name=cls.name,
                method=m.name,
                file=str(cls.file),
                line=m.start_line,
                source_lines=sloc,
                loops=loops,
                branches=branches,
                assignments=assignments,
                returns=returns,
                asserts=asserts,
                raw_index_ops=raw_index_ops,
                pointer_ops=pointer_ops,
                estimated_cost=_estimated_cost(cls, m, body),
                workload_hint=_workload_hint(cls, m),
                score=score,
            ))
    return metrics


def bench_project(root: Path, headers_only: bool = False) -> ProjectReport:
    start = time.perf_counter()
    metrics = collect_bench_metrics(root, headers_only=headers_only)
    report = ProjectReport(root=str(root))
    if not metrics:
        report.diagnostics.append(Diagnostic(level="WARNING", code="NO_BENCH_TARGETS", message="No se encontraron métodos definidos en cabeceras para planificar benchmarks.", file=str(root)))
        return report
    elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
    by_class: dict[str, list[BenchMetric]] = {}
    for bm in metrics:
        by_class.setdefault(bm.class_name, []).append(bm)
    report.diagnostics.append(Diagnostic(
        level="INFO",
        code="BENCH_SUMMARY",
        message=f"Perfil estático de benchmark generado para {len(metrics)} métodos en {len(by_class)} clases.",
        file=str(root),
        details={"elapsed_ms": elapsed_ms, "classes": len(by_class), "methods": len(metrics)},
    ))
    for cls_name, items in sorted(by_class.items()):
        hot = sorted(items, key=lambda x: x.score, reverse=True)[:5]
        report.diagnostics.append(Diagnostic(
            level="INFO",
            code="BENCH_CLASS_PROFILE",
            message=f"{cls_name}: {len(items)} métodos candidatos. Objetivos principales de benchmark seleccionados por puntaje de complejidad estática.",
            symbol=cls_name,
            details={"targets": [asdict(x) for x in hot]},
        ))
    return report


def write_bench_json(metrics: list[BenchMetric], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(x) for x in metrics], indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_bench_harness(metrics: list[BenchMetric], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    includes = sorted({m.file for m in metrics if m.file.endswith((".h", ".hpp", ".hh", ".hxx"))})
    rel_includes = [Path(f).name for f in includes]
    lines = [
        "// Generado por StructGuard. Es un harness inicial, adapta constructores cuando sea necesario.",
        "#include <chrono>",
        "#include <iostream>",
        "#include <vector>",
    ]
    for inc in rel_includes[:30]:
        lines.append(f'#include "{inc}"')
    lines += [
        "",
        "int main() {",
        "  using clock = std::chrono::steady_clock;",
        "  constexpr int N = 10000;",
        "  auto start = clock::now();",
        "  // TODO: Instanciar las clases detectadas y ejecutar los workloads sugeridos debajo.",
    ]
    for bm in metrics[:80]:
        lines.append(f"  // {bm.class_name}::{bm.method}: {bm.workload_hint} | {bm.estimated_cost}")
    lines += [
        "  auto end = clock::now();",
        "  std::cout << \"elapsed_ms=\" << std::chrono::duration_cast<std::chrono::milliseconds>(end-start).count() << \"\\n\";",
        "  return 0;",
        "}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
