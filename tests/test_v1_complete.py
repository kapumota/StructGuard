from pathlib import Path

from structguard.bench import collect_bench_metrics
from structguard.trace import abstract_trace
from structguard.security import security_project
from structguard.fuzz import fuzz_project
from structguard.ci import ci_project

ROOT = Path(__file__).resolve().parents[1]


def test_bench_collects_metrics():
    metrics = collect_bench_metrics(ROOT / "examples", headers_only=True)
    assert metrics
    assert any(m.class_name == "Stack" for m in metrics)


def test_trace_detects_invalid_sequence():
    events = abstract_trace("pop", structure="stack")
    assert any(e.event == "precondition_failure" for e in events)


def test_security_finds_buggy_stack():
    report = security_project(ROOT / "examples" / "stack_bug.h", headers_only=True)
    assert any(d.code == "SEC_MISSING_PRECONDITION" for d in report.diagnostics)


def test_fuzz_ok_stack_is_guarded():
    report = fuzz_project(ROOT / "examples" / "stack_ok.h", headers_only=True, seeds=3, steps=4)
    assert not any(d.level == "FAILED" for d in report.diagnostics)


def test_ci_ok_stack_passes():
    report = ci_project(ROOT / "examples" / "stack_ok.h", headers_only=True, fuzz_seeds=3, fuzz_steps=4)
    assert report.diagnostics[0].code == "CI_GATE_PASSED"
