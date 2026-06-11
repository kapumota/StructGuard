from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from structguard.cppscan import scan_project
from structguard.model import ClassModel, Diagnostic, MethodModel, ProjectReport


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    description: str
    default_severity: str
    good_example: str
    bad_example: str
    profiles: tuple[str, ...]
    cwe: str | None = None
    tags: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "default_severity": self.default_severity,
            "good_example": self.good_example,
            "bad_example": self.bad_example,
            "profiles": list(self.profiles),
            "cwe": self.cwe,
            "tags": list(self.tags),
        }


CONTRACT_RULES: dict[str, RuleDefinition] = {
    "SG-CONTRACT-MISSING-PRECONDITION": RuleDefinition(
        rule_id="SG-CONTRACT-MISSING-PRECONDITION",
        description="Método sensible sin precondición explícita ni guarda local clara.",
        default_severity="warning",
        good_example="// requires n > 0\nint pop();",
        bad_example="int pop() { return data[--n]; }",
        profiles=("cc232", "generic-cpp", "stl-adapters"),
        cwe="CWE-20",
        tags=("contracts", "precondition", "cpp"),
    ),
}

_SENSITIVE_METHODS = {"pop", "top", "peek", "front", "back", "dequeue", "at", "get", "remove", "delete", "extract_min", "extract_max"}
_GUARD_TOKENS = ("if", "assert", "throw", "requires", "empty", "size", "n", "count", "head", "tail")


def analyze_contract_rules_project(root: Path, headers_only: bool = False) -> ProjectReport:
    classes = scan_project(root, headers_only=headers_only)
    report = ProjectReport(root=str(root), diagnostics=[])
    report.diagnostics.append(
        Diagnostic(
            level="INFO",
            code="SG_CONTRACT_RULES_SUMMARY",
            message=f"Reglas contractuales evaluadas: {len(classes)} clases analizadas.",
            file=str(root),
            details={"tags": ["contracts", "rules"], "rules": [rule.as_dict() for rule in CONTRACT_RULES.values()]},
        )
    )
    for cls in classes:
        for method in cls.methods:
            _check_missing_precondition(report, cls, method)
    return report


def is_sensitive_method(method: MethodModel) -> bool:
    name = method.name.lower().strip("~")
    return name in _SENSITIVE_METHODS or any(name.startswith(prefix) for prefix in ("pop", "peek", "front", "back", "dequeue", "remove"))


def has_explicit_precondition(method: MethodModel) -> bool:
    return bool(method.requires or method.assertions)


def has_local_guard(method: MethodModel) -> bool:
    body = (method.body or "").lower()
    if not body:
        return False
    if "if" not in body and "assert" not in body:
        return False
    return any(token in body for token in _GUARD_TOKENS)


def method_changes_size(method: MethodModel, fields: set[str]) -> bool:
    body = method.body or ""
    candidates = {field for field in fields if _looks_like_size_field(field)} | {"n", "size", "size_", "count", "count_", "length", "length_"}
    for field in candidates:
        patterns = (
            f"{field}++",
            f"++{field}",
            f"{field}--",
            f"--{field}",
            f"{field} +=",
            f"{field}-=",
            f"{field} -=",
            f"{field}=",
            f"{field} =",
        )
        if any(pattern in body.replace(" ", "") or pattern in body for pattern in patterns):
            return True
    return False


def _check_missing_precondition(report: ProjectReport, cls: ClassModel, method: MethodModel) -> None:
    if not is_sensitive_method(method):
        return
    if has_explicit_precondition(method) or has_local_guard(method):
        return
    rule = CONTRACT_RULES["SG-CONTRACT-MISSING-PRECONDITION"]
    report.diagnostics.append(
        Diagnostic(
            level="WARNING",
            code=rule.rule_id,
            message=f"{method.qualified_name} es sensible y no tiene precondición explícita ni guarda local visible.",
            file=str(cls.file),
            line=method.start_line,
            symbol=method.qualified_name,
            details={
                "title": "Precondición faltante en método sensible",
                "confidence": "medium",
                "evidence": method.signature,
                "remediation": "Agrega requires explícito o una guarda local antes de acceder, eliminar o devolver elementos.",
                "cwe": rule.cwe,
                "tags": list(rule.tags),
                "rule": rule.as_dict(),
            },
        )
    )


def _looks_like_size_field(field: str) -> bool:
    name = field.lower()
    return name in {"n", "size", "count", "length"} or name.endswith(("_size", "size_", "_count", "count_", "_length", "length_"))
