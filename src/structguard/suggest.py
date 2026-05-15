from __future__ import annotations

from dataclasses import dataclass, asdict
import difflib
import json
import re
from pathlib import Path
from typing import Iterable

from .cppscan import scan_project, iter_cpp_files, extract_assertions
from .lint import UNSAFE_METHOD_NAMES
from .model import ClassModel, Contract, Diagnostic, MethodModel, ProjectReport
from .verifier import infer_class_invariants, infer_method_ensures, size_symbol


@dataclass(frozen=True)
class ContractSuggestion:
    file: str
    line: int
    kind: str  # valores internos: invariant | requires | ensures
    expression: str
    symbol: str
    reason: str
    source: str = "suggested"

    @property
    def comment(self) -> str:
        return f"// {self.kind}: {self.expression}"


def _has_contract(existing: Iterable[Contract], kind: str, expr: str) -> bool:
    norm = lambda s: re.sub(r"\s+", "", s)
    target = norm(expr)
    return any(c.kind == kind and norm(c.expression) == target for c in existing)


def _method_requires_exprs(m: MethodModel) -> set[str]:
    norm = lambda s: re.sub(r"\s+", "", s)
    return {norm(c.expression) for c in m.requires}


def _add_unique(out: list[ContractSuggestion], seen: set[tuple[str, int, str, str, str]], s: ContractSuggestion) -> None:
    key = (s.file, s.line, s.kind, re.sub(r"\s+", "", s.expression), s.symbol)
    if key not in seen:
        seen.add(key)
        out.append(s)


def _class_contract_insert_line(cls: ClassModel, text: str) -> int:
    """Devuelve una línea 1-indexada después de la llave de apertura de la clase."""
    lines = text.splitlines()
    start = max(cls.start_line - 1, 0)
    for idx in range(start, min(len(lines), start + 12)):
        if "{" in lines[idx]:
            return idx + 2
    return cls.start_line + 1


def _method_contract_insert_line(m: MethodModel) -> int:
    # Inserta justo antes de la línea de definición/declaración. En definiciones template esto normalmente
    # significa debajo de template<class T> y encima de Class<T>::method(...), lo cual sigue siendo comentario C++ válido.
    return max(1, m.start_line)


def _unsafe_requires_for_method(cls: ClassModel, m: MethodModel) -> list[tuple[str, str]]:
    """Devuelve sugerencias (expr, razón) para operaciones inseguras comunes."""
    mlower = m.name.lower().replace("~", "")
    suggestions: list[tuple[str, str]] = []
    body = m.body or ""
    sig = m.signature or ""
    existing_norm = _method_requires_exprs(m)
    norm = lambda s: re.sub(r"\s+", "", s)

    # Promueve assert() a requires.
    for a in extract_assertions(body, m.start_line):
        if norm(a.expression) not in existing_norm:
            suggestions.append((a.expression, "promover assert(...) a una precondición explícita de API"))

    # Operaciones comunes de contenedores que requieren precondiciones de no vacío.
    if mlower in {"pop", "top", "front", "back", "peek", "dequeue"}:
        if norm("!empty()") not in existing_norm:
            suggestions.append(("!empty()", "la operación es insegura sobre una estructura de datos vacía"))

    # CC-232 usa remove() tanto en colas como en listas/pilas indexadas.
    if mlower == "remove":
        if re.search(r"\b(?:int|size_t|std::size_t)\s+i\b", sig):
            has_index_bound = any("i" in expr and ("<" in expr or "<=" in expr) for expr, _ in suggestions)
            expr = "0 <= i && i < size()"
            if not has_index_bound and norm(expr) not in existing_norm:
                suggestions.append((expr, "remove indexado necesita un índice dentro de límites"))
        else:
            # Si el cuerpo afirma n > 0, la promoción de assert lo cubrirá; si no, sugiere !empty().
            if not suggestions and norm("!empty()") not in existing_norm:
                suggestions.append(("!empty()", "la operación tipo remove es insegura sobre una estructura de datos vacía"))

    if mlower in {"get", "set"}:
        has_index_bound = any("i" in expr and ("<" in expr or "<=" in expr) for expr, _ in suggestions)
        expr = "0 <= i && i < size()"
        if not has_index_bound and norm(expr) not in existing_norm:
            suggestions.append((expr, "el acceso indexado necesita un índice dentro de límites"))

    # Métodos de arreglo/deque con variable de índice explícita en la firma.
    if re.search(r"\b(?:int|size_t|std::size_t)\s+i\b", sig) and mlower in {"add", "remove", "get", "set"}:
        # Si un assert ya dio un límite concreto como 0 <= i && i < n, no agregues un segundo
        # límite genérico basado en size().
        has_index_bound = any("i" in expr and ("<" in expr or "<=" in expr) for expr, _ in suggestions)
        expr = "0 <= i && i <= size()" if mlower == "add" else "0 <= i && i < size()"
        if not has_index_bound and norm(expr) not in existing_norm:
            suggestions.append((expr, "la operación indexada debería documentar su rango válido de índices"))

    # Acceso manual a arreglo sin precondición clara: útil para pop/top/front/back en Stack/Queue.
    # No agregues !empty() a get/set indexados porque su límite de índice ya implica no vacío
    # cuando existe un acceso válido.
    sz = size_symbol(cls)
    if body and sz and re.search(r"\b[a-zA-Z_]\w*\s*\[", body) and mlower in {"pop", "top", "front", "back", "peek", "dequeue"}:
        expr = "!empty()"
        if norm(expr) not in existing_norm and not any(norm(x[0]) == norm(expr) for x in suggestions):
            suggestions.append((expr, "el método lee almacenamiento interno y suele ser inseguro cuando está vacío"))

    return suggestions


def collect_suggestions(root: Path, headers_only: bool = True, infer: bool = True) -> list[ContractSuggestion]:
    suggestions: list[ContractSuggestion] = []
    seen: set[tuple[str, int, str, str, str]] = set()
    classes = scan_project(root, headers_only=headers_only)
    file_text_cache: dict[Path, str] = {}

    for cls in classes:
        text = file_text_cache.setdefault(cls.file, cls.file.read_text(encoding="utf-8", errors="ignore"))
        insert_line = _class_contract_insert_line(cls, text)
        for inv in infer_class_invariants(cls) if infer else []:
            if not _has_contract(cls.invariants, "invariant", inv.expression):
                _add_unique(
                    suggestions,
                    seen,
                    ContractSuggestion(
                        file=str(cls.file),
                        line=insert_line,
                        kind="invariant",
                        expression=inv.expression,
                        symbol=cls.name,
                        reason="invariante de representación estilo CC-232 inferido a partir de campos",
                        source=inv.source,
                    ),
                )
        for m in cls.methods:
            # sugerencias requires
            for expr, reason in _unsafe_requires_for_method(cls, m):
                if not _has_contract(m.requires, "requires", expr):
                    _add_unique(
                        suggestions,
                        seen,
                        ContractSuggestion(
                            file=str(cls.file),
                            line=_method_contract_insert_line(m),
                            kind="requires",
                            expression=expr,
                            symbol=m.qualified_name,
                            reason=reason,
                            source="suggested-requires",
                        ),
                    )
            # sugerencias ensures desde cambios/accesores simples del cuerpo.
            for ens in infer_method_ensures(cls, m) if infer else []:
                if not _has_contract(m.ensures, "ensures", ens.expression):
                    _add_unique(
                        suggestions,
                        seen,
                        ContractSuggestion(
                            file=str(cls.file),
                            line=_method_contract_insert_line(m),
                            kind="ensures",
                            expression=ens.expression,
                            symbol=m.qualified_name,
                            reason="postcondición inferida desde una actualización simple de tamaño/capacidad o desde el cuerpo de un accesor",
                            source=ens.source,
                        ),
                    )
    return sorted(suggestions, key=lambda s: (s.file, s.line, s.kind, s.expression))


def suggestions_report(root: Path, headers_only: bool = True, infer: bool = True) -> ProjectReport:
    suggestions = collect_suggestions(root, headers_only=headers_only, infer=infer)
    report = ProjectReport(root=str(root))
    if not suggestions:
        report.diagnostics.append(Diagnostic(level="INFO", code="NO_SUGGESTIONS", message="No se generaron sugerencias de contratos.", file=str(root)))
        return report
    for s in suggestions:
        report.diagnostics.append(
            Diagnostic(
                level="INFO",
                code=f"SUGGEST_{s.kind.upper()}",
                message=f"Agregar {s.comment}",
                file=s.file,
                line=s.line,
                symbol=s.symbol,
                details={"expression": s.expression, "reason": s.reason, "source": s.source},
            )
        )
    return report


def _already_near(lines: list[str], line: int, comment: str) -> bool:
    start = max(0, line - 6)
    end = min(len(lines), line + 4)
    target = re.sub(r"\s+", "", comment)
    for raw in lines[start:end]:
        if re.sub(r"\s+", "", raw.strip()) == target:
            return True
    return False


def _indent_for_line(lines: list[str], line: int) -> str:
    if not lines:
        return ""
    idx = min(max(line - 1, 0), len(lines) - 1)
    m = re.match(r"(\s*)", lines[idx])
    return m.group(1) if m else ""


def annotated_text_for_file(path: Path, suggestions: list[ContractSuggestion]) -> str:
    original = path.read_text(encoding="utf-8", errors="ignore")
    lines = original.splitlines()
    # Inserta de abajo hacia arriba para mantener estables los números de línea.
    grouped: dict[int, list[ContractSuggestion]] = {}
    for s in suggestions:
        if Path(s.file) == path:
            grouped.setdefault(s.line, []).append(s)
    for line in sorted(grouped.keys(), reverse=True):
        idx = min(max(line - 1, 0), len(lines))
        indent = _indent_for_line(lines, line)
        comments = []
        for s in sorted(grouped[line], key=lambda x: (x.kind, x.expression)):
            c = f"{indent}{s.comment}"
            if not _already_near(lines, line, c.strip()):
                comments.append(c)
        if comments:
            lines[idx:idx] = comments
    return "\n".join(lines) + ("\n" if original.endswith("\n") else "")


def write_patch(root: Path, suggestions: list[ContractSuggestion], patch_path: Path) -> Path:
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    files = sorted({Path(s.file) for s in suggestions})
    chunks: list[str] = []
    for f in files:
        original = f.read_text(encoding="utf-8", errors="ignore")
        annotated = annotated_text_for_file(f, suggestions)
        if original == annotated:
            continue
        try:
            rel = f.relative_to(root if root.is_dir() else root.parent)
        except ValueError:
            rel = f.name if f.is_file() else f
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            annotated.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
        chunks.extend(diff)
    patch_path.write_text("".join(chunks), encoding="utf-8")
    return patch_path


def write_annotated_copy(root: Path, suggestions: list[ContractSuggestion], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    if root.is_file():
        files = [root]
        base = root.parent
    else:
        files = iter_cpp_files(root, headers_only=True)
        base = root
    sug_by_path = {Path(s.file) for s in suggestions}
    for f in files:
        try:
            rel = f.relative_to(base)
        except ValueError:
            rel = Path(f.name)
        dest = out_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if f in sug_by_path:
            dest.write_text(annotated_text_for_file(f, suggestions), encoding="utf-8")
        else:
            dest.write_bytes(f.read_bytes())
    return out_dir


def write_suggestions_json(root: Path, suggestions: list[ContractSuggestion], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "root": str(root),
        "count": len(suggestions),
        "suggestions": [asdict(s) for s in suggestions],
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
