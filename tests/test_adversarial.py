from pathlib import Path

from structguard.clang_frontend import strict_ast_project
from structguard.verifier import verify_project


def test_bounded_verified_is_not_universal_proof(tmp_path: Path):
    header = tmp_path / "overflow_like_counter.h"
    header.write_text(
        """
// invariant: size_ >= 0
class Counter {
  int size_;
public:
  // ensures: size_ >= 0
  void grow_big() {
    size_ = size_ + 1000000000;
  }
};
""",
        encoding="utf-8",
    )

    report = verify_project(header, headers_only=True, infer=False, max_cases=20)

    assert any(d.level == "BOUNDED_VERIFIED" for d in report.diagnostics)
    assert not any(d.level == "PROVED" for d in report.diagnostics)


def test_strict_ast_reports_failure_when_clang_cannot_run(tmp_path: Path):
    header = tmp_path / "stack.h"
    header.write_text(
        """
class Stack {
  int size_;
public:
  void push() { ++size_; }
};
""",
        encoding="utf-8",
    )

    report = strict_ast_project(header, headers_only=True, clang="/definitely/missing/clang++")

    assert any(d.level == "FAILED" and d.code in {"STRICT_AST_FAILED", "STRICT_AST_FILE_FAILED"} for d in report.diagnostics)


def test_unknown_for_unsupported_constructs_is_not_success(tmp_path: Path):
    header = tmp_path / "loop_stack.h"
    header.write_text(
        """
// invariant: size_ >= 0
class Stack {
  int size_;
public:
  // ensures: size_ >= 0
  void normalize() {
    while (size_ < 0) {
      ++size_;
    }
  }
};
""",
        encoding="utf-8",
    )

    report = verify_project(header, headers_only=True, infer=False, max_cases=20)

    assert any(d.level == "UNKNOWN" for d in report.diagnostics)
    assert not any(d.level == "PROVED" for d in report.diagnostics)
