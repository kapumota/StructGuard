from __future__ import annotations

import json
from pathlib import Path

from structguard.cli import main
from structguard.ir.contract_ir import build_contract_ir
from structguard.ir.contract_validator import validate_contract_ir
from structguard.sgdsl.parser import parse_sgdsl_text


def _diagnostic_codes(text: str) -> set[str]:
    ir = build_contract_ir([parse_sgdsl_text(text, source="contrato.sgdsl")])
    return {diagnostic.code for diagnostic in validate_contract_ir(ir)}


def test_contract_ir_contains_structures_fields_and_methods() -> None:
    module = parse_sgdsl_text(
        """
        package generic.cpp;
        structure Stack {
          field n: int;
          invariant n >= 0;
          method push { ensures n == old(n) + 1; }
        }
        """,
        source="stack.sgdsl",
    )

    ir = build_contract_ir([module])

    assert ir.structures[0].qualified_name == "generic.cpp.Stack"
    assert ir.structures[0].fields[0].name == "n"
    assert ir.structures[0].methods[0].ensures[0].expression == "n == old(n) + 1"


def test_contract_validator_detects_duplicate_method() -> None:
    codes = _diagnostic_codes(
        """
        structure Stack {
          field n: int;
          method pop requires n > 0;
          method pop ensures n == old(n) - 1;
        }
        """
    )

    assert "SGDSL_DUPLICATE_METHOD" in codes


def test_contract_validator_detects_unknown_field_and_method() -> None:
    codes = _diagnostic_codes(
        """
        structure Stack {
          field n: int;
          invariant missing >= 0;
          method pop { requires n > 0; ensures missingCall() == n; }
        }
        """
    )

    assert "SGDSL_UNKNOWN_FIELD" in codes
    assert "SGDSL_UNKNOWN_METHOD" in codes


def test_contract_validator_detects_malformed_expression_and_type_mismatch() -> None:
    codes = _diagnostic_codes(
        """
        structure FlagBox {
          field active: bool;
          invariant active >= 0;
          method check requires active &&;
        }
        """
    )

    assert "SGDSL_TYPE_MISMATCH" in codes
    assert "SGDSL_TRAILING_OPERATOR" in codes


def test_contract_cli_check_and_dump_ir(tmp_path: Path, capsys) -> None:
    contract = tmp_path / "stack.sgdsl"
    contract.write_text(
        """
        package generic.cpp;
        structure Stack {
          field n: int;
          invariant n >= 0;
          method push { ensures n == old(n) + 1; }
        }
        """,
        encoding="utf-8",
    )

    assert main(["contract", "check", str(contract)]) == 0
    captured = capsys.readouterr()
    assert "Resultado: OK" in captured.out

    assert main(["contract", "dump-ir", str(contract), "--json"]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["structures"][0]["qualified_name"] == "generic.cpp.Stack"
