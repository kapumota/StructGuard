from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"
    INFO = "info"


SEVERITY_ORDER: dict[str, int] = {
    Severity.ERROR.value: 0,
    Severity.WARNING.value: 1,
    Severity.NOTE.value: 2,
    Severity.INFO.value: 3,
}


def severity_from_level(level: str) -> str:
    normalized = level.upper()
    if normalized == "FAILED":
        return Severity.ERROR.value
    if normalized in {"WARNING", "UNKNOWN"}:
        return Severity.WARNING.value
    if normalized in {"HEURISTIC", "BOUNDED_VERIFIED", "PROVED"}:
        return Severity.NOTE.value
    return Severity.INFO.value


def sort_key(severity: str) -> int:
    return SEVERITY_ORDER.get(severity, 99)
