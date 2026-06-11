from __future__ import annotations

from typing import Protocol

from .analysis_context import AnalysisContext
from .result import AnalysisPassResult


class AnalysisPass(Protocol):
    name: str

    def run(self, context: AnalysisContext) -> AnalysisPassResult:
        ...


class PassManager:
    def __init__(self, passes: list[AnalysisPass]) -> None:
        self.passes = passes

    def run(self, context: AnalysisContext) -> list[AnalysisPassResult]:
        results: list[AnalysisPassResult] = []
        for analysis_pass in self.passes:
            result = analysis_pass.run(context)
            results.append(result)
            if result.status == "failed":
                context.metadata.setdefault("failed_passes", []).append(analysis_pass.name)
        return results
