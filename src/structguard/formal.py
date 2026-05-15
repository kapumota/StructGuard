from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import re
import subprocess
import shutil
from typing import Any

from .cppscan import scan_project
from .dsl import apply_dsl_contracts, load_dsl
from .expr import Binary, Bool, Call, ExprError, Ident, Node, Number, Unary, parse_expr, normalize_expr
from .model import ClassModel, Contract, Diagnostic, MethodModel, ProjectReport
from .verifier import infer_class_invariants, infer_method_ensures, infer_method_requires, ASSIGN_RE, RETURN_RE, extract_body_vars, contract_exprs, size_symbol, capacity_symbol, extract_initializer_assignments


@dataclass
class FormalArtifact:
    backend: str
    file: str
    symbol: str
    status: str
    notes: list[str]


def _contracts_for(cls: ClassModel, m: MethodModel, infer: bool = True) -> tuple[list[Contract], list[Contract], list[Contract]]:
    inv = list(cls.invariants)
    req = list(m.requires)
    ens = list(m.ensures)
    if infer:
        inv += infer_class_invariants(cls)
        req += infer_method_requires(m, cls)
        ens += infer_method_ensures(cls, m)
    return inv, req, ens


def _all_vars(cls: ClassModel, m: MethodModel, inv: list[Contract], req: list[Contract], ens: list[Contract]) -> set[str]:
    out = set(cls.fields)
    out |= extract_body_vars(m.body)
    for e in contract_exprs(inv + req + ens):
        try:
            out |= parse_expr(e).vars()
        except ExprError:
            pass
    # Símbolos de estado anterior y capacidad suelen aparecer mediante llamadas auxiliares.
    if any("capacity" in e.expression or "capacity" in e.expression for e in inv + req + ens):
        out.add("capacity_")
    return {v for v in out if v and not v[0].isupper() and v not in {"true", "false", "result"}}



def _array_symbols(cls: ClassModel, m: MethodModel) -> set[str]:
    text = "\n".join([m.body or "", " ".join(cls.fields)])
    arrays = set(re.findall(r"\b([A-Za-z_]\w*)\s*\[", m.body or ""))
    # Campos comunes de estructuras de datos modelados como arreglos Int si se usan con [].
    arrays |= {f for f in cls.fields if f in {"data_", "a", "items_", "buffer_"} and re.search(rf"\b{re.escape(f)}\s*\[", m.body or "")}
    return {a for a in arrays if a not in {"if", "for", "while", "return"}}


def _normalize_array_expr_for_smt(expr: str) -> str:
    # Convierte lecturas unidimensionales C++ como data_[i] en una llamada select_*.
    return re.sub(r"\b([A-Za-z_]\w*)\s*\[([^\]]+)\]", r"select_\1(\2)", expr)

def _node_sort(node: Node, sort_env: dict[str, str] | None = None) -> str:
    """Inferencia mínima de sorts de expresiones para generación SMT."""
    sort_env = sort_env or {}
    if isinstance(node, Bool):
        return "Bool"
    if isinstance(node, Number):
        return "Int"
    if isinstance(node, Ident):
        return sort_env.get(node.name, "Int")
    if isinstance(node, Unary):
        return "Bool" if node.op == "!" else "Int"
    if isinstance(node, Binary):
        if node.op in {"&&", "||", "==", "!=", "<", "<=", ">", ">="}:
            return "Bool"
        return "Int"
    if isinstance(node, Call):
        if node.name in {"empty", "is_empty", "valid", "contains"}:
            return "Bool"
        if node.name in {"size", "capacity", "parent", "left", "right", "old"}:
            if node.name == "old" and node.args:
                return _node_sort(node.args[0], sort_env)
            return "Int"
        # Las llamadas no interpretadas se tratan como predicados, salvo que una
        # versión posterior agregue declaraciones de función con firmas tipadas.
        return "Bool"
    return "Int"


def _expr_sort(expr: str, sort_env: dict[str, str] | None = None) -> str:
    try:
        return _node_sort(parse_expr(expr), sort_env)
    except ExprError:
        return "Bool"


def _infer_result_sort(method: MethodModel, ensures: list[Contract]) -> str:
    signature_prefix = method.signature.split("(", 1)[0]
    if re.search(r"\bbool\b", signature_prefix):
        return "Bool"
    body = method.body or ""
    returns = [m.group(1) for m in RETURN_RE.finditer(body)]
    if returns and any(_expr_sort(normalize_expr(r), {"result": "Bool"}) == "Bool" for r in returns):
        return "Bool"
    for c in ensures:
        try:
            node = parse_expr(c.expression)
        except ExprError:
            continue
        if isinstance(node, Binary) and node.op in {"==", "!="}:
            left_result = isinstance(node.left, Ident) and node.left.name == "result"
            right_result = isinstance(node.right, Ident) and node.right.name == "result"
            if left_result and _node_sort(node.right, {"result": "Int"}) == "Bool":
                return "Bool"
            if right_result and _node_sort(node.left, {"result": "Int"}) == "Bool":
                return "Bool"
    return "Int"


class SmtTranslator:
    def __init__(self, *, old_state: bool = False, size_var: str = "n", capacity_var: str = "capacity_", sort_env: dict[str, str] | None = None):
        self.old_state = old_state
        self.size_var = size_var
        self.capacity_var = capacity_var
        self.sort_env = sort_env or {}
        self.unsupported: list[str] = []

    def ident(self, name: str) -> str:
        if name == "result":
            return "result"
        return f"old_{name}" if self.old_state else name

    def emit(self, node: Node) -> str:
        if isinstance(node, Number):
            return str(node.value)
        if isinstance(node, Bool):
            return "true" if node.value else "false"
        if isinstance(node, Ident):
            return self.ident(node.name)
        if isinstance(node, Unary):
            inner = self.emit(node.inner)
            if node.op == "!":
                return f"(not {inner})"
            if node.op == "-":
                return f"(- {inner})"
        if isinstance(node, Binary):
            l = self.emit(node.left); r = self.emit(node.right)
            opmap = {"&&": "and", "||": "or", "==": "=", "!=": "distinct", "+": "+", "-": "-", "*": "*", "/": "div", "%": "mod", "<": "<", "<=": "<=", ">": ">", ">=": ">="}
            op = opmap.get(node.op)
            if op:
                return f"({op} {l} {r})"
        if isinstance(node, Call):
            if node.name.startswith("select_") and len(node.args) == 1:
                arr = node.name[len("select_"):]
                return f"(select {'old_' if self.old_state else ''}{arr} {self.emit(node.args[0])})"
            if node.name == "old" and len(node.args) == 1:
                return SmtTranslator(old_state=True, size_var=self.size_var, capacity_var=self.capacity_var, sort_env=self.sort_env).emit(node.args[0])
            if node.name == "size":
                return self.ident(self.size_var)
            if node.name == "capacity":
                return self.ident(self.capacity_var)
            if node.name == "empty":
                return f"(= {self.ident(self.size_var)} 0)"
            if node.name in {"parent", "left", "right"} and len(node.args) == 1:
                arg = self.emit(node.args[0])
                if node.name == "parent": return f"(div (- {arg} 1) 2)"
                if node.name == "left": return f"(+ (* 2 {arg}) 1)"
                if node.name == "right": return f"(+ (* 2 {arg}) 2)"
            # Trata predicados desconocidos como funciones booleanas no interpretadas.
            args = " ".join(self.emit(a) for a in node.args)
            return f"({node.name} {args})" if args else node.name
        self.unsupported.append(str(node))
        return "true"


def smt_expr(expr: str, *, old_state: bool = False, size_var: str = "n", capacity_var: str = "capacity_", sort_env: dict[str, str] | None = None) -> tuple[str, list[str]]:
    try:
        expr = _normalize_array_expr_for_smt(expr)
        tr = SmtTranslator(old_state=old_state, size_var=size_var, capacity_var=capacity_var, sort_env=sort_env)
        return tr.emit(parse_expr(expr)), tr.unsupported
    except ExprError as e:
        return "true", [f"expresión no soportada {expr!r}: {e}"]


def _assignment_semantics(body: str | None, *, size_var: str = "n", capacity_var: str = "capacity_", sort_env: dict[str, str] | None = None) -> tuple[list[str], list[str]]:
    """Devuelve aserciones SMT que relacionan variables antiguas/actuales para asignaciones simples."""
    notes: list[str] = []
    assertions: list[str] = []
    if not body:
        notes.append("cuerpo del método no disponible; las obligaciones generadas usan solo contratos")
        return assertions, notes
    for am in re.finditer(r"\b([A-Za-z_]\w*)\s*\[([^\]]+)\]\s*=\s*([^;]+);", body):
        arr, idx, rhs = am.group(1), normalize_expr(am.group(2)), normalize_expr(am.group(3))
        smt_idx, u1 = smt_expr(idx, old_state=True, size_var=size_var, capacity_var=capacity_var, sort_env=sort_env)
        smt_rhs, u2 = smt_expr(rhs, old_state=True, size_var=size_var, capacity_var=capacity_var, sort_env=sort_env)
        notes.extend(u1); notes.extend(u2)
        assertions.append(f"(assert (= {arr} (store old_{arr} {smt_idx} {smt_rhs})))")
    for m in ASSIGN_RE.finditer(body):
        lhs, op, rhs = m.group(1), m.group(2), normalize_expr(m.group(3))
        smt_rhs, unsupported = smt_expr(rhs, old_state=True, size_var=size_var, capacity_var=capacity_var, sort_env=sort_env)
        notes.extend(unsupported)
        if op == "=":
            assertions.append(f"(assert (= {lhs} {smt_rhs}))")
        elif op == "+=":
            assertions.append(f"(assert (= {lhs} (+ old_{lhs} {smt_rhs})))")
        elif op == "-=":
            assertions.append(f"(assert (= {lhs} (- old_{lhs} {smt_rhs})))")
    for m in re.finditer(r"\b([A-Za-z_]\w*)\s*(\+\+|--)\s*;", body):
        var, op = m.group(1), m.group(2)
        delta = "1" if op == "++" else "-1"
        assertions.append(f"(assert (= {var} (+ old_{var} {delta})))")
    for m in RETURN_RE.finditer(body):
        rhs = normalize_expr(m.group(1))
        smt_rhs, unsupported = smt_expr(rhs, old_state=False, size_var=size_var, capacity_var=capacity_var, sort_env=sort_env)
        notes.extend(unsupported)
        assertions.append(f"(assert (= result {smt_rhs}))")
    if not assertions:
        notes.append("no se extrajo semántica de asignación simple; se usan defaults de frame")
    return assertions, notes


def smt_for_method(cls: ClassModel, m: MethodModel, *, infer: bool = True) -> tuple[str, list[str]]:
    inv, req, ens = _contracts_for(cls, m, infer=infer)
    vars_ = sorted(_all_vars(cls, m, inv, req, ens))
    sz = size_symbol(cls) or "n"
    cap = capacity_symbol(cls) or "capacity_"
    vars_.extend(v for v in [sz, cap] if v and v not in vars_)
    vars_ = sorted(set(vars_))
    result_sort = _infer_result_sort(m, ens)
    sort_env = {"result": result_sort}
    notes: list[str] = []
    lines = ["; Generado por el puente formal de StructGuard", "(set-logic ALL)", ""]
    arrays = sorted(_array_symbols(cls, m))
    for v in vars_:
        if v in arrays:
            continue
        lines.append(f"(declare-const old_{v} Int)")
        lines.append(f"(declare-const {v} Int)")
    for arr in arrays:
        lines.append(f"(declare-const old_{arr} (Array Int Int))")
        lines.append(f"(declare-const {arr} (Array Int Int))")
    lines.append(f"(declare-const result {result_sort})")
    # Defaults de frame: si ninguna semántica asigna una variable, se conserva sin cambios.
    # Esta regla conservadora se aplica solo a variables no asignadas.
    assigned = {m.group(1) for m in ASSIGN_RE.finditer(m.body or "")}
    assigned |= {m.group(1) for m in re.finditer(r"\b([A-Za-z_]\w*)\s*(?:\+\+|--)\s*;", m.body or "")}
    init_assignments, init_notes = extract_initializer_assignments(m.signature, m)
    assigned |= {field for field, _ in init_assignments}
    notes.extend(init_notes)
    if RETURN_RE.search(m.body or ""):
        assigned.add("result")
    lines.append("")
    lines.append("; Precondiciones e invariantes de clase en el estado anterior")
    for c in inv + req:
        s, u = smt_expr(c.expression, old_state=True, size_var=sz, capacity_var=cap, sort_env=sort_env); notes.extend(u)
        lines.append(f"(assert {s}) ; {c.kind}: {c.expression}")
    lines.append("")
    lines.append("; Semántica simple del método extraída desde C++")
    sem, sem_notes = _assignment_semantics(m.body, size_var=sz, capacity_var=cap, sort_env=sort_env)
    notes.extend(sem_notes)
    for field, rhs in init_assignments:
        smt_rhs, unsupported = smt_expr(rhs, old_state=False, size_var=sz, capacity_var=cap, sort_env=sort_env)
        notes.extend(unsupported)
        sem.append(f"(assert (= {field} {smt_rhs})) ; constructor initializer")
    for v in vars_:
        if v in arrays:
            continue
        if v not in assigned:
            lines.append(f"(assert (= {v} old_{v})) ; frame")
    array_assigned = set(re.findall(r"\b([A-Za-z_]\w*)\s*\[", m.body or ""))
    for arr in arrays:
        if arr not in array_assigned:
            lines.append(f"(assert (= {arr} old_{arr})) ; array frame")
    lines.extend(sem)
    lines.append("")
    lines.append("; Intentar refutar postcondiciones y preservación de invariantes")
    goals=[]
    for c in ens:
        s, u = smt_expr(c.expression, old_state=False, size_var=sz, capacity_var=cap, sort_env=sort_env); notes.extend(u)
        goals.append(s)
    for c in inv:
        s, u = smt_expr(c.expression, old_state=False, size_var=sz, capacity_var=cap, sort_env=sort_env); notes.extend(u)
        goals.append(s)
    if goals:
        lines.append(f"(assert (not (and {' '.join(goals)})))")
    else:
        lines.append("; No hay postcondiciones ni invariantes disponibles; la consulta es vacía.")
        lines.append("(assert false)")
    lines.extend(["(check-sat)", ""])
    return "\n".join(lines), notes


def _viper_name(name: str) -> str:
    return re.sub(r"\W+", "_", name)


def _to_viper_expr(expr: str, *, old_state: bool = False, size_var: str = "n", capacity_var: str = "capacity_") -> str:
    # Emisor ligero de expresiones tipo Viper. Diseñado como artefacto puente, no como lowering completo a Viper.
    e = normalize_expr(expr)
    e = e.replace("!empty()", f"{size_var} != 0")
    e = e.replace("empty()", f"{size_var} == 0")
    e = e.replace("size()", size_var).replace("capacity()", capacity_var)
    e = re.sub(r"old\(([^()]+)\)", r"old(\1)", e)
    return e


def viper_for_method(cls: ClassModel, m: MethodModel, *, infer: bool = True) -> tuple[str, list[str]]:
    inv, req, ens = _contracts_for(cls, m, infer=infer)
    notes = ["La salida Viper es un modelo puente: los contratos se traducen y el cuerpo C++ se resume como comentarios."]
    method_name = _viper_name(m.qualified_name)
    sz = size_symbol(cls) or "n"
    cap = capacity_symbol(cls) or "capacity_"
    lines = [f"// Generado por el puente formal de StructGuard para {m.qualified_name}", f"method {method_name}()", "  requires true"]
    for c in inv + req:
        lines.append(f"  requires {_to_viper_expr(c.expression, old_state=True, size_var=sz, capacity_var=cap)} // {c.source}")
    for c in ens + inv:
        lines.append(f"  ensures {_to_viper_expr(c.expression, size_var=sz, capacity_var=cap)} // {c.kind}:{c.source}")
    lines.append("{")
    if m.body:
        short = " ".join(m.body.split())[:1000]
        lines.append(f"  // Resumen del cuerpo C++: {short}")
    else:
        lines.append("  // cuerpo C++ no disponible")
    lines.append("}")
    lines.append("")
    return "\n".join(lines), notes


def write_formal_artifacts(
    root: Path,
    out_dir: Path,
    *,
    backend: str = "both",
    headers_only: bool = False,
    infer: bool = True,
    dsl_paths: list[str] | None = None,
    run_solver: bool = False,
) -> tuple[list[FormalArtifact], ProjectReport]:
    out_dir.mkdir(parents=True, exist_ok=True)
    classes = scan_project(root, headers_only=headers_only)
    dsl_contracts = load_dsl(dsl_paths)
    dsl_diagnostics = apply_dsl_contracts(classes, dsl_contracts) if dsl_contracts else []
    artifacts: list[FormalArtifact] = []
    report = ProjectReport(root=str(root), diagnostics=list(dsl_diagnostics))
    if not classes:
        report.diagnostics.append(Diagnostic(level="WARNING", code="FORMAL_NO_CLASSES", message="No se encontraron clases para la exportación formal.", file=str(root)))
        return artifacts, report
    z3_bin = shutil.which("z3")
    for cls in classes:
        for m in cls.methods:
            if backend in {"smt", "both"}:
                content, notes = smt_for_method(cls, m, infer=infer)
                name = f"{_viper_name(m.qualified_name)}.smt2"
                path = out_dir / "smt" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                status = "EXPORTED"
                details: dict[str, Any] = {"artifact": str(path), "notes": notes, "solver_semantics": "PROVED solo significa que la obligación generada por el puente SMT fue insatisfacible; BOUNDED_VERIFIED nunca es emitido por el solver."}
                level = "INFO"
                if run_solver and z3_bin:
                    try:
                        proc = subprocess.run([z3_bin, str(path)], text=True, capture_output=True, timeout=8)
                        details["z3_stdout"] = proc.stdout.strip()
                        details["z3_stderr"] = proc.stderr.strip()
                        first = (proc.stdout.strip().splitlines() or [""])[0]
                        if first == "unsat":
                            status = "PROVED"
                            level = "PROVED"
                        elif first == "sat":
                            status = "COUNTEREXAMPLE"
                            level = "FAILED"
                            # Solicita un modelo solo después de que Z3 confirma SAT. Mantener
                            # el artefacto verificado sin `(get-model)` evita el mensaje ruidoso
                            # "model is not available" en obligaciones UNSAT/PROVED.
                            model_proc = subprocess.run(
                                [z3_bin, "-in"],
                                input=content + "\n(get-model)\n",
                                text=True,
                                capture_output=True,
                                timeout=8,
                            )
                            details["z3_model_stdout"] = model_proc.stdout.strip()
                            details["z3_model_stderr"] = model_proc.stderr.strip()
                        else:
                            status = "UNKNOWN"
                            level = "UNKNOWN"
                    except Exception as e:
                        details["solver_error"] = str(e)
                        status = "EXPORTED"
                elif run_solver and not z3_bin:
                    details["solver"] = "z3 no encontrado; solo se exportó el artefacto"
                artifacts.append(FormalArtifact("smt", str(path), m.qualified_name, status, notes))
                report.diagnostics.append(Diagnostic(level=level, code="FORMAL_SMT_ARTIFACT", message=f"Artefacto SMT-LIB generado para {m.qualified_name}.", file=str(cls.file), line=m.start_line, symbol=m.qualified_name, details=details))
            if backend in {"viper", "both"}:
                content, notes = viper_for_method(cls, m, infer=infer)
                name = f"{_viper_name(m.qualified_name)}.vpr"
                path = out_dir / "viper" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                artifacts.append(FormalArtifact("viper", str(path), m.qualified_name, "EXPORTED", notes))
                report.diagnostics.append(Diagnostic(level="INFO", code="FORMAL_VIPER_ARTIFACT", message=f"Artefacto puente Viper generado para {m.qualified_name}.", file=str(cls.file), line=m.start_line, symbol=m.qualified_name, details={"artifact": str(path), "notes": notes}))
    manifest = out_dir / "formal_manifest.json"
    manifest.write_text(json.dumps([asdict(a) for a in artifacts], indent=2, ensure_ascii=False), encoding="utf-8")
    report.diagnostics.append(Diagnostic(level="INFO", code="FORMAL_MANIFEST", message="Manifiesto de artefactos formales escrito.", file=str(manifest), details={"artifacts": len(artifacts), "manifest": str(manifest), "backend": backend}))
    return artifacts, report
