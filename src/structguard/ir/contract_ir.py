from __future__ import annotations

from dataclasses import dataclass, field

from structguard.sgdsl.ast import SGDSLModule


@dataclass(frozen=True)
class FieldIR:
    name: str
    type_name: str
    source: str
    line: int

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "type_name": self.type_name, "source": self.source, "line": self.line}


@dataclass(frozen=True)
class PredicateIR:
    kind: str
    expression: str
    source: str
    line: int

    def as_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "expression": self.expression, "source": self.source, "line": self.line}


@dataclass(frozen=True)
class ParamIR:
    name: str
    type_name: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "type_name": self.type_name}


@dataclass
class MethodIR:
    name: str
    params: list[ParamIR] = field(default_factory=list)
    requires: list[PredicateIR] = field(default_factory=list)
    ensures: list[PredicateIR] = field(default_factory=list)
    source: str = ""
    line: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "params": [p.as_dict() for p in self.params],
            "requires": [p.as_dict() for p in self.requires],
            "ensures": [p.as_dict() for p in self.ensures],
            "source": self.source,
            "line": self.line,
        }


@dataclass
class StructureIR:
    name: str
    package: str | None = None
    fields: list[FieldIR] = field(default_factory=list)
    invariants: list[PredicateIR] = field(default_factory=list)
    methods: list[MethodIR] = field(default_factory=list)
    source: str = ""
    line: int = 0

    @property
    def qualified_name(self) -> str:
        return f"{self.package}.{self.name}" if self.package else self.name

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "qualified_name": self.qualified_name,
            "package": self.package,
            "fields": [f.as_dict() for f in self.fields],
            "invariants": [p.as_dict() for p in self.invariants],
            "methods": [m.as_dict() for m in self.methods],
            "source": self.source,
            "line": self.line,
        }


@dataclass
class ContractIR:
    structures: list[StructureIR] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {"structures": [s.as_dict() for s in self.structures]}


def build_contract_ir(modules: list[SGDSLModule]) -> ContractIR:
    ir = ContractIR()
    for module in modules:
        for structure in module.structures:
            structure_ir = StructureIR(
                name=structure.name,
                package=module.package,
                source=structure.location.source if structure.location else module.source,
                line=structure.location.line if structure.location else 0,
            )
            for field in structure.fields:
                structure_ir.fields.append(FieldIR(name=field.name, type_name=field.type_name, source=field.location.source, line=field.location.line))
            for invariant in structure.invariants:
                structure_ir.invariants.append(PredicateIR(kind=invariant.kind, expression=invariant.expression, source=invariant.location.source, line=invariant.location.line))
            for method in structure.methods:
                method_ir = MethodIR(
                    name=method.name,
                    params=[ParamIR(name=p.name, type_name=p.type_name) for p in method.params],
                    source=method.location.source if method.location else structure_ir.source,
                    line=method.location.line if method.location else structure_ir.line,
                )
                for requires in method.requires:
                    method_ir.requires.append(PredicateIR(kind=requires.kind, expression=requires.expression, source=requires.location.source, line=requires.location.line))
                for ensures in method.ensures:
                    method_ir.ensures.append(PredicateIR(kind=ensures.kind, expression=ensures.expression, source=ensures.location.source, line=ensures.location.line))
                structure_ir.methods.append(method_ir)
            ir.structures.append(structure_ir)
    return ir
