from __future__ import annotations

import itertools
import re
from pathlib import Path
from typing import Any

from .cppscan import scan_project
from .dsl import apply_dsl_contracts, load_dsl
from .expr import ExprError, parse_expr, vars_in_expressions, normalize_expr
from .model import ClassModel, Contract, Diagnostic, MethodModel, ProjectReport
from .counterexample import explain_counterexample
from .standard_contracts import standard_invariants, standard_requires, standard_ensures
from .clang_bridge import merge_clang_structural_model

ASSIGN_RE = re.compile(r"\b([A-Za-z_]\w*)\s*(\+=|-=|(?<![=!<>])=(?!=))\s*([^;]+);")
RETURN_RE = re.compile(r"\breturn\s+([^;]+);")
ASSERT_RE = re.compile(r"\bassert\s*\((.*?)\)\s*;", re.S)
UNSUPPORTED_BODY_RE = re.compile(r"\b(for|while|switch|try|catch|new|delete)\b")
IF_RE = re.compile(r"\bif\s*\(")

DEFAULT_DOMAIN = [-2, -1, 0, 1, 2, 3, 4]
NONNEG_DOMAIN = [0, 1, 2, 3, 4, 5]
CAPACITY_DOMAIN = [1, 2, 3, 4, 5, 8]

KEYWORDS = {
    "return", "if", "else", "for", "while", "int", "bool", "size_t", "void", "true", "false",
    "assert", "std", "cout", "endl", "max", "min", "array", "T", "const", "auto", "nullptr", "new", "delete",
}


def size_symbol(cls: ClassModel) -> str | None:
    for cand in ("n", "size_", "n_", "_size", "count", "count_"):
        if cand in cls.fields:
            return cand
    return None


def capacity_symbol(cls: ClassModel) -> str | None:
    for cand in ("capacity_", "_capacity", "cap", "cap_"):
        if cand in cls.fields:
            return cand
    if "a" in cls.fields:
        return "capacity_"
    return None


def likely_domain(var: str) -> list[int]:
    low = var.lower()
    if "capacity" in low or low in {"cap", "cap_"}:
        return CAPACITY_DOMAIN
    if any(x in low for x in ["size", "count", "n", "top", "front", "back", "rank", "height", "j"]):
        return NONNEG_DOMAIN
    return DEFAULT_DOMAIN


def _safe_vars(expr: str) -> set[str]:
    try:
        return parse_expr(expr).vars()
    except ExprError:
        return set()


def extract_assert_exprs(body: str | None) -> list[str]:
    if not body:
        return []
    return [" ".join(m.group(1).split()) for m in ASSERT_RE.finditer(body)]


def extract_body_vars(body: str | None) -> set[str]:
    if not body:
        return set()
    out: set[str] = set()
    cleaned = ASSERT_RE.sub("", body)
    for m in ASSIGN_RE.finditer(cleaned):
        lhs = m.group(1)
        if lhs not in KEYWORDS:
            out.add(lhs)
        out |= _safe_vars(normalize_expr(m.group(3)))
    for m in RETURN_RE.finditer(cleaned):
        out |= _safe_vars(normalize_expr(m.group(1)))
    for m in re.finditer(r"\b[A-Za-z_]\w*\s*\[([^\]]+)\]", cleaned):
        out |= _safe_vars(normalize_expr(m.group(1)))
    for m in re.finditer(r"(?:\+\+|--)\s*\b([A-Za-z_]\w*)\b|\b([A-Za-z_]\w*)\b\s*(?:\+\+|--)", cleaned):
        var = m.group(1) or m.group(2)
        if var and var not in KEYWORDS:
            out.add(var)
    # La capacidad de arreglos CC-232 usa a.length, se rastrea como capacity_.
    if re.search(r"\ba\s*\.\s*length\b", body):
        out.add("capacity_")
    return {v for v in out if v not in KEYWORDS and not v[0].isupper()}


def contract_exprs(contracts: list[Contract]) -> list[str]:
    return [c.expression for c in contracts]


def clean_statement_expr(expr: str) -> str:
    return normalize_expr(expr.strip())


def _split_top_level_commas(text: str) -> list[str]:
    """Divide una lista de inicialización C++ sin dividir llamadas/plantillas anidadas."""
    parts: list[str] = []
    start = 0
    depth = 0
    angle = 0
    quote = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in {'"', "'"}:
            quote = ch
        elif ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth = max(0, depth - 1)
        elif ch == "<":
            angle += 1
        elif ch == ">" and angle:
            angle -= 1
        elif ch == "," and depth == 0 and angle == 0:
            parts.append(text[start:i].strip())
            start = i + 1
        i += 1
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def extract_initializer_assignments(signature: str, method: MethodModel) -> tuple[list[tuple[str, str]], list[str]]:
    """Extrae asignaciones simples de listas de inicialización de constructores/miembros C++.

    Las formas soportadas son intencionalmente pequeñas, pero cubren constructores
    idiomáticos de estructuras de datos: `field(expr)`, `field{expr}` y `field = expr`.
    Los inicializadores con múltiples argumentos y los de clases base se reportan
    como notas y se omiten.
    """
    notes: list[str] = []
    if method.name != method.class_name or ":" not in signature:
        return [], notes
    sig = signature.replace("\n", " ")
    brace = sig.find("{")
    if brace != -1:
        sig = sig[:brace]
    # Find the constructor parameter-list close, not the last ')' in `field(expr)`.
    open_paren = sig.find("(")
    close = -1
    if open_paren != -1:
        depth = 0
        for idx in range(open_paren, len(sig)):
            if sig[idx] == "(":
                depth += 1
            elif sig[idx] == ")":
                depth -= 1
                if depth == 0:
                    close = idx
                    break
    colon = sig.find(":", close + 1 if close != -1 else 0)
    if colon == -1:
        return [], notes
    init_text = sig[colon + 1 :].strip()
    if not init_text:
        return [], notes
    assignments: list[tuple[str, str]] = []
    for item in _split_top_level_commas(init_text):
        item = item.strip()
        m = re.match(r"^([A-Za-z_]\w*)\s*\((.*)\)\s*$", item, re.S)
        if not m:
            m = re.match(r"^([A-Za-z_]\w*)\s*\{(.*)\}\s*$", item, re.S)
        if m:
            field, expr = m.group(1), m.group(2).strip()
            args = _split_top_level_commas(expr)
            if len(args) == 1 and args[0]:
                assignments.append((field, normalize_expr(args[0])))
            elif not args or expr == "":
                assignments.append((field, "0"))
            else:
                notes.append(f"el inicializador de {field} tiene {len(args)} argumentos; omitido")
            continue
        m = re.match(r"^([A-Za-z_]\w*)\s*=\s*(.+)$", item, re.S)
        if m:
            assignments.append((m.group(1), normalize_expr(m.group(2).strip())))
            continue
        # Los inicializadores de clases base son C++ válido; están fuera del modelo de estado actual.
        if re.match(r"^[A-Z]\w*\s*[({]", item):
            notes.append(f"inicializador de clase base omitido: {item[:80]}")
        else:
            notes.append(f"entrada de lista de inicialización no soportada omitida: {item[:80]}")
    return assignments, notes


def infer_class_invariants(cls: ClassModel) -> list[Contract]:
    existing = {c.expression for c in cls.invariants}
    out: list[Contract] = []
    def add(expr: str) -> None:
        if expr not in existing:
            out.append(Contract(kind="invariant", expression=expr, line=cls.start_line, source="inferred-cc232"))
            existing.add(expr)
    sz = size_symbol(cls)
    cap = capacity_symbol(cls)
    if sz:
        add(f"{sz} >= 0")
    if cap:
        add(f"{cap} >= 1")
    if sz and cap:
        add(f"{sz} <= {cap}")
    if "j" in cls.fields:
        add("j >= 0")
        if cap:
            add(f"j < {cap}")
    for c in standard_invariants(cls):
        if c.expression not in existing:
            out.append(c)
            existing.add(c.expression)
    return out

def infer_method_requires(method: MethodModel, cls: ClassModel | None = None) -> list[Contract]:
    out: list[Contract] = []
    seen = {c.expression for c in method.requires}
    for expr in extract_assert_exprs(method.body):
        if expr not in seen:
            out.append(Contract(kind="requires", expression=expr, line=method.start_line, source="inferred-assert"))
            seen.add(expr)
    if cls is not None:
        for c in standard_requires(cls, method):
            if c.expression not in seen:
                out.append(c)
                seen.add(c.expression)
    return out


def infer_method_ensures(cls: ClassModel, method: MethodModel) -> list[Contract]:
    """Postcondiciones conservadoras incorporadas para accesores comunes de CC-232."""
    name = method.name.lower().replace("~", "")
    existing = {c.expression for c in method.ensures}
    out: list[Contract] = []
    sz = size_symbol(cls)
    cap = capacity_symbol(cls)
    def add(expr: str) -> None:
        if expr not in existing:
            out.append(Contract(kind="ensures", expression=expr, line=method.start_line, source="inferred-cc232"))
    body = method.body or ""
    if sz:
        if "if" not in body and re.search(rf"\b{re.escape(sz)}\s*(\+\+|=\s*{re.escape(sz)}\s*\+\s*1|\+=\s*1)", body):
            add(f"{sz} == old({sz}) + 1")
        if "if" not in body and re.search(rf"\b{re.escape(sz)}\s*(--|=\s*{re.escape(sz)}\s*-\s*1|-=\s*1)", body):
            add(f"{sz} == old({sz}) - 1")
        if name == "clear" and re.search(rf"\b{re.escape(sz)}\s*=\s*0\s*;", body):
            add(f"{sz} == 0")
        if name == "size" and re.search(rf"return\s+{re.escape(sz)}\s*;", body):
            add(f"result == {sz}")
        if name == "empty" and re.search(rf"return\s+{re.escape(sz)}\s*==\s*0\s*;", body):
            add(f"result == ({sz} == 0)")
    if cap and name == "capacity":
        if re.search(rf"return\s+{re.escape(cap)}\s*;", body) or re.search(r"return\s+a\s*\.\s*length\s*;", body):
            add(f"result == {cap}")
    for c in standard_ensures(cls, method):
        if c.expression not in existing:
            out.append(c)
            existing.add(c.expression)
    return out

def model_resize(current: dict[str, int]) -> None:
    n = int(current.get("n", current.get("size_", 0)))
    cap = int(current.get("capacity_", current.get("capacity", 1)))
    current["capacity_"] = max(cap, max(1, 2 * n, n + 1))




def _strip_comments_for_exec(src: str) -> str:
    src = re.sub(r"//.*", "", src)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return src


def _find_matching(text: str, open_pos: int, open_ch: str, close_ch: str) -> int:
    depth = 0
    quote = ""
    i = open_pos
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in {'"', "'"}:
            quote = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _skip_ws(text: str, pos: int) -> int:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def _read_statement_or_block(text: str, pos: int) -> tuple[str, int]:
    pos = _skip_ws(text, pos)
    if pos >= len(text):
        return "", pos
    if text[pos] == "{":
        end = _find_matching(text, pos, "{", "}")
        if end == -1:
            return text[pos + 1 :], len(text)
        return text[pos + 1 : end], end + 1
    depth = 0
    quote = ""
    i = pos
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch in {'"', "'"}:
            quote = ch
        elif ch in "([{" :
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            return text[pos : i + 1], i + 1
        i += 1
    return text[pos:].strip(), len(text)


def _scan_exec_nodes(body: str | None) -> tuple[list[tuple], list[str]]:
    notes: list[str] = []
    if not body:
        return [], notes
    text = _strip_comments_for_exec(ASSERT_RE.sub("", body))
    nodes: list[tuple] = []
    i = 0
    while i < len(text):
        i = _skip_ws(text, i)
        if i >= len(text):
            break
        if re.match(r"if\b", text[i:]):
            pos = i + 2
            pos = _skip_ws(text, pos)
            if pos >= len(text) or text[pos] != "(":
                stmt, i = _read_statement_or_block(text, i)
                if stmt.strip():
                    nodes.append(("stmt", stmt.strip()))
                continue
            close = _find_matching(text, pos, "(", ")")
            if close == -1:
                notes.append("no se pudo parsear la condición if; se usa una sentencia lineal como fallback")
                stmt, i = _read_statement_or_block(text, i)
                if stmt.strip():
                    nodes.append(("stmt", stmt.strip()))
                continue
            cond = normalize_expr(text[pos + 1 : close].strip())
            then_body, next_pos = _read_statement_or_block(text, close + 1)
            next_pos = _skip_ws(text, next_pos)
            else_body = ""
            if re.match(r"else\b", text[next_pos:]):
                else_body, next_pos = _read_statement_or_block(text, next_pos + 4)
            nodes.append(("if", cond, then_body, else_body))
            i = next_pos
            continue
        stmt, i = _read_statement_or_block(text, i)
        if stmt.strip():
            nodes.append(("stmt", stmt.strip()))
    return nodes, notes


def _execute_simple_statement(line: str, old_env: dict[str, int], current: dict[str, int], result: Any) -> tuple[dict[str, int], Any, list[str], bool]:
    notes: list[str] = []
    if not line.strip():
        return current, result, notes, False
    if not line.strip().endswith(";"):
        line = line.strip() + ";"
    if "resize()" in line or re.search(r"\bresize\s*\(", line):
        model_resize(current)
    for mm in re.finditer(r"(\+\+|--)?\s*\b([A-Za-z_]\w*)\b\s*(\+\+|--)?\s*;", line):
        pre, var, post = mm.group(1), mm.group(2), mm.group(3)
        if var in KEYWORDS:
            continue
        op = pre or post
        if op == "++":
            current[var] = int(current.get(var, old_env.get(var, 0))) + 1
        elif op == "--":
            current[var] = int(current.get(var, old_env.get(var, 0))) - 1
    am = ASSIGN_RE.search(line)
    if am:
        var, op, rhs = am.group(1), am.group(2), clean_statement_expr(am.group(3))
        if var not in KEYWORDS:
            try:
                val = parse_expr(rhs).eval(current, old_env, result)
            except Exception:
                notes.append(f"no se pudo evaluar el lado derecho de la asignación: {rhs}")
            else:
                if op == "=":
                    current[var] = int(val)
                elif op == "+=":
                    current[var] = int(current.get(var, old_env.get(var, 0))) + int(val)
                elif op == "-=":
                    current[var] = int(current.get(var, old_env.get(var, 0))) - int(val)
    rm = RETURN_RE.search(line)
    did_return = False
    if rm:
        rhs = clean_statement_expr(rm.group(1))
        try:
            result = parse_expr(rhs).eval(current, old_env, result)
            did_return = True
        except Exception:
            notes.append(f"no se pudo evaluar la expresión de retorno: {rhs}")
            did_return = True
    return current, result, notes, did_return


def _execute_nodes(
    nodes: list[tuple],
    old_env: dict[str, int],
    current: dict[str, int],
    result: Any,
    notes: list[str],
    *,
    max_paths: int = 64,
) -> list[tuple[dict[str, int], Any, list[str]]]:
    paths: list[tuple[dict[str, int], Any, list[str], bool]] = [(dict(current), result, list(notes), False)]
    for node in nodes:
        next_paths: list[tuple[dict[str, int], Any, list[str], bool]] = []
        if node[0] == "stmt":
            for state, res, ns, done in paths:
                if done:
                    next_paths.append((state, res, ns, done))
                    continue
                st, rr, added, did_return = _execute_simple_statement(node[1], old_env, dict(state), res)
                next_paths.append((st, rr, ns + added, did_return))
        elif node[0] == "if":
            _, cond, then_body, else_body = node
            then_nodes, then_notes = _scan_exec_nodes(then_body)
            else_nodes, else_notes = _scan_exec_nodes(else_body)
            for state, res, ns, done in paths:
                if done:
                    next_paths.append((state, res, ns, done))
                    continue
                try:
                    cond_value = bool(parse_expr(cond).eval(state, old_env, res))
                    selected = then_nodes if cond_value else else_nodes
                    branch_notes = then_notes if cond_value else else_notes
                    branch_note = f"condición de camino: {cond} es {'true' if cond_value else 'false'}"
                    for st, rr, added in _execute_nodes(selected, old_env, dict(state), res, ns + branch_notes + [branch_note], max_paths=max_paths):
                        returned = bool(RETURN_RE.search(then_body if cond_value else else_body))
                        next_paths.append((st, rr, added, returned))
                except Exception:
                    # Si la condición no es modelable, explorar ambas ramas conserva seguridad.
                    fork_note = f"no se pudo evaluar la condición de rama: {cond}; se exploraron ambas ramas"
                    for st, rr, added in _execute_nodes(then_nodes, old_env, dict(state), res, ns + then_notes + [fork_note], max_paths=max_paths):
                        next_paths.append((st, rr, added, bool(RETURN_RE.search(then_body))))
                    for st, rr, added in _execute_nodes(else_nodes, old_env, dict(state), res, ns + else_notes + [fork_note], max_paths=max_paths):
                        next_paths.append((st, rr, added, bool(RETURN_RE.search(else_body))))
        paths = next_paths[:max_paths]
        if len(next_paths) > max_paths and paths:
            paths.append((dict(paths[-1][0]), paths[-1][1], list(paths[-1][2]) + ["se alcanzó el límite de caminos simbólicos"], paths[-1][3]))
    return [(state, res, ns) for state, res, ns, _ in paths]


def execute_body_paths(
    body: str | None,
    old_env: dict[str, int],
    current: dict[str, int],
    *,
    initializer_assignments: list[tuple[str, str]] | None = None,
    initializer_notes: list[str] | None = None,
    max_paths: int = 64,
) -> list[tuple[dict[str, int], Any, list[str]]]:
    notes: list[str] = list(initializer_notes or [])
    result: Any = None
    for field, rhs in initializer_assignments or []:
        try:
            current[field] = int(parse_expr(rhs).eval(current, old_env, result))
        except Exception:
            notes.append(f"no se pudo evaluar el inicializador de constructor para {field}: {rhs}")
    if not body:
        if initializer_assignments:
            return [(current, result, notes)]
        return [(current, result, notes + ["el método no tiene cuerpo; solo se analizan declaraciones con lint"])]
    if UNSUPPORTED_BODY_RE.search(body):
        notes.append("el cuerpo usa construcciones fuera del subconjunto del intérprete acotado")
    nodes, scan_notes = _scan_exec_nodes(body)
    notes.extend(scan_notes)
    if not nodes:
        return [(current, result, notes)]
    return _execute_nodes(nodes, old_env, current, result, notes, max_paths=max_paths)
def execute_body(
    body: str | None,
    old_env: dict[str, int],
    current: dict[str, int],
    *,
    initializer_assignments: list[tuple[str, str]] | None = None,
    initializer_notes: list[str] | None = None,
) -> tuple[dict[str, int], Any, list[str]]:
    notes: list[str] = list(initializer_notes or [])
    result: Any = None
    for field, rhs in initializer_assignments or []:
        try:
            current[field] = int(parse_expr(rhs).eval(current, old_env, result))
        except Exception:
            notes.append(f"no se pudo evaluar el inicializador de constructor para {field}: {rhs}")
    if not body:
        if initializer_assignments:
            return current, result, notes
        return current, result, ["el método no tiene cuerpo; solo se analizan declaraciones con lint"]
    if UNSUPPORTED_BODY_RE.search(body):
        notes.append("el cuerpo usa construcciones fuera del subconjunto del intérprete acotado")
    if IF_RE.search(body):
        notes.append("el cuerpo contiene ramas; el intérprete acotado usa una aproximación lineal conservadora")

    body = ASSERT_RE.sub("", body)
    # La ejecución basada en punto y coma captura varias sentencias por línea física.
    statements = [s.strip() for s in body.replace("\n", " ").split(";") if s.strip()]
    for stmt in statements:
        line = stmt + ";"
        if "resize()" in line or re.search(r"\bresize\s*\(", line):
            model_resize(current)
        for mm in re.finditer(r"(\+\+|--)?\s*\b([A-Za-z_]\w*)\b\s*(\+\+|--)?\s*;", line):
            pre, var, post = mm.group(1), mm.group(2), mm.group(3)
            if var in KEYWORDS:
                continue
            op = pre or post
            if op == "++":
                current[var] = int(current.get(var, old_env.get(var, 0))) + 1
            elif op == "--":
                current[var] = int(current.get(var, old_env.get(var, 0))) - 1
        am = ASSIGN_RE.search(line)
        if am:
            var, op, rhs = am.group(1), am.group(2), clean_statement_expr(am.group(3))
            # Omite escrituras a temporales locales salvo que afecten campos lógicos rastreados.
            if var in KEYWORDS:
                continue
            try:
                val = parse_expr(rhs).eval(current, old_env, result)
            except Exception:
                notes.append(f"no se pudo evaluar el lado derecho de la asignación: {rhs}")
                continue
            if op == "=":
                current[var] = int(val)
            elif op == "+=":
                current[var] = int(current.get(var, old_env.get(var, 0))) + int(val)
            elif op == "-=":
                current[var] = int(current.get(var, old_env.get(var, 0))) - int(val)
        rm = RETURN_RE.search(line)
        if rm:
            rhs = clean_statement_expr(rm.group(1))
            try:
                result = parse_expr(rhs).eval(current, old_env, result)
            except Exception:
                # Métodos comunes de CC-232 devuelven valores T desde arreglos; result no afecta invariantes.
                notes.append(f"no se pudo evaluar la expresión de retorno: {rhs}")
    return current, result, notes


def is_size_underflow_failure(contract: Contract, method: MethodModel, requires: list[Contract]) -> bool:
    expr = contract.expression.replace(" ", "")
    if not expr.endswith(">=0"):
        return False
    var = expr[:-3]
    if any(var in r.expression and (">0" in r.expression.replace(" ", "") or "!empty" in r.expression.replace(" ", "")) for r in requires):
        return False
    body = method.body or ""
    return bool(re.search(rf"\b{re.escape(var)}\s*(--|=\s*{re.escape(var)}\s*-\s*1|-=\s*1)", body))


def unsupported_failure_level(contract: Contract, method: MethodModel, notes: list[str] | set[str], requires: list[Contract]) -> tuple[str, str]:
    if is_size_underflow_failure(contract, method, requires):
        return "FAILED", "INVARIANT_NOT_PRESERVED"
    if contract.source != "declared" and notes:
        return "UNKNOWN", "POTENTIAL_FAILURE_UNSUPPORTED"
    return "FAILED", "INVARIANT_NOT_PRESERVED"




def _is_uncertainty_note(note: str) -> bool:
    low = note.lower()
    return any(token in low for token in ("could not", "no se pudo", "unsupported", "no soportad", "outside", "fuera", "limit reached", "límite", "skipped", "omitid", "unavailable", "no disponible"))


def _assumed_requires(requires: list[Contract]) -> list[Contract]:
    # Los contratos de biblioteca estándar son útiles como sugerencias/obligaciones,
    # pero no deben ocultar un bug de implementación convirtiéndose automáticamente en supuestos.
    return [r for r in requires if not r.source.startswith("standard-library")]

def verify_method(cls: ClassModel, method: MethodModel, max_cases: int = 20000, infer: bool = True) -> Diagnostic:
    if method.body is None:
        return Diagnostic(
            level="UNKNOWN",
            code="NO_BODY",
            message=f"{method.qualified_name} no tiene cuerpo inline/en cabecera; StructGuard no puede verificar la implementación.",
            file=str(cls.file),
            line=method.start_line,
            symbol=method.qualified_name,
        )

    invariants = cls.invariants + (infer_class_invariants(cls) if infer else [])
    requires = method.requires + (infer_method_requires(method, cls) if infer else [])
    ensures = method.ensures + (infer_method_ensures(cls, method) if infer else [])

    if not (invariants or requires or ensures):
        return Diagnostic(
            level="UNKNOWN",
            code="NO_CONTRACTS_FOR_METHOD",
            message=f"{method.qualified_name} tiene cuerpo, pero no tiene contratos declarados ni inferidos.",
            file=str(cls.file),
            line=method.start_line,
            symbol=method.qualified_name,
        )

    expressions = contract_exprs(invariants + requires + ensures)
    variables = vars_in_expressions(expressions) | extract_body_vars(method.body)
    sz_alias = size_symbol(cls)
    cap_alias = capacity_symbol(cls)
    if any("size()" in e or "empty()" in e for e in expressions) and sz_alias:
        variables.add(sz_alias)
    if (any("capacity()" in e for e in expressions) or "capacity_" in variables) and cap_alias:
        variables.add(cap_alias)
    variables -= {method.name, cls.name, "std", "cout", "endl", "x", "y", "k", "i", "j_", "lo", "hi", "oldElem"}
    variables = {v for v in variables if v and not v[0].isupper() and v not in KEYWORDS}
    # Descarta variables de payload no rastreadas; StructGuard verifica invariantes de forma/tamaño.
    variables -= {"a", "b", "x", "y"}
    if len(variables) > 8:
        return Diagnostic(
            level="UNKNOWN",
            code="TOO_MANY_SYMBOLS",
            message=f"{method.qualified_name} tiene {len(variables)} variables simbólicas; el modelo acotado lo omitió.",
            file=str(cls.file),
            line=method.start_line,
            symbol=method.qualified_name,
            details={"variables": sorted(variables)},
        )

    try:
        parsed_invariants = [(c, parse_expr(c.expression)) for c in invariants]
        parsed_requires = [(c, parse_expr(c.expression)) for c in _assumed_requires(requires)]
        parsed_ensures = [(c, parse_expr(c.expression)) for c in ensures]
    except ExprError as e:
        return Diagnostic(
            level="UNKNOWN",
            code="CONTRACT_PARSE_ERROR",
            message=f"{method.qualified_name} tiene una expresión de contrato no soportada: {e}",
            file=str(cls.file),
            line=method.start_line,
            symbol=method.qualified_name,
            details={"contracts": expressions},
        )

    var_list = sorted(variables)
    domains = [likely_domain(v) for v in var_list]
    checked = 0
    skipped = 0
    body_notes_seen: set[str] = set()

    explored = 0
    for values in itertools.product(*domains):
        explored += 1
        if explored > max_cases * 5:
            body_notes_seen.add("la búsqueda acotada se detuvo tras alcanzar el límite de exploración")
            break
        old = dict(zip(var_list, values))
        # Mantiene alias coherentes para nombres comunes de CC-232.
        if "capacity_" in old:
            old.setdefault("capacity", old["capacity_"])
        current = dict(old)
        try:
            assumptions_ok = all(expr.eval(old, old) for _, expr in parsed_invariants) and all(
                expr.eval(old, old) for _, expr in parsed_requires
            )
        except Exception:
            skipped += 1
            continue
        if not assumptions_ok:
            skipped += 1
            continue
        checked += 1
        if checked > max_cases:
            break
        init_assignments, init_notes = extract_initializer_assignments(method.signature, method)
        paths = execute_body_paths(method.body, old, current, initializer_assignments=init_assignments, initializer_notes=init_notes)
        for after, result, notes in paths:
            body_notes_seen.update(n for n in notes if _is_uncertainty_note(n))
            for contract, expr in parsed_ensures:
                try:
                    if not bool(expr.eval(after, old, result)):
                        lvl = "UNKNOWN" if contract.source != "declared" and notes else "FAILED"
                        code = "POTENTIAL_POSTCONDITION_FAILURE_UNSUPPORTED" if lvl == "UNKNOWN" else "POSTCONDITION_FAILED"
                        return Diagnostic(
                            level=lvl,
                            code=code,
                            message=f"{method.qualified_name} podría violar ensures: {contract.expression}",
                            file=str(cls.file),
                            line=contract.line or method.start_line,
                            symbol=method.qualified_name,
                            details={"contract_source": contract.source, "counterexample_old": old, "state_after": after, "result": result, "notes": sorted(set(notes)), "symbolic_paths": len(paths), "counterexample": explain_counterexample(method, contract, old, after, result, sorted(set(notes)))},
                        )
                except Exception as e:
                    return Diagnostic(
                        level="UNKNOWN",
                        code="POSTCONDITION_EVAL_ERROR",
                        message=f"No se pudo evaluar la postcondición en {method.qualified_name}: {e}",
                        file=str(cls.file),
                        line=contract.line or method.start_line,
                        symbol=method.qualified_name,
                    )
            for contract, expr in parsed_invariants:
                try:
                    if not bool(expr.eval(after, old, result)):
                        lvl, code = unsupported_failure_level(contract, method, notes, requires)
                        return Diagnostic(
                            level=lvl,
                            code=code,
                            message=f"{method.qualified_name} podría violar el invariante: {contract.expression}",
                            file=str(cls.file),
                            line=contract.line or method.start_line,
                            symbol=method.qualified_name,
                            details={"contract_source": contract.source, "counterexample_old": old, "state_after": after, "result": result, "notes": sorted(set(notes)), "symbolic_paths": len(paths), "counterexample": explain_counterexample(method, contract, old, after, result, sorted(set(notes)))},
                        )
                except Exception as e:
                    return Diagnostic(
                        level="UNKNOWN",
                        code="INVARIANT_EVAL_ERROR",
                        message=f"No se pudo evaluar el invariante en {method.qualified_name}: {e}",
                        file=str(cls.file),
                        line=contract.line or method.start_line,
                        symbol=method.qualified_name,
                    )

    if checked == 0:
        return Diagnostic(
            level="UNKNOWN",
            code="NO_FEASIBLE_STATE",
            message=f"{method.qualified_name} no tuvo estados acotados que satisfagan invariantes y precondiciones.",
            file=str(cls.file),
            line=method.start_line,
            symbol=method.qualified_name,
            details={"skipped_states": skipped, "variables": var_list, "explored_states": locals().get("explored", 0)},
        )

    level = "BOUNDED_VERIFIED"
    code = "BOUNDED_CONTRACTS_HOLD"
    msg = f"{method.qualified_name} se mantiene en el modelo acotado de StructGuard; esto no es una prueba formal."
    details: dict[str, Any] = {
        "checked_states": checked,
        "variables": var_list,
        "executor": "branch_aware_bounded_interpreter",
        "inferred_invariants": [c.expression for c in invariants if c.source != "declared"],
        "inferred_requires": [c.expression for c in requires if c.source != "declared"],
        "inferred_ensures": [c.expression for c in ensures if c.source != "declared"],
        "verification_scope": "bounded_model",
        "evidence": "bounded_exhaustive_over_selected_domains",
        "frontend": "clang_structural_preferred" if locals().get("clang_metadata") else "cppscan",
    }
    init_assignments, init_notes = extract_initializer_assignments(method.signature, method)
    if init_assignments:
        details["constructor_initializers"] = [{"field": field, "expr": expr} for field, expr in init_assignments]
    if init_notes:
        details.setdefault("notes", []).extend(init_notes)
    if body_notes_seen:
        level = "UNKNOWN"
        code = "PARTIAL_VERIFICATION"
        msg = f"{method.qualified_name} verificó estados acotados, pero la implementación usó construcciones no soportadas."
        details["notes"] = sorted(body_notes_seen)
    return Diagnostic(
        level=level,
        code=code,
        message=msg,
        file=str(cls.file),
        line=method.start_line,
        symbol=method.qualified_name,
        details=details,
    )


def verify_project(root: Path, headers_only: bool = False, infer: bool = True, max_cases: int = 20000, dsl_paths: list[str] | None = None, clang_structural: bool = False, clang: str | None = None, std: str = "c++17", max_files: int | None = 30, timeout: int = 12) -> ProjectReport:
    report = ProjectReport(root=str(root))
    classes = scan_project(root, headers_only=headers_only)
    clang_metadata = None
    if clang_structural:
        classes, clang_metadata = merge_clang_structural_model(classes, root, headers_only=headers_only, clang=clang, std=std, max_files=max_files, timeout=timeout)
        report.diagnostics.append(Diagnostic(level="INFO", code="CLANG_STRUCTURAL_MODEL", message="El modelo estructural AST de Clang se usó como índice preferente de clases/campos cuando estuvo disponible.", file=str(root), details=clang_metadata))
    dsl_diagnostics = []
    if dsl_paths:
        try:
            dsl_diagnostics = apply_dsl_contracts(classes, load_dsl(dsl_paths))
        except Exception as e:
            report.diagnostics.append(Diagnostic(level="FAILED", code="DSL_LOAD_ERROR", message=str(e), file=str(root)))
    if not classes:
        report.diagnostics.append(Diagnostic(level="WARNING", code="NO_CLASSES", message="No se detectaron clases/structs C++.", file=str(root)))
        return report

    any_contracts = any(c.invariants or any(m.requires or m.ensures or m.assertions for m in c.methods) for c in classes)
    if not any_contracts and not infer:
        report.diagnostics.append(
            Diagnostic(level="WARNING", code="NO_CONTRACTS", message="Se encontraron clases, pero no se detectaron anotaciones de contratos.", file=str(root))
        )

    report.diagnostics.extend(dsl_diagnostics)

    for cls in classes:
        for method in cls.methods:
            # Omite destructores triviales y constructores sin contratos/efectos de cuerpo,
            # a menos que los invariantes inferidos puedan ser de ayuda.
            if method.name.startswith("~"):
                continue
            if method.body is None and not (method.requires or method.ensures):
                continue
            report.diagnostics.append(verify_method(cls, method, max_cases=max_cases, infer=infer))
    if not report.diagnostics:
        report.diagnostics.append(Diagnostic(level="INFO", code="NO_VERIFIABLE_METHODS", message="No se encontraron métodos verificables."))
    return report
