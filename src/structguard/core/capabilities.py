from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AnalysisCapability:
    name: str
    enabled: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "enabled": self.enabled, "reason": self.reason}


@dataclass(frozen=True)
class AnalysisCapabilities:
    source_ir: bool = False
    contract_ir: bool = False
    binding: bool = False
    bounded: bool = False
    lint: bool = False
    security: bool = False
    memory_safety: bool = False
    formal: bool = False
    reports: bool = True
    notes: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_ir": self.source_ir,
            "contract_ir": self.contract_ir,
            "binding": self.binding,
            "bounded": self.bounded,
            "lint": self.lint,
            "security": self.security,
            "memory_safety": self.memory_safety,
            "formal": self.formal,
            "reports": self.reports,
            "notes": list(self.notes),
        }


PRESET_CAPABILITIES: dict[str, AnalysisCapabilities] = {
    "source": AnalysisCapabilities(source_ir=True, notes=("Solo construye SourceIR y diagnósticos del frontend.",)),
    "contracts": AnalysisCapabilities(
        source_ir=True,
        contract_ir=True,
        binding=True,
        bounded=True,
        lint=True,
        notes=("Valida contratos y ejecuta análisis contractual básico.",),
    ),
    "security": AnalysisCapabilities(
        source_ir=True,
        security=True,
        memory_safety=True,
        notes=("Ejecuta reglas de seguridad estructural y memoria usando el motor común.",),
    ),
    "ci": AnalysisCapabilities(
        source_ir=True,
        contract_ir=True,
        binding=True,
        bounded=True,
        lint=True,
        security=True,
        memory_safety=True,
        notes=("Ejecuta el conjunto base para CI usando el motor común.",),
    ),
    "full": AnalysisCapabilities(
        source_ir=True,
        contract_ir=True,
        binding=True,
        bounded=True,
        lint=True,
        security=True,
        memory_safety=True,
        formal=True,
        notes=("Ejecuta todos los pasos disponibles sin prometer verificación completa.",),
    ),
}


def capabilities_for_preset(preset: str) -> AnalysisCapabilities:
    return PRESET_CAPABILITIES.get(preset, PRESET_CAPABILITIES["contracts"])


def available_presets() -> tuple[str, ...]:
    return tuple(PRESET_CAPABILITIES.keys())
