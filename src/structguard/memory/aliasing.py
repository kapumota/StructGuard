from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .model import MemoryLocation


@dataclass(frozen=True)
class AliasRelation:
    class_name: str
    method_name: str
    target: str
    source: str
    location: MemoryLocation

    def as_dict(self) -> dict[str, Any]:
        return {
            "class_name": self.class_name,
            "method_name": self.method_name,
            "target": self.target,
            "source": self.source,
            "location": self.location.as_dict(),
        }


def detect_local_aliases(class_name: str, method_name: str, source: str, file: str, start_line: int) -> list[AliasRelation]:
    aliases: list[AliasRelation] = []
    for match in re.finditer(r"\b(?P<target>[A-Za-z_]\w*)\s*=\s*(?P<source>[A-Za-z_]\w*)\s*;", source):
        target = match.group("target")
        source_name = match.group("source")
        if target == source_name or source_name in {"nullptr", "NULL"}:
            continue
        aliases.append(
            AliasRelation(
                class_name=class_name,
                method_name=method_name,
                target=target,
                source=source_name,
                location=MemoryLocation(file=file, line=start_line + source.count("\n", 0, match.start())),
            )
        )
    return aliases
