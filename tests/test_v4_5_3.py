from __future__ import annotations

import json
from pathlib import Path

from structguard.ci_outputs import write_sarif
from structguard.clang_frontend import extract_ast_record_models
from structguard.cppscan import scan_project
from structguard.formal import smt_for_method
from structguard.report import report_to_dict
from structguard.schemas import validate_sarif_dict, validate_structguard_report_dict
from structguard.verifier import verify_project


REALISTIC_STACK = """
#pragma once
#include <cstddef>

namespace demo {
class RealisticStack {
  int size_ = 99;
  int capacity_ = 1;
public:
  // invariant: size_ >= 0
  // invariant: size_ <= capacity_
  // invariant: capacity_ >= 1
  // ensures: size_ == 0
  // ensures: capacity_ == 10
  RealisticStack() : size_(0), capacity_(10) {}

  // ensures: result == (size_ == 0)
  bool empty() const { return size_ == 0; }
};
}
"""


def test_constructor_initializer_list_is_executed_before_postconditions(tmp_path: Path) -> None:
    header = tmp_path / "realistic_stack.h"
    header.write_text(REALISTIC_STACK, encoding="utf-8")

    report = verify_project(header, headers_only=True, infer=True, max_cases=500)
    constructor = next(d for d in report.diagnostics if d.symbol == "RealisticStack::RealisticStack")

    assert constructor.level == "BOUNDED_VERIFIED"
    assert constructor.code == "BOUNDED_CONTRACTS_HOLD"
    assert constructor.details["verification_scope"] == "bounded_model"
    assert constructor.details["evidence"] == "bounded_exhaustive_over_selected_domains"
    assert constructor.details["constructor_initializers"] == [
        {"field": "size_", "expr": "0"},
        {"field": "capacity_", "expr": "10"},
    ]


def test_default_initialized_fields_and_bool_result_smt_are_typed(tmp_path: Path) -> None:
    header = tmp_path / "realistic_stack.h"
    header.write_text(REALISTIC_STACK, encoding="utf-8")

    classes = scan_project(header, headers_only=True)
    cls = classes[0]
    assert {"size_", "capacity_"}.issubset(cls.fields)
    empty = next(m for m in cls.methods if m.name == "empty")

    smt, notes = smt_for_method(cls, empty, infer=True)
    assert "(declare-const result Bool)" in smt
    assert "(declare-const result Int)" not in smt
    assert "(assert (= result (= size_ 0)))" in smt
    assert isinstance(notes, list)


def test_json_and_sarif_outputs_validate_against_bundled_contracts(tmp_path: Path) -> None:
    header = tmp_path / "realistic_stack.h"
    header.write_text(REALISTIC_STACK, encoding="utf-8")
    report = verify_project(header, headers_only=True, infer=True, max_cases=500)

    data = report_to_dict(report)
    assert validate_structguard_report_dict(data) == []
    assert data["schema_version"] == "structguard-report/v1"
    assert "BOUNDED_VERIFIED" in data["result_semantics"]
    assert "PROVED" in data["result_semantics"]

    sarif_path = tmp_path / "structguard.sarif"
    write_sarif(report, sarif_path)
    sarif = json.loads(sarif_path.read_text(encoding="utf-8"))
    assert validate_sarif_dict(sarif) == []
    assert sarif["runs"][0]["tool"]["driver"]["name"] == "StructGuard"


def test_clang_ast_record_model_extracts_fields_and_methods(tmp_path: Path) -> None:
    target = tmp_path / "sample.h"
    ast = {
        "kind": "TranslationUnitDecl",
        "inner": [
            {
                "kind": "CXXRecordDecl",
                "name": "Sample",
                "tagUsed": "class",
                "loc": {"file": str(target), "line": 3},
                "inner": [
                    {"kind": "FieldDecl", "name": "size_", "loc": {"file": str(target), "line": 4}},
                    {"kind": "FieldDecl", "name": "capacity_", "loc": {"file": str(target), "line": 5}},
                    {"kind": "CXXConstructorDecl", "name": "Sample", "loc": {"file": str(target), "line": 8}},
                    {"kind": "CXXMethodDecl", "name": "empty", "loc": {"file": str(target), "line": 9}},
                ],
            }
        ],
    }

    records = extract_ast_record_models(ast, target)
    assert len(records) == 1
    assert records[0].name == "Sample"
    assert records[0].fields == ["size_", "capacity_"]
    assert records[0].methods == ["Sample", "empty"]
