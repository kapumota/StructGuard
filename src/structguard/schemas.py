from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

REPORT_LEVELS = {"FAILED", "WARNING", "UNKNOWN", "HEURISTIC", "BOUNDED_VERIFIED", "PROVED", "INFO"}
GUARANTEE_LEVELS = {"G1_HEURISTIC", "G2_STRUCTURAL", "G3_BOUNDED", "G4_EXECUTED", "G5_FORMALLY_VERIFIED"}
SARIF_LEVELS = {"error", "warning", "note", "none"}


def load_schema(name: str) -> dict[str, Any]:
    """Carga un documento JSON Schema incluido por nombre de archivo."""
    return json.loads((files("structguard") / "schemas" / name).read_text(encoding="utf-8"))


def validate_structguard_report_dict(data: dict[str, Any]) -> list[str]:
    """Validador pequeño, sin dependencias, para el esquema de reportes incluido.

    Los archivos JSON Schema se incluyen para validadores externos; esta función
    aplica el contrato requerido en pruebas y entornos ligeros donde jsonschema
    no está instalado.
    """
    errors: list[str] = []
    for key in ["schema_version", "tool", "root", "counts", "result_semantics", "diagnostics"]:
        if key not in data:
            errors.append(f"falta clave de nivel superior: {key}")
    if data.get("schema_version") != "structguard-report/v1":
        errors.append("schema_version debe ser structguard-report/v1")
    tool = data.get("tool")
    if not isinstance(tool, dict) or tool.get("name") != "StructGuard" or not tool.get("version"):
        errors.append("tool debe contener name=StructGuard y una version no vacía")
    if not isinstance(data.get("counts"), dict):
        errors.append("counts debe ser un objeto")
    if "guarantee_counts" in data and not isinstance(data.get("guarantee_counts"), dict):
        errors.append("guarantee_counts debe ser un objeto")
    if not isinstance(data.get("result_semantics"), dict):
        errors.append("result_semantics debe ser un objeto")
    diagnostics = data.get("diagnostics")
    if not isinstance(diagnostics, list):
        errors.append("diagnostics debe ser una lista")
        return errors
    for i, diag in enumerate(diagnostics):
        if not isinstance(diag, dict):
            errors.append(f"diagnostics[{i}] debe ser un objeto")
            continue
        for key in ["level", "code", "message", "details"]:
            if key not in diag:
                errors.append(f"diagnostics[{i}] no contiene {key}")
        if diag.get("level") not in REPORT_LEVELS:
            errors.append(f"diagnostics[{i}].level no es válido: {diag.get('level')!r}")
        if not diag.get("code"):
            errors.append(f"diagnostics[{i}].code no debe estar vacío")
        if not isinstance(diag.get("details", {}), dict):
            errors.append(f"diagnostics[{i}].details debe ser un objeto")
        guarantee = diag.get("guarantee")
        if guarantee is not None:
            if not isinstance(guarantee, dict):
                errors.append(f"diagnostics[{i}].guarantee debe ser un objeto")
            elif guarantee.get("level") not in GUARANTEE_LEVELS:
                errors.append(f"diagnostics[{i}].guarantee.level no es válido: {guarantee.get('level')!r}")
    return errors


def validate_sarif_dict(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("version") != "2.1.0":
        errors.append("La versión SARIF debe ser 2.1.0")
    runs = data.get("runs")
    if not isinstance(runs, list) or not runs:
        errors.append("SARIF runs debe ser una lista no vacía")
        return errors
    for ri, run in enumerate(runs):
        driver = ((run.get("tool") or {}).get("driver") or {}) if isinstance(run, dict) else {}
        if driver.get("name") != "StructGuard":
            errors.append(f"runs[{ri}].tool.driver.name debe ser StructGuard")
        results = run.get("results") if isinstance(run, dict) else None
        if not isinstance(results, list):
            errors.append(f"runs[{ri}].results debe ser una lista")
            continue
        for i, result in enumerate(results):
            if result.get("level") not in SARIF_LEVELS:
                errors.append(f"runs[{ri}].results[{i}].level no es válido: {result.get('level')!r}")
            for key in ["ruleId", "message", "locations"]:
                if key not in result:
                    errors.append(f"runs[{ri}].results[{i}] no contiene {key}")
    return errors
