from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from structguard.ir.contract_ir import ContractIR, FieldIR, MethodIR, StructureIR
from structguard.ir.source_ir import SourceIR

from .name_resolution import NameResolutionResult, resolve_field, resolve_method, resolve_structure
from .symbol_table import SourceFieldSymbol, SourceMethodSymbol, SourceStructureSymbol, SourceSymbolTable, build_source_symbol_table, build_source_symbol_table_from_source_ir


@dataclass(frozen=True)
class FieldBinding:
    contract: FieldIR
    source: SourceFieldSymbol | None
    resolution: NameResolutionResult

    @property
    def matched(self) -> bool:
        return self.source is not None

    def as_dict(self) -> dict[str, object]:
        return {
            "contract": self.contract.as_dict(),
            "source": self.source.as_dict() if self.source else None,
            "resolution": self.resolution.as_dict(),
            "matched": self.matched,
        }


@dataclass(frozen=True)
class MethodBinding:
    contract: MethodIR
    source: list[SourceMethodSymbol]
    resolution: NameResolutionResult

    @property
    def matched(self) -> bool:
        return bool(self.source)

    @property
    def inline_contract_count(self) -> int:
        return sum(len(method.requires) + len(method.ensures) for method in self.source)

    def as_dict(self) -> dict[str, object]:
        return {
            "contract": self.contract.as_dict(),
            "source": [method.as_dict() for method in self.source],
            "resolution": self.resolution.as_dict(),
            "matched": self.matched,
            "inline_contract_count": self.inline_contract_count,
        }


@dataclass(frozen=True)
class StructureBinding:
    contract: StructureIR
    source: SourceStructureSymbol | None
    resolution: NameResolutionResult
    fields: list[FieldBinding] = field(default_factory=list)
    methods: list[MethodBinding] = field(default_factory=list)

    @property
    def matched(self) -> bool:
        return self.source is not None

    def as_dict(self) -> dict[str, object]:
        return {
            "contract": self.contract.as_dict(),
            "source": self.source.as_dict() if self.source else None,
            "resolution": self.resolution.as_dict(),
            "matched": self.matched,
            "fields": [field_binding.as_dict() for field_binding in self.fields],
            "methods": [method_binding.as_dict() for method_binding in self.methods],
        }


@dataclass
class BindingIR:
    source_table: SourceSymbolTable
    contract_ir: ContractIR
    structures: list[StructureBinding] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "source_table": self.source_table.as_dict(),
            "contract_ir": self.contract_ir.as_dict(),
            "structures": [binding.as_dict() for binding in self.structures],
        }


def build_binding_ir_from_table(contract_ir: ContractIR, source_table: SourceSymbolTable) -> BindingIR:
    binding_ir = BindingIR(source_table=source_table, contract_ir=contract_ir)
    for contract_structure in contract_ir.structures:
        source_structure, structure_resolution = resolve_structure(source_table, contract_structure.qualified_name)
        field_bindings: list[FieldBinding] = []
        method_bindings: list[MethodBinding] = []
        if source_structure:
            for contract_field in contract_structure.fields:
                field_resolution = resolve_field(source_structure, contract_field.name)
                source_field = source_structure.fields.get(contract_field.name) if field_resolution.matched else None
                field_bindings.append(FieldBinding(contract=contract_field, source=source_field, resolution=field_resolution))
            for contract_method in contract_structure.methods:
                method_resolution = resolve_method(source_structure, contract_method.name)
                source_methods = source_structure.methods.get(contract_method.name, []) if method_resolution.matched else []
                method_bindings.append(MethodBinding(contract=contract_method, source=source_methods, resolution=method_resolution))
        binding_ir.structures.append(
            StructureBinding(
                contract=contract_structure,
                source=source_structure,
                resolution=structure_resolution,
                fields=field_bindings,
                methods=method_bindings,
            )
        )
    return binding_ir


def build_binding_ir(root: Path, contract_ir: ContractIR, headers_only: bool = False, source_ir: SourceIR | None = None) -> BindingIR:
    if source_ir is not None:
        source_table = build_source_symbol_table_from_source_ir(source_ir)
    else:
        source_table = build_source_symbol_table(root, headers_only=headers_only)
    return build_binding_ir_from_table(contract_ir, source_table)
