from __future__ import annotations

import re
from pathlib import Path

from structguard.analyzers.contracts import RuleDefinition
from structguard.cppscan import scan_project
from structguard.model import ClassModel, Diagnostic, MethodModel, ProjectReport


COMPLEXITY_RULES: dict[str, RuleDefinition] = {
    "SG-COMPLEXITY-DEQUEUE-LINEAR-RISK": RuleDefinition(
        rule_id="SG-COMPLEXITY-DEQUEUE-LINEAR-RISK",
        description="Operación dequeue parece desplazar elementos y puede ser O(n).",
        default_severity="warning",
        good_example="return data[head++];",
        bad_example="for (int i = 1; i < n; ++i) data[i - 1] = data[i];",
        profiles=("cc232", "generic-cpp"),
        cwe=None,
        tags=("complexity", "queue", "cpp"),
    ),
}


def analyze_complexity_hints_project(root: Path, headers_only: bool = False) -> ProjectReport:
    classes = scan_project(root, headers_only=headers_only)
    report = ProjectReport(root=str(root), diagnostics=[])
    report.diagnostics.append(
        Diagnostic(
            level="INFO",
            code="SG_COMPLEXITY_RULES_SUMMARY",
            message=f"Pistas de complejidad evaluadas: {len(classes)} clases analizadas.",
            file=str(root),
            details={"tags": ["complexity", "rules"], "rules": [rule.as_dict() for rule in COMPLEXITY_RULES.values()]},
        )
    )
    for cls in classes:
        for method in cls.methods:
            _check_linear_dequeue(report, cls, method)
    return report


def _check_linear_dequeue(report: ProjectReport, cls: ClassModel, method: MethodModel) -> None:
    if "queue" not in cls.name.lower() or method.name.lower() not in {"dequeue", "pop"}:
        return
    body = method.body or ""
    if not body:
        return
    if not re.search(r"\b(for|while)\b", body):
        return
    if not re.search(r"data\s*\[.*\]\s*=\s*data\s*\[", body, re.S):
        return
    rule = COMPLEXITY_RULES["SG-COMPLEXITY-DEQUEUE-LINEAR-RISK"]
    report.diagnostics.append(
        Diagnostic(
            level="WARNING",
            code=rule.rule_id,
            message=f"{method.qualified_name} parece desplazar elementos durante dequeue.",
            file=str(cls.file),
            line=method.start_line,
            symbol=method.qualified_name,
            details={
                "title": rule.description,
                "confidence": "low",
                "evidence": method.signature,
                "remediation": "Usa índices head/tail o buffer circular si el contrato espera dequeue O(1).",
                "tags": list(rule.tags),
                "rule": rule.as_dict(),
            },
        )
    )
