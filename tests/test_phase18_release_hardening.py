from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase18_smoke_new_user_script_exists_and_uses_canonical_scan() -> None:
    script = ROOT / "scripts" / "smoke_new_user.sh"
    text = script.read_text(encoding="utf-8")

    assert script.exists()
    assert "set -euo pipefail" in text
    assert "structguard doctor" in text
    assert "structguard scan examples/generic_cpp" in text
    assert "--profile generic-cpp" in text
    assert "--preset contracts" in text
    assert "--contract profiles/generic-cpp/contracts/stack.sgdsl" in text
    assert "python -m json.tool" in text


def test_phase18_ci_runs_smoke_test() -> None:
    text = (ROOT / ".github" / "workflows" / "structguard.yml").read_text(encoding="utf-8")

    assert "Ejecutar smoke test de usuario nuevo" in text
    assert "bash scripts/smoke_new_user.sh" in text
    assert "--contract profiles/generic-cpp/contracts/stack.sgdsl" in text


def test_phase18_benchmark_workflow_is_documented_as_gate() -> None:
    text = (ROOT / ".github" / "workflows" / "benchmark.yml").read_text(encoding="utf-8")

    assert "python benchmarks/run_benchmark.py" in text
    assert "--thresholds benchmarks/thresholds.yml" in text
    assert "--fail-on-threshold" in text
    assert "scripts/check_benchmark_thresholds.py" in text


def test_phase18_contracts_layout_documents_root_contracts_as_compatibility() -> None:
    text = (ROOT / "docs" / "CONTRACTS_LAYOUT.md").read_text(encoding="utf-8")

    assert "contracts/cc232_core.sgdsl" in text
    assert "contracts/advanced_structures.sgdsl" in text
    assert "profiles/generic-cpp/contracts/stack.sgdsl" in text
    assert "git rm -r contracts" in text
    assert "Mantener temporalmente" in text


def test_phase18_changelog_mentions_release_hardening_without_fixed_metrics() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "Fase 18" in text
    assert "scripts/smoke_new_user.sh" in text
    assert ".github/workflows/benchmark.yml" in text
    assert "docs/LEGACY_MODULES.md" in text
    assert "docs/CONTRACTS_LAYOUT.md" in text
    assert "No se registran valores fijos" in text
