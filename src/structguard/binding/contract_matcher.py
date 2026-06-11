from __future__ import annotations

from structguard.sgdsl.diagnostics import SGDSLDiagnostic

from .binder import BindingIR, FieldBinding, MethodBinding, StructureBinding


def _candidate_text(candidates: list[str]) -> str:
    if not candidates:
        return ""
    return " Candidatos cercanos: " + ", ".join(candidates) + "."


def _structure_diag(code: str, message: str, binding: StructureBinding) -> SGDSLDiagnostic:
    return SGDSLDiagnostic(
        level="FAILED",
        code=code,
        message=message,
        source=binding.contract.source,
        line=binding.contract.line,
        symbol=binding.contract.qualified_name,
    )


def _field_diag(code: str, message: str, binding: StructureBinding, field: FieldBinding) -> SGDSLDiagnostic:
    return SGDSLDiagnostic(
        level="FAILED",
        code=code,
        message=message,
        source=field.contract.source,
        line=field.contract.line,
        symbol=f"{binding.contract.name}.{field.contract.name}",
    )


def _method_diag(code: str, message: str, binding: StructureBinding, method: MethodBinding) -> SGDSLDiagnostic:
    return SGDSLDiagnostic(
        level="FAILED",
        code=code,
        message=message,
        source=method.contract.source,
        line=method.contract.line,
        symbol=f"{binding.contract.name}.{method.contract.name}",
    )


def match_contracts_to_source(binding_ir: BindingIR) -> list[SGDSLDiagnostic]:
    diagnostics: list[SGDSLDiagnostic] = []
    for structure_binding in binding_ir.structures:
        if not structure_binding.matched:
            diagnostics.append(
                _structure_diag(
                    "BINDING_ORPHAN_STRUCTURE",
                    f"El contrato declara la estructura {structure_binding.contract.qualified_name}, pero no existe una clase o struct equivalente en el código fuente."
                    + _candidate_text(structure_binding.resolution.candidates),
                    structure_binding,
                )
            )
            continue
        for field_binding in structure_binding.fields:
            if not field_binding.matched:
                diagnostics.append(
                    _field_diag(
                        "BINDING_ORPHAN_FIELD",
                        f"El contrato declara el campo {field_binding.contract.name}, pero no existe en {structure_binding.source.name}."
                        + _candidate_text(field_binding.resolution.candidates),
                        structure_binding,
                        field_binding,
                    )
                )
        for method_binding in structure_binding.methods:
            if not method_binding.matched:
                diagnostics.append(
                    _method_diag(
                        "BINDING_ORPHAN_METHOD",
                        f"FAIL: contrato huérfano. El contrato declara el método {structure_binding.contract.name}::{method_binding.contract.name}, pero no existe en el código fuente."
                        + _candidate_text(method_binding.resolution.candidates),
                        structure_binding,
                        method_binding,
                    )
                )
    if not diagnostics:
        diagnostics.append(SGDSLDiagnostic(level="INFO", code="BINDING_CONTRACTS_MATCH_SOURCE", message="BindingIR válido: todos los contratos externos tienen símbolo fuente asociado."))
    return diagnostics
