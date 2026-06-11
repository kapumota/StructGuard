from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class SourceLocation:
    source: str
    line: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class SGDSLField:
    name: str
    type_name: str
    location: SourceLocation

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type_name": self.type_name,
            "location": self.location.as_dict(),
        }


@dataclass(frozen=True)
class SGDSLParam:
    name: str
    type_name: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "type_name": self.type_name}


@dataclass(frozen=True)
class SGDSLContract:
    kind: str
    expression: str
    location: SourceLocation

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "expression": self.expression,
            "location": self.location.as_dict(),
        }


@dataclass
class SGDSLMethod:
    name: str
    params: list[SGDSLParam] = field(default_factory=list)
    requires: list[SGDSLContract] = field(default_factory=list)
    ensures: list[SGDSLContract] = field(default_factory=list)
    location: SourceLocation | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "params": [p.as_dict() for p in self.params],
            "requires": [c.as_dict() for c in self.requires],
            "ensures": [c.as_dict() for c in self.ensures],
            "location": self.location.as_dict() if self.location else None,
        }


@dataclass
class SGDSLStructure:
    name: str
    fields: list[SGDSLField] = field(default_factory=list)
    invariants: list[SGDSLContract] = field(default_factory=list)
    methods: list[SGDSLMethod] = field(default_factory=list)
    location: SourceLocation | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "fields": [f.as_dict() for f in self.fields],
            "invariants": [c.as_dict() for c in self.invariants],
            "methods": [m.as_dict() for m in self.methods],
            "location": self.location.as_dict() if self.location else None,
        }


@dataclass
class SGDSLModule:
    source: str
    package: str | None = None
    structures: list[SGDSLStructure] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "package": self.package,
            "structures": [s.as_dict() for s in self.structures],
        }
