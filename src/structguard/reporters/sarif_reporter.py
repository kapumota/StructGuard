from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from structguard import __version__
from structguard.findings import findings_from_report
from structguard.model import ProjectReport


def _sarif_level(severity: str) -> str:
    return {
        "error": "error",
        "warning": "warning",
        "note": "note",
        "info": "note",
    }.get(severity, "note")


def sarif_document(report: ProjectReport) -> dict[str, Any]:
    rules: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    for finding in findings_from_report(report):
        guarantee = finding.guarantee.as_dict()
        rules.setdefault(
            finding.rule_id,
            {
                "id": finding.rule_id,
                "name": finding.title,
                "shortDescription": {"text": finding.title},
                "fullDescription": {"text": finding.message[:500]},
                "defaultConfiguration": {"level": _sarif_level(finding.severity)},
                "properties": {
                    "tags": finding.tags,
                    "cwe": finding.cwe,
                    "guarantee_level": guarantee["level"],
                    "guarantee_label": guarantee["label"],
                },
            },
        )
        physical_location: dict[str, Any] = {
            "artifactLocation": {"uri": finding.location.file or ""},
        }
        if finding.location.line:
            physical_location["region"] = {"startLine": int(finding.location.line)}
        properties = finding.as_dict()
        properties["guarantee_level"] = guarantee["level"]
        properties["guarantee_label"] = guarantee["label"]
        results.append(
            {
                "ruleId": finding.rule_id,
                "level": _sarif_level(finding.severity),
                "message": {"text": finding.message},
                "locations": [{"physicalLocation": physical_location}],
                "properties": properties,
            }
        )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "StructGuard",
                        "version": __version__,
                        "rules": list(rules.values()),
                    },
                },
                "results": results,
            }
        ],
    }


def render_sarif(report: ProjectReport) -> str:
    return json.dumps(sarif_document(report), indent=2, ensure_ascii=False) + "\n"


def write_sarif_report(report: ProjectReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_sarif(report), encoding="utf-8")
    return path
