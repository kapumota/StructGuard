from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from structguard.core import AnalysisContext, AnalysisEngine, available_presets


def test_available_presets_include_ci_and_security() -> None:
    presets = set(available_presets())

    assert {"source", "contracts", "security", "ci", "full"}.issubset(presets)


def test_ci_and_security_are_planned_by_same_engine() -> None:
    engine = AnalysisEngine()

    ci_plan = engine.plan("ci")
    security_plan = engine.plan("security")

    assert ci_plan[0] == "LoadProfile"
    assert security_plan[0] == "LoadProfile"
    assert "RunSecurity" in ci_plan
    assert "RunSecurity" in security_plan


def test_engine_source_preset_builds_source_ir() -> None:
    context = AnalysisContext(
        root=Path("examples/cpp_projects"),
        preset="source",
        language="cpp",
        compile_commands=Path("examples/cpp_projects/compile_commands.json"),
        fallback_allowed=True,
    )

    result = AnalysisEngine().run(context)

    assert result.report.root == "examples/cpp_projects"
    assert result.context.source_ir is not None
    assert any(diagnostic.code == "ENGINE_PRESET" for diagnostic in result.report.diagnostics)
    assert any(diagnostic.code == "CPP_SOURCE_IR_SUMMARY" for diagnostic in result.report.diagnostics)


def test_scan_preset_security_uses_engine() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "structguard.cli",
            "scan",
            "examples/generic_cpp",
            "--profile",
            "generic-cpp",
            "--preset",
            "security",
        ],
        text=True,
        capture_output=True,
        env={"PYTHONPATH": "src"},
        check=False,
    )

    assert result.returncode == 0
    assert "ENGINE_PRESET" in result.stdout
    assert "RunSecurity" not in result.stderr


def test_scan_preset_ci_uses_engine() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "structguard.cli",
            "scan",
            "examples/generic_cpp",
            "--profile",
            "generic-cpp",
            "--preset",
            "ci",
        ],
        text=True,
        capture_output=True,
        env={"PYTHONPATH": "src"},
        check=False,
    )

    assert "ENGINE_PRESET" in result.stdout
    assert "ENGINE_DOMAIN_PROFILE_LOADED" in result.stdout


def test_scan_preset_ci_accepts_explicit_contract_scope() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "structguard.cli",
            "scan",
            "examples/generic_cpp",
            "--profile",
            "generic-cpp",
            "--preset",
            "ci",
            "--contract",
            "profiles/generic-cpp/contracts/stack.sgdsl",
        ],
        text=True,
        capture_output=True,
        env={"PYTHONPATH": "src"},
        check=False,
    )

    assert result.returncode == 0
    assert "ENGINE_CONTRACT_SCOPE_EXPLICIT" in result.stdout
    assert "BINDING_ORPHAN_STRUCTURE" not in result.stdout
