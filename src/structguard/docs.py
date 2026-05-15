from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import html
import json
import re
from typing import Any

from .cppscan import scan_project
from .dsl import apply_dsl_contracts, load_dsl
from .model import ClassModel, Contract, Diagnostic, ProjectReport
from .verifier import infer_class_invariants, infer_method_requires, infer_method_ensures, size_symbol, capacity_symbol


@dataclass
class OperationDoc:
    name: str
    qualified_name: str
    signature: str
    file: str
    line: int
    category: str
    has_body: bool
    requires: list[dict[str, Any]] = field(default_factory=list)
    ensures: list[dict[str, Any]] = field(default_factory=list)
    assertions: list[dict[str, Any]] = field(default_factory=list)
    inferred_requires: list[dict[str, Any]] = field(default_factory=list)
    inferred_ensures: list[dict[str, Any]] = field(default_factory=list)
    empirical_cost: str = "desconocido"
    notes: list[str] = field(default_factory=list)


@dataclass
class StructureDoc:
    name: str
    file: str
    line: int
    fields: list[str]
    size_symbol: str | None
    capacity_symbol: str | None
    category: str
    invariants: list[dict[str, Any]] = field(default_factory=list)
    inferred_invariants: list[dict[str, Any]] = field(default_factory=list)
    operations: list[OperationDoc] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class DocumentationModel:
    root: str
    structures: list[StructureDoc]
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, int]:
        ops = sum(len(s.operations) for s in self.structures)
        declared_inv = sum(len(s.invariants) for s in self.structures)
        inferred_inv = sum(len(s.inferred_invariants) for s in self.structures)
        req = sum(len(o.requires) + len(o.inferred_requires) for s in self.structures for o in s.operations)
        ens = sum(len(o.ensures) + len(o.inferred_ensures) for s in self.structures for o in s.operations)
        bodies = sum(1 for s in self.structures for o in s.operations if o.has_body)
        return {
            "structures": len(self.structures),
            "operations": ops,
            "operations_with_body": bodies,
            "declared_invariants": declared_inv,
            "inferred_invariants": inferred_inv,
            "requires": req,
            "ensures": ens,
            "diagnostics": len(self.diagnostics),
        }


def _contract_to_dict(c: Contract) -> dict[str, Any]:
    return {"kind": c.kind, "expression": c.expression, "line": c.line, "source": c.source}


def _clean_signature(sig: str) -> str:
    return " ".join(sig.replace("{", "").strip().split())


def _category_for_class(cls: ClassModel) -> str:
    name = cls.name.lower()
    if "heap" in name:
        return "cola de prioridad / heap"
    if "avl" in name:
        return "árbol balanceado"
    if "bst" in name or "tree" in name:
        return "árbol"
    if "hash" in name or "dictionary" in name or "map" in name:
        return "hash/mapa"
    if "queue" in name:
        return "cola"
    if "stack" in name:
        return "pila"
    if "deque" in name:
        return "deque"
    if "array" in name or "list" in name:
        return "secuencia"
    if "fenwick" in name:
        return "consulta de rango"
    if "segment" in name:
        return "consulta de rango"
    if "disjoint" in name or "dsu" in name or "union" in name:
        return "conjunto disjunto"
    if "graph" in name:
        return "grafo"
    return "estructura de datos"


def _category_for_method(name: str) -> str:
    lower = name.lower().replace("~", "")
    if lower in {"size", "empty", "capacity", "height", "contains", "find", "search", "get", "top", "front", "back", "peek"}:
        return "consulta/acceso"
    if lower in {"add", "push", "insert", "enqueue", "append", "put", "set", "union", "merge"}:
        return "actualización/inserción"
    if lower in {"remove", "pop", "dequeue", "erase", "delete", "clear"}:
        return "actualización/eliminación"
    if lower in {"resize", "rehash", "rotateleft", "rotateright", "siftup", "siftdown", "heapify"}:
        return "mantenimiento"
    if lower.startswith("~") or lower == "destroy":
        return "ciclo de vida"
    return "operación"


def _cost_hint(cls: ClassModel, name: str, body: str | None) -> str:
    cname = cls.name.lower()
    lower = name.lower().replace("~", "")
    body = body or ""
    if lower in {"size", "empty", "capacity", "top", "front", "back", "peek"}:
        return "O(1) esperado"
    if "hash" in cname and lower in {"find", "get", "set", "put", "insert", "remove"}:
        return "O(1) esperado; O(n) en el peor caso dependiendo de colisiones"
    if any(t in cname for t in ["avl", "bst", "tree", "btree"]):
        if lower in {"find", "search", "contains", "insert", "remove", "erase", "add"}:
            return "O(h); O(log n) cuando se mantiene el invariante de balance"
    if "heap" in cname and lower in {"push", "pop", "add", "remove", "insert"}:
        return "O(log n) esperado por la altura del heap"
    if "array" in cname or "list" in cname or "deque" in cname or "queue" in cname or "stack" in cname:
        if lower in {"push", "pop", "add", "remove", "enqueue", "dequeue"}:
            if re.search(r"\bfor\b|\bwhile\b", body):
                return "O(n) en esta ruta de implementación; revisar bucles/redimensionamiento"
            return "O(1) esperado; amortizado si se usa redimensionamiento"
        if lower in {"get", "set"}:
            return "O(1) esperado para estructuras respaldadas por arreglo"
    if re.search(r"\bfor\b|\bwhile\b", body):
        return "bucle detectado; derivar cota desde la variable/invariante del bucle"
    return "no inferido"


def _notes_for_method(name: str, body: str | None, requires: list[Contract], assertions: list[Contract]) -> list[str]:
    notes: list[str] = []
    lname = name.lower().replace("~", "")
    req_expr = " && ".join(c.expression for c in requires)
    if lname in {"pop", "top", "front", "back", "remove", "dequeue", "get", "set"} and not requires and not assertions:
        notes.append("API de estilo inseguro: documentar una cláusula requires para verificaciones de vacío/límites.")
    if assertions and not requires:
        notes.append("Assert en tiempo de ejecución encontrado; considerar promoverlo a un contrato requires declarado.")
    if body and re.search(r"\bnew\b|\bdelete\b", body):
        notes.append("Gestión manual de memoria detectada; documentar ownership e invariantes de capacidad.")
    if body and re.search(r"\[[^\]]+\]", body) and not re.search(r"<|>|<=|>=|!empty|empty\(\)", req_expr):
        notes.append("Acceso indexado detectado; documentar límites de índice como precondición o invariante.")
    return notes


def build_documentation_model(root: Path, headers_only: bool = False, dsl_paths: list[str] | None = None, infer: bool = True) -> DocumentationModel:
    classes = scan_project(root, headers_only=headers_only)
    diagnostics: list[Diagnostic] = []
    if dsl_paths:
        try:
            diagnostics.extend(apply_dsl_contracts(classes, load_dsl(dsl_paths)))
        except Exception as e:
            diagnostics.append(Diagnostic(level="FAILED", code="DOCS_DSL_LOAD_ERROR", message=str(e), file=str(root)))
    structures: list[StructureDoc] = []
    for cls in classes:
        declared_inv = [_contract_to_dict(c) for c in cls.invariants]
        inferred_inv = []
        if infer:
            existing = {c.expression for c in cls.invariants}
            inferred_inv = [_contract_to_dict(c) for c in infer_class_invariants(cls) if c.expression not in existing]
        ops: list[OperationDoc] = []
        for m in cls.methods:
            inferred_req = []
            inferred_ens = []
            if infer:
                existing_req = {c.expression for c in m.requires}
                existing_ens = {c.expression for c in m.ensures}
                inferred_req = [_contract_to_dict(c) for c in infer_method_requires(m, cls) if c.expression not in existing_req]
                inferred_ens = [_contract_to_dict(c) for c in infer_method_ensures(cls, m) if c.expression not in existing_ens]
            notes = _notes_for_method(m.name, m.body, m.requires, m.assertions)
            ops.append(OperationDoc(
                name=m.name,
                qualified_name=m.qualified_name,
                signature=_clean_signature(m.signature),
                file=str(cls.file),
                line=m.start_line,
                category=_category_for_method(m.name),
                has_body=m.body is not None,
                requires=[_contract_to_dict(c) for c in m.requires],
                ensures=[_contract_to_dict(c) for c in m.ensures],
                assertions=[_contract_to_dict(c) for c in m.assertions],
                inferred_requires=inferred_req,
                inferred_ensures=inferred_ens,
                empirical_cost=_cost_hint(cls, m.name, m.body),
                notes=notes,
            ))
        notes=[]
        if not cls.invariants and inferred_inv:
            notes.append("No hay invariantes de clase declarados; los candidatos inferidos se muestran abajo.")
        if not ops:
            notes.append("El frontend ligero de C++ no detectó métodos.")
        structures.append(StructureDoc(
            name=cls.name,
            file=str(cls.file),
            line=cls.start_line,
            fields=sorted(cls.fields),
            size_symbol=size_symbol(cls),
            capacity_symbol=capacity_symbol(cls),
            category=_category_for_class(cls),
            invariants=declared_inv,
            inferred_invariants=inferred_inv,
            operations=ops,
            notes=notes,
        ))
    return DocumentationModel(root=str(root), structures=structures, diagnostics=[asdict(d) for d in diagnostics])


def _model_to_dict(model: DocumentationModel) -> dict[str, Any]:
    return {
        "root": model.root,
        "summary": model.summary(),
        "structures": [asdict(s) for s in model.structures],
        "diagnostics": model.diagnostics,
    }


def write_docs_json(model: DocumentationModel, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_model_to_dict(model), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def _md_contracts(items: list[dict[str, Any]]) -> str:
    if not items:
        return "_Ninguno._\n"
    return "\n".join(f"- `{x['expression']}` _{x.get('source','')}_" for x in items) + "\n"


def write_docs_markdown(model: DocumentationModel, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    index_lines = [f"# Documentación StructGuard", "", f"Raíz: `{model.root}`", "", "## Resumen", ""]
    for k, v in model.summary().items():
        index_lines.append(f"- **{k}**: {v}")
    index_lines += ["", "## Estructuras", ""]
    for st in model.structures:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", st.name)
        index_lines.append(f"- [{st.name}](structures/{safe}.md) — {st.category}, {len(st.operations)} operaciones")
        lines = [f"# {st.name}", "", f"**Categoría:** {st.category}", f"**Archivo:** `{st.file}:{st.line}`", ""]
        if st.fields:
            lines += ["## Campos", "", "\n".join(f"- `{f}`" for f in st.fields), ""]
        if st.notes:
            lines += ["## Notas", "", "\n".join(f"- {n}" for n in st.notes), ""]
        lines += ["## Invariantes", "", "### Declarados", "", _md_contracts(st.invariants), "### Candidatos inferidos", "", _md_contracts(st.inferred_invariants)]
        lines += ["## Operaciones", ""]
        for op in st.operations:
            lines += [f"### `{op.name}`", "", f"Firma: `{op.signature}`", f"Línea: `{op.line}`", f"Categoría: {op.category}", f"Costo estimado: **{op.empirical_cost}**", "", "**Requires**", "", _md_contracts(op.requires + op.inferred_requires), "**Ensures**", "", _md_contracts(op.ensures + op.inferred_ensures)]
            if op.assertions:
                lines += ["**Asserts en tiempo de ejecución**", "", _md_contracts(op.assertions)]
            if op.notes:
                lines += ["**Notas**", "", "\n".join(f"- {n}" for n in op.notes), ""]
        p = out_dir / "structures" / f"{safe}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines), encoding="utf-8")
    index = out_dir / "index.md"
    index.write_text("\n".join(index_lines), encoding="utf-8")
    return index


def write_docs_html(model: DocumentationModel, path: Path, title: str = "Documentación StructGuard") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = model.summary()
    cards = "".join(f"<div class='card'><b>{html.escape(k.replace('_',' ').title())}</b><span>{v}</span></div>" for k, v in summary.items())
    nav = "".join(f"<li><a href='#s-{html.escape(st.name)}'>{html.escape(st.name)}</a></li>" for st in model.structures[:120])
    sections=[]
    for st in model.structures:
        inv_decl = "".join(f"<li><code>{html.escape(x['expression'])}</code> <small>{html.escape(x.get('source',''))}</small></li>" for x in st.invariants) or "<li><em>Ninguno declarado.</em></li>"
        inv_inf = "".join(f"<li><code>{html.escape(x['expression'])}</code> <small>{html.escape(x.get('source',''))}</small></li>" for x in st.inferred_invariants) or "<li><em>Ninguno inferido.</em></li>"
        fields = "".join(f"<code>{html.escape(f)}</code> " for f in st.fields) or "<em>No se detectaron campos.</em>"
        notes = "".join(f"<li>{html.escape(n)}</li>" for n in st.notes)
        ops_rows=[]
        for op in st.operations:
            reqs = op.requires + op.inferred_requires
            enss = op.ensures + op.inferred_ensures
            req_html = "<br>".join(f"<code>{html.escape(c['expression'])}</code>" for c in reqs) or "<em>Ninguno</em>"
            ens_html = "<br>".join(f"<code>{html.escape(c['expression'])}</code>" for c in enss) or "<em>Ninguno</em>"
            note_html = "<br>".join(html.escape(n) for n in op.notes) or ""
            body_badge = "<span class='ok'>cuerpo</span>" if op.has_body else "<span class='warn'>declaración</span>"
            ops_rows.append(f"<tr><td><b>{html.escape(op.name)}</b><br><small>{body_badge} {html.escape(op.category)}</small></td><td><code>{html.escape(op.signature)}</code><br><small>línea {op.line}</small></td><td>{req_html}</td><td>{ens_html}</td><td>{html.escape(op.empirical_cost)}<br><small>{note_html}</small></td></tr>")
        sections.append(f"""
<section class='panel structure' id='s-{html.escape(st.name)}'>
  <h2>{html.escape(st.name)}</h2>
  <p><b>Categoría:</b> {html.escape(st.category)} · <b>Archivo:</b> <code>{html.escape(st.file)}:{st.line}</code></p>
  <p><b>Campos:</b> {fields}</p>
  {f"<ul class='notes'>{notes}</ul>" if notes else ""}
  <div class='grid2'><div><h3>Invariantes declarados</h3><ul>{inv_decl}</ul></div><div><h3>Candidatos de invariantes inferidos</h3><ul>{inv_inf}</ul></div></div>
  <h3>Operaciones</h3>
  <table><thead><tr><th>Operación</th><th>Firma</th><th>Requires</th><th>Ensures</th><th>Costo / Notas</th></tr></thead><tbody>{''.join(ops_rows) or '<tr><td colspan=5><em>No se detectaron operaciones.</em></td></tr>'}</tbody></table>
</section>""")
    raw = html.escape(json.dumps(_model_to_dict(model), indent=2, ensure_ascii=False))
    doc = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>
:root{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;color:#172033;background:#f6f7fb}}body{{margin:0}}header{{background:#0f172a;color:white;padding:2rem 2.5rem}}header h1{{margin:0 0 .35rem;font-size:2rem}}.layout{{display:grid;grid-template-columns:280px 1fr;gap:1.25rem;padding:1.25rem}}aside{{position:sticky;top:1rem;align-self:start;background:white;border:1px solid #e5e7eb;border-radius:1rem;padding:1rem;max-height:calc(100vh - 2rem);overflow:auto}}main{{min-width:0}}a{{color:#2563eb;text-decoration:none}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:.75rem;margin-bottom:1rem}}.card{{background:white;border:1px solid #e5e7eb;border-radius:1rem;padding:1rem;display:flex;justify-content:space-between;gap:.75rem;box-shadow:0 1px 2px rgba(0,0,0,.04)}}.card span{{font-size:1.4rem;font-weight:800}}.panel{{background:white;border:1px solid #e5e7eb;border-radius:1rem;padding:1rem;margin-bottom:1rem;box-shadow:0 1px 2px rgba(0,0,0,.04)}}.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:1rem}}code{{background:#eef2ff;color:#3730a3;border-radius:.4rem;padding:.12rem .28rem}}table{{width:100%;border-collapse:collapse;font-size:.92rem}}th,td{{border-bottom:1px solid #e5e7eb;padding:.65rem;vertical-align:top;text-align:left}}th{{background:#f8fafc}}.ok,.warn{{border-radius:999px;padding:.12rem .42rem;font-size:.72rem;font-weight:800}}.ok{{background:#dcfce7;color:#166534}}.warn{{background:#fef3c7;color:#92400e}}.notes{{background:#f8fafc;border-radius:.75rem;padding:.75rem 1.25rem}}pre{{white-space:pre-wrap;background:#111827;color:#e5e7eb;padding:1rem;border-radius:1rem;overflow:auto}}input{{width:100%;box-sizing:border-box;padding:.65rem;border-radius:.65rem;border:1px solid #cbd5e1;margin-bottom:.75rem}}@media(max-width:1000px){{.layout{{grid-template-columns:1fr}}aside{{position:static}}.grid2{{grid-template-columns:1fr}}}}
</style></head><body><header><h1>{html.escape(title)}</h1><p>Documentación generada para <code>{html.escape(model.root)}</code>. Los contratos pueden estar declarados, inferidos desde asserts, importados desde DSL o sugeridos por convenciones CC-232.</p></header><div class='layout'><aside><input id='filter' placeholder='Filtrar estructuras...' oninput='filterSections()'><h2>Estructuras</h2><ul>{nav}</ul><p><a href='#raw'>JSON crudo</a></p></aside><main><section class='cards'>{cards}</section>{''.join(sections)}<section class='panel' id='raw'><h2>JSON crudo</h2><details><summary>Mostrar modelo de documentación</summary><pre>{raw}</pre></details></section></main></div><script>function filterSections(){{const q=document.getElementById('filter').value.toLowerCase();document.querySelectorAll('.structure').forEach(s=>{{s.style.display=s.id.toLowerCase().includes(q)||s.innerText.toLowerCase().includes(q)?'':'none';}});}}</script></body></html>"""
    path.write_text(doc, encoding="utf-8")
    return path


def docs_report(model: DocumentationModel) -> ProjectReport:
    r = ProjectReport(root=model.root)
    summary = model.summary()
    r.diagnostics.append(Diagnostic(level="INFO", code="DOCS_GENERATED_MODEL", message=f"Modelo de documentación construido para {summary['structures']} estructuras y {summary['operations']} operaciones.", details=summary))
    for st in model.structures:
        if not st.invariants and not st.inferred_invariants:
            r.diagnostics.append(Diagnostic(level="WARNING", code="DOCS_NO_INVARIANTS", message=f"{st.name} no tiene invariantes declarados ni inferidos en el modelo de documentación.", file=st.file, line=st.line, symbol=st.name))
        if not st.operations:
            r.diagnostics.append(Diagnostic(level="WARNING", code="DOCS_NO_OPERATIONS", message=f"{st.name} no tiene operaciones en el modelo de documentación.", file=st.file, line=st.line, symbol=st.name))
    return r
