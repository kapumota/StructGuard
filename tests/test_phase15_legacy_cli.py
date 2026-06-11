from __future__ import annotations

from structguard.legacy import LEGACY_COMMANDS
from structguard.legacy import emit_legacy_notice
from structguard.legacy import get_legacy_policy
from structguard.legacy import legacy_policy_rows


EXPECTED_COMMANDS = {
    "verify",
    "lint",
    "security",
    "perf",
    "ci",
    "bench",
    "assist",
    "advanced",
    "clang",
    "formal",
    "fuzz",
}


def test_legacy_registry_covers_expected_commands() -> None:
    commands = {policy.command for policy in legacy_policy_rows()}

    assert commands == EXPECTED_COMMANDS


def test_legacy_registry_has_decision_and_replacement() -> None:
    valid_decisions = {"mantener", "migrar", "deprecar", "eliminar despues"}

    for policy in LEGACY_COMMANDS:
        assert policy.decision in valid_decisions
        assert policy.replacement
        assert policy.removal
        assert policy.rationale


def test_fuzz_is_deprecated_in_favor_of_testgen() -> None:
    policy = get_legacy_policy("fuzz")

    assert policy.decision == "deprecar"
    assert policy.replacement == "testgen"


def test_verify_migrates_to_scan_contracts() -> None:
    policy = get_legacy_policy("verify")

    assert policy.decision == "migrar"
    assert policy.replacement == "scan --preset contracts"


def test_security_migrates_to_scan_security() -> None:
    policy = get_legacy_policy("security")

    assert policy.decision == "migrar"
    assert policy.replacement == "scan --preset security"


def test_emit_legacy_notice_mentions_command_and_replacement(capsys) -> None:  # type: ignore[no-untyped-def]
    emit_legacy_notice("verify")

    captured = capsys.readouterr()

    assert "verify" in captured.err
    assert "scan --preset contracts" in captured.err


def test_legacy_rows_keep_stable_order() -> None:
    commands = [policy.command for policy in legacy_policy_rows()]

    assert commands == [
        "verify",
        "lint",
        "security",
        "perf",
        "ci",
        "bench",
        "assist",
        "advanced",
        "clang",
        "formal",
        "fuzz",
    ]
