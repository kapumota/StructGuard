from __future__ import annotations

from dataclasses import dataclass, asdict
from html import escape
from pathlib import Path
import json
import math
import re
import statistics
from typing import Any

from .bench import collect_bench_metrics, BenchMetric
from .cppscan import scan_project
from .model import Diagnostic, ProjectReport, ClassModel, MethodModel


DATASET_SIZES = [128, 512, 2048, 8192, 32768]


@dataclass
class ComplexityFit:
    model: str
    score: float
    explanation: str


@dataclass
class PerformanceTarget:
    class_name: str
    method: str
    file: str
    line: int
    category: str
    estimated_cost: str
    complexity_model: str
    workload: str
    counters: list[str]
    metrics: dict[str, int]
    risk: str
    notes: list[str]


@dataclass
class ClassPerformanceProfile:
    class_name: str
    file: str
    category: str
    targets: list[PerformanceTarget]
    structure_counters: list[str]
    workloads: list[str]
    instrumentation_points: list[str]
    risk_score: int


def _body(m: MethodModel) -> str:
    return m.body or ""


def _category(name: str) -> str:
    n = name.lower()
    if any(x in n for x in ["avl", "bst", "tree", "btree", "skiplist"]):
        return "tree"
    if any(x in n for x in ["heap", "priority"]):
        return "heap"
    if any(x in n for x in ["hash", "table", "dictionary", "map"]):
        return "hash"
    if any(x in n for x in ["graph", "dsu", "union", "find"]):
        return "graph"
    if any(x in n for x in ["fenwick", "segment", "rmq"]):
        return "range-query"
    if any(x in n for x in ["array", "vector", "deque", "queue", "stack", "list"]):
        return "sequence"
    return "generic"


def _counter_hints(cls: ClassModel) -> list[str]:
    cat = _category(cls.name)
    base: list[str] = ["calls", "elapsed_ns"]
    if cat == "tree":
        base += ["comparisons", "rotations", "height", "visited_nodes"]
    elif cat == "heap":
        base += ["comparisons", "swaps", "sift_steps"]
    elif cat == "hash":
        base += ["hash_calls", "collisions", "rehashes", "max_bucket_size", "load_factor"]
    elif cat == "sequence":
        base += ["reallocations", "copies", "moves", "index_ops", "capacity"]
    elif cat == "range-query":
        base += ["combine_ops", "visited_nodes", "index_ops"]
    elif cat == "graph":
        base += ["edge_scans", "find_steps", "path_compressions", "visited_nodes"]
    else:
        base += ["ramas", "loops", "assignments"]
    return list(dict.fromkeys(base))


def _method_counters(cls: ClassModel, bm: BenchMetric) -> list[str]:
    counters = _counter_hints(cls)
    mn = bm.method.lower()
    if mn in {"insert", "add", "push", "enqueue"}:
        counters += ["insertions"]
    if mn in {"remove", "erase", "delete", "pop", "dequeue"}:
        counters += ["removals"]
    if mn in {"find", "search", "contains", "get"}:
        counters += ["lookups", "hits", "misses"]
    return list(dict.fromkeys(counters))


def _workloads(cls: ClassModel) -> list[str]:
    cat = _category(cls.name)
    if cat == "tree":
        return ["random_insert_search", "sorted_insert_degenerate", "delete_heavy", "duplicates"]
    if cat == "heap":
        return ["random_push_pop", "sorted_push_pop", "alternating_push_pop", "duplicates"]
    if cat == "hash":
        return ["uniform_keys", "collision_heavy", "rehash_stress", "lookup_miss_heavy"]
    if cat == "sequence":
        return ["push_back_growth", "front_operations", "random_index_access", "alternating_add_remove"]
    if cat == "range-query":
        return ["point_updates", "range_queries", "mixed_update_query", "boundary_ranges"]
    if cat == "graph":
        return ["sparse_graph", "dense_graph", "incremental_connectivity", "path_compression_stress"]
    return ["smoke", "random_operations", "boundary_cases"]


def _complexity_model(cls: ClassModel, bm: BenchMetric) -> str:
    est = bm.estimated_cost.lower()
    mn = bm.method.lower()
    cat = _category(cls.name)
    if "n^2" in est or bm.loops >= 2:
        return "quadratic"
    if "log" in est:
        return "logarithmic"
    if "amortized" in est:
        return "amortized_constant"
    if "o(1)" in est or "straight-line" in est:
        return "constant"
    if cat in {"tree", "heap", "range-query"} and mn in {"insert", "add", "remove", "find", "get", "set", "query", "update"}:
        return "logarithmic"
    if cat == "hash" and mn in {"insert", "add", "remove", "find", "get", "set", "contains"}:
        return "amortized_constant"
    if bm.loops == 1:
        return "linear"
    return "constant"


def _risk(bm: BenchMetric, model: str) -> str:
    score = bm.score
    if model == "quadratic" or bm.loops >= 2 or score >= 70:
        return "high"
    if bm.loops == 1 or bm.raw_index_ops >= 4 or score >= 35:
        return "medium"
    return "low"


def _notes(cls: ClassModel, bm: BenchMetric, body: str) -> list[str]:
    notes: list[str] = []
    cat = _category(cls.name)
    if re.search(r"\bresize\s*\(|\bnew\b|capacity", body):
        notes.append("Medir reasignaciones/crecimiento de capacidad; las constantes ocultas pueden dominar operaciones amortizadas.")
    if re.search(r"rotate|balance|height", body, re.I):
        notes.append("Medir rotaciones y altura; comparar cargas aleatorias contra cargas ordenadas.")
    if re.search(r"hash|rehash|bucket|load", body, re.I) or cat == "hash":
        notes.append("Medir colisiones, rehashes y factor de carga bajo claves adversariales.")
    if bm.raw_index_ops:
        notes.append("Instrumentar operaciones de índice y entradas de borde.")
    if bm.loops:
        notes.append("Medir crecimiento con varios valores de n; verificar el modelo empírico contra la complejidad esperada.")
    if not notes:
        notes.append("Usar como operación base de bajo overhead en cargas mixtas.")
    return notes


def build_performance_profiles(root: Path, headers_only: bool = False) -> list[ClassPerformanceProfile]:
    classes = scan_project(root, headers_only=headers_only)
    metrics = collect_bench_metrics(root, headers_only=headers_only)
    by_key: dict[tuple[str, str, int], BenchMetric] = {(m.class_name, m.method, m.line): m for m in metrics}
    profiles: list[ClassPerformanceProfile] = []
    for cls in classes:
        targets: list[PerformanceTarget] = []
        cat = _category(cls.name)
        for m in cls.methods:
            if m.body is None or m.name.startswith("~"):
                continue
            bm = by_key.get((cls.name, m.name, m.start_line))
            if not bm:
                continue
            body = _body(m)
            model = _complexity_model(cls, bm)
            targets.append(PerformanceTarget(
                class_name=cls.name,
                method=m.name,
                file=str(cls.file),
                line=m.start_line,
                category=cat,
                estimated_cost=bm.estimated_cost,
                complexity_model=model,
                workload=bm.workload_hint,
                counters=_method_counters(cls, bm),
                metrics={
                    "source_lines": bm.source_lines,
                    "loops": bm.loops,
                    "ramas": bm.branches,
                    "assignments": bm.assignments,
                    "raw_index_ops": bm.raw_index_ops,
                    "pointer_ops": bm.pointer_ops,
                    "static_score": bm.score,
                },
                risk=_risk(bm, model),
                notes=_notes(cls, bm, body),
            ))
        if targets:
            risk_score = sum({"low": 1, "medium": 3, "high": 7}.get(t.risk, 1) for t in targets)
            profiles.append(ClassPerformanceProfile(
                class_name=cls.name,
                file=str(cls.file),
                category=cat,
                targets=sorted(targets, key=lambda t: ({"high":0,"medium":1,"low":2}.get(t.risk, 3), -t.metrics["static_score"])),
                structure_counters=_counter_hints(cls),
                workloads=_workloads(cls),
                instrumentation_points=_instrumentation_points(cls, targets),
                risk_score=risk_score,
            ))
    return sorted(profiles, key=lambda p: (-p.risk_score, p.class_name))


def _instrumentation_points(cls: ClassModel, targets: list[PerformanceTarget]) -> list[str]:
    cat = _category(cls.name)
    points: list[str] = []
    if cat == "sequence":
        points += ["antes/después de operaciones que cambian capacidad", "dentro de rutas de validación de índices", "alrededor de bucles de copia/movimiento"]
    elif cat == "tree":
        points += ["antes/después de rotaciones", "durante comparaciones de descenso", "después de actualizaciones de altura/balance"]
    elif cat == "heap":
        points += ["dentro de bucles sift-up/sift-down", "en intercambios", "en comparaciones"]
    elif cat == "hash":
        points += ["en cada cálculo de hash", "en colisión de bucket", "antes/después de rehash"]
    elif cat == "range-query":
        points += ["en nodos visitados del árbol", "en operaciones de combinación", "en verificaciones de rangos de borde"]
    elif cat == "graph":
        points += ["en escaneos de aristas", "en recorrido de camino find", "en compresión de caminos"]
    else:
        points += ["entrada/salida", "iteraciones de bucle", "ramas"]
    if any(t.risk == "high" for t in targets):
        points.append("agregar temporizador de pared alrededor de métodos de alto riesgo")
    return points


def performance_report(root: Path, headers_only: bool = False, baseline: Path | None = None, regression_threshold: float = 20.0) -> ProjectReport:
    profiles = build_performance_profiles(root, headers_only=headers_only)
    report = ProjectReport(root=str(root))
    report.diagnostics.append(Diagnostic(
        level="INFO",
        code="PERF_SUMMARY",
        message=f"Perfil de rendimiento StructGuard 4.5 generado para {sum(len(p.targets) for p in profiles)} métodos en {len(profiles)} clases.",
        file=str(root),
        details={"classes": len(profiles), "methods": sum(len(p.targets) for p in profiles), "version": "4.5"},
    ))
    for p in profiles:
        level = "WARNING" if p.risk_score >= 20 else "INFO"
        report.diagnostics.append(Diagnostic(
            level=level,
            code="PERF_CLASS_PROFILE",
            message=f"{p.class_name}: {len(p.targets)} objetivos de benchmark, categoría={p.category}, risk_score={p.risk_score}.",
            file=p.file,
            symbol=p.class_name,
            details={
                "category": p.category,
                "risk_score": p.risk_score,
                "workloads": p.workloads,
                "counters": p.structure_counters,
                "top_targets": [asdict(t) for t in p.targets[:5]],
            },
        ))
    if baseline and baseline.exists():
        report.diagnostics.extend(compare_baseline(root, profiles, baseline, regression_threshold).diagnostics)
    elif baseline:
        report.diagnostics.append(Diagnostic(level="WARNING", code="PERF_BASELINE_MISSING", message=f"Archivo baseline no encontrado: {baseline}", file=str(baseline)))
    return report


def write_performance_json(profiles: list[ClassPerformanceProfile], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "4.5",
        "dataset_sizes": DATASET_SIZES,
        "profiles": [asdict(p) for p in profiles],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _estimated_series(model: str, n_values: list[int]) -> list[float]:
    vals: list[float] = []
    for n in n_values:
        if model == "constant":
            vals.append(1.0)
        elif model == "amortized_constant":
            vals.append(1.0 + math.log2(max(n, 2)) / 64.0)
        elif model == "logarithmic":
            vals.append(math.log2(max(n, 2)))
        elif model == "linear":
            vals.append(float(n))
        elif model == "quadratic":
            vals.append(float(n) * float(n))
        else:
            vals.append(float(n))
    first = vals[0] if vals and vals[0] else 1.0
    return [round(v / first, 3) for v in vals]


def write_growth_json(profiles: list[ClassPerformanceProfile], path: Path, sizes: list[int] | None = None) -> Path:
    sizes = sizes or DATASET_SIZES
    rows: list[dict[str, Any]] = []
    for p in profiles:
        for t in p.targets:
            rows.append({
                "class_name": p.class_name,
                "method": t.method,
                "model": t.complexity_model,
                "sizes": sizes,
                "normalized_expected_growth": _estimated_series(t.complexity_model, sizes),
                "risk": t.risk,
            })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": "4.5", "growth": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_performance_markdown(profiles: list[ClassPerformanceProfile], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Reporte de ingeniería de rendimiento StructGuard 4.5", ""]
    for p in profiles:
        lines.append(f"## {p.class_name}")
        lines.append("")
        lines.append(f"- Categoría: `{p.category}`")
        lines.append(f"- Puntaje de riesgo: `{p.risk_score}`")
        lines.append(f"- Contadores: {', '.join('`'+c+'`' for c in p.structure_counters)}")
        lines.append(f"- Cargas: {', '.join('`'+w+'`' for w in p.workloads)}")
        lines.append("")
        lines.append("| Método | Modelo | Riesgo | Costo estimado | Contadores |")
        lines.append("|---|---|---:|---|---|")
        for t in p.targets[:12]:
            lines.append(f"| `{t.method}` | `{t.complexity_model}` | `{t.risk}` | {t.estimated_cost} | {', '.join(t.counters[:6])} |")
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_performance_html(profiles: list[ClassPerformanceProfile], path: Path, title: str = "Ingeniería de rendimiento StructGuard 4.5") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    total_methods = sum(len(p.targets) for p in profiles)
    high = sum(1 for p in profiles for t in p.targets if t.risk == "high")
    medium = sum(1 for p in profiles for t in p.targets if t.risk == "medium")
    low = sum(1 for p in profiles for t in p.targets if t.risk == "low")
    rows = []
    for p in profiles:
        for t in p.targets:
            details = escape(json.dumps(asdict(t), indent=2, ensure_ascii=False))
            rows.append(f"<tr data-risk='{escape(t.risk)}' data-class='{escape(p.class_name)}'><td>{escape(p.class_name)}</td><td>{escape(t.method)}</td><td><span class='pill {escape(t.risk)}'>{escape(t.risk)}</span></td><td>{escape(t.complexity_model)}</td><td>{escape(t.estimated_cost)}</td><td>{escape(', '.join(t.counters[:8]))}</td><td><details><summary>detalles</summary><pre>{details}</pre></details></td></tr>")
    cards = f"""
    <div class='card'><span>CLASES</span><b>{len(profiles)}</b></div>
    <div class='card'><span>MÉTODOS</span><b>{total_methods}</b></div>
    <div class='card high'><span>RIESGO ALTO</span><b>{high}</b></div>
    <div class='card medium'><span>MEDIO</span><b>{medium}</b></div>
    <div class='card low'><span>BAJO</span><b>{low}</b></div>
    """
    sections = []
    for p in profiles:
        targets = "".join(f"<li><b>{escape(t.method)}</b>: {escape(t.complexity_model)} · <span class='pill {escape(t.risk)}'>{escape(t.risk)}</span><br><small>{escape(t.estimated_cost)}</small></li>" for t in p.targets[:10])
        points = "".join(f"<li>{escape(x)}</li>" for x in p.instrumentation_points)
        workloads = "".join(f"<code>{escape(w)}</code> " for w in p.workloads)
        counters = "".join(f"<code>{escape(c)}</code> " for c in p.structure_counters)
        sections.append(f"<section class='panel'><h2>{escape(p.class_name)}</h2><p><b>Categoría:</b> {escape(p.category)} · <b>Puntaje de riesgo:</b> {p.risk_score}</p><p><b>Cargas:</b> {workloads}</p><p><b>Contadores:</b> {counters}</p><h3>Puntos de instrumentación</h3><ul>{points}</ul><h3>Objetivos principales</h3><ul>{targets}</ul></section>")
    raw = escape(json.dumps({"profiles": [asdict(p) for p in profiles]}, indent=2, ensure_ascii=False))
    html = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{escape(title)}</title><style>
body{{margin:0;background:#f8fafc;color:#0f172a;font-family:system-ui,-apple-system,Segoe UI,sans-serif}}header{{padding:2rem;background:linear-gradient(135deg,#111827,#334155);color:white}}main{{padding:1rem;max-width:1280px;margin:auto}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem;margin:1rem 0}}.card,.panel{{background:white;border:1px solid #e5e7eb;border-radius:1rem;padding:1rem;box-shadow:0 8px 24px #0f172a12}}.card span{{display:block;color:#64748b;font-size:.75rem;font-weight:800;letter-spacing:.08em}}.card b{{font-size:2rem}}.high{{border-top:4px solid #dc2626}}.medium{{border-top:4px solid #f59e0b}}.low{{border-top:4px solid #16a34a}}.pill{{border-radius:999px;padding:.15rem .45rem;font-weight:800;font-size:.75rem}}.pill.high{{background:#fee2e2;color:#991b1b}}.pill.medium{{background:#fef3c7;color:#92400e}}.pill.low{{background:#dcfce7;color:#166534}}code{{background:#e2e8f0;border-radius:.35rem;padding:.1rem .3rem}}table{{width:100%;border-collapse:collapse;font-size:.88rem}}th,td{{border-bottom:1px solid #e5e7eb;padding:.55rem;text-align:left;vertical-align:top}}th{{background:#f1f5f9;position:sticky;top:0}}pre{{background:#0b1020;color:#d1e7ff;padding:.75rem;border-radius:.75rem;overflow:auto}}input,select{{padding:.55rem;border:1px solid #cbd5e1;border-radius:.65rem}}
</style></head><body><header><h1>{escape(title)}</h1><p>Perfil estático de ingeniería de rendimiento, plan de cargas, contadores y artefactos de regresión.</p></header><main><section class='cards'>{cards}</section><section class='panel'><h2>Objetivos</h2><p><input id='q' placeholder='filtrar clase/método/modelo' oninput='filterRows()'> <select id='risk' onchange='filterRows()'><option value=''>todos los riesgos</option><option>high</option><option>medium</option><option>low</option></select></p><table id='targets'><thead><tr><th>Clase</th><th>Método</th><th>Riesgo</th><th>Modelo</th><th>Costo estimado</th><th>Contadores</th><th>Detalles</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>{''.join(sections)}<section class='panel'><h2>JSON crudo del perfil</h2><details><summary>mostrar</summary><pre>{raw}</pre></details></section></main><script>function filterRows(){{let q=document.getElementById('q').value.toLowerCase();let r=document.getElementById('risk').value;document.querySelectorAll('#targets tbody tr').forEach(tr=>{{let ok=(!q||tr.innerText.toLowerCase().includes(q))&&(!r||tr.dataset.risk===r);tr.style.display=ok?'':'none';}});}}</script></body></html>"""
    path.write_text(html, encoding="utf-8")
    return path


def write_perf_harness(profiles: list[ClassPerformanceProfile], path: Path) -> Path:
    """Escribe un esqueleto de harness C++ autocontenido con contadores de instrumentación.

    Intencionalmente no instancia todas las clases detectadas porque las plantillas
    CC-232 usan constructores distintos. El archivo generado es un punto de partida
    con contadores, temporizadores y espacios para cargas de trabajo.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    includes = sorted({Path(p.file).name for p in profiles if p.file.endswith((".h", ".hpp", ".hh", ".hxx"))})[:40]
    lines = [
        "// Generado por StructGuard 4.5 Performance Engineering.",
        "// Adapta llamadas a constructores y rutas include a la estructura de tu proyecto.",
        "#include <chrono>",
        "#include <cstdint>",
        "#include <iostream>",
        "#include <random>",
        "#include <string>",
        "#include <vector>",
        "",
    ]
    for inc in includes:
        lines.append(f'#include "{inc}"')
    lines += [
        "",
        "struct SGPerfCounters {",
        "  std::uint64_t calls = 0;",
        "  std::uint64_t comparisons = 0;",
        "  std::uint64_t rotations = 0;",
        "  std::uint64_t reallocations = 0;",
        "  std::uint64_t collisions = 0;",
        "  std::uint64_t rehashes = 0;",
        "  std::uint64_t visited_nodes = 0;",
        "};",
        "",
        "template <class F>",
        "auto time_ms(F&& f) {",
        "  auto start = std::chrono::steady_clock::now();",
        "  f();",
        "  auto end = std::chrono::steady_clock::now();",
        "  return std::chrono::duration_cast<std::chrono::microseconds>(end - start).count() / 1000.0;",
        "}",
        "",
        "int main() {",
        "  const std::vector<int> sizes = {128, 512, 2048, 8192, 32768};",
        "  std::mt19937 rng(123456);",
        "  std::cout << \"structure,workload,n,elapsed_ms,calls,comparisons,rotations,reallocations,collisions,rehashes,visited_nodes\\n\";",
        "",
        "  // TODO: instanciar estructuras y conectar contadores. Objetivos sugeridos:",
    ]
    for p in profiles[:50]:
        lines.append(f"  // {p.class_name}: workloads={', '.join(p.workloads)} counters={', '.join(p.structure_counters)}")
        for t in p.targets[:3]:
            lines.append(f"  //   - {t.method}: {t.complexity_model}, {t.estimated_cost}")
    lines += [
        "",
        "  // Patrón de ejemplo:",
        "  // for (int n : sizes) {",
        "  //   SGPerfCounters c;",
        "  //   auto elapsed = time_ms([&] {",
        "  //     for (int i = 0; i < n; ++i) { /* structure.add(i); ++c.calls; */ }",
        "  //   });",
        "  //   std::cout << \"MyStructure,random_insert,\" << n << ',' << elapsed << ',' << c.calls << ',' << c.comparisons << ',' << c.rotations << ',' << c.reallocations << ',' << c.collisions << ',' << c.rehashes << ',' << c.visited_nodes << \"\\n\";",
        "  // }",
        "  return 0;",
        "}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def compare_baseline(root: Path, profiles: list[ClassPerformanceProfile], baseline: Path, threshold_percent: float = 20.0) -> ProjectReport:
    report = ProjectReport(root=str(root))
    try:
        data = json.loads(baseline.read_text(encoding="utf-8"))
    except Exception as e:
        report.diagnostics.append(Diagnostic(level="WARNING", code="PERF_BASELINE_READ_FAILED", message=str(e), file=str(baseline)))
        return report
    # Acepta un JSON de performance de StructGuard o un diccionario compacto indexado por Class::method.
    current: dict[str, int] = {}
    for p in profiles:
        for t in p.targets:
            current[f"{p.class_name}::{t.method}"] = int(t.metrics.get("static_score", 0))
    old: dict[str, float] = {}
    if isinstance(data, dict) and "profiles" in data:
        for p in data.get("profiles", []):
            for t in p.get("targets", []):
                old[f"{p.get('class_name')}::{t.get('method')}"] = float(t.get("metrics", {}).get("static_score", 0))
    elif isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, (int, float)):
                old[str(k)] = float(v)
    regressions = 0
    for k, score in current.items():
        if k in old and old[k] > 0:
            delta = ((score - old[k]) / old[k]) * 100.0
            if delta > threshold_percent:
                regressions += 1
                report.diagnostics.append(Diagnostic(
                    level="FAILED",
                    code="PERF_STATIC_REGRESSION",
                    message=f"{k} tuvo una regresión de puntaje estático de rendimiento de {delta:.1f}% sobre el umbral {threshold_percent:.1f}%.",
                    symbol=k,
                    details={"old_score": old[k], "new_score": score, "delta_percent": round(delta, 2), "threshold_percent": threshold_percent},
                ))
    report.diagnostics.append(Diagnostic(
        level="INFO" if regressions == 0 else "WARNING",
        code="PERF_BASELINE_COMPARE",
        message=f"Se compararon {len(current)} objetivos actuales contra {len(old)} objetivos baseline; regresiones={regressions}.",
        file=str(baseline),
        details={"regressions": regressions, "current_targets": len(current), "baseline_targets": len(old)},
    ))
    return report
