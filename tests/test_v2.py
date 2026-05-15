from pathlib import Path
from structguard.dsl import parse_dsl_text, apply_dsl_contracts
from structguard.cppscan import scan_project
from structguard.frontend import summarize_frontend


def test_dsl_parser_basic():
    spec = parse_dsl_text('''package cc232; structure ArrayQueue { invariant n >= 0; method remove { requires n > 0; ensures n == old(n) - 1; } }''')
    assert spec.package == 'cc232'
    assert 'ArrayQueue' in spec.structures
    assert spec.structures['ArrayQueue'].methods['remove'].requires[0].expression == 'n > 0'


def test_dsl_applies_to_example_stack():
    classes = scan_project(Path('examples'), headers_only=True)
    spec = parse_dsl_text('structure Stack { invariant size_ >= 0; method pop { requires size_ > 0; } }')
    diags = apply_dsl_contracts(classes, [spec])
    assert diags
    stack = next(c for c in classes if c.name == 'Stack')
    assert any(c.expression == 'size_ >= 0' for c in stack.invariants)


def test_frontend_summary_examples():
    summaries = summarize_frontend(Path('examples'), headers_only=True)
    assert summaries
    assert sum(s.classes for s in summaries) >= 1
