from __future__ import annotations

from html import escape
from pathlib import Path

from structguard.findings import findings_from_report, relative_location
from structguard.model import ProjectReport


def render_html(report: ProjectReport, title: str = "Reporte de hallazgos StructGuard") -> str:
    findings = findings_from_report(report)
    rows = []
    for finding in findings:
        rows.append(
            "<tr>"
            f"<td>{escape(finding.severity)}</td>"
            f"<td><code>{escape(finding.rule_id)}</code></td>"
            f"<td>{escape(finding.symbol)}</td>"
            f"<td>{escape(relative_location(finding, report.root))}</td>"
            f"<td>{escape(finding.message)}<br><small>confianza={escape(finding.confidence)}</small></td>"
            f"<td>{escape(', '.join(finding.evidence))}</td>"
            f"<td>{escape(finding.remediation)}</td>"
            "</tr>"
        )
    table = "\n".join(rows) if rows else "<tr><td colspan='7'>Sin hallazgos</td></tr>"
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: .5rem; vertical-align: top; }}
    th {{ text-align: left; }}
    code {{ white-space: nowrap; }}
  </style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <p>Raíz: <code>{escape(report.root)}</code></p>
  <table>
    <thead>
      <tr><th>Severidad</th><th>Regla</th><th>Símbolo</th><th>Ubicación</th><th>Mensaje</th><th>Evidencia</th><th>Remediación</th></tr>
    </thead>
    <tbody>
      {table}
    </tbody>
  </table>
</body>
</html>
"""


def write_html_report(report: ProjectReport, path: Path, title: str = "Reporte de hallazgos StructGuard") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(report, title=title), encoding="utf-8")
    return path
