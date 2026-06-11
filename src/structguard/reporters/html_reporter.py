from __future__ import annotations

from html import escape
from pathlib import Path

from structguard.findings import findings_from_report, relative_location
from structguard.findings.guarantee import guarantee_counts
from structguard.model import ProjectReport
from structguard.reporters.guarantee_badge import guarantee_badge_html


def render_html(report: ProjectReport, title: str = "Reporte de hallazgos StructGuard") -> str:
    findings = findings_from_report(report)
    rows = []
    for finding in findings:
        rows.append(
            "<tr>"
            f"<td>{escape(finding.severity)}</td>"
            f"<td>{guarantee_badge_html(finding.guarantee)}<br><small>{escape(finding.guarantee.description)}</small></td>"
            f"<td><code>{escape(finding.rule_id)}</code></td>"
            f"<td>{escape(finding.symbol)}</td>"
            f"<td>{escape(relative_location(finding, report.root))}</td>"
            f"<td>{escape(finding.message)}<br><small>confianza={escape(finding.confidence)}</small></td>"
            f"<td>{escape(', '.join(finding.evidence))}</td>"
            f"<td>{escape(finding.remediation)}</td>"
            "</tr>"
        )
    table = "\n".join(rows) if rows else "<tr><td colspan='8'>Sin hallazgos</td></tr>"
    guarantee_by_level = guarantee_counts(finding.guarantee for finding in findings)
    guarantee_summary = "".join(
        f"<li><code>{escape(level)}</code>: <b>{count}</b></li>"
        for level, count in guarantee_by_level.items()
    )
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
    .guarantee-badge {{ display: inline-block; border: 1px solid #999; border-radius: .5rem; padding: .15rem .45rem; font-weight: 700; font-size: .78rem; }}
    .guarantee-g1-heuristic {{ background: #eef2ff; }}
    .guarantee-g2-structural {{ background: #ecfeff; }}
    .guarantee-g3-bounded {{ background: #fef9c3; }}
    .guarantee-g4-executed {{ background: #dcfce7; }}
    .guarantee-g5-formally-verified {{ background: #dbeafe; }}
  </style>
</head>
<body>
  <h1>{escape(title)}</h1>
  <p>Raíz: <code>{escape(report.root)}</code></p>
  <section>
    <h2>Resumen por garantía</h2>
    <ul>{guarantee_summary}</ul>
  </section>
  <table>
    <thead>
      <tr><th>Severidad</th><th>Garantía</th><th>Regla</th><th>Símbolo</th><th>Ubicación</th><th>Mensaje</th><th>Evidencia</th><th>Remediación</th></tr>
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
