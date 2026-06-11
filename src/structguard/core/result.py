from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from structguard.model import Diagnostic, ProjectReport


@dataclass
class AnalysisPassResult:
    name: str
    status: str
    diagnostics: list[Diagnostic] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "diagnostics": [diagnostic.__dict__ for diagnostic in self.diagnostics],
            "details": self.details,
        }


@dataclass
class AnalysisEngineResult:
    context: Any
    pass_results: list[AnalysisPassResult]
    report: ProjectReport

    @property
    def failed(self) -> bool:
        return any(diagnostic.level == "FAILED" for diagnostic in self.report.diagnostics)

    def as_dict(self) -> dict[str, Any]:
        return {
            "context": self.context.as_dict() if hasattr(self.context, "as_dict") else {},
            "passes": [result.as_dict() for result in self.pass_results],
            "report": {
                "root": self.report.root,
                "diagnostics": [diagnostic.__dict__ for diagnostic in self.report.diagnostics],
                "counts": self.report.counts(),
            },
        }
