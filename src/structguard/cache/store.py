from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from structguard.model import Diagnostic


@dataclass
class CacheRecord:
    key: str
    fingerprint: dict[str, Any]
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "key": self.key,
            "fingerprint": self.fingerprint,
            "diagnostics": [diagnostic.__dict__ for diagnostic in self.diagnostics],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CacheRecord":
        diagnostics = [Diagnostic(**item) for item in payload.get("diagnostics", [])]
        return cls(key=str(payload["key"]), fingerprint=dict(payload.get("fingerprint", {})), diagnostics=diagnostics)


class JsonCacheStore:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir

    def clear(self) -> None:
        if not self.cache_dir.exists():
            return
        for item in self.cache_dir.glob("*.json"):
            item.unlink()

    def path_for_key(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> CacheRecord | None:
        path = self.path_for_key(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return CacheRecord.from_dict(payload)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            # Si una entrada está corrupta, se ignora y el análisis se recalcula.
            return None

    def put(self, record: CacheRecord) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for_key(record.key)
        path.write_text(json.dumps(record.as_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
