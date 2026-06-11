from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from structguard.profiles import load_profile_file, resolve_profile


def test_profile_loader_reads_generic_cpp_profile() -> None:
    profile = load_profile_file(Path("profiles/generic-cpp/profile.yml"))
    assert profile.name == "generic-cpp"
    assert profile.language == "cpp"
    assert profile.contracts
    assert all(path.exists() for path in profile.contract_paths())


def test_profile_resolver_finds_profile_by_name() -> None:
    profile = resolve_profile("cc232")
    assert profile.name == "cc232"
    assert profile.contract_paths()


def test_profiles_list_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "structguard.cli", "profiles", "list"],
        text=True,
        capture_output=True,
        env={"PYTHONPATH": "src"},
        check=False,
    )
    assert result.returncode == 0
    assert "generic-cpp" in result.stdout
    assert "cc232" in result.stdout


def test_profiles_validate_cli() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "structguard.cli", "profiles", "validate", "profiles/generic-cpp/profile.yml"],
        text=True,
        capture_output=True,
        env={"PYTHONPATH": "src"},
        check=False,
    )
    assert result.returncode == 0
    assert "Perfil válido: generic-cpp" in result.stdout


def test_scan_uses_domain_profile_contracts() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "structguard.cli", "scan", "examples/generic_cpp", "--profile", "generic-cpp"],
        text=True,
        capture_output=True,
        env={"PYTHONPATH": "src"},
        check=False,
    )
    assert result.returncode == 0
    assert "ANALYSIS_PROFILE" in result.stdout
    assert "generic-cpp" in result.stdout
