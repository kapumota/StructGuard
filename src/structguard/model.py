from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


CONFIDENCE_LEVELS = {"PROVED", "BOUNDED_VERIFIED", "HEURISTIC", "UNKNOWN"}
OUTCOME_LEVELS = {"FAILED", "WARNING", "INFO"}
ALL_LEVELS = ("FAILED", "WARNING", "UNKNOWN", "HEURISTIC", "BOUNDED_VERIFIED", "PROVED", "INFO")



@dataclass(frozen=True)
class Contract:
    kind: str  # requires | ensures | invariant
    expression: str
    line: int = 0
    source: str = "declared"  # declared | inferred-assert | inferred-cc232


@dataclass
class MethodModel:
    class_name: str
    name: str
    signature: str
    body: str | None
    start_line: int
    requires: list[Contract] = field(default_factory=list)
    ensures: list[Contract] = field(default_factory=list)
    assertions: list[Contract] = field(default_factory=list)
    unsupported_notes: list[str] = field(default_factory=list)

    @property
    def qualified_name(self) -> str:
        return f"{self.class_name}::{self.name}"


@dataclass
class ClassModel:
    name: str
    file: Path
    start_line: int
    invariants: list[Contract] = field(default_factory=list)
    methods: list[MethodModel] = field(default_factory=list)
    fields: set[str] = field(default_factory=set)


@dataclass
class Diagnostic:
    level: str  # PROVED | BOUNDED_VERIFIED | HEURISTIC | UNKNOWN | FAILED | WARNING | INFO
    code: str
    message: str
    file: str | None = None
    line: int | None = None
    symbol: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectReport:
    root: str
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for d in self.diagnostics:
            out[d.level] = out.get(d.level, 0) + 1
        return out
