from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path
from typing import Any


def _findings(document: dict[str, Any]) -> list[dict[str, Any]]:
    raw = document.get("findings", [])
    return [item for item in raw if isinstance(item, dict)]


def _guarantee_label(finding: dict[str, Any]) -> str:
    guarantee = finding.get("guarantee", {})
    if isinstance(guarantee, dict):
        level = guarantee.get("level", "G1_HEURISTIC")
        label = guarantee.get("label", "Heurístico")
        return f"[{level} {label}]"
    return "[G1_HEURISTIC Heurístico]"


def render_html_from_canonical(document: dict[str, Any]) -> str:
    rows = []
    for finding in _findings(document):
        location = finding.get("location", {}) if isinstance(finding.get("location"), dict) else {}
        file_name = location.get("file", "")
        line = location.get("line") or ""
        rows.append(
            "<tr>"
            f"<td>{escape(str(finding.get('severity', 'INFO')))}</td>"
            f"<td>{escape(_guarantee_label(finding))}</td>"
            f"<td><code>{escape(str(finding.get('rule_id', '')))}</code></td>"
            f"<td>{escape(str(file_name))}:{escape(str(line))}</td>"
            f"<td>{escape(str(finding.get('message', '')))}</td>"
            "</tr>"
        )
    body = "\n".join(rows) if rows else "<tr><td colspan='5'>Sin hallazgos</td></tr>"
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>Reporte canónico StructGuard</title>
  <style>body {{ font-family: system-ui, sans-serif; margin: 2rem; }} table {{ border-collapse: collapse; width: 100%; }} th, td {{ border: 1px solid #ddd; padding: .5rem; vertical-align: top; }} th {{ text-align: left; }}</style>
</head>
<body>
  <h1>Reporte canónico StructGuard</h1>
  <p>Fuente: <code>report.json</code></p>
  <table>
    <thead><tr><th>Severidad</th><th>Garantía</th><th>Regla</th><th>Ubicación</th><th>Mensaje</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</body>
</html>
"""


def render_markdown_from_canonical(document: dict[str, Any]) -> str:
    lines = ["### Reporte canónico StructGuard", "", "Fuente: `report.json`.", "", "| Severidad | Garantía | Regla | Ubicación | Mensaje |", "|---|---|---|---|---|"]
    for finding in _findings(document):
        location = finding.get("location", {}) if isinstance(finding.get("location"), dict) else {}
        file_name = str(location.get("file", ""))
        line = str(location.get("line") or "")
        lines.append(
            f"| {finding.get('severity', 'INFO')} | {_guarantee_label(finding)} | `{finding.get('rule_id', '')}` | {file_name}:{line} | {finding.get('message', '')} |"
        )
    return "\n".join(lines) + "\n"


def render_sarif_from_canonical(document: dict[str, Any]) -> str:
    rules: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    for finding in _findings(document):
        rule_id = str(finding.get("rule_id", ""))
        guarantee = finding.get("guarantee", {}) if isinstance(finding.get("guarantee"), dict) else {}
        rules.setdefault(
            rule_id,
            {
                "id": rule_id,
                "name": str(finding.get("title", rule_id)),
                "shortDescription": {"text": str(finding.get("title", rule_id))},
                "properties": {
                    "guarantee_level": guarantee.get("level"),
                    "guarantee_label": guarantee.get("label"),
                },
            },
        )
        location = finding.get("location", {}) if isinstance(finding.get("location"), dict) else {}
        physical_location: dict[str, Any] = {"artifactLocation": {"uri": str(location.get("file", ""))}}
        if location.get("line"):
            physical_location["region"] = {"startLine": int(location["line"])}
        results.append(
            {
                "ruleId": rule_id,
                "level": "error" if str(finding.get("severity", "")).lower() == "error" else "warning" if str(finding.get("severity", "")).lower() == "warning" else "note",
                "message": {"text": str(finding.get("message", ""))},
                "locations": [{"physicalLocation": physical_location}],
                "properties": finding,
            }
        )
    tool = document.get("tool", {}) if isinstance(document.get("tool"), dict) else {}
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": str(tool.get("name", "StructGuard")), "version": str(tool.get("version", "")), "rules": list(rules.values())}},
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, indent=2, ensure_ascii=False) + "\n"


def render_junit_from_canonical(document: dict[str, Any]) -> str:
    findings = _findings(document)
    suite = ET.Element("testsuite", name="StructGuard canonical report", tests=str(len(findings)))
    for finding in findings:
        case = ET.SubElement(suite, "testcase", name=str(finding.get("rule_id", "SG-FINDING")), classname="structguard.finding")
        if str(finding.get("severity", "")).lower() in {"error", "critical", "failed"}:
            failure = ET.SubElement(case, "failure", message=str(finding.get("message", "")))
            failure.text = json.dumps(finding, indent=2, ensure_ascii=False)
    return ET.tostring(suite, encoding="unicode") + "\n"


def derive_reports_from_canonical(
    document: dict[str, Any],
    *,
    html: Path | None = None,
    markdown: Path | None = None,
    sarif: Path | None = None,
    junit: Path | None = None,
    json_out: Path | None = None,
) -> list[Path]:
    written: list[Path] = []
    outputs = [
        (html, render_html_from_canonical(document)),
        (markdown, render_markdown_from_canonical(document)),
        (sarif, render_sarif_from_canonical(document)),
        (junit, render_junit_from_canonical(document)),
        (json_out, json.dumps(document, indent=2, ensure_ascii=False) + "\n"),
    ]
    for path, content in outputs:
        if path is None:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written
