from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from structguard import __version__
from structguard.findings import findings_from_report
from structguard.findings.guarantee import guarantee_counts
from structguard.metadata import diagnostic_to_dict
from structguard.model import ProjectReport

SCHEMA_VERSION = "structguard-canonical-report/v1"


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_context(context: dict[str, Any] | None) -> dict[str, Any]:
    if context is None:
        return {}
    return {key: value for key, value in context.items() if value is not None}


def _rules_from_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    for finding in findings:
        rule_id = str(finding.get("rule_id", ""))
        if not rule_id:
            continue
        rules.setdefault(
            rule_id,
            {
                "rule_id": rule_id,
                "title": finding.get("title", rule_id),
                "default_severity": finding.get("severity", "INFO"),
                "guarantee": finding.get("guarantee", {}),
                "tags": finding.get("tags", []),
                "cwe": finding.get("cwe"),
            },
        )
    return [rules[key] for key in sorted(rules)]


def _severity_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for finding in findings:
        severity = str(finding.get("severity", "INFO"))
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def build_canonical_report(report: ProjectReport, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Construye el reporte canónico usado como fuente de verdad."""
    finding_models = findings_from_report(report)
    findings = [finding.as_dict() for finding in finding_models]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {
            "name": "StructGuard",
            "version": __version__,
        },
        "run": {
            "root": report.root,
            "generated_at_utc": _now_utc(),
            **_normalize_context(context),
        },
        "summary": {
            "total_findings": len(findings),
            "counts": _severity_counts(findings),
            "guarantee_counts": guarantee_counts(finding.guarantee for finding in finding_models),
        },
        "rules": _rules_from_findings(findings),
        "findings": findings,
        "legacy_diagnostics": [diagnostic_to_dict(diagnostic) for diagnostic in report.diagnostics],
    }


def write_canonical_report(report: ProjectReport, path: Path, context: dict[str, Any] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = build_canonical_report(report, context=context)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_canonical_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"Formato de reporte canónico no soportado: {version}")
    return data
