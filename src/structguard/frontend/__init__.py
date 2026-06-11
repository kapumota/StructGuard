from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import re

from ..cppscan import iter_cpp_files, scan_project
from ..model import Diagnostic, ProjectReport


@dataclass
class FrontendFileSummary:
    file: str
    includes: int
    namespaces: list[str]
    classes: int
    methods: int
    fields: int
    templates: int
    external_definitions: int
    macros: int


def _namespaces(text: str) -> list[str]:
    return sorted(
        set(
            re.findall(
                r"\bnamespace\s+([A-Za-z_]\w*)\s*\{",
                text,
            )
        )
    )


def summarize_frontend(
    root: Path,
    headers_only: bool = False,
) -> list[FrontendFileSummary]:
    out = []

    for f in iter_cpp_files(root, headers_only=headers_only):
        text = f.read_text(
            encoding="utf-8",
            errors="ignore",
        )

        classes = scan_project(
            f,
            headers_only=headers_only,
        )

        out.append(
            FrontendFileSummary(
                file=str(f),
                includes=len(
                    re.findall(
                        r"^\s*#\s*include\b",
                        text,
                        re.M,
                    )
                ),
                namespaces=_namespaces(text),
                classes=len(classes),
                methods=sum(len(c.methods) for c in classes),
                fields=sum(len(c.fields) for c in classes),
                templates=len(
                    re.findall(
                        r"\btemplate\s*<",
                        text,
                    )
                ),
                external_definitions=len(
                    re.findall(
                        r"\b[A-Za-z_]\w*\s*(?:<[^>]+>)?\s*::\s*~?[A-Za-z_]\w*\s*\(",
                        text,
                    )
                ),
                macros=len(
                    re.findall(
                        r"^\s*#\s*define\b",
                        text,
                        re.M,
                    )
                ),
            )
        )

    return out


def frontend_project(
    root: Path,
    headers_only: bool = False,
) -> ProjectReport:
    report = ProjectReport(root=str(root))

    summaries = summarize_frontend(
        root,
        headers_only=headers_only,
    )

    if not summaries:
        report.diagnostics.append(
            Diagnostic(
                level="WARNING",
                code="FRONTEND_NO_FILES",
                message="No C++ files discovered.",
                file=str(root),
            )
        )
        return report

    totals = {
        "files": len(summaries),
        "classes": sum(s.classes for s in summaries),
        "methods": sum(s.methods for s in summaries),
        "fields": sum(s.fields for s in summaries),
        "templates": sum(s.templates for s in summaries),
        "external_definitions": sum(
            s.external_definitions for s in summaries
        ),
        "includes": sum(s.includes for s in summaries),
    }

    report.diagnostics.append(
        Diagnostic(
            level="INFO",
            code="FRONTEND_SUMMARY",
            message="C++ frontend scan completed.",
            file=str(root),
            details=totals,
        )
    )

    for s in summaries:
        if s.classes or s.external_definitions or s.templates:
            report.diagnostics.append(
                Diagnostic(
                    level="INFO",
                    code="FRONTEND_FILE",
                    message=(
                        f"{Path(s.file).name}: "
                        f"{s.classes} classes, "
                        f"{s.methods} methods, "
                        f"{s.external_definitions} external definitions."
                    ),
                    file=s.file,
                    details=asdict(s),
                )
            )

    return report


def write_frontend_json(
    summaries: list[FrontendFileSummary],
    out: Path,
) -> Path:
    out.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.write_text(
        json.dumps(
            [asdict(s) for s in summaries],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return out