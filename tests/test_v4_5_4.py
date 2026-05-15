from __future__ import annotations

from pathlib import Path

from structguard.assist import assist_project
from structguard.cppscan import scan_project
from structguard.formal import smt_for_method


def test_smt_artifact_omits_get_model_until_sat() -> None:
    root = Path(__file__).resolve().parents[1]
    classes = scan_project(root / "examples" / "stack_ok.h", headers_only=True)
    cls = classes[0]
    method = next(m for m in cls.methods if m.name == "empty")

    smt, _notes = smt_for_method(cls, method, infer=True)

    assert "(check-sat)" in smt
    assert "(get-model)" not in smt


def test_assist_is_labeled_as_heuristic_not_ai() -> None:
    root = Path(__file__).resolve().parents[1]
    report = assist_project(root / "examples" / "stack_ok.h", headers_only=True, seeds=1, steps=1)
    codes = {d.code for d in report.diagnostics}
    messages = "\n".join(d.message for d in report.diagnostics)

    assert "HEURISTIC_ASSIST_SUMMARY" in codes
    assert not any(code.startswith("AI_ASSIST") for code in codes)
    assert "IA generativa" in messages
    assert "AI-assisted" not in messages


def test_release_demo_scripts_do_not_hide_failures_with_or_true() -> None:
    root = Path(__file__).resolve().parents[1]
    scripts = [
        root / "scripts" / "demo_clean_ci.sh",
        root / "scripts" / "demo_bug_detection.sh",
        root / "scripts" / "final_demo.sh",
        root / "scripts" / "validate_release.sh",
        root / "scripts" / "smoke_test.sh",
    ]
    for script in scripts:
        text = script.read_text(encoding="utf-8")
        assert "|| true" not in text, script


def test_demo_scripts_separate_clean_and_intentional_bug_without_docs() -> None:
    root = Path(__file__).resolve().parents[1]
    clean = (root / "scripts" / "demo_clean_ci.sh").read_text(encoding="utf-8")
    bug = (root / "scripts" / "demo_bug_detection.sh").read_text(encoding="utf-8")

    assert "stack_ok.h" in clean
    assert "stack_bug.h" in bug
    assert "BuggyStack::pop" in bug
    assert "|| true" not in clean
    assert "|| true" not in bug
