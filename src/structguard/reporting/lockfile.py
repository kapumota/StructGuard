from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from structguard import __version__

SCHEMA_VERSION = "structguard-lock/v1"
_SKIP_DIRS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", "__pycache__", "artifacts", "report", "reports", "struct_guard"}
_SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".py", ".sgdsl", ".yml", ".yaml", ".json"}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_input_files(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in _SOURCE_SUFFIXES:
            yield path


def _file_record(path: Path, base: Path) -> dict[str, Any]:
    try:
        relative = str(path.resolve().relative_to(base.resolve()))
    except Exception:
        relative = str(path)
    return {
        "path": relative,
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _normalize_context(context: dict[str, Any] | None) -> dict[str, Any]:
    if context is None:
        return {}
    return {key: value for key, value in context.items() if value is not None}


def build_lockfile(root: Path, context: dict[str, Any] | None = None, extra_paths: list[Path] | None = None) -> dict[str, Any]:
    """Construye un lockfile mínimo con hashes y entorno reproducible."""
    base = root if root.is_dir() else root.parent
    files = [_file_record(path, base) for path in _iter_input_files(root)]
    for extra in extra_paths or []:
        if extra.exists() and extra.is_file():
            files.append(_file_record(extra, base))
    files = sorted({record["path"]: record for record in files}.values(), key=lambda item: item["path"])
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": {
            "name": "StructGuard",
            "version": __version__,
        },
        "generated_at_utc": _now_utc(),
        "root": str(root),
        "context": _normalize_context(context),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "input_hashes": files,
    }


def write_lockfile(root: Path, path: Path, context: dict[str, Any] | None = None, extra_paths: list[Path] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = build_lockfile(root, context=context, extra_paths=extra_paths)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
