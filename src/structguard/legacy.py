from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import Literal, TextIO

LegacyDecision = Literal["mantener", "migrar", "deprecar", "eliminar despues"]


@dataclass(frozen=True)
class LegacyCommandPolicy:
    command: str
    decision: LegacyDecision
    replacement: str
    removal: str
    rationale: str


LEGACY_COMMANDS: tuple[LegacyCommandPolicy, ...] = (
    LegacyCommandPolicy(
        command="verify",
        decision="migrar",
        replacement="scan --preset contracts",
        removal="despues de migrar pruebas, ejemplos y documentacion activa",
        rationale="El analisis acotado debe ejecutarse desde el motor modular de scan.",
    ),
    LegacyCommandPolicy(
        command="lint",
        decision="migrar",
        replacement="scan --preset contracts",
        removal="despues de migrar pruebas, ejemplos y documentacion activa",
        rationale="El lint de contratos debe converger con FindingIR y presets de contratos.",
    ),
    LegacyCommandPolicy(
        command="security",
        decision="migrar",
        replacement="scan --preset security",
        removal="despues de validar equivalencia de reportes de seguridad",
        rationale="La seguridad debe ejecutarse como preset del motor modular.",
    ),
    LegacyCommandPolicy(
        command="perf",
        decision="mantener",
        replacement="mantener como reporte especializado de rendimiento",
        removal="sin eliminacion programada",
        rationale="El comando conserva reportes y harnesses de rendimiento que aun no pertenecen al benchmark de regresion.",
    ),
    LegacyCommandPolicy(
        command="ci",
        decision="migrar",
        replacement="scan --preset ci y workflows de CI de Fase 14",
        removal="despues de migrar gates locales y documentacion principal",
        rationale="El gate de CI debe depender de presets, politica validada y benchmarks medibles.",
    ),
    LegacyCommandPolicy(
        command="bench",
        decision="migrar",
        replacement="python benchmarks/run_benchmark.py",
        removal="despues de estabilizar un comando benchmark canonico",
        rationale="El benchmark de regresion ya vive en benchmarks/run_benchmark.py y thresholds.yml.",
    ),
    LegacyCommandPolicy(
        command="assist",
        decision="deprecar",
        replacement="docs, reportes canonicos y futuras recomendaciones derivadas de FindingIR",
        removal="despues de retirar referencias en demos y README",
        rationale="El comando produce recomendaciones heuristicas historicas sin contrato estable.",
    ),
    LegacyCommandPolicy(
        command="advanced",
        decision="deprecar",
        replacement="perfiles y contratos SGDSL documentados",
        removal="despues de migrar plantillas utiles a profiles/ y docs/",
        rationale="Las plantillas avanzadas deben vivir como perfiles, contratos o documentacion versionada.",
    ),
    LegacyCommandPolicy(
        command="clang",
        decision="migrar",
        replacement="scan --language cpp --frontend clang --compile-commands ...",
        removal="despues de validar el frontend Clang dentro de scan",
        rationale="Clang debe ser una opcion de frontend dentro del flujo canonico scan.",
    ),
    LegacyCommandPolicy(
        command="formal",
        decision="mantener",
        replacement="mantener como backend formal experimental",
        removal="sin eliminacion programada antes de estabilizar exportadores formales",
        rationale="El backend formal sigue siendo experimental y no debe confundirse con scan estable.",
    ),
    LegacyCommandPolicy(
        command="fuzz",
        decision="deprecar",
        replacement="testgen",
        removal="despues de retirar referencias activas a fuzz como flujo principal",
        rationale="fuzz no ejecuta binarios ni instrumentacion; testgen describe mejor la generacion abstracta.",
    ),
)


def legacy_policy_rows() -> tuple[LegacyCommandPolicy, ...]:
    return LEGACY_COMMANDS


def get_legacy_policy(command: str) -> LegacyCommandPolicy:
    for policy in LEGACY_COMMANDS:
        if policy.command == command:
            return policy
    raise KeyError(f"Comando heredado no registrado: {command}")


def format_legacy_notice(policy: LegacyCommandPolicy) -> str:
    prefix = "Advertencia legacy"
    if policy.command == "formal":
        prefix = "Aviso experimental"
    elif policy.decision == "mantener":
        prefix = "Aviso legacy"
    return (
        f"{prefix}: el comando '{policy.command}' tiene decision '{policy.decision}'. "
        f"Reemplazo o estado recomendado: {policy.replacement}. "
        f"Retiro: {policy.removal}."
    )


def emit_legacy_notice(command: str, stream: TextIO | None = None) -> None:
    target = stream or sys.stderr
    print(format_legacy_notice(get_legacy_policy(command)), file=target)
