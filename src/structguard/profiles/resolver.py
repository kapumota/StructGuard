from __future__ import annotations

from pathlib import Path
from typing import Any

from .loader import ProfileLoadError, load_profile_file, load_profiles
from .schema import DomainProfile


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists() or (candidate / "profiles").exists():
            return candidate
    return current


def default_profiles_root(start: Path | None = None) -> Path:
    return find_project_root(start) / "profiles"


def resolve_profile(name_or_path: str, start: Path | None = None) -> DomainProfile:
    raw = Path(name_or_path)
    if raw.exists():
        return load_profile_file(raw)

    project_root = find_project_root(start)
    by_name = project_root / "profiles" / name_or_path / "profile.yml"
    if by_name.exists():
        return load_profile_file(by_name)

    profiles = load_profiles(project_root / "profiles")
    if name_or_path in profiles:
        return profiles[name_or_path]

    raise ProfileLoadError(f"Perfil no encontrado: {name_or_path}")


def apply_domain_profile(args: Any, start: Path | None = None) -> DomainProfile | None:
    name = getattr(args, "profile", None)
    if not name:
        return None
    try:
        profile = resolve_profile(str(name), start=start)
    except ProfileLoadError:
        return None

    dsl_paths = list(getattr(args, "dsl", None) or [])
    for contract in profile.contract_paths():
        contract_text = str(contract)
        if contract_text not in dsl_paths:
            dsl_paths.append(contract_text)
    setattr(args, "dsl", dsl_paths)

    if profile.analysis.headers_only and hasattr(args, "headers_only") and not getattr(args, "headers_only", False):
        setattr(args, "headers_only", True)
    if profile.analysis.strict_ast and hasattr(args, "strict_ast") and not getattr(args, "strict_ast", False):
        setattr(args, "strict_ast", True)
    if profile.analysis.max_cases is not None and hasattr(args, "max_cases"):
        current = getattr(args, "max_cases", None)
        if current in (None, 300):
            setattr(args, "max_cases", profile.analysis.max_cases)
    if profile.analysis.deep_security and hasattr(args, "deep_security") and not getattr(args, "deep_security", False):
        setattr(args, "deep_security", True)
    if profile.analysis.fail_on_warnings and hasattr(args, "fail_on_warnings") and not getattr(args, "fail_on_warnings", False):
        setattr(args, "fail_on_warnings", True)
    if profile.analysis.fail_on_unknown and hasattr(args, "fail_on_unknown") and not getattr(args, "fail_on_unknown", False):
        setattr(args, "fail_on_unknown", True)
    return profile
