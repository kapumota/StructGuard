from structguard.analyzers.bounds import BOUNDS_RULES, analyze_bounds_project
from structguard.analyzers.complexity_hints import COMPLEXITY_RULES, analyze_complexity_hints_project
from structguard.analyzers.contracts import CONTRACT_RULES, RuleDefinition, analyze_contract_rules_project
from structguard.analyzers.memory_safety import MEMORY_RULES, analyze_memory_safety_project
from structguard.analyzers.structure_semantics import STRUCTURE_RULES, analyze_structure_semantics_project

ALL_RULES: dict[str, RuleDefinition] = {
    **CONTRACT_RULES,
    **BOUNDS_RULES,
    **STRUCTURE_RULES,
    **MEMORY_RULES,
    **COMPLEXITY_RULES,
}


def rule_catalog() -> list[dict[str, object]]:
    return [rule.as_dict() for rule in sorted(ALL_RULES.values(), key=lambda item: item.rule_id)]


__all__ = [
    "ALL_RULES",
    "BOUNDS_RULES",
    "COMPLEXITY_RULES",
    "CONTRACT_RULES",
    "MEMORY_RULES",
    "STRUCTURE_RULES",
    "RuleDefinition",
    "analyze_bounds_project",
    "analyze_complexity_hints_project",
    "analyze_contract_rules_project",
    "analyze_memory_safety_project",
    "analyze_structure_semantics_project",
    "rule_catalog",
]
