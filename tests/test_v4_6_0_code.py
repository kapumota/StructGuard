from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from structguard.clang_bridge import merge_clang_structural_model
from structguard.cppscan import scan_project
from structguard.formal import smt_for_method
from structguard.standard_contracts import standard_requires, structure_kind
from structguard.verifier import verify_project


TEMPLATE_VECTOR = r'''
template<typename T>
class Vector {
    int size_, capacity_;
    T* data_;
public:
    // invariant: size_ >= 0
    // invariant: size_ <= capacity_
    Vector() : size_(0), capacity_(4), data_(nullptr) {}

    // ensures: result == size_
    int size() const { return size_; }

    T& operator[](int index) { return data_[index]; }

    void push_back(const T& value) {
        if (size_ < capacity_) {
            data_[size_] = value;
            size_++;
        }
    }
};
'''


def test_standard_contract_library_infers_stack_pop_requires(tmp_path: Path) -> None:
    h = tmp_path / "stack.h"
    h.write_text('''
class Stack {
  int size_, capacity_;
public:
  void pop() { size_--; }
};
''', encoding="utf-8")
    cls = scan_project(h, headers_only=True)[0]
    pop = next(m for m in cls.methods if m.name == "pop")
    assert structure_kind(cls) == "stack"
    assert any(c.expression == "size_ > 0" for c in standard_requires(cls, pop))


def test_standard_contracts_do_not_hide_underflow_counterexample(tmp_path: Path) -> None:
    h = tmp_path / "bug.h"
    h.write_text('''
class BuggyStack {
  int size_;
public:
  // invariant: size_ >= 0
  void pop() { size_--; }
};
''', encoding="utf-8")
    report = verify_project(h, headers_only=True)
    failed = next(d for d in report.diagnostics if d.level == "FAILED")
    assert failed.code == "INVARIANT_NOT_PRESERVED"
    assert failed.details["counterexample"]["initial_state"]["size_"] == 0
    assert failed.details["counterexample"]["state_after"]["size_"] == -1
    assert "Estado inicial" in failed.details["counterexample"]["explanation"]


def test_symbolic_executor_handles_guarded_push_without_unconditional_increment(tmp_path: Path) -> None:
    h = tmp_path / "guarded.h"
    h.write_text('''
class GuardedStack {
  int size_, capacity_;
public:
  // invariant: size_ >= 0
  // invariant: size_ <= capacity_
  GuardedStack() : size_(0), capacity_(2) {}
  void push(int x) {
    if (size_ < capacity_) {
      size_++;
    }
  }
};
''', encoding="utf-8")
    report = verify_project(h, headers_only=True, max_cases=200)
    push = next(d for d in report.diagnostics if d.symbol == "GuardedStack::push")
    assert push.level == "BOUNDED_VERIFIED"
    assert push.details["executor"] == "branch_aware_bounded_interpreter"


def test_template_simple_vector_scans_and_smt_models_arrays(tmp_path: Path) -> None:
    h = tmp_path / "vector.h"
    h.write_text(TEMPLATE_VECTOR, encoding="utf-8")
    classes = scan_project(h, headers_only=True)
    assert classes and classes[0].name == "Vector"
    assert {"size_", "capacity_", "data_"}.issubset(classes[0].fields)
    push = next(m for m in classes[0].methods if m.name == "push_back")
    smt, notes = smt_for_method(classes[0], push, infer=True)
    assert "(Array Int Int)" in smt
    assert "(store old_data_" in smt
    assert isinstance(notes, list)


def test_analyze_profile_student_cli(tmp_path: Path) -> None:
    h = tmp_path / "stack.h"
    h.write_text('''
class Stack {
  int size_;
public:
  // invariant: size_ >= 0
  bool empty() const { return size_ == 0; }
};
''', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "structguard.cli", "analyze", str(h), "--headers-only", "--profile", "student"],
        text=True,
        capture_output=True,
        env={"PYTHONPATH": "src"},
        check=False,
    )
    assert "ANALYSIS_PROFILE" in result.stdout
    assert "student" in result.stdout


def test_clang_bridge_falls_back_cleanly_without_required_binary(tmp_path: Path) -> None:
    h = tmp_path / "sample.h"
    h.write_text('class Sample { int size_; public: int size() const { return size_; } };', encoding="utf-8")
    classes = scan_project(h, headers_only=True)
    merged, meta = merge_clang_structural_model(classes, h, headers_only=True, clang="/definitely/missing/clang++")
    assert merged
    assert meta["fallback"] is True
