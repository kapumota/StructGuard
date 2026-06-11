from __future__ import annotations

from structguard.sgdsl.parser import parse_sgdsl_text


def test_parse_sgdsl_fields_methods_and_contracts() -> None:
    module = parse_sgdsl_text(
        """
        package generic.cpp;

        structure Vector {
          field n: int;
          field data: int;
          invariant n >= 0;
          method get(i: int) requires 0 <= i && i < n;
          method add(i: int) {
            requires 0 <= i && i <= n;
            ensures n == old(n) + 1;
          }
        }
        """,
        source="vector.sgdsl",
    )

    assert module.package == "generic.cpp"
    assert len(module.structures) == 1
    structure = module.structures[0]
    assert structure.name == "Vector"
    assert [field.name for field in structure.fields] == ["n", "data"]
    assert len(structure.invariants) == 1
    assert [method.name for method in structure.methods] == ["add", "get"] or [method.name for method in structure.methods] == ["get", "add"]


def test_parse_sgdsl_keeps_profile_patterns() -> None:
    module = parse_sgdsl_text(
        """
        package cc232;

        structure *Stack {
          invariant n >= 0;
          method pop requires n > 0;
        }
        """,
        source="cc232_core.sgdsl",
    )

    assert module.structures[0].name == "*Stack"
    assert module.structures[0].methods[0].name == "pop"
