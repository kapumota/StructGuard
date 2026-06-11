from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from structguard.model import Diagnostic


class GuaranteeLevel(str, Enum):
    G1_HEURISTIC = "G1_HEURISTIC"
    G2_STRUCTURAL = "G2_STRUCTURAL"
    G3_BOUNDED = "G3_BOUNDED"
    G4_EXECUTED = "G4_EXECUTED"
    G5_FORMALLY_VERIFIED = "G5_FORMALLY_VERIFIED"


@dataclass(frozen=True)
class GuaranteeInfo:
    level: GuaranteeLevel
    label: str
    description: str

    def as_dict(self) -> dict[str, str]:
        return {
            "level": self.level.value,
            "label": self.label,
            "description": self.description,
        }


GUARANTEE_CATALOG: dict[GuaranteeLevel, GuaranteeInfo] = {
    GuaranteeLevel.G1_HEURISTIC: GuaranteeInfo(
        level=GuaranteeLevel.G1_HEURISTIC,
        label="Heurístico",
        description="Resultado basado en patrones, nombres, tokens o señales incompletas. No prueba corrección.",
    ),
    GuaranteeLevel.G2_STRUCTURAL: GuaranteeInfo(
        level=GuaranteeLevel.G2_STRUCTURAL,
        label="Estructural",
        description="Resultado derivado de SourceIR, ContractIR, BindingIR o reglas estructurales documentadas.",
    ),
    GuaranteeLevel.G3_BOUNDED: GuaranteeInfo(
        level=GuaranteeLevel.G3_BOUNDED,
        label="Acotado",
        description="Resultado dentro de límites finitos. No equivale a prueba formal para todo C++.",
    ),
    GuaranteeLevel.G4_EXECUTED: GuaranteeInfo(
        level=GuaranteeLevel.G4_EXECUTED,
        label="Ejecutado",
        description="Resultado observado mediante ejecución de tests, harnesses o fuzzing nativo.",
    ),
    GuaranteeLevel.G5_FORMALLY_VERIFIED: GuaranteeInfo(
        level=GuaranteeLevel.G5_FORMALLY_VERIFIED,
        label="Formal",
        description="Resultado descargado por un backend formal soportado sobre un modelo explícito.",
    ),
}

GUARANTEE_ORDER: tuple[GuaranteeLevel, ...] = (
    GuaranteeLevel.G1_HEURISTIC,
    GuaranteeLevel.G2_STRUCTURAL,
    GuaranteeLevel.G3_BOUNDED,
    GuaranteeLevel.G4_EXECUTED,
    GuaranteeLevel.G5_FORMALLY_VERIFIED,
)

_DISPLAY_LEVELS = {
    "BOUNDED_VERIFIED": "BOUNDED_CHECK_PASSED",
    "PROVED": "FORMALLY_VERIFIED",
}

_STRUCTURAL_PREFIXES = (
    "BINDING_",
    "CONTRACT_",
    "DSL_",
    "MEM_",
    "POLICY_",
    "SOURCE_",
    "SG-",
    "STRICT_AST_",
    "CLANG_",
)

_HEURISTIC_PREFIXES = (
    "SEC_",
    "FUZZ_",
    "PERF_",
    "BENCH_",
    "DOCS_",
    "HEURISTIC_",
    "ASSIST_",
)


def guarantee_info(level: GuaranteeLevel | str) -> GuaranteeInfo:
    if isinstance(level, str):
        level = GuaranteeLevel(level)
    return GUARANTEE_CATALOG[level]


def default_guarantee() -> GuaranteeInfo:
    return guarantee_info(GuaranteeLevel.G1_HEURISTIC)


def diagnostic_display_level(diagnostic: Diagnostic) -> str:
    return _DISPLAY_LEVELS.get(diagnostic.level, diagnostic.level)


def normalize_display_level(level: str) -> str:
    return _DISPLAY_LEVELS.get(level, level)


def infer_guarantee(diagnostic: Diagnostic) -> GuaranteeInfo:
    details = dict(diagnostic.details or {})
    explicit = details.get("guarantee_level") or details.get("guarantee")
    if isinstance(explicit, dict):
        explicit = explicit.get("level")
    if explicit:
        try:
            return guarantee_info(str(explicit))
        except ValueError:
            pass

    level = diagnostic.level.upper()
    code = diagnostic.code.upper()
    evidence = str(details.get("evidence", "")).lower()

    if level == "PROVED" or evidence in {"formal_backend", "smt_solver_or_formal_bridge"}:
        return guarantee_info(GuaranteeLevel.G5_FORMALLY_VERIFIED)
    if evidence in {"native_execution", "test_execution", "native_fuzzing"}:
        return guarantee_info(GuaranteeLevel.G4_EXECUTED)
    if level == "BOUNDED_VERIFIED" or "BOUNDED" in code or evidence == "bounded_symbolic_execution":
        return guarantee_info(GuaranteeLevel.G3_BOUNDED)
    if code.startswith(_STRUCTURAL_PREFIXES) or evidence in {"binding", "contract_dsl", "clang_ast", "clang_ast_gate", "static_analysis"}:
        return guarantee_info(GuaranteeLevel.G2_STRUCTURAL)
    if level == "HEURISTIC" or code.startswith(_HEURISTIC_PREFIXES) or evidence in {"heuristic_analysis", "abstract_fuzzing", "abstract_test_generation"}:
        return guarantee_info(GuaranteeLevel.G1_HEURISTIC)
    if level in {"FAILED", "WARNING"} and code.startswith(("INVARIANT", "POSTCONDITION", "PRECONDITION")):
        return guarantee_info(GuaranteeLevel.G3_BOUNDED)
    return guarantee_info(GuaranteeLevel.G1_HEURISTIC)


def guarantee_counts(items: Iterable[GuaranteeInfo]) -> dict[str, int]:
    counts = {level.value: 0 for level in GUARANTEE_ORDER}
    for item in items:
        counts[item.level.value] = counts.get(item.level.value, 0) + 1
    return counts


def guarantee_counts_from_diagnostics(diagnostics: Iterable[Diagnostic]) -> dict[str, int]:
    return guarantee_counts(infer_guarantee(diagnostic) for diagnostic in diagnostics)


def guarantee_summary_lines(counts: dict[str, int]) -> list[str]:
    lines: list[str] = []
    for level in GUARANTEE_ORDER:
        info = guarantee_info(level)
        lines.append(f"{level.value} {info.label}: {counts.get(level.value, 0)}")
    return lines


def guarantee_to_dict(diagnostic: Diagnostic) -> dict[str, Any]:
    info = infer_guarantee(diagnostic)
    return info.as_dict()
