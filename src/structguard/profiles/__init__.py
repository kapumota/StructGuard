from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .loader import ProfileLoadError, discover_profile_files, load_profile_file, load_profiles, parse_profile_yaml
from .resolver import apply_domain_profile, default_profiles_root, find_project_root, resolve_profile
from .schema import DomainProfile, ProfileAnalysisConfig, ProfileOutputConfig, validate_domain_profile


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
    domain: str | None = None


BUILTIN_ANALYSIS_PROFILES: dict[str, AnalysisProfile] = {
    "student": AnalysisProfile("student", max_cases=150, verbose_hint=True),
    "ci": AnalysisProfile("ci", include_security=True, deep_security=True, max_cases=300),
    "strict": AnalysisProfile("strict", strict_ast=True, include_security=True, deep_security=True, max_cases=800, fail_on_unknown=True),
    "formal": AnalysisProfile("formal", strict_ast=True, include_formal=True, run_solver=True, max_cases=500),
    "security": AnalysisProfile("security", include_security=True, deep_security=True, max_cases=300),
}


def _discover_domain_profile_names() -> set[str]:
    try:
        return set(load_profiles(default_profiles_root()).keys())
    except Exception:
        return set()


PROFILES: dict[str, AnalysisProfile] = {
    **BUILTIN_ANALYSIS_PROFILES,
    **{name: AnalysisProfile(name=name, domain=name) for name in _discover_domain_profile_names()},
}


def get_profile(name: str | None) -> AnalysisProfile | None:
    if not name:
        return None
    return BUILTIN_ANALYSIS_PROFILES.get(name)


def _profile_from_domain(domain_profile: DomainProfile) -> AnalysisProfile:
    analysis = domain_profile.analysis
    return AnalysisProfile(
        name=domain_profile.name,
        strict_ast=analysis.strict_ast,
        include_security=analysis.include_security,
        deep_security=analysis.deep_security,
        include_formal=analysis.include_formal,
        run_solver=analysis.run_solver,
        fail_on_warnings=analysis.fail_on_warnings,
        fail_on_unknown=analysis.fail_on_unknown,
        max_cases=analysis.max_cases or 300,
        domain=domain_profile.name,
    )


def _apply_analysis_profile(prof: AnalysisProfile, args: Any) -> None:
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


def apply_profile_defaults(args: Any) -> AnalysisProfile | None:
    name = getattr(args, "profile", None)
    prof = get_profile(name)
    if prof:
        _apply_analysis_profile(prof, args)
        return prof

    domain_profile = apply_domain_profile(args)
    if not domain_profile:
        return None
    domain_as_analysis = _profile_from_domain(domain_profile)
    _apply_analysis_profile(domain_as_analysis, args)
    setattr(args, "resolved_domain_profile", domain_profile)
    return domain_as_analysis


__all__ = [
    "AnalysisProfile",
    "BUILTIN_ANALYSIS_PROFILES",
    "DomainProfile",
    "PROFILES",
    "ProfileAnalysisConfig",
    "ProfileLoadError",
    "ProfileOutputConfig",
    "apply_domain_profile",
    "apply_profile_defaults",
    "default_profiles_root",
    "discover_profile_files",
    "find_project_root",
    "get_profile",
    "load_profile_file",
    "load_profiles",
    "parse_profile_yaml",
    "resolve_profile",
    "validate_domain_profile",
]
