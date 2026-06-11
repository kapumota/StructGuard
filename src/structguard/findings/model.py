from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from structguard.metadata import diagnostic_to_dict, enriched_details
from structguard.model import Diagnostic, ProjectReport

from .severity import severity_from_level, sort_key


@dataclass(frozen=True)
class Location:
    file: str | None = None
    line: int | None = None
    column: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
        }

    @property
    def display(self) -> str:
        if not self.file:
            return ""
        if self.line is None:
            return self.file
        if self.column is None:
            return f"{self.file}:{self.line}"
        return f"{self.file}:{self.line}:{self.column}"


@dataclass(frozen=True)
class Finding:
    rule_id: str
    title: str
    message: str
    severity: str
    confidence: str
    location: Location = field(default_factory=Location)
    symbol: str = ""
    evidence: list[str] = field(default_factory=list)
    remediation: str = ""
    cwe: str | None = None
    tags: list[str] = field(default_factory=list)
    level: str = "INFO"
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "confidence": self.confidence,
            "location": self.location.as_dict(),
            "symbol": self.symbol,
            "evidence": list(self.evidence),
            "remediation": self.remediation,
            "cwe": self.cwe,
            "tags": list(self.tags),
            "level": self.level,
            "details": dict(self.details),
        }

    @classmethod
    def from_diagnostic(cls, diagnostic: Diagnostic) -> Finding:
        details = enriched_details(diagnostic)
        evidence = _normalize_evidence(details.get("evidence"))
        tags = _normalize_tags(details, diagnostic)
        return cls(
            rule_id=diagnostic.code,
            title=_title_from_diagnostic(diagnostic),
            message=diagnostic.message,
            severity=severity_from_level(diagnostic.level),
            confidence=str(details.get("confidence", "medium")),
            location=Location(file=diagnostic.file, line=diagnostic.line, column=details.get("column")),
            symbol=diagnostic.symbol or "",
            evidence=evidence,
            remediation=str(details.get("remediation", "")),
            cwe=_normalize_cwe(details.get("cwe")),
            tags=tags,
            level=diagnostic.level,
            details=details,
        )


def findings_from_diagnostics(diagnostics: list[Diagnostic]) -> list[Finding]:
    findings = [Finding.from_diagnostic(diagnostic) for diagnostic in diagnostics]
    return sorted(
        findings,
        key=lambda finding: (
            sort_key(finding.severity),
            finding.location.file or "",
            finding.location.line or 0,
            finding.rule_id,
            finding.symbol,
        ),
    )


def findings_from_report(report: ProjectReport) -> list[Finding]:
    return findings_from_diagnostics(report.diagnostics)


def findings_document(report: ProjectReport) -> dict[str, Any]:
    findings = findings_from_report(report)
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    return {
        "schema_version": "structguard-findings/v1",
        "root": report.root,
        "counts": counts,
        "findings": [finding.as_dict() for finding in findings],
    }


def _title_from_diagnostic(diagnostic: Diagnostic) -> str:
    title = diagnostic.details.get("title") if diagnostic.details else None
    if title:
        return str(title)
    return diagnostic.code.replace("_", " ").title()


def _normalize_evidence(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    return [str(value)]


def _normalize_cwe(value: Any) -> str | None:
    if value is None or value == "":
        return None
    text = str(value)
    if text.upper().startswith("CWE-"):
        return text.upper()
    if text.isdigit():
        return f"CWE-{text}"
    return text


def _normalize_tags(details: dict[str, Any], diagnostic: Diagnostic) -> list[str]:
    tags: list[str] = []
    raw = details.get("tags")
    if isinstance(raw, list):
        tags.extend(str(item) for item in raw)
    elif isinstance(raw, str) and raw:
        tags.append(raw)
    category = details.get("category")
    if category:
        tags.append(str(category))
    prefix = diagnostic.code.split("_", 1)[0].lower()
    if prefix:
        tags.append(prefix)
    return sorted(set(tags))


def relative_location(finding: Finding, root: str) -> str:
    file_name = finding.location.file
    if not file_name:
        return ""
    try:
        file_name = str(Path(file_name).resolve().relative_to(Path(root).resolve()))
    except Exception:
        pass
    if finding.location.line is None:
        return file_name
    return f"{file_name}:{finding.location.line}"


__all__ = [
    "Finding",
    "Location",
    "findings_document",
    "findings_from_diagnostics",
    "findings_from_report",
    "relative_location",
]
