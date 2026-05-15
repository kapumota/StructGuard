from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_common_ci_artifacts(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    report = {"diagnostics": [], "counts": {}, "result_semantics": {"BOUNDED_VERIFIED": "bounded"}}
    _write_json(root / "structguard-ci.json", report)
    (root / "structguard-ci.html").write_text("<h1>StructGuard</h1>", encoding="utf-8")
    (root / "structguard-junit.xml").write_text("<testsuite></testsuite>", encoding="utf-8")
    _write_json(root / "structguard.sarif", {"version": "2.1.0", "runs": [{}]})
    (root / "structguard-summary.md").write_text("# Summary", encoding="utf-8")


def test_validate_outputs_accepts_profile_and_dir_for_ci(tmp_path: Path) -> None:
    project = Path(__file__).resolve().parents[1]
    out = tmp_path / "custom_ci"
    _write_common_ci_artifacts(out)

    result = subprocess.run(
        [sys.executable, str(project / "scripts" / "validate_outputs.py"), "--profile", "ci", "--dir", str(out)],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "profile=ci" in result.stdout
    assert str(out) in result.stdout


def test_validate_outputs_accepts_demo_bug_profile(tmp_path: Path) -> None:
    project = Path(__file__).resolve().parents[1]
    out = tmp_path / "bug"
    out.mkdir()
    _write_json(
        out / "bug_analysis.json",
        {
            "diagnostics": [
                {"level": "FAILED", "code": "INVARIANT_NOT_PRESERVED", "symbol": "BuggyStack::pop"}
            ],
            "counts": {"FAILED": 1},
        },
    )
    (out / "bug_analysis.html").write_text("<h1>StructGuard</h1>", encoding="utf-8")
    (out / "bug_analysis.txt").write_text("BuggyStack::pop violates size_ >= 0", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(project / "scripts" / "validate_outputs.py"), "--profile", "demo-bug", "--dir", str(out)],
        text=True,
        capture_output=True,
        check=True,
    )

    assert "profile=demo-bug" in result.stdout


def test_release_validation_script_runs_code_checks_and_output_profiles() -> None:
    root = Path(__file__).resolve().parents[1]
    release_script = (root / "scripts" / "validate_release.sh").read_text(encoding="utf-8")

    assert "compileall" in release_script
    assert "pytest" in release_script
    assert "validate_outputs.py --profile ci" in release_script
    assert "validate_outputs.py --profile demo-clean" in release_script
    assert "validate_outputs.py --profile demo-bug" in release_script
