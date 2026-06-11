from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from structguard.core import AnalysisContext, AnalysisEngine
from structguard.core.result import AnalysisEngineResult, AnalysisPassResult
from structguard.cppscan import iter_cpp_files
from structguard.model import Diagnostic, ProjectReport

from .fingerprint import build_analysis_fingerprint
from .store import CacheRecord, JsonCacheStore


@dataclass
class CachedScanResult:
    engine_result: AnalysisEngineResult
    hits: int
    misses: int
    files: int


def _cacheable_files(root: Path, headers_only: bool) -> list[Path]:
    if root.is_file():
        return [root]
    return iter_cpp_files(root, headers_only=headers_only)


def _diagnostic_for_cache(code: str, message: str, root: Path, details: dict[str, object]) -> Diagnostic:
    return Diagnostic(level="INFO", code=code, message=message, file=str(root), details=details)


def _run_single_file(context: AnalysisContext, path: Path) -> AnalysisEngineResult:
    file_context = replace(context, root=path)
    return AnalysisEngine().run(file_context)


def run_cached_scan(context: AnalysisContext, cache_dir: Path, clear: bool = False) -> CachedScanResult:
    store = JsonCacheStore(cache_dir)
    if clear:
        store.clear()

    files = _cacheable_files(context.root, context.headers_only)
    if not files:
        result = AnalysisEngine().run(context)
        result.report.diagnostics.insert(
            0,
            _diagnostic_for_cache(
                "CACHE_DISABLED_NO_FILES",
                "No se encontraron archivos cacheables; se ejecutó análisis completo.",
                context.root,
                {"cache_dir": str(cache_dir)},
            ),
        )
        return CachedScanResult(engine_result=result, hits=0, misses=0, files=0)

    hits = 0
    misses = 0
    diagnostics: list[Diagnostic] = []
    pass_results: list[AnalysisPassResult] = []

    for file_path in files:
        fingerprint = build_analysis_fingerprint(file_path, context)
        record = store.get(fingerprint.key)
        if record is not None:
            hits += 1
            diagnostics.extend(record.diagnostics)
            pass_results.append(
                AnalysisPassResult(
                    name="FileCache",
                    status="cached",
                    diagnostics=[],
                    details={"file": str(file_path), "key": fingerprint.key},
                )
            )
            continue

        misses += 1
        file_result = _run_single_file(context, file_path)
        diagnostics.extend(file_result.report.diagnostics)
        pass_results.extend(file_result.pass_results)
        store.put(CacheRecord(key=fingerprint.key, fingerprint=fingerprint.as_dict(), diagnostics=list(file_result.report.diagnostics)))

    summary = _diagnostic_for_cache(
        "CACHE_SUMMARY",
        f"Cache incremental: {hits} reutilizados, {misses} recalculados, {len(files)} archivos.",
        context.root,
        {"hits": hits, "misses": misses, "files": len(files), "cache_dir": str(cache_dir)},
    )
    report = ProjectReport(root=str(context.root), diagnostics=[summary, *diagnostics])
    header = AnalysisPassResult(
        name="FileCache",
        status="ok",
        diagnostics=[summary],
        details={"hits": hits, "misses": misses, "files": len(files), "cache_dir": str(cache_dir)},
    )
    engine_result = AnalysisEngineResult(context=context, pass_results=[header, *pass_results], report=report)
    return CachedScanResult(engine_result=engine_result, hits=hits, misses=misses, files=len(files))
