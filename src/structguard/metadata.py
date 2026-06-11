from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .model import Diagnostic


EVIDENCE_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("FORMAL", "smt_solver_or_formal_bridge"),
    ("STRICT_AST", "clang_ast_gate"),
    ("CLANG", "clang_ast"),
    ("PIPELINE", "clang_ast_pipeline"),
    ("SEC", "security_heuristic"),
    ("FUZZ", "abstract_test_generation"),
    ("LINT", "contract_lint"),
    ("DSL", "contract_dsl"),
    ("DOCS", "documentation_model"),
    ("PERF", "static_performance_model"),
    ("HEURISTIC", "heuristic_recommendation"),
)

REMEDIATION_BY_CODE: dict[str, str] = {
    "INVARIANT_NOT_PRESERVED": "Revisar la operación que modifica estado; añadir guardas requires o corregir la actualización que rompe el invariante.",
    "POSTCONDITION_FAILED": "Comparar la postcondición con el estado final modelado; corregir la implementación o ajustar el contrato.",
    "PRECONDITION_VIOLATED": "Añadir requires explícito o validar la condición antes de llamar la operación.",
    "MISSING_REQUIRES": "Añadir un comentario // requires: ... cerca del método o usar contratos estándar/DSL.",
    "NO_CONTRACTS": "Agregar invariantes/requires/ensures mínimos para que el verificador tenga obligaciones verificables.",
    "STRICT_AST_CLANG_NOT_FOUND": "Instalar clang++/clang o ejecutar sin --strict-ast si solo se desea análisis heurístico.",
    "STRICT_AST_FAILED": "Compilar/parsear la cabecera con Clang; revisar includes, estándar C++ y errores sintácticos.",
    "FORMAL_SMT_ARTIFACT": "Inspeccionar el .smt2 generado y, si hay SAT, revisar el modelo de Z3 como posible contraejemplo del puente formal.",
    "SEC_OVERFLOW_RISK": "Revisar límites de índice/capacidad y añadir guards antes de incrementar o indexar.",
    "SEC_UNINITIALIZED_FIELD": "Inicializar campos en constructor, initializer list o valor por defecto de miembro.",
    "FUZZ_MISSING_PRECONDITION_COUNTEREXAMPLE": "Agregar una precondición o guarda en tiempo de ejecución para bloquear la secuencia inválida generada por testgen abstracto.",
}


def infer_evidence(d: Diagnostic) -> str:
    code = d.code.upper()
    for prefix, evidence in EVIDENCE_BY_PREFIX:
        if code.startswith(prefix):
            return evidence
    if d.level == "PROVED":
        return "formal_backend"
    if d.level == "BOUNDED_VERIFIED" or any(key in code for key in ("INVARIANT", "POSTCONDITION", "BOUNDED")):
        return "bounded_symbolic_execution"
    if d.level == "HEURISTIC":
        return "heuristic_analysis"
    if d.level == "UNKNOWN":
        return "insufficient_model_coverage"
    return "static_analysis"


def infer_confidence(d: Diagnostic) -> str:
    evidence = infer_evidence(d)
    if d.level == "PROVED":
        return "high"
    if d.level == "FAILED" and d.details.get("counterexample"):
        return "high"
    if evidence in {"clang_ast_gate", "bounded_symbolic_execution", "formal_backend"}:
        return "high"
    if evidence in {"clang_ast", "contract_lint", "contract_dsl", "abstract_fuzzing", "abstract_test_generation"}:
        return "medium"
    if d.level in {"UNKNOWN", "WARNING"}:
        return "low" if d.level == "UNKNOWN" else "medium"
    if d.level in {"HEURISTIC", "INFO"}:
        return "medium"
    return "medium"


def infer_category(d: Diagnostic) -> str:
    code = d.code.upper()
    if code.startswith(("SEC", "FUZZ")):
        return "security"
    if code.startswith(("FORMAL", "PIPELINE")):
        return "formal"
    if code.startswith(("STRICT_AST", "CLANG", "FRONTEND")):
        return "frontend"
    if code.startswith(("LINT", "DSL")):
        return "contracts"
    if code.startswith(("PERF", "BENCH")):
        return "performance"
    if code.startswith(("DOCS", "HEURISTIC_ASSIST")):
        return "developer_experience"
    if any(k in code for k in ("INVARIANT", "POSTCONDITION", "PRECONDITION", "BOUNDED")):
        return "verification"
    return "general"


def remediation(d: Diagnostic) -> str:
    if d.code in REMEDIATION_BY_CODE:
        return REMEDIATION_BY_CODE[d.code]
    code = d.code.upper()
    if code.startswith("SEC_"):
        return "Revisar manualmente la señal de seguridad, las reglas SEC son heurísticas salvo que se eleven mediante política CI."
    if code.startswith("FORMAL_"):
        return "Tratar el artefacto formal como evidencia experimental, revisar el SMT/Viper generado antes de concluir prueba completa."
    if d.level == "UNKNOWN":
        return "Reducir complejidad del método, añadir contratos explícitos o activar Clang/SMT para aumentar cobertura del modelo."
    if d.level == "WARNING":
        return "Revisar la advertencia y decidir si debe convertirse en contrato, excepción de política o corrección de código."
    return "No hay acción obligatoria; conservar como evidencia o contexto de análisis."


def enriched_details(d: Diagnostic) -> dict[str, Any]:
    details = dict(d.details or {})
    details.setdefault("confidence", infer_confidence(d))
    details.setdefault("evidence", infer_evidence(d))
    details.setdefault("category", infer_category(d))
    if d.level in {"FAILED", "WARNING", "UNKNOWN"}:
        details.setdefault("remediation", remediation(d))
    return details


def diagnostic_to_dict(d: Diagnostic) -> dict[str, Any]:
    data = asdict(d)
    data["details"] = enriched_details(d)
    from .findings.guarantee import diagnostic_display_level, guarantee_to_dict

    data["display_level"] = diagnostic_display_level(d)
    data["guarantee"] = guarantee_to_dict(d)
    return data


def enrich_report_in_place(diagnostics: list[Diagnostic]) -> None:
    for d in diagnostics:
        d.details = enriched_details(d)
