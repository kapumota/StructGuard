from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MemoryLocation:
    file: str
    line: int

    def as_dict(self) -> dict[str, Any]:
        return {"file": self.file, "line": self.line}


@dataclass(frozen=True)
class PointerField:
    class_name: str
    name: str
    location: MemoryLocation
    initialized_null: bool = False

    @property
    def qualified_name(self) -> str:
        return f"{self.class_name}::{self.name}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "location": self.location.as_dict(),
            "initialized_null": self.initialized_null,
        }


@dataclass(frozen=True)
class MemoryAllocation:
    class_name: str
    method_name: str
    target: str
    kind: str
    location: MemoryLocation
    expression: str

    @property
    def symbol(self) -> str:
        return f"{self.class_name}::{self.method_name}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "method_name": self.method_name,
            "target": self.target,
            "kind": self.kind,
            "location": self.location.as_dict(),
            "expression": self.expression,
        }


@dataclass(frozen=True)
class MemoryRelease:
    class_name: str
    method_name: str
    target: str
    kind: str
    location: MemoryLocation
    expression: str

    @property
    def symbol(self) -> str:
        return f"{self.class_name}::{self.method_name}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "method_name": self.method_name,
            "target": self.target,
            "kind": self.kind,
            "location": self.location.as_dict(),
            "expression": self.expression,
        }


@dataclass(frozen=True)
class PointerDereference:
    class_name: str
    method_name: str
    target: str
    access: str
    location: MemoryLocation
    guarded: bool

    @property
    def symbol(self) -> str:
        return f"{self.class_name}::{self.method_name}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "method_name": self.method_name,
            "target": self.target,
            "access": self.access,
            "location": self.location.as_dict(),
            "guarded": self.guarded,
        }


@dataclass(frozen=True)
class NullAssignment:
    class_name: str
    method_name: str
    target: str
    location: MemoryLocation

    def as_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "method_name": self.method_name,
            "target": self.target,
            "location": self.location.as_dict(),
        }


@dataclass(frozen=True)
class CapacityRelation:
    class_name: str
    method_name: str
    size_field: str
    capacity_field: str
    relation: str
    location: MemoryLocation
    expression: str

    @property
    def symbol(self) -> str:
        return f"{self.class_name}::{self.method_name}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "method_name": self.method_name,
            "size_field": self.size_field,
            "capacity_field": self.capacity_field,
            "relation": self.relation,
            "location": self.location.as_dict(),
            "expression": self.expression,
        }


@dataclass
class ClassMemoryModel:
    class_name: str
    file: str
    pointer_fields: list[PointerField] = field(default_factory=list)
    allocations: list[MemoryAllocation] = field(default_factory=list)
    releases: list[MemoryRelease] = field(default_factory=list)
    dereferences: list[PointerDereference] = field(default_factory=list)
    null_assignments: list[NullAssignment] = field(default_factory=list)
    capacity_relations: list[CapacityRelation] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "file": self.file,
            "pointer_fields": [field.as_dict() for field in self.pointer_fields],
            "allocations": [allocation.as_dict() for allocation in self.allocations],
            "releases": [release.as_dict() for release in self.releases],
            "dereferences": [dereference.as_dict() for dereference in self.dereferences],
            "null_assignments": [assignment.as_dict() for assignment in self.null_assignments],
            "capacity_relations": [relation.as_dict() for relation in self.capacity_relations],
        }
