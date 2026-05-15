from __future__ import annotations

from pathlib import Path
from typing import Any

from .clang_frontend import strict_ast_project
from .fuzz import fuzz_project
from .lint import lint_project
from .model import Diagnostic, ProjectReport
from .policy import CIPolicy, load_policy
from .security import security_project
from .verifier import verify_project


def _tag(report: ProjectReport, module: str) -> None:
    for d in report.diagnostics:
        d.details.setdefault("ci_module", module)


def _count(report: ProjectReport, level: str) -> int:
    return sum(1 for d in report.diagnostics if d.level == level)


def _security_warnings(report: ProjectReport) -> int:
    return sum(
        1
        for d in report.diagnostics
        if d.level == "WARNING"
        and (
            d.code.startswith("SEC_")
            or d.details.get("ci_module") == "security"
        )
    )


def _fuzz_failures(report: ProjectReport) -> int:
    return sum(
        1
        for d in report.diagnostics
        if d.level == "FAILED"
        and (
            d.code.startswith("FUZZ_")
            or d.details.get("ci_module") == "fuzz"
        )
    )


def evaluate_policy(
    report: ProjectReport,
    policy: CIPolicy,
    fail_on_warnings: bool | None = None,
    fail_on_unknown: bool | None = None,
) -> tuple[bool, dict[str, Any]]:
    failures = _count(report, "FAILED")
    warnings = _count(report, "WARNING")
    unknown = _count(report, "UNKNOWN")
    sec_warnings = _security_warnings(report)
    fuzz_failures = _fuzz_failures(report)

    fow = policy.fail_on_warnings if fail_on_warnings is None else fail_on_warnings
    fou = policy.fail_on_unknown if fail_on_unknown is None else fail_on_unknown

    reasons = []

    if policy.fail_on_failed_contract and failures > policy.max_failures:
        reasons.append(
            f"fallas {failures} > max_failures {policy.max_failures}"
        )

    if fow and warnings > 0:
        reasons.append(f"advertencias presentes: {warnings}")

    if fou and unknown > 0:
        reasons.append(f"diagnósticos UNKNOWN presentes: {unknown}")

    if policy.max_warnings is not None and warnings > policy.max_warnings:
        reasons.append(
            f"advertencias {warnings} > max_warnings {policy.max_warnings}"
        )

    if policy.max_unknown is not None and unknown > policy.max_unknown:
        reasons.append(
            f"UNKNOWN {unknown} > max_unknown {policy.max_unknown}"
        )

    if policy.fail_on_security_warnings and sec_warnings > 0:
        reasons.append(
            f"advertencias de seguridad presentes: {sec_warnings}"
        )

    if policy.fail_on_fuzz_failures and fuzz_failures > 0:
        reasons.append(
            f"fallas de fuzzing presentes: {fuzz_failures}"
        )

    details = {
        "failures": failures,
        "warnings": warnings,
        "unknown": unknown,
        "security_warnings": sec_warnings,
        "fuzz_failures": fuzz_failures,
        "policy": {
            "project": policy.project,
            "path": str(policy.path) if policy.path else None,
            "max_failures": policy.max_failures,
            "max_warnings": policy.max_warnings,
            "max_unknown": policy.max_unknown,
            "fail_on_warnings": fow,
            "fail_on_unknown": fou,
            "fail_on_security_warnings": policy.fail_on_security_warnings,
            "fail_on_fuzz_failures": policy.fail_on_fuzz_failures,
            "deep_security": policy.deep_security,
        },
        "reasons": reasons,
    }

    return not reasons, details


def ci_project(
    root: Path,
    headers_only: bool = False,
    max_cases: int = 300,
    fuzz_seeds: int = 10,
    fuzz_steps: int = 25,
    fail_on_warnings: bool = False,
    dsl_paths: list[str] | None = None,
    deep_security: bool = False,
    policy_path: str | Path | None = None,
    fail_on_unknown: bool | None = None,
    strict_ast: bool = False,
    clang: str | None = None,
    std: str = "c++17",
    max_files: int | None = 30,
    timeout: int = 12,
    ast_filter: str | None = None,
) -> ProjectReport:
    policy = load_policy(policy_path) if policy_path else CIPolicy()

    h = headers_only or policy.scan_headers_only
    mc = max_cases if max_cases != 300 else policy.max_cases
    fs = fuzz_seeds if fuzz_seeds != 10 else policy.fuzz_seeds
    fst = fuzz_steps if fuzz_steps != 25 else policy.fuzz_steps
    ds = deep_security or policy.deep_security
    dsl = list(dsl_paths or []) + list(policy.dsl_files or [])
    strict = strict_ast or policy.strict_ast

    reports = []
    mods = set(policy.required_modules or ["verify", "lint", "security", "fuzz"])

    if strict:
        r = strict_ast_project(
            root,
            headers_only=h,
            clang=clang or policy.clang,
            std=std or policy.clang_std,
            max_files=max_files if max_files != 30 else policy.clang_max_files,
            timeout=timeout if timeout != 12 else policy.clang_timeout,
            ast_filter=ast_filter,
        )
        _tag(r, "strict_ast")
        reports.append(r)

    if "verify" in mods:
        r = verify_project(
            root,
            headers_only=h,
            infer=True,
            max_cases=mc,
            dsl_paths=dsl or None,
        )
        _tag(r, "verify")
        reports.append(r)

    if "lint" in mods:
        r = lint_project(
            root,
            headers_only=h,
            dsl_paths=dsl or None,
        )
        _tag(r, "lint")
        reports.append(r)

    if "security" in mods:
        r = security_project(
            root,
            headers_only=h,
            deep=ds,
        )
        _tag(r, "security")
        reports.append(r)

    if "fuzz" in mods:
        r = fuzz_project(
            root,
            headers_only=h,
            seeds=fs,
            steps=fst,
        )
        _tag(r, "fuzz")
        reports.append(r)

    merged = ProjectReport(root=str(root), diagnostics=[])

    for r in reports:
        merged.diagnostics.extend(r.diagnostics)

    passed, details = evaluate_policy(
        merged,
        policy,
        fail_on_warnings=fail_on_warnings or policy.fail_on_warnings,
        fail_on_unknown=fail_on_unknown,
    )

    status = "aprobado" if passed else "fallido"

    merged.diagnostics.insert(
        0,
        Diagnostic(
            level="INFO" if passed else "FAILED",
            code="CI_GATE_PASSED" if passed else "CI_GATE_FAILED",
            message=(
                f"Gate CI de StructGuard {status}: "
                f"{details['failures']} fallas, "
                f"{details['warnings']} advertencias, "
                f"{details['unknown']} diagnósticos UNKNOWN."
            ),
            file=str(root),
            details=details,
        ),
    )

    return merged