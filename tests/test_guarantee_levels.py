from __future__ import annotations

from structguard.findings.guarantee import (
    GuaranteeLevel,
    diagnostic_display_level,
    guarantee_counts_from_diagnostics,
    infer_guarantee,
)
from structguard.model import Diagnostic


def test_bounded_verified_is_displayed_as_bounded_check_passed() -> None:
    diagnostic = Diagnostic(
        level="BOUNDED_VERIFIED",
        code="POSTCONDITION_HOLDS_BOUNDED",
        message="No se encontró contraejemplo dentro del límite.",
    )

    assert diagnostic_display_level(diagnostic) == "BOUNDED_CHECK_PASSED"
    assert infer_guarantee(diagnostic).level == GuaranteeLevel.G3_BOUNDED


def test_structural_rules_receive_structural_guarantee() -> None:
    diagnostic = Diagnostic(
        level="WARNING",
        code="SG-BOUNDS-INDEX-RISK",
        message="Riesgo estructural de índice fuera de rango.",
    )

    assert infer_guarantee(diagnostic).level == GuaranteeLevel.G2_STRUCTURAL


def test_guarantee_counts_include_all_levels() -> None:
    diagnostics = [
        Diagnostic(level="HEURISTIC", code="FUZZ_NO_COUNTEREXAMPLE", message="Sin contraejemplo abstracto."),
        Diagnostic(level="WARNING", code="SG-SIZE-NOT-UPDATED", message="size no se actualiza."),
        Diagnostic(level="BOUNDED_VERIFIED", code="INVARIANT_HOLDS", message="Invariante acotado."),
        Diagnostic(level="PROVED", code="FORMAL_SMT_ARTIFACT", message="Obligación descargada."),
    ]

    counts = guarantee_counts_from_diagnostics(diagnostics)

    assert counts["G1_HEURISTIC"] == 1
    assert counts["G2_STRUCTURAL"] == 1
    assert counts["G3_BOUNDED"] == 1
    assert counts["G5_FORMALLY_VERIFIED"] == 1
