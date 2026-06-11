from __future__ import annotations

from pathlib import Path

from structguard.binding import build_binding_ir, match_contracts_to_source
from structguard.ir.contract_ir import build_contract_ir
from structguard.sgdsl.parser import parse_sgdsl_text
from structguard.binding.symbol_table import build_source_symbol_table


def _write_stack_header(path: Path) -> None:
    path.write_text(
        """
class ArrayStack {
public:
    // requires size() > 0
    // ensures result == old(top())
    int pop();
    void push(int value);
    int top() const;
private:
    int n;
};
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _contract_ir(text: str):
    module = parse_sgdsl_text(text, source="contrato.sgdsl")
    return build_contract_ir([module])


def test_binding_matches_existing_contract_symbols(tmp_path: Path) -> None:
    header = tmp_path / "ArrayStack.hpp"
    _write_stack_header(header)
    ir = _contract_ir(
        """
structure ArrayStack {
  field n: int;
  method push { ensures n == old(n) + 1; }
  method pop { requires n > 0; ensures n == old(n) - 1; }
  method top { requires n > 0; }
}
"""
    )

    binding_ir = build_binding_ir(tmp_path, ir, headers_only=True)
    diagnostics = match_contracts_to_source(binding_ir)

    assert [diagnostic.code for diagnostic in diagnostics] == ["BINDING_CONTRACTS_MATCH_SOURCE"]
    assert binding_ir.structures[0].matched is True
    assert all(method.matched for method in binding_ir.structures[0].methods)


def test_binding_reports_orphan_method(tmp_path: Path) -> None:
    header = tmp_path / "ArrayStack.hpp"
    _write_stack_header(header)
    ir = _contract_ir(
        """
structure ArrayStack {
  field n: int;
  method add { ensures n == old(n) + 1; }
}
"""
    )

    binding_ir = build_binding_ir(tmp_path, ir, headers_only=True)
    diagnostics = match_contracts_to_source(binding_ir)

    assert any(diagnostic.code == "BINDING_ORPHAN_METHOD" for diagnostic in diagnostics)
    assert "contrato huérfano" in diagnostics[0].message


def test_binding_reports_orphan_field(tmp_path: Path) -> None:
    header = tmp_path / "ArrayStack.hpp"
    _write_stack_header(header)
    ir = _contract_ir(
        """
structure ArrayStack {
  field count: int;
  method push { ensures count == old(count) + 1; }
}
"""
    )

    binding_ir = build_binding_ir(tmp_path, ir, headers_only=True)
    diagnostics = match_contracts_to_source(binding_ir)

    assert any(diagnostic.code == "BINDING_ORPHAN_FIELD" for diagnostic in diagnostics)


def test_source_symbol_table_reads_inline_contracts_without_colon(tmp_path: Path) -> None:
    header = tmp_path / "ArrayStack.hpp"
    _write_stack_header(header)

    table = build_source_symbol_table(tmp_path, headers_only=True)
    pop = table.structures["ArrayStack"].methods["pop"][0]

    assert pop.requires[0].expression == "size() > 0"
    assert pop.ensures[0].expression == "result == old(top())"
