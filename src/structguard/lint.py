from __future__ import annotations

from pathlib import Path
import re
from .cppscan import scan_project, extract_assertions
from .dsl import apply_dsl_contracts, load_dsl
from .model import Diagnostic, ProjectReport
from .verifier import infer_class_invariants

UNSAFE_METHOD_NAMES = {"pop", "top", "front", "back", "peek", "dequeue", "remove", "get", "set"}
COMPLEX_STRUCTURE_HINTS = {
    "heap", "tree", "avl", "bst", "queue", "stack", "deque", "hash", "dsu", "fenwick", "segment", "btree",
    "array", "list", "trie", "bitmap", "dictionary", "priority"
}


def lint_project(root: Path, headers_only: bool = False, dsl_paths: list[str] | None = None) -> ProjectReport:
    report = ProjectReport(root=str(root))
    classes = scan_project(root, headers_only=headers_only)
    dsl_diagnostics = []
    if dsl_paths:
        try:
            dsl_diagnostics = apply_dsl_contracts(classes, load_dsl(dsl_paths))
        except Exception as e:
            report.diagnostics.append(Diagnostic(level="FAILED", code="DSL_LOAD_ERROR", message=str(e), file=str(root)))
    if not classes:
        report.diagnostics.append(Diagnostic(level="WARNING", code="NO_CLASSES", message="No se detectaron clases/structs de C++.", file=str(root)))
        return report

    report.diagnostics.extend(dsl_diagnostics)

    for cls in classes:
        lname = cls.name.lower()
        inferred_inv = infer_class_invariants(cls)
        if any(h in lname for h in COMPLEX_STRUCTURE_HINTS) and not cls.invariants:
            report.diagnostics.append(
                Diagnostic(
                    level="WARNING",
                    code="MISSING_CLASS_INVARIANT",
                    message=f"{cls.name} parece una estructura de datos, pero no tiene anotaciones // invariant:.",
                    file=str(cls.file),
                    line=cls.start_line,
                    symbol=cls.name,
                    details={"suggested_invariants": [c.expression for c in inferred_inv]},
                )
            )
        elif inferred_inv and cls.invariants:
            missing = [c.expression for c in inferred_inv if c.expression not in {x.expression for x in cls.invariants}]
            if missing:
                report.diagnostics.append(
                    Diagnostic(
                        level="INFO",
                        code="INVARIANT_SUGGESTION",
                        message=f"{cls.name} tiene invariantes; StructGuard también puede inferir invariantes adicionales de estilo CC-232.",
                        file=str(cls.file),
                        line=cls.start_line,
                        symbol=cls.name,
                        details={"suggested_invariants": missing},
                    )
                )
        for m in cls.methods:
            mlower = m.name.lower().replace("~", "")
            has_declared_requires = bool(m.requires)
            inferred_asserts = extract_assertions(m.body, m.start_line)
            if mlower in UNSAFE_METHOD_NAMES and not has_declared_requires:
                suggestion = []
                if mlower in {"pop", "top", "front", "back", "peek", "dequeue"}:
                    suggestion.append("!empty()")
                if mlower == "remove" and re.search(r"\bint\s+i\b|\bsize_t\s+i\b|\bstd::size_t\s+i\b", m.signature):
                    suggestion.append("0 <= i && i < size()")
                elif mlower == "remove":
                    suggestion.append("!empty()")
                if mlower in {"get", "set"}:
                    suggestion.append("0 <= i && i < size()")
                if inferred_asserts:
                    suggestion.extend(a.expression for a in inferred_asserts)
                report.diagnostics.append(
                    Diagnostic(
                        level="WARNING",
                        code="MISSING_PRECONDITION",
                        message=f"{m.qualified_name} suele ser inseguro sin una precondición; agrega // requires: ...",
                        file=str(cls.file),
                        line=m.start_line,
                        symbol=m.qualified_name,
                        details={"suggested_requires": sorted(set(suggestion))},
                    )
                )
            if (m.requires or m.ensures) and m.body is None:
                report.diagnostics.append(
                    Diagnostic(
                        level="INFO",
                        code="CONTRACT_ON_DECLARATION",
                        message=f"{m.qualified_name} tiene contratos, pero no tiene cuerpo inline/en cabecera; la verificación necesita la definición.",
                        file=str(cls.file),
                        line=m.start_line,
                        symbol=m.qualified_name,
                    )
                )
            if inferred_asserts and not has_declared_requires:
                report.diagnostics.append(
                    Diagnostic(
                        level="INFO",
                        code="ASSERT_AS_CONTRACT_CANDIDATE",
                        message=f"{m.qualified_name} contiene assert(); considera documentarlo como // requires: para verificación y claridad de API.",
                        file=str(cls.file),
                        line=m.start_line,
                        symbol=m.qualified_name,
                        details={"assertions": [a.expression for a in inferred_asserts]},
                    )
                )
            if m.body and re.search(r"\b(new|delete)\b", m.body) and not any("ownership" in c.expression.lower() for c in cls.invariants):
                report.diagnostics.append(
                    Diagnostic(
                        level="INFO",
                        code="POINTER_OWNERSHIP_NOTE",
                        message=f"{m.qualified_name} usa asignación/liberación manual de memoria; documenta invariantes de ownership para una verificación más fuerte.",
                        file=str(cls.file),
                        line=m.start_line,
                        symbol=m.qualified_name,
                    )
                )
    if not report.diagnostics:
        report.diagnostics.append(Diagnostic(level="INFO", code="LINT_CLEAN", message="No se encontraron hallazgos de lint de StructGuard."))
    return report
