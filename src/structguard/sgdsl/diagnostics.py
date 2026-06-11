from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SGDSLDiagnostic:
    level: str
    code: str
    message: str
    source: str | None = None
    line: int | None = None
    symbol: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "source": self.source,
            "line": self.line,
            "symbol": self.symbol,
            "details": self.details,
        }


class SGDSLParseError(Exception):
    def __init__(self, message: str, source: str | None = None, line: int | None = None) -> None:
        self.source = source
        self.line = line
        prefix = ""
        if source:
            prefix = source
            if line:
                prefix = f"{prefix}:{line}"
            prefix = f"{prefix}: "
        super().__init__(f"{prefix}{message}")
