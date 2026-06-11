from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from structguard.profiles import AnalysisProfile, DomainProfile

from .capabilities import AnalysisCapabilities, capabilities_for_preset


@dataclass
class AnalysisContext:
    root: Path
    preset: str
    profile: AnalysisProfile | None = None
    domain_profile: DomainProfile | None = None
    headers_only: bool = False
    infer_contracts: bool = True
    max_cases: int = 300
    dsl_paths: tuple[str, ...] = field(default_factory=tuple)
    language: str | None = None
    compile_commands: Path | None = None
    frontend: str = "auto"
    fallback_allowed: bool = False
    clang: str | None = None
    std: str = "c++17"
    max_files: int = 30
    timeout: int = 12
    strict_ast: bool = False
    capabilities: AnalysisCapabilities = field(default_factory=lambda: capabilities_for_preset("contracts"))
    source_ir: Any | None = None
    contract_ir: Any | None = None
    binding_ir: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_namespace(cls, args: Any, profile: AnalysisProfile | None, preset: str) -> "AnalysisContext":
        compile_commands = getattr(args, "compile_commands", None)
        dsl_paths = list(getattr(args, "dsl", None) or [])
        for contract in getattr(args, "contract_paths", None) or []:
            if contract not in dsl_paths:
                dsl_paths.append(contract)
        return cls(
            root=Path(getattr(args, "path", ".")),
            preset=preset,
            profile=profile,
            domain_profile=getattr(args, "resolved_domain_profile", None),
            headers_only=bool(getattr(args, "headers_only", False)),
            infer_contracts=not bool(getattr(args, "no_infer", False)),
            max_cases=int(getattr(args, "max_cases", 300) or 300),
            dsl_paths=tuple(dsl_paths),
            language=getattr(args, "language", None),
            compile_commands=Path(compile_commands) if compile_commands else None,
            frontend=getattr(args, "frontend", "auto") or "auto",
            fallback_allowed=bool(getattr(args, "fallback_allowed", False)),
            clang=getattr(args, "clang", None),
            std=getattr(args, "std", "c++17"),
            max_files=int(getattr(args, "max_files", 30) or 30),
            timeout=int(getattr(args, "timeout", 12) or 12),
            strict_ast=bool(getattr(args, "strict_ast", False)),
            capabilities=capabilities_for_preset(preset),
            metadata={"profile_contract_mode": getattr(args, "profile_contract_mode", "profile")},
        )

    def wants_cpp_source_ir(self) -> bool:
        return self.language == "cpp" or self.compile_commands is not None or self.frontend != "auto"

    def as_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "preset": self.preset,
            "profile": self.profile.name if self.profile else None,
            "domain_profile": self.domain_profile.name if self.domain_profile else None,
            "headers_only": self.headers_only,
            "infer_contracts": self.infer_contracts,
            "max_cases": self.max_cases,
            "dsl_paths": list(self.dsl_paths),
            "language": self.language,
            "compile_commands": str(self.compile_commands) if self.compile_commands else None,
            "frontend": self.frontend,
            "fallback_allowed": self.fallback_allowed,
            "std": self.std,
            "max_files": self.max_files,
            "timeout": self.timeout,
            "strict_ast": self.strict_ast,
            "capabilities": self.capabilities.as_dict(),
            "metadata": self.metadata,
        }
