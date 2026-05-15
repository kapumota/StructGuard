from pathlib import Path

from structguard.cppscan import scan_project
from structguard.security import security_project
from structguard.verifier import verify_project


def test_branch_aware_executor_handles_early_return_bool(tmp_path: Path) -> None:
    header = tmp_path / "branch_bool.h"
    header.write_text(
        """
class BranchStack {
    int size_, capacity_;
public:
    // invariant: size_ >= 0
    // invariant: size_ <= capacity_
    BranchStack() : size_(0), capacity_(4) {}

    // ensures: result == (size_ == 0)
    bool empty() const {
        if (size_ == 0) {
            return true;
        }
        return false;
    }
};
""",
        encoding="utf-8",
    )

    report = verify_project(header, headers_only=True)
    diag = {d.symbol: d for d in report.diagnostics}

    assert diag["BranchStack::empty"].level == "BOUNDED_VERIFIED"
    assert diag["BranchStack::empty"].details["executor"] == "branch_aware_bounded_interpreter"


def test_cppscan_extracts_multiple_field_declarations(tmp_path: Path) -> None:
    header = tmp_path / "multi_fields.h"
    header.write_text(
        """
class MultiFields {
    int size_, capacity_;
    int head_ = 0, tail_ = 0;
public:
    // invariant: size_ >= 0
    MultiFields() : size_(0), capacity_(8), head_(0), tail_(0) {}
};
""",
        encoding="utf-8",
    )

    classes = scan_project(header, headers_only=True)
    assert len(classes) == 1
    assert {"size_", "capacity_", "head_", "tail_"}.issubset(classes[0].fields)


def test_security_initializer_lists_count_as_initialized_fields(tmp_path: Path) -> None:
    header = tmp_path / "secure_init.h"
    header.write_text(
        """
class SecureInit {
    int size_, capacity_;
public:
    SecureInit() : size_(0), capacity_(4) {}
};
""",
        encoding="utf-8",
    )

    report = security_project(header, headers_only=True, deep=True)
    assert not [d for d in report.diagnostics if d.code == "SEC_UNINITIALIZED_FIELD"]
