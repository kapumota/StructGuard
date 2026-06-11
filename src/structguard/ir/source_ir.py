from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceLocation:
    file: str
    line: int = 0
    column: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column,
        }


@dataclass(frozen=True)
class SourceDiagnostic:
    level: str
    code: str
    message: str
    location: SourceLocation | None = None
    details: dict[str, object] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "location": self.location.as_dict() if self.location else None,
            "details": self.details,
        }


@dataclass(frozen=True)
class SourceFieldIR:
    name: str
    type_name: str
    location: SourceLocation
    access: str = "unknown"

    @property
    def qualified_name(self) -> str:
        return self.name

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type_name": self.type_name,
            "location": self.location.as_dict(),
            "access": self.access,
        }


@dataclass(frozen=True)
class SourceMethodIR:
    name: str
    return_type: str
    parameters: list[str]
    location: SourceLocation
    signature: str
    access: str = "unknown"
    is_const: bool = False
    is_template: bool = False

    @property
    def qualified_name(self) -> str:
        return self.name

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "return_type": self.return_type,
            "parameters": self.parameters,
            "location": self.location.as_dict(),
            "signature": self.signature,
            "access": self.access,
            "is_const": self.is_const,
            "is_template": self.is_template,
        }


@dataclass
class SourceStructureIR:
    name: str
    kind: str
    location: SourceLocation
    namespace: str = ""
    fields: list[SourceFieldIR] = field(default_factory=list)
    methods: list[SourceMethodIR] = field(default_factory=list)
    is_template: bool = False

    @property
    def qualified_name(self) -> str:
        if self.namespace:
            return f"{self.namespace}::{self.name}"
        return self.name

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "qualified_name": self.qualified_name,
            "kind": self.kind,
            "location": self.location.as_dict(),
            "namespace": self.namespace,
            "fields": [field_ir.as_dict() for field_ir in self.fields],
            "methods": [method_ir.as_dict() for method_ir in self.methods],
            "is_template": self.is_template,
        }


@dataclass(frozen=True)
class SourceFileIR:
    path: str
    language: str
    frontend: str
    includes: list[str] = field(default_factory=list)
    namespaces: list[str] = field(default_factory=list)
    diagnostics: list[SourceDiagnostic] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "language": self.language,
            "frontend": self.frontend,
            "includes": self.includes,
            "namespaces": self.namespaces,
            "diagnostics": [diagnostic.as_dict() for diagnostic in self.diagnostics],
        }


@dataclass
class SourceIR:
    root: str
    language: str
    frontend: str
    files: list[SourceFileIR] = field(default_factory=list)
    structures: list[SourceStructureIR] = field(default_factory=list)
    diagnostics: list[SourceDiagnostic] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "language": self.language,
            "frontend": self.frontend,
            "files": [file_ir.as_dict() for file_ir in self.files],
            "structures": [structure.as_dict() for structure in self.structures],
            "diagnostics": [diagnostic.as_dict() for diagnostic in self.diagnostics],
            "summary": self.summary(),
        }

    def summary(self) -> dict[str, int]:
        return {
            "files": len(self.files),
            "structures": len(self.structures),
            "fields": sum(len(structure.fields) for structure in self.structures),
            "methods": sum(len(structure.methods) for structure in self.structures),
            "diagnostics": len(self.diagnostics),
        }
