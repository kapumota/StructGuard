from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from structguard.cppscan import scan_project
from structguard.ir.source_ir import SourceIR


@dataclass(frozen=True)
class InlineContractSymbol:
    kind: str
    expression: str
    source: str
    line: int

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "expression": self.expression,
            "source": self.source,
            "line": self.line,
        }


@dataclass(frozen=True)
class SourceFieldSymbol:
    name: str
    class_name: str
    source: str
    line: int = 0

    @property
    def qualified_name(self) -> str:
        return f"{self.class_name}::{self.name}"

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "class_name": self.class_name,
            "qualified_name": self.qualified_name,
            "source": self.source,
            "line": self.line,
        }


@dataclass(frozen=True)
class SourceMethodSymbol:
    name: str
    class_name: str
    signature: str
    source: str
    line: int
    requires: list[InlineContractSymbol] = field(default_factory=list)
    ensures: list[InlineContractSymbol] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        return f"{self.class_name}::{self.name}"

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "class_name": self.class_name,
            "qualified_name": self.qualified_name,
            "signature": self.signature,
            "source": self.source,
            "line": self.line,
            "requires": [contract.as_dict() for contract in self.requires],
            "ensures": [contract.as_dict() for contract in self.ensures],
        }


@dataclass
class SourceStructureSymbol:
    name: str
    source: str
    line: int
    fields: dict[str, SourceFieldSymbol] = field(default_factory=dict)
    methods: dict[str, list[SourceMethodSymbol]] = field(default_factory=dict)
    invariants: list[InlineContractSymbol] = field(default_factory=list)

    def add_method(self, method: SourceMethodSymbol) -> None:
        self.methods.setdefault(method.name, []).append(method)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "source": self.source,
            "line": self.line,
            "fields": [field.as_dict() for field in sorted(self.fields.values(), key=lambda item: item.name)],
            "methods": [method.as_dict() for name in sorted(self.methods) for method in self.methods[name]],
            "invariants": [contract.as_dict() for contract in self.invariants],
        }


@dataclass
class SourceSymbolTable:
    root: str
    structures: dict[str, SourceStructureSymbol] = field(default_factory=dict)

    def get_structure(self, name: str) -> SourceStructureSymbol | None:
        if name in self.structures:
            return self.structures[name]
        short_name = name.split(".")[-1].split("::")[-1]
        return self.structures.get(short_name)

    def as_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "structures": [self.structures[name].as_dict() for name in sorted(self.structures)],
        }


def _inline_contracts(raw_contracts: list[Any], source: str) -> list[InlineContractSymbol]:
    out: list[InlineContractSymbol] = []
    for contract in raw_contracts or []:
        out.append(
            InlineContractSymbol(
                kind=str(getattr(contract, "kind", "")),
                expression=str(getattr(contract, "expression", "")),
                source=source,
                line=int(getattr(contract, "line", 0) or 0),
            )
        )
    return out


def build_source_symbol_table_from_source_ir(source_ir: SourceIR) -> SourceSymbolTable:
    table = SourceSymbolTable(root=source_ir.root)
    for structure_ir in source_ir.structures:
        source = structure_ir.location.file
        structure = table.structures.setdefault(
            structure_ir.qualified_name,
            SourceStructureSymbol(
                name=structure_ir.qualified_name,
                source=source,
                line=structure_ir.location.line,
            ),
        )
        if structure_ir.name not in table.structures:
            table.structures[structure_ir.name] = structure
        for field_ir in structure_ir.fields:
            structure.fields.setdefault(
                field_ir.name,
                SourceFieldSymbol(
                    name=field_ir.name,
                    class_name=structure_ir.qualified_name,
                    source=field_ir.location.file,
                    line=field_ir.location.line,
                ),
            )
        for method_ir in structure_ir.methods:
            structure.add_method(
                SourceMethodSymbol(
                    name=method_ir.name,
                    class_name=structure_ir.qualified_name,
                    signature=method_ir.signature,
                    source=method_ir.location.file,
                    line=method_ir.location.line,
                )
            )
    return table


def build_source_symbol_table(root: Path, headers_only: bool = False) -> SourceSymbolTable:
    table = SourceSymbolTable(root=str(root))
    classes = scan_project(root, headers_only=headers_only)
    for cls in classes:
        source = str(cls.file)
        structure = table.structures.setdefault(
            cls.name,
            SourceStructureSymbol(
                name=cls.name,
                source=source,
                line=cls.start_line,
            ),
        )
        for field_name in sorted(cls.fields):
            structure.fields.setdefault(
                field_name,
                SourceFieldSymbol(
                    name=field_name,
                    class_name=cls.name,
                    source=source,
                ),
            )
        structure.invariants.extend(_inline_contracts(cls.invariants, source))
        for method in cls.methods:
            structure.add_method(
                SourceMethodSymbol(
                    name=method.name,
                    class_name=cls.name,
                    signature=method.signature,
                    source=source,
                    line=method.start_line,
                    requires=_inline_contracts(method.requires, source),
                    ensures=_inline_contracts(method.ensures, source),
                )
            )
    return table
