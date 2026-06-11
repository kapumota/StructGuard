from __future__ import annotations

from dataclasses import dataclass
from difflib import get_close_matches

from .symbol_table import SourceStructureSymbol, SourceSymbolTable


@dataclass(frozen=True)
class NameResolutionResult:
    requested: str
    resolved: str | None
    candidates: list[str]

    @property
    def matched(self) -> bool:
        return self.resolved is not None

    def as_dict(self) -> dict[str, object]:
        return {
            "requested": self.requested,
            "resolved": self.resolved,
            "candidates": self.candidates,
            "matched": self.matched,
        }


def normalize_contract_name(name: str) -> str:
    return name.split(".")[-1].split("::")[-1].strip()


def suggest_names(name: str, candidates: list[str], limit: int = 3) -> list[str]:
    if not candidates:
        return []
    return get_close_matches(normalize_contract_name(name), candidates, n=limit, cutoff=0.45)


def resolve_structure(table: SourceSymbolTable, contract_name: str) -> tuple[SourceStructureSymbol | None, NameResolutionResult]:
    short_name = normalize_contract_name(contract_name)
    structure = table.get_structure(short_name)
    candidates = suggest_names(short_name, sorted(table.structures))
    if structure:
        return structure, NameResolutionResult(requested=contract_name, resolved=structure.name, candidates=candidates)
    return None, NameResolutionResult(requested=contract_name, resolved=None, candidates=candidates)


def resolve_field(structure: SourceStructureSymbol, field_name: str) -> NameResolutionResult:
    candidates = suggest_names(field_name, sorted(structure.fields))
    if field_name in structure.fields:
        return NameResolutionResult(requested=field_name, resolved=field_name, candidates=candidates)
    return NameResolutionResult(requested=field_name, resolved=None, candidates=candidates)


def resolve_method(structure: SourceStructureSymbol, method_name: str) -> NameResolutionResult:
    candidates = suggest_names(method_name, sorted(structure.methods))
    if method_name in structure.methods:
        return NameResolutionResult(requested=method_name, resolved=method_name, candidates=candidates)
    return NameResolutionResult(requested=method_name, resolved=None, candidates=candidates)
