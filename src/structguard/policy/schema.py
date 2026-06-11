from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PolicySchemaNode:
    """Nodo simple de esquema para validar claves de política."""

    allowed_keys: frozenset[str] = field(default_factory=frozenset)
    children: dict[str, "PolicySchemaNode"] = field(default_factory=dict)
    allow_unknown_keys: bool = False

    def child_for(self, key: str) -> "PolicySchemaNode | None":
        if self.allow_unknown_keys:
            return self.children.get("*")
        return self.children.get(key)


RULE_NODE = PolicySchemaNode(
    allowed_keys=frozenset({"severity", "confidence", "enabled", "cwe", "tags", "remediation", "description"})
)

POLICY_SCHEMA = PolicySchemaNode(
    allowed_keys=frozenset(
        {
            "project",
            "version",
            "profile",
            "paths",
            "scan",
            "frontend",
            "frontends",
            "verification",
            "lint",
            "security",
            "deep-security",
            "fuzz",
            "thresholds",
            "clang",
            "ci",
            "report",
            "outputs",
            "rules",
            "dsl",
            "bench",
            "performance",
            "trace",
            "formal",
            "pipeline",
            "assist",
            "advanced",
            "docs",
        }
    ),
    children={
        "scan": PolicySchemaNode(
            allowed_keys=frozenset({"headers_only", "language", "compile_commands", "frontend", "fallback_allowed", "paths", "path"})
        ),
        "frontend": PolicySchemaNode(
            allowed_keys=frozenset({"cpp"}),
            children={
                "cpp": PolicySchemaNode(
                    allowed_keys=frozenset(
                        {"primary", "fallback", "fallback_allowed", "compile_commands", "std", "clang", "timeout", "max_files"}
                    )
                )
            },
        ),
        "frontends": PolicySchemaNode(allowed_keys=frozenset({"rust", "python", "cpp"})),
        "verification": PolicySchemaNode(
            allowed_keys=frozenset({"mode", "max_cases", "strict_ast", "fail_on_failed_contract", "infer_cc232_contracts"})
        ),
        "lint": PolicySchemaNode(allowed_keys=frozenset({"require_invariants_for_data_structures"})),
        "security": PolicySchemaNode(
            allowed_keys=frozenset({"deep", "fail_on_warnings", "fail_on_missing_preconditions", "rules_json"})
        ),
        "fuzz": PolicySchemaNode(allowed_keys=frozenset({"seeds", "steps", "fail_on_failures"})),
        "thresholds": PolicySchemaNode(allowed_keys=frozenset({"max_failures", "max_warnings", "max_unknown"})),
        "clang": PolicySchemaNode(allowed_keys=frozenset({"binary", "std", "max_files", "timeout", "strict_ast"})),
        "ci": PolicySchemaNode(
            allowed_keys=frozenset(
                {
                    "required_modules",
                    "fail_on_warnings",
                    "fail_on_unknown",
                    "fail_on_security_warnings",
                    "fail_on_fuzz_failures",
                    "fail_on_failed_contract",
                    "deep_security",
                    "max_failures",
                    "max_warnings",
                    "max_unknown",
                    "fuzz_seeds",
                    "fuzz_steps",
                }
            )
        ),
        "report": PolicySchemaNode(
            allowed_keys=frozenset(
                {
                    "html",
                    "json",
                    "junit",
                    "sarif",
                    "summary_md",
                    "markdown",
                    "findings_json",
                    "findings_html",
                    "findings_md",
                    "findings_junit",
                    "findings_sarif",
                }
            )
        ),
        "outputs": PolicySchemaNode(
            allowed_keys=frozenset({"sarif", "junit", "html", "json", "markdown", "summary_md"})
        ),
        "rules": PolicySchemaNode(allow_unknown_keys=True, children={"*": RULE_NODE}),
        "dsl": PolicySchemaNode(allowed_keys=frozenset({"files"})),
        "bench": PolicySchemaNode(allowed_keys=frozenset({"mode"})),
        "performance": PolicySchemaNode(
            allowed_keys=frozenset({"mode", "regression_threshold_percent", "report", "baseline"})
        ),
        "trace": PolicySchemaNode(allowed_keys=frozenset({"mode"})),
        "formal": PolicySchemaNode(allowed_keys=frozenset({"backend", "out_dir", "run_solver"})),
        "pipeline": PolicySchemaNode(allowed_keys=frozenset({"out_dir", "backend", "run_solver"})),
        "assist": PolicySchemaNode(allowed_keys=frozenset({"mode"})),
        "advanced": PolicySchemaNode(allowed_keys=frozenset({"dsl"})),
        "docs": PolicySchemaNode(allowed_keys=frozenset({"html", "markdown_dir", "json"})),
    },
)


def policy_schema_as_dict() -> dict[str, Any]:
    return {
        "title": "StructGuard Policy",
        "type": "object",
        "additionalProperties": False,
        "required": ["version"],
        "properties": {
            "version": {"type": ["integer", "string"]},
            "profile": {"type": "string"},
            "frontend": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "cpp": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "primary": {"type": "string"},
                            "fallback": {"type": "string"},
                            "fallback_allowed": {"type": "boolean"},
                        },
                    }
                },
            },
            "rules": {"type": "object", "additionalProperties": True},
            "outputs": {"type": "object", "additionalProperties": False},
        },
    }
