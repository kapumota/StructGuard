from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from structguard.cache import JsonCacheStore, build_analysis_fingerprint, run_cached_scan
from structguard.core import AnalysisContext
from structguard.model import Diagnostic
from structguard.profiles import apply_profile_defaults


def _write_header(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def _context(root: Path) -> AnalysisContext:
    args = Namespace(
        path=str(root),
        profile="generic-cpp",
        preset="security",
        headers_only=True,
        no_infer=False,
        max_cases=300,
        dsl=None,
        contract_paths=None,
        language=None,
        compile_commands=None,
        frontend="auto",
        fallback_allowed=False,
        clang=None,
        std="c++17",
        max_files=30,
        timeout=12,
        strict_ast=False,
    )
    profile = apply_profile_defaults(args)
    return AnalysisContext.from_namespace(args, profile, "security")


def test_analysis_fingerprint_changes_when_file_changes(tmp_path: Path) -> None:
    source = tmp_path / "Stack.hpp"
    _write_header(source, "class Stack { int n_; };\n")
    context = _context(tmp_path)

    first = build_analysis_fingerprint(source, context)
    _write_header(source, "class Stack { int n_; int capacity_; };\n")
    second = build_analysis_fingerprint(source, context)

    assert first.key != second.key
    assert first.file.sha256 != second.file.sha256


def test_json_cache_store_roundtrip(tmp_path: Path) -> None:
    store = JsonCacheStore(tmp_path / ".structguard" / "cache")
    diagnostic = Diagnostic(level="INFO", code="CACHE_TEST", message="Diagnóstico de prueba", file="Stack.hpp")

    from structguard.cache.store import CacheRecord

    store.put(CacheRecord(key="abc", fingerprint={"archivo": "Stack.hpp"}, diagnostics=[diagnostic]))
    loaded = store.get("abc")

    assert loaded is not None
    assert loaded.key == "abc"
    assert loaded.diagnostics[0].code == "CACHE_TEST"


def test_incremental_cache_reuses_unmodified_files(tmp_path: Path) -> None:
    _write_header(
        tmp_path / "StackOk.hpp",
        """
class StackOk {
public:
  void push(int value) { (void)value; }
};
""".strip()
        + "\n",
    )
    _write_header(
        tmp_path / "QueueOk.hpp",
        """
class QueueOk {
public:
  void push(int value) { (void)value; }
};
""".strip()
        + "\n",
    )

    cache_dir = tmp_path / ".structguard" / "cache"
    first = run_cached_scan(_context(tmp_path), cache_dir)
    second = run_cached_scan(_context(tmp_path), cache_dir)

    assert first.hits == 0
    assert first.misses == 2
    assert second.hits == 2
    assert second.misses == 0

    _write_header(
        tmp_path / "QueueOk.hpp",
        """
class QueueOk {
public:
  void push(int value) { (void)value; }
  void pop() {}
};
""".strip()
        + "\n",
    )

    third = run_cached_scan(_context(tmp_path), cache_dir)

    assert third.hits == 1
    assert third.misses == 1
