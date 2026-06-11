from __future__ import annotations

from pathlib import Path
from typing import Any

from .schema import DomainProfile, ProfileAnalysisConfig, ProfileOutputConfig, PROFILE_REQUIRED_FIELDS, validate_domain_profile


class ProfileLoadError(ValueError):
    pass


def _parse_scalar(value: str) -> Any:
    clean = value.strip()
    if clean in {"true", "True", "yes", "si", "sí"}:
        return True
    if clean in {"false", "False", "no"}:
        return False
    if clean in {"null", "None", ""}:
        return None
    try:
        return int(clean)
    except ValueError:
        return clean.strip('"').strip("'")


def _strip_comment(line: str) -> str:
    if "#" not in line:
        return line.rstrip()
    before, _, _ = line.partition("#")
    return before.rstrip()


def parse_profile_yaml(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    current_map: dict[str, Any] | None = None
    current_list: list[Any] | None = None

    for raw_line in text.splitlines():
        line = _strip_comment(raw_line)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            if ":" not in stripped:
                raise ProfileLoadError(f"Línea YAML no reconocida: {raw_line}")
            key, _, value = stripped.partition(":")
            current_key = key.strip()
            current_map = None
            current_list = None
            if value.strip():
                data[current_key] = _parse_scalar(value)
            else:
                data[current_key] = {}
            continue

        if current_key is None:
            raise ProfileLoadError(f"Entrada YAML sin clave principal: {raw_line}")

        if stripped.startswith("- "):
            if current_list is None:
                current_list = []
                data[current_key] = current_list
            current_list.append(_parse_scalar(stripped[2:]))
            continue

        if ":" in stripped:
            if current_map is None:
                current_map = {}
                data[current_key] = current_map
            key, _, value = stripped.partition(":")
            current_map[key.strip()] = _parse_scalar(value)
            continue

        raise ProfileLoadError(f"Línea YAML no reconocida: {raw_line}")

    return data


def _bool_from_map(data: dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    return bool(value)


def _int_or_none(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except ValueError as exc:
        raise ProfileLoadError(f"El campo {key} debe ser entero.") from exc


def load_profile_file(path: Path) -> DomainProfile:
    profile_path = path.resolve()
    if profile_path.is_dir():
        profile_path = profile_path / "profile.yml"
    if not profile_path.exists():
        raise ProfileLoadError(f"No existe el perfil: {profile_path}")

    raw = parse_profile_yaml(profile_path.read_text(encoding="utf-8"))
    missing = sorted(PROFILE_REQUIRED_FIELDS - set(raw))
    if missing:
        raise ProfileLoadError("Faltan campos obligatorios en el perfil: " + ", ".join(missing))

    analysis_data = raw.get("analysis") or {}
    outputs_data = raw.get("outputs") or {}
    if not isinstance(analysis_data, dict):
        raise ProfileLoadError("El bloque analysis debe ser un mapa YAML.")
    if not isinstance(outputs_data, dict):
        raise ProfileLoadError("El bloque outputs debe ser un mapa YAML.")

    contracts = raw.get("contracts") or []
    if not isinstance(contracts, list):
        raise ProfileLoadError("El campo contracts debe ser una lista YAML.")

    profile = DomainProfile(
        name=str(raw["name"]),
        display_name=str(raw["display_name"]),
        description=str(raw["description"]),
        language=str(raw["language"]),
        status=str(raw["status"]),
        contracts=tuple(str(c) for c in contracts),
        analysis=ProfileAnalysisConfig(
            headers_only=_bool_from_map(analysis_data, "headers_only", True),
            strict_ast=_bool_from_map(analysis_data, "strict_ast", False),
            bounded=_bool_from_map(analysis_data, "bounded", True),
            max_cases=_int_or_none(analysis_data, "max_cases"),
            include_security=_bool_from_map(analysis_data, "include_security", False),
            deep_security=_bool_from_map(analysis_data, "deep_security", False),
            include_formal=_bool_from_map(analysis_data, "include_formal", False),
            run_solver=_bool_from_map(analysis_data, "run_solver", False),
            fail_on_warnings=_bool_from_map(analysis_data, "fail_on_warnings", False),
            fail_on_unknown=_bool_from_map(analysis_data, "fail_on_unknown", False),
        ),
        outputs=ProfileOutputConfig(
            html=_bool_from_map(outputs_data, "html", True),
            json=_bool_from_map(outputs_data, "json", True),
            sarif=_bool_from_map(outputs_data, "sarif", True),
            junit=_bool_from_map(outputs_data, "junit", False),
        ),
        path=profile_path,
    )
    errors = validate_domain_profile(profile)
    if errors:
        raise ProfileLoadError("\n".join(errors))
    return profile


def discover_profile_files(root: Path) -> list[Path]:
    profiles_root = root.resolve()
    if not profiles_root.exists():
        return []
    return sorted(p for p in profiles_root.glob("*/profile.yml") if p.is_file())


def load_profiles(root: Path) -> dict[str, DomainProfile]:
    profiles: dict[str, DomainProfile] = {}
    for profile_path in discover_profile_files(root):
        profile = load_profile_file(profile_path)
        profiles[profile.name] = profile
    return profiles
