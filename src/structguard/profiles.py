from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalysisProfile:
    name: str
    strict_ast: bool = False
    include_security: bool = False
    deep_security: bool = False
    include_formal: bool = False
    run_solver: bool = False
    fail_on_warnings: bool = False
    fail_on_unknown: bool = False
    max_cases: int = 300
    verbose_hint: bool = False


PROFILES: dict[str, AnalysisProfile] = {
    "student": AnalysisProfile("student", max_cases=150, verbose_hint=True),
    "ci": AnalysisProfile("ci", include_security=True, deep_security=True, max_cases=300),
    "strict": AnalysisProfile("strict", strict_ast=True, include_security=True, deep_security=True, max_cases=800, fail_on_unknown=True),
    "formal": AnalysisProfile("formal", strict_ast=True, include_formal=True, run_solver=True, max_cases=500),
    "security": AnalysisProfile("security", include_security=True, deep_security=True, max_cases=300),
}


def get_profile(name: str | None) -> AnalysisProfile | None:
    if not name:
        return None
    return PROFILES.get(name)


def apply_profile_defaults(args: Any) -> AnalysisProfile | None:
    prof = get_profile(getattr(args, "profile", None))
    if not prof:
        return None
    if prof.strict_ast and not getattr(args, "strict_ast", False):
        setattr(args, "strict_ast", True)
    if getattr(args, "max_cases", None) in (None, 300):
        setattr(args, "max_cases", prof.max_cases)
    if hasattr(args, "deep_security") and prof.deep_security and not getattr(args, "deep_security", False):
        setattr(args, "deep_security", True)
    if hasattr(args, "fail_on_warnings") and prof.fail_on_warnings and not getattr(args, "fail_on_warnings", False):
        setattr(args, "fail_on_warnings", True)
    if hasattr(args, "fail_on_unknown") and prof.fail_on_unknown and not getattr(args, "fail_on_unknown", False):
        setattr(args, "fail_on_unknown", True)
    return prof
