from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProfileAnalysisConfig:
    headers_only: bool = True
    strict_ast: bool = False
    bounded: bool = True
    max_cases: int | None = None
    include_security: bool = False
    deep_security: bool = False
    include_formal: bool = False
    run_solver: bool = False
    fail_on_warnings: bool = False
    fail_on_unknown: bool = False


@dataclass(frozen=True)
class ProfileOutputConfig:
    html: bool = True
    json: bool = True
    sarif: bool = True
    junit: bool = False


@dataclass(frozen=True)
class DomainProfile:
    name: str
    display_name: str
    description: str
    language: str
    status: str
    contracts: tuple[str, ...] = field(default_factory=tuple)
    analysis: ProfileAnalysisConfig = field(default_factory=ProfileAnalysisConfig)
    outputs: ProfileOutputConfig = field(default_factory=ProfileOutputConfig)
    path: Path | None = None

    def contract_paths(self) -> list[Path]:
        if not self.path:
            return [Path(c) for c in self.contracts]
        base = self.path.parent
        return [(base / c).resolve() for c in self.contracts]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "language": self.language,
            "status": self.status,
            "contracts": list(self.contracts),
            "analysis": {
                "headers_only": self.analysis.headers_only,
                "strict_ast": self.analysis.strict_ast,
                "bounded": self.analysis.bounded,
                "max_cases": self.analysis.max_cases,
                "include_security": self.analysis.include_security,
                "deep_security": self.analysis.deep_security,
                "include_formal": self.analysis.include_formal,
                "run_solver": self.analysis.run_solver,
                "fail_on_warnings": self.analysis.fail_on_warnings,
                "fail_on_unknown": self.analysis.fail_on_unknown,
            },
            "outputs": {
                "html": self.outputs.html,
                "json": self.outputs.json,
                "sarif": self.outputs.sarif,
                "junit": self.outputs.junit,
            },
            "path": str(self.path) if self.path else None,
        }


ALLOWED_LANGUAGES = {"cpp", "rust", "python", "multi"}
ALLOWED_STATUS = {"draft", "stable", "experimental", "template"}


PROFILE_REQUIRED_FIELDS = {
    "name",
    "display_name",
    "description",
    "language",
    "status",
}


def validate_domain_profile(profile: DomainProfile) -> list[str]:
    errors: list[str] = []
    if not profile.name:
        errors.append("El perfil no define name.")
    if profile.language not in ALLOWED_LANGUAGES:
        errors.append(f"Lenguaje no soportado en {profile.name}: {profile.language}.")
    if profile.status not in ALLOWED_STATUS:
        errors.append(f"Estado no soportado en {profile.name}: {profile.status}.")
    if not profile.contracts:
        errors.append(f"El perfil {profile.name} no declara contratos.")
    for contract in profile.contract_paths():
        if not contract.exists():
            errors.append(f"Contrato no encontrado para {profile.name}: {contract}.")
    return errors
