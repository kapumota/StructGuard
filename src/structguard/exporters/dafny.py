from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re
import shutil
import subprocess
from typing import Literal

from structguard.ir.contract_ir import ContractIR, MethodIR, StructureIR, build_contract_ir
from structguard.sgdsl.parser import load_sgdsl

DafnyStatus = Literal["GENERATED", "PARSED", "VERIFIED", "FAILED", "UNKNOWN", "UNSUPPORTED"]

SUPPORTED_STRUCTURES = frozenset({"ArrayStack", "ArrayQueue", "ArrayVector", "DisjointSet"})
FIELD_NAMES = frozenset({"n", "j", "capacity", "parent", "rank", "count", "size"})
RESERVED_NAMES = frozenset({"old", "true", "false", "and", "or", "not", "capacity", "empty"})


@dataclass(frozen=True)
class DafnyExportResult:
    structure: str
    status: DafnyStatus
    file: str | None
    notes: list[str]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _safe_name(name: str) -> str:
    cleaned = re.sub(r"\W+", "_", name).strip("_")
    return cleaned or "StructGuardModel"


def _needs_capacity(structure: StructureIR) -> bool:
    text = "\n".join(
        [p.expression for p in structure.invariants]
        + [p.expression for method in structure.methods for p in method.requires + method.ensures]
    )
    return "capacity" in text or structure.name in {"ArrayStack", "ArrayQueue", "ArrayVector"}


def _extra_fields(structure: StructureIR) -> list[str]:
    fields = ["n"]
    if _needs_capacity(structure):
        fields.append("capacity")
    if structure.name == "ArrayQueue":
        fields.append("j")
    if structure.name == "DisjointSet":
        fields.extend(["count"])
    return list(dict.fromkeys(fields))


def _translate_expr(expr: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    out = expr.strip()
    replacements = {
        "&&": "&&",
        "||": "||",
        "true": "true",
        "false": "false",
    }
    for source, target in replacements.items():
        out = out.replace(source, target)
    out = re.sub(r"\bcapacity\s*\(\s*\)", "capacity", out)
    out = re.sub(r"\bsize\s*\(\s*\)", "n", out)
    out = re.sub(r"\bempty\s*\(\s*\)", "n == 0", out)
    out = re.sub(r"\bold\s*\(\s*([A-Za-z_]\w*)\s*\)", r"old(\1)", out)
    if "->" in out or "delete" in out or "new " in out:
        notes.append(f"expresión no soportada para Dafny abstracto: {expr}")
    if "[" in out or "]" in out:
        notes.append(f"acceso por índice no traducido en esta fase: {expr}")
    return out, notes


def _expr_variables(expr: str) -> set[str]:
    names = set(re.findall(r"\b[A-Za-z_]\w*\b", expr))
    return {name for name in names if name not in RESERVED_NAMES and name not in FIELD_NAMES}


def _method_params(method: MethodIR, fields: set[str]) -> list[str]:
    params = [param.name for param in method.params if param.name]
    exprs = [p.expression for p in method.requires + method.ensures]
    for expr in exprs:
        for name in sorted(_expr_variables(expr)):
            if name not in fields and name not in params:
                params.append(name)
    return params


def _valid_predicate(structure: StructureIR, fields: list[str]) -> tuple[list[str], list[str]]:
    lines: list[str] = []
    notes: list[str] = []
    if structure.invariants:
        for predicate in structure.invariants:
            translated, unsupported = _translate_expr(predicate.expression)
            notes.extend(unsupported)
            lines.append(translated)
    else:
        lines.append("true")
    if "capacity" in fields and not any("capacity" in line for line in lines):
        lines.append("capacity >= 0")
    return lines, notes


def _emit_structure(structure: StructureIR) -> tuple[str, list[str]]:
    notes: list[str] = ["Modelo Dafny abstracto generado desde SGDSL; no traduce C++ real ni punteros."]
    name = _safe_name(structure.name)
    fields = _extra_fields(structure)
    valid_lines, valid_notes = _valid_predicate(structure, fields)
    notes.extend(valid_notes)

    lines: list[str] = [
        f"// Generado por StructGuard para {structure.qualified_name}",
        "// Backend Dafny experimental: modelo abstracto, no traducción de C++ real.",
        f"trait {name}Model {{",
    ]
    for field in fields:
        lines.append(f"  ghost var {field}: int")
    lines.append("")
    lines.append("  predicate Valid()")
    lines.append("    reads this")
    lines.append("  {")
    for index, expr in enumerate(valid_lines):
        suffix = " &&" if index < len(valid_lines) - 1 else ""
        lines.append(f"    {expr}{suffix}")
    lines.append("  }")
    lines.append("")

    field_set = set(fields)
    for method in structure.methods:
        params = _method_params(method, field_set)
        param_text = ", ".join(f"{param}: int" for param in params)
        lines.append(f"  method {method.name}({param_text})")
        lines.append("    requires Valid()")
        for requires in method.requires:
            translated, unsupported = _translate_expr(requires.expression)
            notes.extend(unsupported)
            lines.append(f"    requires {translated}")
        lines.append("    ensures Valid()")
        for ensures in method.ensures:
            translated, unsupported = _translate_expr(ensures.expression)
            notes.extend(unsupported)
            lines.append(f"    ensures {translated}")
        lines.append("")
    lines.append("}")
    lines.append("")
    return "\n".join(lines), notes


def _verify_with_dafny(path: Path) -> tuple[DafnyStatus, list[str]]:
    dafny_bin = shutil.which("dafny")
    if not dafny_bin:
        return "UNKNOWN", ["dafny no está instalado; el artefacto fue generado pero no verificado"]
    try:
        proc = subprocess.run([dafny_bin, "verify", str(path)], text=True, capture_output=True, timeout=20)
    except Exception as exc:
        return "UNKNOWN", [f"no se pudo ejecutar Dafny: {exc}"]
    if proc.returncode == 0:
        return "VERIFIED", [proc.stdout.strip() or "Dafny terminó sin errores"]
    output = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part)
    if "parse" in output.lower() or "syntax" in output.lower():
        return "FAILED", [output or "Dafny rechazó el archivo generado"]
    return "FAILED", [output or "Dafny devolvió código de error distinto de cero"]


def export_dafny_contracts(contract_paths: list[str], out_dir: Path, *, run_verifier: bool = False) -> list[DafnyExportResult]:
    out_dir.mkdir(parents=True, exist_ok=True)
    modules = load_sgdsl([Path(path) for path in contract_paths])
    contract_ir = build_contract_ir(modules)
    return export_dafny_ir(contract_ir, out_dir, run_verifier=run_verifier)


def export_dafny_ir(contract_ir: ContractIR, out_dir: Path, *, run_verifier: bool = False) -> list[DafnyExportResult]:
    results: list[DafnyExportResult] = []
    models_dir = out_dir / "dafny"
    models_dir.mkdir(parents=True, exist_ok=True)
    for structure in contract_ir.structures:
        if structure.name not in SUPPORTED_STRUCTURES:
            results.append(
                DafnyExportResult(
                    structure=structure.qualified_name,
                    status="UNSUPPORTED",
                    file=None,
                    notes=["estructura fuera del subconjunto inicial soportado por Dafny"],
                )
            )
            continue
        content, notes = _emit_structure(structure)
        path = models_dir / f"{_safe_name(structure.name)}Model.dfy"
        path.write_text(content, encoding="utf-8")
        status: DafnyStatus = "GENERATED"
        if run_verifier:
            status, verifier_notes = _verify_with_dafny(path)
            notes.extend(verifier_notes)
        results.append(DafnyExportResult(structure=structure.qualified_name, status=status, file=str(path), notes=notes))
    return results


def write_dafny_manifest(results: list[DafnyExportResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "backend": "dafny",
        "status_values": ["GENERATED", "PARSED", "VERIFIED", "FAILED", "UNKNOWN", "UNSUPPORTED"],
        "results": [result.as_dict() for result in results],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
