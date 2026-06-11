from __future__ import annotations

import tempfile
from pathlib import Path

from structguard.binding import build_binding_ir, match_contracts_to_source
from structguard.analyzers.bounds import analyze_bounds_project
from structguard.analyzers.complexity_hints import analyze_complexity_hints_project
from structguard.analyzers.contracts import analyze_contract_rules_project
from structguard.analyzers.memory_safety import analyze_memory_safety_project
from structguard.analyzers.structure_semantics import analyze_structure_semantics_project
from structguard.frontend.cpp import build_cpp_source_ir
from structguard.ir.contract_ir import build_contract_ir
from structguard.ir.contract_validator import validate_contract_ir
from structguard.lint import lint_project
from structguard.model import Diagnostic, ProjectReport
from structguard.security import security_project
from structguard.sgdsl.diagnostics import SGDSLDiagnostic, SGDSLParseError
from structguard.sgdsl.parser import load_sgdsl
from structguard.verifier import verify_project

from .analysis_context import AnalysisContext
from .pass_manager import AnalysisPass, PassManager
from .result import AnalysisEngineResult, AnalysisPassResult


class LoadProfilePass:
    name = "LoadProfile"

    def run(self, context: AnalysisContext) -> AnalysisPassResult:
        diagnostics: list[Diagnostic] = []
        if context.profile:
            diagnostics.append(
                Diagnostic(
                    level="INFO",
                    code="ANALYSIS_PROFILE",
                    message=f"Perfil de análisis activo: {context.profile.name}",
                    file=str(context.root),
                    details={"profile": context.profile.__dict__},
                )
            )
        if context.domain_profile:
            diagnostics.append(
                Diagnostic(
                    level="INFO",
                    code="ENGINE_DOMAIN_PROFILE_LOADED",
                    message=f"Perfil de dominio activo: {context.domain_profile.name}",
                    file=str(context.root),
                    details=context.domain_profile.as_dict(),
                )
            )
            if context.metadata.get("profile_contract_mode") == "explicit":
                diagnostics.append(
                    Diagnostic(
                        level="INFO",
                        code="ENGINE_CONTRACT_SCOPE_EXPLICIT",
                        message="Alcance de contratos definido por --contract.",
                        file=str(context.root),
                        details={"contracts": list(context.dsl_paths)},
                    )
                )
        if not diagnostics:
            diagnostics.append(
                Diagnostic(
                    level="INFO",
                    code="ENGINE_PROFILE_DEFAULT",
                    message="Análisis sin perfil explícito de dominio.",
                    file=str(context.root),
                )
            )
        return AnalysisPassResult(self.name, "ok", diagnostics, {"preset": context.preset})


class BuildSourceIRPass:
    name = "BuildSourceIR"

    def run(self, context: AnalysisContext) -> AnalysisPassResult:
        if not context.capabilities.source_ir:
            return AnalysisPassResult(self.name, "skipped", [], {"reason": "El preset no solicita SourceIR."})
        if not context.wants_cpp_source_ir():
            return AnalysisPassResult(self.name, "skipped", [], {"reason": "No se solicitó frontend C++ canónico."})
        try:
            if context.frontend == "lightweight":
                from structguard.frontend.cpp.source_ir_builder import _lightweight_source_ir

                source_ir = _lightweight_source_ir(
                    context.root,
                    headers_only=context.headers_only,
                    reason="Frontend ligero solicitado explícitamente",
                )
            else:
                source_ir = build_cpp_source_ir(
                    context.root,
                    compile_commands=context.compile_commands,
                    clang=context.clang,
                    std=context.std,
                    timeout=context.timeout,
                    headers_only=context.headers_only,
                    fallback_allowed=context.fallback_allowed,
                )
        except Exception as exc:
            return AnalysisPassResult(
                self.name,
                "failed",
                [Diagnostic(level="FAILED", code="ENGINE_SOURCE_IR_ERROR", message=str(exc), file=str(context.root))],
            )
        context.source_ir = source_ir
        diagnostics = [
            Diagnostic(
                level="INFO",
                code="CPP_SOURCE_IR_SUMMARY",
                message=f"Frontend C++ activo: {source_ir.frontend}",
                file=str(context.root),
                details=source_ir.summary(),
            )
        ]
        for diagnostic in source_ir.diagnostics:
            location = diagnostic.location
            diagnostics.append(
                Diagnostic(
                    level=diagnostic.level,
                    code=diagnostic.code,
                    message=diagnostic.message,
                    file=location.file if location else None,
                    line=location.line if location and location.line else None,
                    details=diagnostic.details,
                )
            )
        return AnalysisPassResult(self.name, "ok", diagnostics, source_ir.summary())


class BuildContractIRPass:
    name = "BuildContractIR"

    def run(self, context: AnalysisContext) -> AnalysisPassResult:
        if not context.capabilities.contract_ir:
            return AnalysisPassResult(self.name, "skipped", [], {"reason": "El preset no solicita ContractIR."})
        if not context.dsl_paths:
            return AnalysisPassResult(self.name, "skipped", [], {"reason": "No hay contratos SGDSL declarados."})
        try:
            modules = load_sgdsl([Path(path) for path in context.dsl_paths])
        except SGDSLParseError as exc:
            diagnostic = SGDSLDiagnostic(level="FAILED", code="SGDSL_PARSE_ERROR", message=str(exc), source=exc.source, line=exc.line)
            return AnalysisPassResult(self.name, "failed", [_sgdsl_to_diagnostic(diagnostic)])
        contract_ir = build_contract_ir(modules)
        context.contract_ir = contract_ir
        diagnostics = [_sgdsl_to_diagnostic(diagnostic) for diagnostic in validate_contract_ir(contract_ir)]
        status = "failed" if any(diagnostic.level == "FAILED" for diagnostic in diagnostics) else "ok"
        details = {"structures": len(contract_ir.structures), "contracts": list(context.dsl_paths)}
        return AnalysisPassResult(self.name, status, diagnostics, details)


class BindContractsPass:
    name = "BindContracts"

    def run(self, context: AnalysisContext) -> AnalysisPassResult:
        if not context.capabilities.binding:
            return AnalysisPassResult(self.name, "skipped", [], {"reason": "El preset no solicita BindingIR."})
        if context.contract_ir is None:
            return AnalysisPassResult(self.name, "skipped", [], {"reason": "No hay ContractIR para vincular."})
        binding_ir = build_binding_ir(
            context.root,
            context.contract_ir,
            headers_only=context.headers_only,
            source_ir=context.source_ir,
        )
        context.binding_ir = binding_ir
        diagnostics = [_sgdsl_to_diagnostic(diagnostic) for diagnostic in match_contracts_to_source(binding_ir)]
        status = "failed" if any(diagnostic.level == "FAILED" for diagnostic in diagnostics) else "ok"
        return AnalysisPassResult(self.name, status, diagnostics, {"bindings": binding_ir.as_dict()})


class BoundedContractsPass:
    name = "RunBoundedContracts"

    def run(self, context: AnalysisContext) -> AnalysisPassResult:
        if not context.capabilities.bounded:
            return AnalysisPassResult(self.name, "skipped", [], {"reason": "El preset no solicita verificación acotada."})
        report = verify_project(
            context.root,
            headers_only=context.headers_only,
            infer=context.infer_contracts,
            max_cases=context.max_cases,
            dsl_paths=list(context.dsl_paths) or None,
            clang_structural=bool(context.profile and context.profile.strict_ast),
            clang=context.clang,
            std=context.std,
            max_files=context.max_files,
            timeout=context.timeout,
        )
        return _report_to_pass_result(self.name, report)


class LintContractsPass:
    name = "RunLint"

    def run(self, context: AnalysisContext) -> AnalysisPassResult:
        if not context.capabilities.lint:
            return AnalysisPassResult(self.name, "skipped", [], {"reason": "El preset no solicita lint."})
        report = lint_project(context.root, headers_only=context.headers_only, dsl_paths=list(context.dsl_paths) or None)
        return _report_to_pass_result(self.name, report)


class SecurityPass:
    name = "RunSecurity"

    def run(self, context: AnalysisContext) -> AnalysisPassResult:
        if not context.capabilities.security:
            return AnalysisPassResult(self.name, "skipped", [], {"reason": "El preset no solicita seguridad."})
        deep = bool(context.profile and context.profile.deep_security) or context.preset in {"ci", "full", "security"}
        report = security_project(context.root, headers_only=context.headers_only, deep=deep)
        return _report_to_pass_result(self.name, report)


class StructuralRulesPass:
    name = "RunStructuralRules"

    def run(self, context: AnalysisContext) -> AnalysisPassResult:
        if not context.capabilities.structural_rules:
            return AnalysisPassResult(self.name, "skipped", [], {"reason": "El preset no solicita reglas estructurales."})
        diagnostics: list[Diagnostic] = []
        for report in (
            analyze_contract_rules_project(context.root, headers_only=context.headers_only),
            analyze_bounds_project(context.root, headers_only=context.headers_only),
            analyze_structure_semantics_project(context.root, headers_only=context.headers_only),
        ):
            diagnostics.extend(report.diagnostics)
        status = "failed" if any(diagnostic.level == "FAILED" for diagnostic in diagnostics) else "ok"
        return AnalysisPassResult(self.name, status, diagnostics, {"counts": _counts(diagnostics)})


class ComplexityHintsPass:
    name = "RunComplexityHints"

    def run(self, context: AnalysisContext) -> AnalysisPassResult:
        if not context.capabilities.complexity_hints:
            return AnalysisPassResult(self.name, "skipped", [], {"reason": "El preset no solicita pistas de complejidad."})
        report = analyze_complexity_hints_project(context.root, headers_only=context.headers_only)
        return _report_to_pass_result(self.name, report)


class MemorySafetyPass:
    name = "RunMemorySafety"

    def run(self, context: AnalysisContext) -> AnalysisPassResult:
        if not context.capabilities.memory_safety:
            return AnalysisPassResult(self.name, "skipped", [], {"reason": "El preset no solicita modelo de memoria."})
        report = analyze_memory_safety_project(context.root, headers_only=context.headers_only)
        return _report_to_pass_result(self.name, report)


class FormalPass:
    name = "RunFormal"

    def run(self, context: AnalysisContext) -> AnalysisPassResult:
        if not context.capabilities.formal:
            return AnalysisPassResult(self.name, "skipped", [], {"reason": "El preset no solicita formalización."})
        from structguard.formal import write_formal_artifacts

        with tempfile.TemporaryDirectory(prefix="structguard-engine-formal-") as tmp:
            _, report = write_formal_artifacts(
                context.root,
                Path(tmp),
                backend="smt",
                headers_only=context.headers_only,
                infer=context.infer_contracts,
                dsl_paths=list(context.dsl_paths) or None,
                run_solver=bool(context.profile and context.profile.run_solver),
            )
        return _report_to_pass_result(self.name, report)


class AnalysisEngine:
    def plan(self, preset: str) -> list[str]:
        return [analysis_pass.name for analysis_pass in self._passes_for_preset(preset)]

    def run(self, context: AnalysisContext) -> AnalysisEngineResult:
        context.capabilities = context.capabilities
        header = AnalysisPassResult(
            "AnalysisEngine",
            "ok",
            [
                Diagnostic(
                    level="INFO",
                    code="ENGINE_PRESET",
                    message=f"Preset de análisis activo: {context.preset}",
                    file=str(context.root),
                    details=context.capabilities.as_dict(),
                )
            ],
        )
        pass_results = [header, *PassManager(self._passes_for_preset(context.preset)).run(context)]
        report = ProjectReport(root=str(context.root), diagnostics=[])
        for result in pass_results:
            report.diagnostics.extend(result.diagnostics)
        return AnalysisEngineResult(context=context, pass_results=pass_results, report=report)

    def _passes_for_preset(self, preset: str) -> list[AnalysisPass]:
        common: list[AnalysisPass] = [LoadProfilePass(), BuildSourceIRPass()]
        if preset == "source":
            return common
        if preset == "security":
            return [*common, SecurityPass(), MemorySafetyPass(), StructuralRulesPass(), ComplexityHintsPass()]
        if preset == "ci":
            return [*common, BuildContractIRPass(), BindContractsPass(), BoundedContractsPass(), LintContractsPass(), SecurityPass(), MemorySafetyPass(), StructuralRulesPass(), ComplexityHintsPass()]
        if preset == "full":
            return [*common, BuildContractIRPass(), BindContractsPass(), BoundedContractsPass(), LintContractsPass(), SecurityPass(), MemorySafetyPass(), StructuralRulesPass(), ComplexityHintsPass(), FormalPass()]
        return [*common, BuildContractIRPass(), BindContractsPass(), BoundedContractsPass(), LintContractsPass(), StructuralRulesPass()]


def _sgdsl_to_diagnostic(diagnostic: SGDSLDiagnostic) -> Diagnostic:
    return Diagnostic(
        level=diagnostic.level,
        code=diagnostic.code,
        message=diagnostic.message,
        file=str(diagnostic.source) if diagnostic.source else None,
        line=diagnostic.line,
    )


def _report_to_pass_result(name: str, report: ProjectReport) -> AnalysisPassResult:
    status = "failed" if any(diagnostic.level == "FAILED" for diagnostic in report.diagnostics) else "ok"
    return AnalysisPassResult(name, status, list(report.diagnostics), {"counts": report.counts()})


def _counts(diagnostics: list[Diagnostic]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for diagnostic in diagnostics:
        counts[diagnostic.level] = counts.get(diagnostic.level, 0) + 1
    return counts
