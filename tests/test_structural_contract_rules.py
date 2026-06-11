from __future__ import annotations

from pathlib import Path

from structguard.analyzers import ALL_RULES, rule_catalog
from structguard.analyzers.bounds import analyze_bounds_project
from structguard.analyzers.contracts import analyze_contract_rules_project
from structguard.analyzers.memory_safety import analyze_memory_safety_project
from structguard.analyzers.structure_semantics import analyze_structure_semantics_project
from structguard.core import AnalysisContext, AnalysisEngine


def _write_header(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "RulesCase.hpp"
    path.write_text(text, encoding="utf-8")
    return path


def _codes(report) -> set[str]:
    return {diagnostic.code for diagnostic in report.diagnostics}


def test_rule_catalog_contains_initial_structural_rules() -> None:
    expected = {
        "SG-CONTRACT-MISSING-PRECONDITION",
        "SG-STACK-POP-EMPTY",
        "SG-QUEUE-FIFO-VIOLATION",
        "SG-BOUNDS-INDEX-RISK",
        "SG-SIZE-NOT-UPDATED",
        "SG-HEAP-PROPERTY-RISK",
        "SG-BST-ORDER-RISK",
        "SG-NULL-DEREFERENCE-RISK",
        "SG-MEMORY-OWNERSHIP-RISK",
    }

    assert expected.issubset(set(ALL_RULES))
    for item in rule_catalog():
        assert item["rule_id"]
        assert item["description"]
        assert item["default_severity"] in {"info", "warning", "error"}
        assert item["good_example"]
        assert item["bad_example"]
        assert item["profiles"]


def test_contract_rules_detect_missing_precondition(tmp_path: Path) -> None:
    path = _write_header(
        tmp_path,
        """
class Stack {
    int data[8];
    int n;
public:
    int pop() {
        return data[--n];
    }
};
""",
    )

    codes = _codes(analyze_contract_rules_project(path))

    assert "SG-CONTRACT-MISSING-PRECONDITION" in codes


def test_bounds_rules_detect_index_risk_without_guard(tmp_path: Path) -> None:
    path = _write_header(
        tmp_path,
        """
class Vector {
    int data[8];
public:
    int at(int i) const {
        return data[i];
    }
};
""",
    )

    codes = _codes(analyze_bounds_project(path))

    assert "SG-BOUNDS-INDEX-RISK" in codes


def test_structure_semantics_detects_stack_and_size_risks(tmp_path: Path) -> None:
    path = _write_header(
        tmp_path,
        """
class Stack {
    int data[8];
    int n;
public:
    int pop() {
        return data[--n];
    }
    void push(int value) {
        data[n] = value;
    }
};
""",
    )

    codes = _codes(analyze_structure_semantics_project(path))

    assert "SG-STACK-POP-EMPTY" in codes
    assert "SG-SIZE-NOT-UPDATED" in codes


def test_structure_semantics_detects_queue_fifo_violation(tmp_path: Path) -> None:
    path = _write_header(
        tmp_path,
        """
class Queue {
    int data[8];
    int tail;
public:
    int dequeue() {
        return data[--tail];
    }
};
""",
    )

    codes = _codes(analyze_structure_semantics_project(path))

    assert "SG-QUEUE-FIFO-VIOLATION" in codes


def test_memory_safety_emits_structural_ownership_rule(tmp_path: Path) -> None:
    path = _write_header(
        tmp_path,
        """
class MissingDelete {
    int* data;
public:
    MissingDelete(int capacity) : data(new int[capacity]) {}
};
""",
    )

    codes = _codes(analyze_memory_safety_project(path))

    assert "MEM_ARRAY_NEW_WITHOUT_DELETE_ARRAY" in codes
    assert "SG-MEMORY-OWNERSHIP-RISK" in codes


def test_engine_runs_structural_rules_for_security_preset(tmp_path: Path) -> None:
    path = _write_header(
        tmp_path,
        """
class Vector {
    int data[8];
public:
    int at(int i) const {
        return data[i];
    }
};
""",
    )
    context = AnalysisContext(root=path, preset="security")

    result = AnalysisEngine().run(context)
    codes = {diagnostic.code for diagnostic in result.report.diagnostics}

    assert "ENGINE_PRESET" in codes
    assert "SG-BOUNDS-INDEX-RISK" in codes
