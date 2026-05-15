from __future__ import annotations

from collections import Counter, defaultdict
from html import escape
from pathlib import Path
import json

from . import __version__
from .metadata import diagnostic_to_dict
from .model import ALL_LEVELS, ProjectReport


RESULT_SEMANTICS = {
    "PROVED": (
        "Un backend formal/solver descargó la obligación de prueba generada. "
        "Es más fuerte que la verificación acotada, pero solo es tan sólido "
        "como el modelo formal generado."
    ),
    "BOUNDED_VERIFIED": (
        "No se encontró ninguna violación dentro del modelo finito acotado de "
        "StructGuard. Esto no es una prueba para todas las ejecuciones C++."
    ),
    "HEURISTIC": (
        "Evidencia por patrón, lint, fuzzing o seguridad. "
        "Es una señal útil, no una prueba."
    ),
    "UNKNOWN": (
        "StructGuard no tuvo suficiente cobertura de modelo o evidencia para decidir."
    ),
    "FAILED": (
        "Se reportó una violación, contraejemplo o falla estricta de gate."
    ),
    "WARNING": (
        "Se reportó riesgo, ambigüedad o ausencia de contrato/documentación."
    ),
    "INFO": "Hallazgo informativo auxiliar.",
}


def report_to_dict(report: ProjectReport) -> dict:
    return {
        "schema_version": "structguard-report/v1",
        "tool": {
            "name": "StructGuard",
            "version": __version__,
        },
        "root": report.root,
        "counts": report.counts(),
        "result_semantics": RESULT_SEMANTICS,
        "diagnostics": [
            diagnostic_to_dict(d)
            for d in report.diagnostics
        ],
    }


def write_json(report: ProjectReport, path: Path) -> Path:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            report_to_dict(report),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return path


def _rel(path: str | None, root: str) -> str:
    if not path:
        return ""

    try:
        return str(
            Path(path)
            .resolve()
            .relative_to(Path(root).resolve())
        )
    except Exception:
        return path


def _order(level: str) -> int:
    return {
        level: i
        for i, level in enumerate(ALL_LEVELS)
    }.get(level, 99)


def _cards_html(counts: dict, total: int, levels: list[str]) -> str:
    cards = "".join(
        (
            f"<div class='card level-{escape(level.lower())}'>"
            f"<div>{escape(level)}</div>"
            f"<b>{counts.get(level, 0)}</b>"
            "</div>"
        )
        for level in levels
    )

    cards += (
        "<div class='card'>"
        "<div>TOTAL</div>"
        f"<b>{total}</b>"
        "</div>"
    )

    return cards


def _diagnostic_rows(report: ProjectReport) -> list[str]:
    rows = []

    for d in sorted(
        report.diagnostics,
        key=lambda x: (
            _order(x.level),
            x.file or "",
            x.line or 0,
            x.code,
        ),
    ):
        diagnostic = diagnostic_to_dict(d)
        details = escape(
            json.dumps(
                diagnostic.get("details", {}),
                ensure_ascii=False,
                indent=2,
            )
        )
        loc = f"{_rel(d.file, report.root)}:{d.line or ''}" if d.file else ""
        meta = diagnostic.get("details", {})
        confidence = escape(str(meta.get("confidence", "")))
        evidence = escape(str(meta.get("evidence", "")))

        rows.append(
            f"<tr data-level='{escape(d.level)}'>"
            f"<td><span class='pill {escape(d.level.lower())}'>"
            f"{escape(d.level)}</span></td>"
            f"<td><code>{escape(d.code)}</code></td>"
            f"<td>{escape(d.symbol or '')}</td>"
            f"<td>{escape(loc)}</td>"
            f"<td>{escape(d.message)}<br>"
            f"<small>confianza={confidence} · evidencia={evidence}</small></td>"
            "<td><details><summary>detalles</summary>"
            f"<pre>{details}</pre></details></td>"
            "</tr>"
        )

    return rows


def _file_groups_html(report: ProjectReport) -> tuple[list[str], list[str]]:
    groups = defaultdict(list)

    for d in report.diagnostics:
        groups[_rel(d.file, report.root) or "proyecto"].append(d)

    file_nav = []
    file_sections = []

    for f, items in sorted(
        groups.items(),
        key=lambda kv: (
            min(_order(d.level) for d in kv[1]),
            kv[0],
        ),
    ):
        anchor = "file-" + str(abs(hash(f)))
        badges = " ".join(
            (
                f"<span class='mini {escape(k.lower())}'>"
                f"{escape(k)} {v}</span>"
            )
            for k, v in sorted(
                Counter(d.level for d in items).items(),
                key=lambda kv: _order(kv[0]),
            )
        )

        file_nav.append(
            f"<li><a href='#{anchor}'>{escape(f)}</a><br>{badges}</li>"
        )

        items_html = "".join(
            (
                f"<li><span class='pill {escape(d.level.lower())}'>"
                f"{escape(d.level)}</span> "
                f"<code>{escape(d.code)}</code> "
                f"{escape(d.symbol or '')}: {escape(d.message)}</li>"
            )
            for d in sorted(
                items,
                key=lambda x: (
                    _order(x.level),
                    x.line or 0,
                ),
            )[:100]
        )

        file_sections.append(
            f"<section id='{anchor}'>"
            f"<h3>{escape(f)}</h3>"
            f"<ul>{items_html}</ul>"
            "</section>"
        )

    return file_nav, file_sections


def _top_codes_html(report: ProjectReport) -> str:
    return "".join(
        f"<li><code>{escape(code)}</code> <b>{n}</b></li>"
        for code, n in Counter(d.code for d in report.diagnostics).most_common(15)
    )


def _module_panel_html(report: ProjectReport) -> str:
    return "".join(
        (
            f"<div class='module'>"
            f"<b>{escape(module)}</b>"
            f"<span>{count}</span>"
            "</div>"
        )
        for module, count in Counter(
            d.code.split("_", 1)[0]
            for d in report.diagnostics
        ).most_common()
    )


def _style_html() -> str:
    return """
body{margin:0;font-family:system-ui,-apple-system,Segoe UI,sans-serif;background:#f1f5f9;color:#0f172a}
header{background:linear-gradient(135deg,#0f172a,#334155);color:white;padding:2rem}
header p{color:#cbd5e1}
.layout{display:grid;grid-template-columns:290px 1fr;gap:1rem;padding:1rem}
aside,.panel{background:white;border:1px solid #e5e7eb;border-radius:1rem;padding:1rem;box-shadow:0 8px 24px #0f172a12}
aside{position:sticky;top:1rem;align-self:start;max-height:calc(100vh - 2rem);overflow:auto}
.cards{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:.75rem;margin-bottom:1rem}
.card{background:white;border:1px solid #e5e7eb;border-radius:1rem;padding:1rem;box-shadow:0 8px 24px #0f172a12}
.card div{color:#64748b;font-size:.75rem;font-weight:800;letter-spacing:.08em}
.card b{font-size:2rem}
.level-failed{border-top:4px solid #dc2626}
.level-warning{border-top:4px solid #f59e0b}
.level-unknown{border-top:4px solid #f97316}
.level-heuristic{border-top:4px solid #0ea5e9}
.level-bounded_verified{border-top:4px solid #16a34a}
.level-proved{border-top:4px solid #15803d}
.level-info{border-top:4px solid #2563eb}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th,td{border-bottom:1px solid #e5e7eb;padding:.55rem;text-align:left;vertical-align:top}
th{background:#f8fafc;position:sticky;top:0}
tr:hover{background:#f8fafc}
input,select{border:1px solid #cbd5e1;border-radius:.65rem;padding:.55rem .7rem}
pre{white-space:pre-wrap;background:#0b1020;color:#d1e7ff;padding:.75rem;border-radius:.75rem;overflow:auto}
.pill,.mini{display:inline-block;border-radius:999px;padding:.18rem .45rem;font-size:.72rem;font-weight:800}
.failed{background:#fee2e2;color:#991b1b}
.warning,.unknown{background:#fef3c7;color:#92400e}
.heuristic{background:#e0f2fe;color:#075985}
.bounded_verified,.proved{background:#dcfce7;color:#166534}
.info{background:#dbeafe;color:#1d4ed8}
.modules{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:.5rem}
.module{border:1px solid #e5e7eb;border-radius:.75rem;padding:.65rem;display:flex;justify-content:space-between;background:#f8fafc}
@media(max-width:1000px){
  .layout{grid-template-columns:1fr}
  aside{position:static}
  .cards{grid-template-columns:repeat(2,1fr)}
}
"""


def write_html(
    report: ProjectReport,
    path: Path,
    title: str = "Reporte StructGuard",
) -> Path:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    counts = report.counts()
    total = sum(counts.values())
    levels = list(ALL_LEVELS)

    cards = _cards_html(counts, total, levels)
    rows = _diagnostic_rows(report)
    file_nav, file_sections = _file_groups_html(report)
    top_codes = _top_codes_html(report)
    module_panel = _module_panel_html(report)

    raw = escape(
        json.dumps(
            report_to_dict(report),
            indent=2,
            ensure_ascii=False,
        )
    )

    semantics = "".join(
        f"<li><b>{escape(k)}</b>: {escape(v)}</li>"
        for k, v in RESULT_SEMANTICS.items()
    )

    level_options = "".join(
        f"<option>{escape(level)}</option>"
        for level in levels
    )

    style = _style_html()

    html = f"""<!doctype html>
<html lang='es'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{escape(title)}</title>
<style>
{style}
</style>
</head>
<body>
<header>
  <h1>{escape(title)}</h1>
  <p><b>Raíz:</b> {escape(report.root)}</p>
  <p>
    Reporte StructGuard: <b>BOUNDED_VERIFIED</b> significa evidencia acotada;
    <b>PROVED</b> solo aparece cuando un backend formal/solver descarga la
    obligación generada.
  </p>
</header>
<div class='layout'>
  <aside>
    <h2>Navegación</h2>
    <ul>
      <li><a href='#summary'>Resumen</a></li>
      <li><a href='#diagnostics'>Diagnósticos</a></li>
      <li><a href='#files'>Archivos</a></li>
      <li><a href='#raw'>JSON crudo</a></li>
    </ul>
    <h3>Archivos</h3>
    <ul>{''.join(file_nav[:50])}</ul>
  </aside>
  <main>
    <section id='summary' class='cards'>{cards}</section>

    <section class='panel'>
      <h2>Semántica de niveles</h2>
      <ul>{semantics}</ul>
    </section>

    <section class='panel'>
      <h2>Distribución por módulo</h2>
      <div class='modules'>{module_panel}</div>
    </section>

    <section class='panel'>
      <h2>Códigos de diagnóstico principales</h2>
      <ol>{top_codes}</ol>
    </section>

    <section id='diagnostics' class='panel'>
      <h2>Diagnósticos</h2>
      <p>
        <input
          id='q'
          placeholder='filtrar texto, símbolo, archivo, código'
          oninput='filterRows()'
        >
        <select id='level' onchange='filterRows()'>
          <option value=''>todos los niveles</option>
          {level_options}
        </select>
      </p>
      <table id='diag'>
        <thead>
          <tr>
            <th>Nivel</th>
            <th>Código</th>
            <th>Símbolo</th>
            <th>Ubicación</th>
            <th>Mensaje</th>
            <th>Detalles</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </section>

    <section id='files' class='panel'>
      <h2>Agrupado por archivo</h2>
      {''.join(file_sections)}
    </section>

    <section id='raw' class='panel'>
      <h2>JSON crudo</h2>
      <details>
        <summary>mostrar JSON del reporte</summary>
        <pre>{raw}</pre>
      </details>
    </section>
  </main>
</div>
<script>
function filterRows(){{
  const q = document.getElementById('q').value.toLowerCase();
  const l = document.getElementById('level').value;
  document.querySelectorAll('#diag tbody tr').forEach(tr => {{
    const ok =
      (!q || tr.innerText.toLowerCase().includes(q)) &&
      (!l || tr.dataset.level === l);
    tr.style.display = ok ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

    path.write_text(
        html,
        encoding="utf-8",
    )

    return path
