from pathlib import Path
from structguard.verifier import verify_project


def test_stack_ok_has_bounded_verified():
    report = verify_project(Path('examples/stack_ok.h'))
    assert any(d.level == 'BOUNDED_VERIFIED' for d in report.diagnostics)


def test_stack_bug_fails():
    report = verify_project(Path('examples/stack_bug.h'))
    assert any(d.level == 'FAILED' for d in report.diagnostics)
