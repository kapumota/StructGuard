from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import _minimal_yaml
from .schema import POLICY_SCHEMA, PolicySchemaNode


@dataclass(frozen=True)
class PolicyValidationIssue:
    level: str
    code: str
    message: str
    path: str
    key: str | None = None
    suggestion: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "key": self.key,
            "suggestion": self.suggestion,
        }


@dataclass(frozen=True)
class PolicyValidationResult:
    path: Path | None
    issues: list[PolicyValidationIssue]

    @property
    def valid(self) -> bool:
        return not any(issue.level == "FAILED" for issue in self.issues)

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path) if self.path else None,
            "valid": self.valid,
            "issues": [issue.as_dict() for issue in self.issues],
        }


def load_policy_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() == ".json":
        value = json.loads(text)
        return value if isinstance(value, dict) else {}
    return _minimal_yaml(text)


def validate_policy_mapping(data: dict[str, Any], path: Path | None = None) -> PolicyValidationResult:
    issues: list[PolicyValidationIssue] = []
    _validate_node(data, POLICY_SCHEMA, [], issues)
    if "version" not in data:
        issues.append(
            PolicyValidationIssue(
                level="FAILED",
                code="POLICY_REQUIRED_KEY_MISSING",
                message="Clave obligatoria ausente: version.",
                path="version",
                key="version",
            )
        )
    return PolicyValidationResult(path=path, issues=issues)


def validate_policy_file(path: str | Path) -> PolicyValidationResult:
    policy_path = Path(path)
    if not policy_path.exists():
        return PolicyValidationResult(
            path=policy_path,
            issues=[
                PolicyValidationIssue(
                    level="FAILED",
                    code="POLICY_FILE_MISSING",
                    message=f"Archivo de política no encontrado: {policy_path}",
                    path=str(policy_path),
                )
            ],
        )
    try:
        data = load_policy_mapping(policy_path)
    except Exception as exc:
        return PolicyValidationResult(
            path=policy_path,
            issues=[
                PolicyValidationIssue(
                    level="FAILED",
                    code="POLICY_PARSE_ERROR",
                    message=f"No se pudo leer la política: {exc}",
                    path=str(policy_path),
                )
            ],
        )
    return validate_policy_mapping(data, path=policy_path)


def _validate_node(data: Any, node: PolicySchemaNode, path: list[str], issues: list[PolicyValidationIssue]) -> None:
    if not isinstance(data, dict):
        return
    allowed = node.allowed_keys
    for key, value in data.items():
        if not node.allow_unknown_keys and key not in allowed:
            suggestion = _suggest_key(key, allowed)
            if suggestion:
                message = f"Clave desconocida: {key}. Quizá quiso decir {suggestion}."
            else:
                message = f"Clave desconocida: {key}."
            issues.append(
                PolicyValidationIssue(
                    level="FAILED",
                    code="POLICY_UNKNOWN_KEY",
                    message=message,
                    path=".".join([*path, key]),
                    key=key,
                    suggestion=suggestion,
                )
            )
            continue
        child = node.child_for(key)
        if child is not None:
            _validate_node(value, child, [*path, key], issues)


def _suggest_key(key: str, allowed: frozenset[str]) -> str | None:
    if key == "deep-secuirty" and "deep-security" in allowed:
        return "deep-security"
    matches = difflib.get_close_matches(key, sorted(allowed), n=1, cutoff=0.74)
    return matches[0] if matches else None
