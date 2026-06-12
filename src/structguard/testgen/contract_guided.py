from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from structguard.fuzz import FuzzCase, collect_fuzz_cases, fuzz_project, write_cpp_tests, write_fuzz_html, write_replay_script
from structguard.ir.contract_ir import build_contract_ir
from structguard.model import Diagnostic, ProjectReport
from structguard.sgdsl.diagnostics import SGDSLParseError
from structguard.sgdsl.parser import load_sgdsl
from structguard.testgen.model import ContractHint, TestgenCaseIR, TestgenManifest


def _normalize_name(name: str) -> str:
    return name.split(".")[-1].lower().replace("*", "").replace("?", "")


def load_contract_hints(contract_paths: Iterable[str | Path] | None) -> dict[str, ContractHint]:
    if not contract_paths:
        return {}
    modules = load_sgdsl([Path(raw_path) for raw_path in contract_paths])
    contract_ir = build_contract_ir(modules)
    hints: dict[str, ContractHint] = {}
    for structure in contract_ir.structures:
        methods = sorted({method.name.lower() for method in structure.methods})
        requires_count = sum(len(method.requires) for method in structure.methods)
        ensures_count = sum(len(method.ensures) for method in structure.methods)
        hint = ContractHint(
            structure=structure.qualified_name,
            methods=methods,
            requires_count=requires_count,
            ensures_count=ensures_count,
        )
        hints[_normalize_name(structure.name)] = hint
        hints[_normalize_name(structure.qualified_name)] = hint
    return hints


def _find_hint(case: FuzzCase, hints: dict[str, ContractHint]) -> ContractHint | None:
    if not hints:
        return None
    normalized = _normalize_name(case.structure)
    if normalized in hints:
        return hints[normalized]
    for name, hint in hints.items():
        if name and (name in normalized or normalized in name):
            return hint
    return None


def _utility_score(case: FuzzCase, hint: ContractHint | None) -> float:
    score = 0.20
    if case.failure:
        score += 0.35
    if case.minimized_operations:
        score += 0.10
    if hint:
        score += 0.10
        if hint.requires_count:
            score += 0.10
        if hint.ensures_count:
            score += 0.05
        if case.target_method and case.target_method.lower() in hint.methods:
            score += 0.10
    if len(case.operations) >= 5:
        score += 0.05
    return round(min(score, 1.0), 4)


def _classification(case: FuzzCase, hint: ContractHint | None) -> str:
    if case.failure and hint:
        return "contract-regression-candidate"
    if case.failure:
        return "model-regression-candidate"
    if hint:
        return "contract-smoke-candidate"
    return "smoke-candidate"


def build_testgen_manifest(
    root: Path,
    *,
    headers_only: bool = False,
    seeds: int = 30,
    steps: int = 60,
    structure_filter: str | None = None,
    contract_paths: Iterable[str | Path] | None = None,
) -> TestgenManifest:
    hints = load_contract_hints(contract_paths)
    raw_cases = collect_fuzz_cases(root, headers_only=headers_only, seeds=seeds, steps=steps, structure_filter=structure_filter)
    mode = "contract-guided" if hints else "model-based"
    cases: list[TestgenCaseIR] = []
    for raw_case in raw_cases:
        hint = _find_hint(raw_case, hints)
        cases.append(
            TestgenCaseIR(
                structure=raw_case.structure,
                seed=raw_case.seed,
                operations=raw_case.operations,
                failure=raw_case.failure,
                final_state=raw_case.final_state,
                target_method=raw_case.target_method,
                minimized_operations=raw_case.minimized_operations,
                generation_mode="contract-guided" if hint else mode,
                utility_score=_utility_score(raw_case, hint),
                contract_hint=hint,
                classification=_classification(raw_case, hint),
            )
        )
    return TestgenManifest(root=str(root), generation_mode=mode, cases=cases)


def testgen_project(
    root: Path,
    *,
    headers_only: bool = False,
    seeds: int = 30,
    steps: int = 60,
    structure_filter: str | None = None,
    contract_paths: Iterable[str | Path] | None = None,
) -> ProjectReport:
    try:
        manifest = build_testgen_manifest(
            root,
            headers_only=headers_only,
            seeds=seeds,
            steps=steps,
            structure_filter=structure_filter,
            contract_paths=contract_paths,
        )
    except SGDSLParseError as exc:
        return ProjectReport(
            root=str(root),
            diagnostics=[Diagnostic(level="FAILED", code="TESTGEN_CONTRACT_PARSE_ERROR", message=str(exc), file=getattr(exc, "source", None))],
        )

    legacy_report = fuzz_project(root, headers_only=headers_only, seeds=seeds, steps=steps, structure_filter=structure_filter)
    diagnostics: list[Diagnostic] = [
        Diagnostic(
            level="INFO",
            code="TESTGEN_SUMMARY",
            message=(
                f"StructGuard TestGen generó {manifest.summary()['case_count']} casos en modo {manifest.generation_mode}. "
                "Estos casos son candidatos abstractos, no fuzzing nativo."
            ),
            file=str(root),
            details=manifest.summary(),
        )
    ]
    for diagnostic in legacy_report.diagnostics:
        if diagnostic.code == "FUZZ_TESTGEN_SUMMARY":
            code = "TESTGEN_TARGET_SUMMARY"
        else:
            code = diagnostic.code.replace("FUZZ_", "TESTGEN_") if diagnostic.code.startswith("FUZZ_") else diagnostic.code
        message = (
            diagnostic.message.replace("Fuzzing", "TestGen")
            .replace("fuzzing", "generación abstracta")
            .replace("fuzz/testgen", "TestGen")
        )
        details = dict(diagnostic.details)
        details["evidence"] = "abstract_test_generation"
        details["native_fuzzing"] = False
        diagnostics.append(
            Diagnostic(
                level=diagnostic.level,
                code=code,
                message=message,
                file=diagnostic.file,
                line=diagnostic.line,
                symbol=diagnostic.symbol,
                details=details,
            )
        )
    return ProjectReport(root=str(root), diagnostics=diagnostics)


def write_testgen_json(manifest: TestgenManifest, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path

def _testgen_cases_as_fuzz_cases(cases: list[TestgenCaseIR]) -> list[FuzzCase]:
    # Adaptador interno: reutiliza el reporte HTML existente sin exponer vocabulario fuzz al usuario.
    return [
        FuzzCase(
            structure=case.structure,
            seed=case.seed,
            operations=case.operations,
            failure=case.failure,
            final_state=case.final_state,
            target_method=case.target_method,
            minimized_operations=case.minimized_operations,
        )
        for case in cases
    ]


def write_testgen_html(root: Path, manifest: TestgenManifest, path: Path) -> Path:
    return write_fuzz_html(root, _testgen_cases_as_fuzz_cases(manifest.cases), path)



def write_testgen_cpp_tests(
    root: Path,
    *,
    headers_only: bool,
    out_dir: Path,
    seeds: int,
    steps: int,
    structure_filter: str | None = None,
    include_smoke_tests: bool = False,
    manifest: TestgenManifest | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    legacy_manifest = write_cpp_tests(
        root,
        headers_only,
        out_dir,
        seeds=seeds,
        steps=steps,
        structure_filter=structure_filter,
        only_failures=not include_smoke_tests,
    )
    if manifest:
        write_testgen_json(manifest, out_dir / "structguard_testgen_manifest_v2.json")
    return legacy_manifest


def write_testgen_replay(root: Path, cases: list[TestgenCaseIR], path: Path) -> Path:
    raw_cases = [
        FuzzCase(
            structure=case.structure,
            seed=case.seed,
            operations=case.operations,
            failure=case.failure,
            final_state=case.final_state,
            target_method=case.target_method,
            minimized_operations=case.minimized_operations,
        )
        for case in cases
    ]
    return write_replay_script(root, raw_cases, path)


def manifest_cases_as_legacy_dicts(manifest: TestgenManifest) -> list[dict[str, object]]:
    return [asdict(case) for case in manifest.cases]
