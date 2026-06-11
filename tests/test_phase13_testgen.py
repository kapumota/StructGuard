from __future__ import annotations

import json
from pathlib import Path

from structguard.cli import main
from structguard.testgen import build_testgen_manifest


def _write_stack_header(path: Path) -> None:
    path.write_text(
        """
        template <typename T>
        class Stack {
        public:
          void push(T value) { data_[size_] = value; size_++; }
          void pop() { size_--; }
          T top() const { return data_[size_ - 1]; }
          bool empty() const { return size_ == 0; }
        private:
          T data_[8];
          int size_ = 0;
        };
        """,
        encoding="utf-8",
    )


def _write_stack_contract(path: Path) -> None:
    path.write_text(
        """
        package generic.cpp;
        structure Stack {
          field size_: int;
          invariant size_ >= 0;
          method push { ensures size_ == old(size_) + 1; }
          method pop { requires size_ > 0; ensures size_ == old(size_) - 1; }
          method top { requires size_ > 0; }
        }
        """,
        encoding="utf-8",
    )


def test_contract_guided_manifest_contains_utility_scores(tmp_path: Path) -> None:
    header = tmp_path / "Stack.hpp"
    contract = tmp_path / "stack.sgdsl"
    _write_stack_header(header)
    _write_stack_contract(contract)

    manifest = build_testgen_manifest(tmp_path, headers_only=True, seeds=4, steps=8, contract_paths=[contract])

    assert manifest.generation_mode == "contract-guided"
    assert manifest.cases
    assert any(case.contract_hint for case in manifest.cases)
    assert all(0.0 <= case.utility_score <= 1.0 for case in manifest.cases)


def test_testgen_cli_writes_output_and_generated_tests(tmp_path: Path, capsys) -> None:
    header = tmp_path / "Stack.hpp"
    contract = tmp_path / "stack.sgdsl"
    output = tmp_path / "testgen.json"
    test_dir = tmp_path / "generated_tests"
    _write_stack_header(header)
    _write_stack_contract(contract)

    exit_code = main(
        [
            "testgen",
            str(tmp_path),
            "--headers-only",
            "--contract",
            str(contract),
            "--seeds",
            "4",
            "--steps",
            "8",
            "--output",
            str(output),
            "--test-dir",
            str(test_dir),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code in {0, 1}
    assert "TestGen" in captured.out
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["generation_mode"] == "contract-guided"
    assert payload["summary"]["case_count"] > 0
    assert (test_dir / "structguard_testgen_manifest_v2.json").exists()


def test_fuzz_cli_warns_that_it_is_deprecated(tmp_path: Path, capsys) -> None:
    header = tmp_path / "Stack.hpp"
    _write_stack_header(header)

    main(["fuzz", str(tmp_path), "--headers-only", "--seeds", "1", "--steps", "3"])

    captured = capsys.readouterr()
    assert "DEPRECATED" in captured.out
    assert "testgen" in captured.out
