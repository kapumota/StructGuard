from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json

from .model import Diagnostic, ProjectReport
from .verifier import verify_project
from .lint import lint_project
from .security import security_project
from .fuzz import fuzz_project


def _recommendation_for(d: Diagnostic) -> str | None:
    code = d.code
    msg = d.message.lower()

    if "requires" in msg or "precondition" in msg or "empty" in msg:
        return "Agrega una cláusula requires explícita antes de accesos inseguros; normalmente requires: !empty() o un límite de índice."

    if "invariant" in msg:
        return "Documenta el invariante de la estructura cerca de la clase y demuestra su preservación después de métodos mutadores."

    if "assert" in msg:
        return "Promueve las verificaciones assert de tiempo de ejecución a cláusulas requires formales para que CI pueda razonar sobre ellas."

    if "security" in code.lower() or "unsafe" in msg:
        return "Trata esto como un problema de corrección defensiva; agrega una guarda, un contrato y un caso de fuzzing."

    if d.level == "UNKNOWN":
        return "Simplifica el método, agrega contratos DSL o mueve este método al pipeline de Clang para obtener una IR más rica."

    return None


def assist_project(
    root: Path,
    *,
    headers_only=False,
    dsl_paths=None,
    seeds=8,
    steps=20,
) -> ProjectReport:
    reports = [
        verify_project(root, headers_only=headers_only, dsl_paths=dsl_paths),
        lint_project(root, headers_only=headers_only, dsl_paths=dsl_paths),
        security_project(root, headers_only=headers_only),
        fuzz_project(root, headers_only=headers_only, seeds=seeds, steps=steps),
    ]

    all_diags = [d for r in reports for d in r.diagnostics]
    out = ProjectReport(root=str(root))
    actionable = [d for d in all_diags if d.level in {"FAILED", "WARNING", "UNKNOWN"}]

    out.diagnostics.append(
        Diagnostic(
            level="INFO",
            code="HEURISTIC_ASSIST_SUMMARY",
            message="Revisión heurística de recomendaciones completada. No se usó ningún LLM externo, llamada de red ni modelo de IA generativa.",
            file=str(root),
            details={
                "input_diagnostics": len(all_diags),
                "actionable": len(actionable),
            },
        )
    )

    seen = set()

    for d in actionable[:50]:
        rec = _recommendation_for(d)
        key = (d.file, d.symbol, rec)

        if rec and key not in seen:
            seen.add(key)
            out.diagnostics.append(
                Diagnostic(
                    level="INFO",
                    code="HEURISTIC_ASSIST_RECOMMENDATION",
                    message=rec,
                    file=d.file,
                    line=d.line,
                    symbol=d.symbol,
                    details={"based_on": asdict(d)},
                )
            )

    if not seen:
        out.diagnostics.append(
            Diagnostic(
                level="HEURISTIC",
                code="HEURISTIC_ASSIST_NO_ACTIONS",
                message="No se encontraron recomendaciones inmediatas a partir de los diagnósticos actuales.",
                file=str(root),
            )
        )

    return out


def write_assist_json(report: ProjectReport, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            [asdict(d) for d in report.diagnostics],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return out