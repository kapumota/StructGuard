from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ContractHint:
    structure: str
    methods: list[str] = field(default_factory=list)
    requires_count: int = 0
    ensures_count: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "structure": self.structure,
            "methods": self.methods,
            "requires_count": self.requires_count,
            "ensures_count": self.ensures_count,
        }


@dataclass(frozen=True)
class TestgenCaseIR:
    structure: str
    seed: int
    operations: list[str]
    failure: str | None
    final_state: dict[str, Any]
    target_method: str | None = None
    minimized_operations: list[str] | None = None
    generation_mode: str = "model-based"
    utility_score: float = 0.0
    contract_hint: ContractHint | None = None
    classification: str = "smoke-candidate"

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "structure": self.structure,
            "seed": self.seed,
            "operations": self.operations,
            "failure": self.failure,
            "final_state": self.final_state,
            "target_method": self.target_method,
            "minimized_operations": self.minimized_operations,
            "generation_mode": self.generation_mode,
            "utility_score": self.utility_score,
            "classification": self.classification,
        }
        if self.contract_hint:
            payload["contract_hint"] = self.contract_hint.as_dict()
        return payload


@dataclass(frozen=True)
class TestgenManifest:
    root: str
    generation_mode: str
    cases: list[TestgenCaseIR]

    def summary(self) -> dict[str, object]:
        failures = [case for case in self.cases if case.failure]
        contract_guided = [case for case in self.cases if case.contract_hint]
        return {
            "case_count": len(self.cases),
            "failure_count": len(failures),
            "contract_guided_count": len(contract_guided),
            "max_utility_score": max((case.utility_score for case in self.cases), default=0.0),
            "generation_mode": self.generation_mode,
        }

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": "structguard-testgen.v1",
            "root": self.root,
            "generation_mode": self.generation_mode,
            "summary": self.summary(),
            "cases": [case.as_dict() for case in self.cases],
        }
