#!/usr/bin/env python3
"""Validación mínima de artefactos generados por StructGuard.

Uso típico:
  python scripts/validate_outputs.py
  python scripts/validate_outputs.py --profile ci --dir report
  python scripts/validate_outputs.py --profile demo-clean --dir report/demo_clean
  python scripts/validate_outputs.py --profile demo-bug --dir report/demo_bug
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


class ValidationError(AssertionError):
    """Se lanza cuando un artefacto de salida de StructGuard está ausente o mal formado."""


def require(path: Path) -> Path:
    if not path.exists() or path.stat().st_size == 0:
        raise ValidationError(f"Artefacto ausente o vacío: {path}")
    return path


def read_json(path: Path) -> dict:
    try:
        return json.loads(require(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"JSON inválido: {path}: {exc}") from exc


def validate_report_json(path: Path) -> dict:
    data = read_json(path)
    if "diagnostics" not in data or "counts" not in data:
        raise ValidationError(f"Reporte StructGuard sin diagnostics/counts: {path}")
    if not isinstance(data["diagnostics"], list) or not isinstance(data["counts"], dict):
        raise ValidationError(f"Reporte StructGuard con tipos inválidos: {path}")
    require_professional_metadata = bool(data.get("schema_version"))
    for idx, diag in enumerate(data.get("diagnostics", [])):
        details = diag.get("details", {})
        if details and not isinstance(details, dict):
            raise ValidationError(f"Diagnostic details inválidos en {path} índice {idx}")
        if require_professional_metadata and ("confidence" not in details or "evidence" not in details):
            raise ValidationError(f"Diagnostic sin metadata profesional confidence/evidence en {path} índice {idx}")
    semantics = data.get("result_semantics", {})
    if semantics and not isinstance(semantics, dict):
        raise ValidationError(f"result_semantics debe ser objeto JSON: {path}")
    return data


def validate_html(path: Path) -> None:
    html = require(path).read_text(encoding="utf-8", errors="ignore")
    if "StructGuard" not in html:
        raise ValidationError(f"HTML no parece reporte StructGuard: {path}")


def validate_junit(path: Path) -> None:
    try:
        ET.parse(require(path))
    except ET.ParseError as exc:
        raise ValidationError(f"JUnit XML inválido: {path}: {exc}") from exc


def validate_sarif(path: Path) -> None:
    sarif = read_json(path)
    if sarif.get("version") != "2.1.0" or not sarif.get("runs"):
        raise ValidationError(f"SARIF inválido o incompleto: {path}")


def validate_ci(root: Path) -> None:
    validate_report_json(root / "structguard-ci.json")
    validate_html(root / "structguard-ci.html")
    validate_junit(root / "structguard-junit.xml")
    validate_sarif(root / "structguard.sarif")
    require(root / "structguard-summary.md")


def validate_demo_clean(root: Path) -> None:
    analyze = validate_report_json(root / "analyze.json")
    ci = validate_report_json(root / "ci.json")
    security = validate_report_json(root / "security.json")
    docs = read_json(root / "docs.json")

    for html_name in ["analyze.html", "security.html", "ci.html", "docs.html"]:
        validate_html(root / html_name)
    validate_junit(root / "junit.xml")
    validate_sarif(root / "structguard.sarif")
    require(root / "summary.md")

    if ci.get("counts", {}).get("FAILED", 0):
        raise ValidationError("La demo limpia no debe contener FAILED")
    if analyze.get("counts", {}).get("FAILED", 0):
        raise ValidationError("El análisis limpio no debe contener FAILED")
    if not isinstance(docs, dict):
        raise ValidationError("docs.json debe ser un objeto JSON")
    # Las señales de seguridad de nivel INFO son esperadas: revisión heurística, no gate de contrato.
    if "diagnostics" not in security:
        raise ValidationError("security.json debe contener diagnostics")


def validate_demo_bug(root: Path) -> None:
    report = validate_report_json(root / "bug_analysis.json")
    validate_html(root / "bug_analysis.html")
    txt = require(root / "bug_analysis.txt").read_text(encoding="utf-8", errors="ignore")
    expected = [
        d for d in report.get("diagnostics", [])
        if d.get("level") == "FAILED"
        and d.get("code") == "INVARIANT_NOT_PRESERVED"
        and d.get("symbol") == "BuggyStack::pop"
    ]
    if not expected:
        raise ValidationError("No se encontró el fallo intencional BuggyStack::pop / INVARIANT_NOT_PRESERVED")
    if "BuggyStack::pop" not in txt:
        raise ValidationError("bug_analysis.txt no evidencia BuggyStack::pop")



def validate_doctor(root: Path) -> None:
    data = read_json(root / "doctor.json")
    if "checks" not in data or "counts" not in data:
        raise ValidationError("doctor.json debe contener checks/counts")
    checks = data.get("checks", [])
    if not checks:
        raise ValidationError("doctor.json no contiene checks")
    names = {c.get("name") for c in checks}
    for required in {"python", "source-tree", "clean-source"}:
        if required not in names:
            raise ValidationError(f"doctor.json no contiene check requerido: {required}")

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Valida artefactos de salida de StructGuard.")
    parser.add_argument(
        "--profile",
        choices=["ci", "demo-clean", "demo-bug", "doctor"],
        default="ci",
        help="Tipo de artefactos a validar. Por defecto: ci.",
    )
    parser.add_argument(
        "--dir",
        default="report",
        help="Directorio que contiene los artefactos del perfil seleccionado.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = Path(args.dir)
    validators = {
        "ci": validate_ci,
        "demo-clean": validate_demo_clean,
        "demo-bug": validate_demo_bug,
        "doctor": validate_doctor,
    }
    validators[args.profile](root)
    print(f"Validación de salidas de StructGuard completada correctamente: profile={args.profile} dir={root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
