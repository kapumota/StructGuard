from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from . import __version__
from .metadata import diagnostic_to_dict
from .model import ALL_LEVELS, ProjectReport


def _sarif_level(level: str) -> str:
    return {
        "FAILED": "error",
        "WARNING": "warning",
        "UNKNOWN": "warning",
        "HEURISTIC": "note",
        "BOUNDED_VERIFIED": "note",
        "PROVED": "note",
        "INFO": "note",
    }.get(level, "note")


def write_junit(
    report: ProjectReport,
    path: Path,
    suite_name: str = "StructGuard",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    diagnostics = [
        d
        for d in report.diagnostics
        if d.code not in {"CI_GATE_PASSED", "CI_GATE_FAILED"}
    ]

    ts = ET.Element(
        "testsuite",
        {
            "name": suite_name,
            "tests": str(len(diagnostics)),
            "failures": str(sum(d.level == "FAILED" for d in diagnostics)),
            "errors": "0",
            "skipped": str(sum(d.level == "UNKNOWN" for d in diagnostics)),
        },
    )

    for i, d in enumerate(diagnostics):
        tc = ET.SubElement(
            ts,
            "testcase",
            {
                "classname": (d.file or report.root).replace("/", "."),
                "name": f"{d.code}:{d.symbol or i}",
            },
        )

        msg = f"{d.code} {d.symbol or ''}: {d.message}"

        if d.level == "FAILED":
            e = ET.SubElement(
                tc,
                "failure",
                {
                    "message": msg,
                    "type": d.code,
                },
            )
            e.text = json.dumps(
                diagnostic_to_dict(d),
                indent=2,
                ensure_ascii=False,
            )

        elif d.level == "UNKNOWN":
            e = ET.SubElement(
                tc,
                "skipped",
                {
                    "message": msg,
                },
            )
            e.text = json.dumps(
                diagnostic_to_dict(d),
                indent=2,
                ensure_ascii=False,
            )

        elif d.level == "WARNING":
            props = ET.SubElement(tc, "properties")
            ET.SubElement(
                props,
                "property",
                {
                    "name": "warning",
                    "value": msg,
                },
            )

    tree = ET.ElementTree(ts)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="utf-8", xml_declaration=True)

    return path


def write_sarif(report: ProjectReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    rules = {}
    results = []

    for d in report.diagnostics:
        if d.code in {"CI_GATE_PASSED", "CI_GATE_FAILED"}:
            continue

        rules.setdefault(
            d.code,
            {
                "id": d.code,
                "name": d.code,
                "shortDescription": {
                    "text": d.code.replace("_", " ").title(),
                },
                "fullDescription": {
                    "text": d.message[:500],
                },
                "defaultConfiguration": {
                    "level": _sarif_level(d.level),
                },
            },
        )

        loc = {
            "physicalLocation": {
                "artifactLocation": {
                    "uri": d.file or "",
                },
            },
        }

        if d.line:
            loc["physicalLocation"]["region"] = {
                "startLine": int(d.line),
            }

        results.append(
            {
                "ruleId": d.code,
                "level": _sarif_level(d.level),
                "message": {
                    "text": d.message,
                },
                "locations": [loc],
                "properties": {
                    "structguardLevel": d.level,
                    "symbol": d.symbol,
                    "details": diagnostic_to_dict(d).get("details", {}),
                    "confidenceSemantics": (
                        "BOUNDED_VERIFIED es evidencia acotada, no una prueba formal; "
                        "PROVED se emite únicamente por backends formales o solvers."
                    ),
                },
            }
        )

    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "StructGuard",
                        "version": __version__,
                        "informationUri": "https://structguard.local",
                        "rules": list(rules.values()),
                    },
                },
                "results": results,
            },
        ],
    }

    path.write_text(
        json.dumps(sarif, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return path


def write_summary_markdown(
    report: ProjectReport,
    path: Path,
    title: str = "Resumen CI de StructGuard",
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)

    counts = report.counts()
    gate = next(
        (
            d
            for d in report.diagnostics
            if d.code in {"CI_GATE_PASSED", "CI_GATE_FAILED"}
        ),
        None,
    )

    top = {}
    for d in report.diagnostics:
        top[d.code] = top.get(d.code, 0) + 1

    lines = [
        f"# {title}",
        "",
        f"Raíz: `{report.root}`",
        "",
        "## Gate",
        "",
    ]

    if gate:
        lines += [
            f"**{gate.code}** — {gate.message}",
            "",
        ]

    lines += [
        "## Conteos",
        "",
        "| Nivel | Cantidad |",
        "|---|---:|",
    ]

    for level in ALL_LEVELS:
        lines.append(f"| {level} | {counts.get(level, 0)} |")

    lines += [
        "",
        "## Códigos de diagnóstico principales",
        "",
        "| Código | Cantidad |",
        "|---|---:|",
    ]

    for code, n in sorted(top.items(), key=lambda kv: (-kv[1], kv[0]))[:20]:
        lines.append(f"| `{code}` | {n} |")

    lines += [
        "",
        "## Primeras fallas/advertencias",
        "",
    ]

    for d in [x for x in report.diagnostics if x.level in {"FAILED", "WARNING"}][:30]:
        loc = f"{d.file}:{d.line}" if d.file and d.line else (d.file or "")
        lines.append(
            f"- **{d.level}** `{d.code}` `{d.symbol or ''}` {loc} — {d.message}"
        )

    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return path


def _escape(value: str | None) -> str:
    return (
        value or ""
    ).replace(
        "%",
        "%25",
    ).replace(
        "\r",
        "%0D",
    ).replace(
        "\n",
        "%0A",
    ).replace(
        ":",
        "%3A",
    ).replace(
        ",",
        "%2C",
    )


def print_github_annotations(report: ProjectReport) -> None:
    for d in report.diagnostics:
        if d.level not in {"FAILED", "WARNING"}:
            continue

        cmd = "error" if d.level == "FAILED" else "warning"
        file_part = f" file={_escape(d.file)}," if d.file else ""
        line_part = f"line={int(d.line)}," if d.line else ""
        title = _escape((d.code + " " + (d.symbol or "")).strip())
        message = _escape(d.message)

        print(f"::{cmd}{file_part}{line_part}title={title}::{message}")