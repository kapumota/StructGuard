from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from structguard.policy.validator import validate_policy_file, validate_policy_mapping


def test_policy_accepts_current_structguard_yml() -> None:
    result = validate_policy_file("structguard.yml")
    assert result.valid, [issue.as_dict() for issue in result.issues]


def test_policy_rejects_unknown_key_with_suggestion() -> None:
    result = validate_policy_mapping({"version": 1, "deep-secuirty": True})
    assert not result.valid
    assert result.issues[0].code == "POLICY_UNKNOWN_KEY"
    assert result.issues[0].message == "Clave desconocida: deep-secuirty. Quizá quiso decir deep-security."


def test_policy_rejects_unknown_nested_key() -> None:
    result = validate_policy_mapping({"version": 1, "frontend": {"cpp": {"primari": "clang"}}})
    assert not result.valid
    assert result.issues[0].path == "frontend.cpp.primari"


def test_policy_validate_cli_reports_invalid_key(tmp_path: Path) -> None:
    policy = tmp_path / "structguard.yml"
    policy.write_text("version: 1\ndeep-secuirty: true\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "structguard.cli", "policy", "validate", str(policy)],
        text=True,
        capture_output=True,
        env={"PYTHONPATH": "src"},
        check=False,
    )
    assert result.returncode == 1
    assert "Clave desconocida: deep-secuirty. Quizá quiso decir deep-security." in result.stdout


def test_policy_validate_cli_accepts_valid_policy(tmp_path: Path) -> None:
    policy = tmp_path / "structguard.yml"
    policy.write_text(
        """version: 1
profile: generic-cpp
frontend:
  cpp:
    primary: clang
    fallback_allowed: false
rules:
  SG-CONTRACT-MISSING-PRECONDITION:
    severity: error
outputs:
  sarif: true
  junit: true
  html: true
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "structguard.cli", "policy", "validate", str(policy)],
        text=True,
        capture_output=True,
        env={"PYTHONPATH": "src"},
        check=False,
    )
    assert result.returncode == 0
    assert "Política válida" in result.stdout
