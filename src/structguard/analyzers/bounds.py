from __future__ import annotations

import re
from pathlib import Path

from structguard.analyzers.contracts import RuleDefinition, has_explicit_precondition, has_local_guard
from structguard.cppscan import scan_project
from structguard.model import ClassModel, Diagnostic, MethodModel, ProjectReport


BOUNDS_RULES: dict[str, RuleDefinition] = {
    "SG-BOUNDS-INDEX-RISK": RuleDefinition(
        rule_id="SG-BOUNDS-INDEX-RISK",
        description="Acceso indexado sin guarda local o precondición de límites visible.",
        default_severity="warning",
        good_example="// requires 0 <= i && i < size\nreturn data[i];",
        bad_example="return data[i];",
        profiles=("cc232", "generic-cpp", "stl-adapters"),
        cwe="CWE-125",
        tags=("bounds", "cpp"),
    ),
}

_INDEX_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\[\s*([^\]]+)\s*\]")


def analyze_bounds_project(root: Path, headers_only: bool = False) -> ProjectReport:
    classes = scan_project(root, headers_only=headers_only)
    report = ProjectReport(root=str(root), diagnostics=[])
    report.diagnostics.append(
        Diagnostic(
            level="INFO",
            code="SG_BOUNDS_RULES_SUMMARY",
            message=f"Reglas de límites evaluadas: {len(classes)} clases analizadas.",
            file=str(root),
            details={"tags": ["bounds", "rules"], "rules": [rule.as_dict() for rule in BOUNDS_RULES.values()]},
        )
    )
    for cls in classes:
        for method in cls.methods:
            _check_index_access(report, cls, method)
    return report


def _check_index_access(report: ProjectReport, cls: ClassModel, method: MethodModel) -> None:
    body = method.body or ""
    if not body or has_explicit_precondition(method) or has_local_guard(method):
        return
    for match in _INDEX_RE.finditer(body):
        array_name = match.group(1)
        index_expr = " ".join(match.group(2).split())
        rule = BOUNDS_RULES["SG-BOUNDS-INDEX-RISK"]
        report.diagnostics.append(
            Diagnostic(
                level="WARNING",
                code=rule.rule_id,
                message=f"{method.qualified_name} accede a {array_name}[{index_expr}] sin una guarda de límites visible.",
                file=str(cls.file),
                line=method.start_line + body.count("\n", 0, match.start()),
                symbol=method.qualified_name,
                details={
                    "title": "Riesgo de acceso fuera de rango",
                    "confidence": "medium",
                    "evidence": f"{array_name}[{index_expr}]",
                    "remediation": "Agrega requires de límites o una guarda local antes del acceso indexado.",
                    "cwe": rule.cwe,
                    "tags": list(rule.tags),
                    "rule": rule.as_dict(),
                },
            )
        )
