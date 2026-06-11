from __future__ import annotations

from pathlib import Path

from structguard.findings import findings_from_report, relative_location
from structguard.model import ProjectReport


def render_markdown(report: ProjectReport, title: str = "Reporte de hallazgos StructGuard") -> str:
    findings = findings_from_report(report)
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    lines = [f"### {title}", "", f"Raíz: `{report.root}`", "", "#### Resumen", ""]
    if counts:
        for severity in sorted(counts):
            lines.append(f"- {severity}: {counts[severity]}")
    else:
        lines.append("- Sin hallazgos")
    lines.extend(["", "#### Hallazgos", ""])
    if not findings:
        lines.append("No se registraron hallazgos.")
    for finding in findings:
        location = relative_location(finding, report.root)
        lines.append(f"- **{finding.severity.upper()}** `{finding.rule_id}` {finding.symbol}".rstrip())
        if location:
            lines.append(f"  - ubicación: `{location}`")
        lines.append(f"  - mensaje: {finding.message}")
        if finding.confidence:
            lines.append(f"  - confianza: {finding.confidence}")
        if finding.evidence:
            lines.append(f"  - evidencia: {', '.join(finding.evidence)}")
        if finding.remediation:
            lines.append(f"  - remediación: {finding.remediation}")
    return "\n".join(lines) + "\n"


def write_markdown_report(report: ProjectReport, path: Path, title: str = "Reporte de hallazgos StructGuard") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report, title=title), encoding="utf-8")
    return path
