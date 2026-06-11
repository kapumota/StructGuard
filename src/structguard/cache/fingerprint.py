from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from structguard import __version__
from structguard.core import AnalysisContext


@dataclass(frozen=True)
class FileFingerprint:
    path: str
    sha256: str
    size: int

    def as_dict(self) -> dict[str, Any]:
        return {"path": self.path, "sha256": self.sha256, "size": self.size}


@dataclass(frozen=True)
class AnalysisFingerprint:
    key: str
    file: FileFingerprint
    contract_hashes: dict[str, str]
    flags: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "file": self.file.as_dict(),
            "contract_hashes": self.contract_hashes,
            "flags": self.flags,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_file_fingerprint(path: Path, root: Path | None = None) -> FileFingerprint:
    resolved = path.resolve()
    base = root.resolve() if root else resolved.parent
    try:
        relative = resolved.relative_to(base)
    except ValueError:
        relative = resolved
    stat = resolved.stat()
    return FileFingerprint(path=str(relative), sha256=sha256_file(resolved), size=stat.st_size)


def _contract_hashes(paths: tuple[str, ...]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for raw in sorted(paths):
        path = Path(raw)
        if path.is_file():
            hashes[str(path)] = sha256_file(path)
        elif path.is_dir():
            for item in sorted(path.rglob("*.sgdsl")):
                hashes[str(item)] = sha256_file(item)
        else:
            hashes[str(path)] = "missing"
    return hashes


def _context_flags(context: AnalysisContext) -> dict[str, Any]:
    return {
        "version": __version__,
        "preset": context.preset,
        "profile": context.profile.name if context.profile else None,
        "domain_profile": context.domain_profile.name if context.domain_profile else None,
        "headers_only": context.headers_only,
        "infer_contracts": context.infer_contracts,
        "max_cases": context.max_cases,
        "language": context.language,
        "compile_commands": str(context.compile_commands) if context.compile_commands else None,
        "frontend": context.frontend,
        "fallback_allowed": context.fallback_allowed,
        "std": context.std,
        "max_files": context.max_files,
        "timeout": context.timeout,
        "strict_ast": context.strict_ast,
        "capabilities": context.capabilities.as_dict(),
    }


def build_analysis_fingerprint(path: Path, context: AnalysisContext) -> AnalysisFingerprint:
    root = context.root if context.root.is_dir() else context.root.parent
    file_fp = build_file_fingerprint(path, root=root)
    contract_hashes = _contract_hashes(context.dsl_paths)
    flags = _context_flags(context)
    payload = {
        "file": file_fp.as_dict(),
        "contract_hashes": contract_hashes,
        "flags": flags,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    key = hashlib.sha256(encoded).hexdigest()
    return AnalysisFingerprint(key=key, file=file_fp, contract_hashes=contract_hashes, flags=flags)
