from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import __version__
from .bench import bench_project, collect_bench_metrics, write_bench_harness, write_bench_json
from .ci import ci_project
from .fuzz import fuzz_project, collect_fuzz_cases, write_fuzz_json, write_replay_script, write_cpp_tests, write_seed_corpus, write_fuzz_html
from .lint import lint_project
from .report import write_html, write_json
from .security import security_project, write_security_json, write_security_rules_json
from .trace import abstract_trace, trace_project, write_trace_json
from .verifier import verify_project
from .suggest import collect_suggestions, suggestions_report, write_annotated_copy, write_patch, write_suggestions_json
from .model import Diagnostic, ProjectReport
from .dsl import dsl_report, write_dsl_json
from .frontend import frontend_project, summarize_frontend, write_frontend_json
from .clang_frontend import clang_frontend_project, clang_summaries, strict_ast_project, write_clang_json
from .formal import write_formal_artifacts
from .pipeline import build_pipeline_units, pipeline_report, write_pipeline_artifacts, write_pipeline_json
from .rust_frontend import rust_frontend_project, write_rust_json
from .python_frontend import python_frontend_project, write_python_json
from .assist import assist_project, write_assist_json
from .advanced import advanced_report, write_advanced_dsl, write_advanced_json
from .docs import build_documentation_model, docs_report, write_docs_html, write_docs_json, write_docs_markdown
from .performance import build_performance_profiles, performance_report, write_performance_json, write_performance_html, write_performance_markdown, write_perf_harness, write_growth_json
from .ci_outputs import write_junit, write_sarif, write_summary_markdown, print_github_annotations
from .policy import default_policy_text, github_actions_workflow_text
from .policy.validator import validate_policy_file
from .profiles import PROFILES, ProfileLoadError, default_profiles_root, load_profile_file, load_profiles, apply_profile_defaults
from .metadata import enriched_details
from .doctor import collect_doctor_checks, write_doctor_json
from .sgdsl.diagnostics import SGDSLDiagnostic, SGDSLParseError
from .sgdsl.parser import load_sgdsl
from .ir.contract_ir import ContractIR, build_contract_ir
from .ir.contract_validator import validate_contract_ir
from .binding import build_binding_ir, match_contracts_to_source
from .frontend.cpp import build_cpp_source_ir
from .ir.source_ir import SourceDiagnostic, SourceIR
from .core import AnalysisContext, AnalysisEngine, available_presets
from .reporters import write_html_report, write_json_report, write_junit_report, write_markdown_report, write_sarif_report
from .findings.guarantee import diagnostic_display_level, guarantee_counts_from_diagnostics, guarantee_summary_lines, infer_guarantee
from .reporters.guarantee_badge import guarantee_badge_text
from .reporting import derive_reports_from_canonical, load_canonical_report, write_canonical_report, write_lockfile
from .cache import run_cached_scan


def print_report(report: ProjectReport, verbose: bool = False) -> int:
    counts = report.counts()
    guarantee_counts = guarantee_counts_from_diagnostics(report.diagnostics)
    print(f"StructGuard {__version__}")
    print(f"Raíz: {report.root}")
    print("Resumen: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print("Resumen por garantía:")
    for line in guarantee_summary_lines(guarantee_counts):
        print(f"  {line}")
    if counts.get("BOUNDED_VERIFIED") or counts.get("PROVED"):
        print("Nota: BOUNDED_CHECK_PASSED indica evidencia acotada; FORMALLY_VERIFIED solo aplica a backends formales soportados.")
    print()
    for d in report.diagnostics:
        loc = f"{d.file}:{d.line}" if d.file and d.line else (d.file or "")
        guarantee = infer_guarantee(d)
        display_level = diagnostic_display_level(d)
        badge = guarantee_badge_text(guarantee)
        print(f"[{display_level}] {badge} {d.code} {d.symbol or ''}")
        if loc:
            print(f"  en {loc}")
        print(f"  {d.message}")
        print(f"  garantía={guarantee.level.value} {guarantee.label}")
        meta = enriched_details(d)
        if d.level in {"FAILED", "WARNING", "UNKNOWN", "PROVED", "BOUNDED_VERIFIED"}:
            print(f"  confianza={meta.get('confidence')} evidencia={meta.get('evidence')}")
            if meta.get("remediation") and d.level in {"FAILED", "WARNING", "UNKNOWN"}:
                print(f"  remediación: {meta.get('remediation')}")
        cex = meta.get("counterexample")
        if cex and d.level == "FAILED":
            print("  contraejemplo:")
            for line in str(cex.get("explanation", "")).splitlines():
                print(f"    {line}")
        if verbose and d.details:
            print(f"  detalles: {d.details}")
        print()
    return 1 if any(d.level == "FAILED" for d in report.diagnostics) else 0



def _strict_ast_report(root: Path, args: argparse.Namespace) -> ProjectReport | None:
    if not getattr(args, "strict_ast", False):
        return None
    return strict_ast_project(
        root,
        headers_only=getattr(args, "headers_only", False),
        clang=getattr(args, "clang", None),
        std=getattr(args, "std", "c++17"),
        max_files=getattr(args, "max_files", 30),
        timeout=getattr(args, "timeout", 12),
        ast_filter=None,
    )


def _merge_reports(root: Path, *reports: ProjectReport | None) -> ProjectReport:
    merged = ProjectReport(root=str(root), diagnostics=[])
    for report in reports:
        if report:
            merged.diagnostics.extend(report.diagnostics)
    return merged


def _context_from_args(args: argparse.Namespace) -> dict[str, object]:
    return {
        "command": getattr(args, "cmd", None),
        "profile": getattr(args, "profile", None),
        "preset": getattr(args, "preset", None),
        "language": getattr(args, "language", None),
        "compile_commands": getattr(args, "compile_commands", None),
        "frontend": getattr(args, "frontend", None),
        "contract_paths": getattr(args, "contract_paths", None),
        "headers_only": getattr(args, "headers_only", None),
        "strict_ast": getattr(args, "strict_ast", None),
    }


def _root_from_args(args: argparse.Namespace, report: ProjectReport) -> Path:
    raw = getattr(args, "path", None) or report.root or "."
    return Path(str(raw))


def _write_outputs(report: ProjectReport, args: argparse.Namespace, title: str) -> None:
    context = _context_from_args(args)
    if getattr(args, "json", None):
        write_json(report, Path(args.json))
    if getattr(args, "html", None):
        write_html(report, Path(args.html), title=title)
    if getattr(args, "findings_json", None):
        write_json_report(report, Path(args.findings_json))
    if getattr(args, "findings_html", None):
        write_html_report(report, Path(args.findings_html), title=title)
    if getattr(args, "findings_md", None):
        write_markdown_report(report, Path(args.findings_md), title=title)
    if getattr(args, "findings_junit", None):
        write_junit_report(report, Path(args.findings_junit))
    if getattr(args, "findings_sarif", None):
        write_sarif_report(report, Path(args.findings_sarif))
    if getattr(args, "report_json", None):
        write_canonical_report(report, Path(args.report_json), context=context)
    if getattr(args, "lockfile", None):
        root = _root_from_args(args, report)
        write_lockfile(root, Path(args.lockfile), context=context)





def _source_diagnostic_to_project(diagnostic: SourceDiagnostic) -> Diagnostic:
    location = diagnostic.location
    return Diagnostic(
        level=diagnostic.level,
        code=diagnostic.code,
        message=diagnostic.message,
        file=location.file if location else None,
        line=location.line if location and location.line else None,
        details=diagnostic.details,
    )


def _write_source_ir_if_requested(source_ir: SourceIR, args: argparse.Namespace) -> None:
    out_path = getattr(args, "source_ir_json", None)
    if not out_path:
        return
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(source_ir.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"SourceIR escrito en: {out}")


def _build_cpp_source_ir_if_requested(root: Path, args: argparse.Namespace) -> SourceIR | None:
    language = getattr(args, "language", None)
    compile_commands = getattr(args, "compile_commands", None)
    frontend = getattr(args, "frontend", "auto")
    if language != "cpp" and not compile_commands and frontend == "auto":
        return None
    if language not in {None, "cpp"}:
        return None
    if frontend == "lightweight":
        from .frontend.cpp.source_ir_builder import _lightweight_source_ir

        source_ir = _lightweight_source_ir(root, headers_only=getattr(args, "headers_only", False), reason="Frontend ligero solicitado explícitamente")
    else:
        source_ir = build_cpp_source_ir(
            root,
            compile_commands=Path(compile_commands) if compile_commands else None,
            clang=getattr(args, "clang", None),
            std=getattr(args, "std", "c++17"),
            timeout=getattr(args, "timeout", 12),
            headers_only=getattr(args, "headers_only", False),
            fallback_allowed=getattr(args, "fallback_allowed", False),
        )
    _write_source_ir_if_requested(source_ir, args)
    return source_ir

def cmd_doctor(args: argparse.Namespace) -> int:
    root = Path(getattr(args, "path", "."))
    checks = collect_doctor_checks(root)
    print(f"StructGuard {__version__} doctor")
    print(f"Raíz: {root}")
    worst = 0
    for c in checks:
        marker = "OK" if c.status == "ok" else ("WARN" if c.status == "warning" else "MISSING")
        print(f"[{marker}] {c.name}: {c.message}")
        if c.status == "missing" or (getattr(args, "strict", False) and c.status != "ok"):
            worst = 1
    if getattr(args, "json", None):
        write_doctor_json(root, Path(args.json))
        print(f"JSON de doctor escrito en: {args.json}")
    return worst




def cmd_policy(args: argparse.Namespace) -> int:
    result = validate_policy_file(Path(args.policy_path))
    if getattr(args, "json", False):
        print(json.dumps(result.as_dict(), indent=2, ensure_ascii=False))
        return 0 if result.valid else 1
    if result.valid:
        print(f"Política válida: {result.path}")
        return 0
    print(f"Política inválida: {result.path}")
    for issue in result.issues:
        print(f"[{issue.level}] {issue.code} {issue.path}")
        print(f"  {issue.message}")
    return 1

def cmd_profiles(args: argparse.Namespace) -> int:
    root = Path(getattr(args, "profiles_root", "profiles"))
    if getattr(args, "profiles_action", "list") == "list":
        profiles = load_profiles(root)
        if not profiles:
            print(f"No se encontraron perfiles en: {root}")
            return 1
        print("Perfiles de dominio disponibles:")
        for name in sorted(profiles):
            profile = profiles[name]
            print(f"- {profile.name}: {profile.display_name} [{profile.language}, {profile.status}]")
            print(f"  ruta: {profile.path}")
            print(f"  contratos: {len(profile.contracts)}")
        print()
        print("Perfiles de ejecución compatibles:")
        for name in sorted(k for k in PROFILES if k not in profiles):
            print(f"- {name}")
        return 0

    profile_path = Path(args.profile_path)
    try:
        profile = load_profile_file(profile_path)
    except ProfileLoadError as exc:
        print(f"Perfil inválido: {profile_path}")
        for line in str(exc).splitlines():
            print(f"- {line}")
        return 1
    print(f"Perfil válido: {profile.name}")
    print(f"Nombre visible: {profile.display_name}")
    print(f"Lenguaje: {profile.language}")
    print(f"Estado: {profile.status}")
    print("Contratos:")
    for contract in profile.contract_paths():
        print(f"- {contract}")
    return 0

def _load_contract_ir(paths: list[str]) -> tuple[ContractIR | None, list[SGDSLDiagnostic]]:
    try:
        modules = load_sgdsl([Path(path) for path in paths])
    except SGDSLParseError as exc:
        diagnostic = SGDSLDiagnostic(level="FAILED", code="SGDSL_PARSE_ERROR", message=str(exc), source=exc.source, line=exc.line)
        return None, [diagnostic]
    ir = build_contract_ir(modules)
    return ir, validate_contract_ir(ir)


def cmd_contract(args: argparse.Namespace) -> int:
    paths = list(getattr(args, "contract_paths", []))
    ir, diagnostics = _load_contract_ir(paths)
    if ir is None:
        for diagnostic in diagnostics:
            print(f"Contrato inválido: {diagnostic}")
        return 1

    if getattr(args, "contract_action", "check") == "bind":
        root = Path(args.path)
        source_ir = _build_cpp_source_ir_if_requested(root, args)
        binding_ir = build_binding_ir(root, ir, headers_only=getattr(args, "headers_only", False), source_ir=source_ir)
        binding_diagnostics = match_contracts_to_source(binding_ir)
        failed = [diagnostic for diagnostic in binding_diagnostics if getattr(diagnostic, "level", "") == "FAILED"]
        if getattr(args, "output", None):
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(binding_ir.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"BindingIR escrito en: {out}")
        if getattr(args, "json", False):
            print(json.dumps({"binding": binding_ir.as_dict(), "diagnostics": [diagnostic.as_dict() for diagnostic in binding_diagnostics]}, indent=2, ensure_ascii=False))
        else:
            print("Validación de binding contrato-código")
            print(f"Fuente: {args.path}")
            print("Contratos:")
            for path in paths:
                print(f"- {path}")
            print(f"Resultado: {'FALLÓ' if failed else 'OK'}")
            for diagnostic in binding_diagnostics:
                loc = ""
                if getattr(diagnostic, "source", None):
                    loc = str(diagnostic.source)
                    if getattr(diagnostic, "line", None):
                        loc = f"{loc}:{diagnostic.line}"
                prefix = f"[{diagnostic.level}] {diagnostic.code}"
                if loc:
                    prefix = f"{prefix} {loc}"
                print(prefix)
                print(f"  {diagnostic.message}")
        return 1 if failed else 0

    if getattr(args, "contract_action", "check") == "dump-ir":
        payload = json.dumps(ir.as_dict(), indent=2, ensure_ascii=False)
        if getattr(args, "output", None):
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(payload + "\n", encoding="utf-8")
            print(f"ContractIR escrito en: {out}")
        elif getattr(args, "json", False):
            print(payload)
        else:
            print("ContractIR:")
            for structure in ir.structures:
                print(f"- {structure.qualified_name}: {len(structure.fields)} campos, {len(structure.methods)} métodos")
        return 0

    failed = [diagnostic for diagnostic in diagnostics if getattr(diagnostic, "level", "") == "FAILED"]
    warning = [diagnostic for diagnostic in diagnostics if getattr(diagnostic, "level", "") == "WARNING"]
    print("Validación de contratos SGDSL")
    print("Fuentes:")
    for path in paths:
        print(f"- {path}")
    print(f"Resultado: {'FALLÓ' if failed else 'OK'}")
    print(f"Errores: {len(failed)}")
    print(f"Advertencias: {len(warning)}")
    for diagnostic in diagnostics:
        loc = ""
        if getattr(diagnostic, "source", None):
            loc = str(diagnostic.source)
            if getattr(diagnostic, "line", None):
                loc = f"{loc}:{diagnostic.line}"
        prefix = f"[{diagnostic.level}] {diagnostic.code}"
        if loc:
            prefix = f"{prefix} {loc}"
        print(prefix)
        print(f"  {diagnostic.message}")
    return 1 if failed else 0


def cmd_verify(args: argparse.Namespace) -> int:
    profile = apply_profile_defaults(args)
    root = Path(args.path)
    strict = _strict_ast_report(root, args)
    verify = verify_project(root, headers_only=args.headers_only, infer=not args.no_infer, max_cases=args.max_cases, dsl_paths=getattr(args, "dsl", None), clang_structural=bool(profile and profile.strict_ast), clang=getattr(args, "clang", None), std=getattr(args, "std", "c++17"), max_files=getattr(args, "max_files", 30), timeout=getattr(args, "timeout", 12))
    report = _merge_reports(root, strict, verify)
    _write_outputs(report, args, "Reporte de análisis acotado de contratos StructGuard")
    return print_report(report, verbose=args.verbose)


def cmd_lint(args: argparse.Namespace) -> int:
    root = Path(args.path)
    report = lint_project(root, headers_only=args.headers_only, dsl_paths=getattr(args, "dsl", None))
    _write_outputs(report, args, "Reporte de lint StructGuard")
    return print_report(report, verbose=args.verbose)


def cmd_analyze(args: argparse.Namespace) -> int:
    profile = apply_profile_defaults(args)
    root = Path(args.path)
    source_ir = _build_cpp_source_ir_if_requested(root, args)
    source_report = None
    if source_ir is not None:
        source_report = ProjectReport(root=str(root), diagnostics=[
            Diagnostic(
                level="INFO",
                code="CPP_SOURCE_IR_SUMMARY",
                message=f"Frontend C++ activo: {source_ir.frontend}",
                file=str(root),
                details=source_ir.summary(),
            ),
            *[_source_diagnostic_to_project(diagnostic) for diagnostic in source_ir.diagnostics],
        ])
    strict = _strict_ast_report(root, args)
    verify = verify_project(root, headers_only=args.headers_only, infer=not args.no_infer, max_cases=args.max_cases, dsl_paths=getattr(args, "dsl", None), clang_structural=bool(profile and profile.strict_ast), clang=getattr(args, "clang", None), std=getattr(args, "std", "c++17"), max_files=getattr(args, "max_files", 30), timeout=getattr(args, "timeout", 12))
    lint = lint_project(root, headers_only=args.headers_only, dsl_paths=getattr(args, "dsl", None))
    extra_reports = []
    if profile and profile.include_security:
        extra_reports.append(security_project(root, headers_only=args.headers_only, deep=profile.deep_security))
    if profile and profile.include_formal:
        from tempfile import TemporaryDirectory
        with TemporaryDirectory(prefix="structguard-formal-") as tmp:
            _, formal_report = write_formal_artifacts(root, Path(tmp), backend="smt", headers_only=args.headers_only, infer=not args.no_infer, dsl_paths=getattr(args, "dsl", None), run_solver=profile.run_solver)
            extra_reports.append(formal_report)
    merged = _merge_reports(root, source_report, strict, verify, lint, *extra_reports)
    if profile:
        merged.diagnostics.insert(0, ProjectReport(root=str(root), diagnostics=[]).diagnostics[0] if False else Diagnostic(level="INFO", code="ANALYSIS_PROFILE", message=f"Perfil de análisis activo: {profile.name}", file=str(root), details={"profile": profile.__dict__}))
    _write_outputs(merged, args, "Reporte de análisis StructGuard")
    return print_report(merged, verbose=args.verbose)


def _default_scan_preset(args: argparse.Namespace) -> str:
    if getattr(args, "preset", None):
        return str(args.preset)
    return "source"


def cmd_scan(args: argparse.Namespace) -> int:
    profile = apply_profile_defaults(args)
    preset = _default_scan_preset(args)
    context = AnalysisContext.from_namespace(args, profile, preset)
    if getattr(args, "cache", False):
        cached = run_cached_scan(
            context,
            cache_dir=Path(getattr(args, "cache_dir", ".structguard/cache")),
            clear=bool(getattr(args, "cache_clear", False)),
        )
        result = cached.engine_result
        print(f"Cache incremental: {cached.hits} reutilizados, {cached.misses} recalculados, {cached.files} archivos")
    else:
        result = AnalysisEngine().run(context)
    if result.context.source_ir is not None:
        _write_source_ir_if_requested(result.context.source_ir, args)
    _write_outputs(result.report, args, "Reporte de scan StructGuard")
    return print_report(result.report, verbose=args.verbose)


def cmd_suggest(args: argparse.Namespace) -> int:
    root = Path(args.path)
    suggestions = collect_suggestions(root, headers_only=args.headers_only, infer=not args.no_infer)
    report = suggestions_report(root, headers_only=args.headers_only, infer=not args.no_infer)
    _write_outputs(report, args, "Sugerencias de contratos StructGuard")
    if args.suggestions_json:
        write_suggestions_json(root, suggestions, Path(args.suggestions_json))
    if args.patch:
        write_patch(root, suggestions, Path(args.patch))
        print(f"Parche escrito en: {args.patch}")
    if args.apply_to:
        write_annotated_copy(root, suggestions, Path(args.apply_to))
        print(f"Copia anotada escrita en: {args.apply_to}")
    return print_report(report, verbose=args.verbose)


def cmd_bench(args: argparse.Namespace) -> int:
    root = Path(args.path)
    report = bench_project(root, headers_only=args.headers_only)
    _write_outputs(report, args, "Perfil de benchmark StructGuard")
    metrics = collect_bench_metrics(root, headers_only=args.headers_only)
    if args.metrics_json:
        write_bench_json(metrics, Path(args.metrics_json))
        print(f"Métricas de benchmark escritas en: {args.metrics_json}")
    if args.harness:
        write_bench_harness(metrics, Path(args.harness))
        print(f"Harness de benchmark escrito en: {args.harness}")
    return print_report(report, verbose=args.verbose)


def cmd_trace(args: argparse.Namespace) -> int:
    root = Path(args.path)
    report = trace_project(root, headers_only=args.headers_only, ops=args.ops, structure=args.structure)
    _write_outputs(report, args, "Reporte de trazas StructGuard")
    if args.trace_json:
        write_trace_json(abstract_trace(args.ops, args.structure), Path(args.trace_json))
        print(f"Eventos de traza escritos en: {args.trace_json}")
    return print_report(report, verbose=args.verbose)


def cmd_fuzz(args: argparse.Namespace) -> int:
    print("[DEPRECATED] El comando fuzz genera secuencias abstractas y será reemplazado por testgen. No ejecuta binarios ni realiza fuzzing nativo.")
    root = Path(args.path)
    report = fuzz_project(root, headers_only=args.headers_only, seeds=args.seeds, steps=args.steps, structure_filter=args.structure)
    _write_outputs(report, args, "StructGuard Fuzz/TestGen heurístico")
    cases = collect_fuzz_cases(root, headers_only=args.headers_only, seeds=args.seeds, steps=args.steps, structure_filter=args.structure)
    if args.fuzz_json:
        write_fuzz_json(root, cases, Path(args.fuzz_json)); print(f"JSON de casos fuzz escrito en: {args.fuzz_json}")
    if args.fuzz_html:
        write_fuzz_html(root, cases, Path(args.fuzz_html)); print(f"HTML de Fuzz/TestGen escrito en: {args.fuzz_html}")
    if args.replay:
        write_replay_script(root, cases, Path(args.replay)); print(f"Script de reproducción escrito en: {args.replay}")
    if args.seed_corpus:
        manifest = write_seed_corpus(root, cases, Path(args.seed_corpus)); print(f"Corpus de semillas escrito en: {manifest}")
    if args.emit_tests or args.test_dir:
        manifest = write_cpp_tests(root, args.headers_only, Path(args.test_dir or "generated_tests"), seeds=args.seeds, steps=args.steps, structure_filter=args.structure, only_failures=not args.include_smoke_tests)
        print(f"Candidatos de pruebas C++ generados en: {manifest}")
    return print_report(report, verbose=args.verbose)

def cmd_testgen(args: argparse.Namespace) -> int:
    root = Path(args.path)
    cases = collect_fuzz_cases(root, headers_only=args.headers_only, seeds=args.seeds, steps=args.steps, structure_filter=args.structure)
    report = fuzz_project(root, headers_only=args.headers_only, seeds=args.seeds, steps=args.steps, structure_filter=args.structure)
    _write_outputs(report, args, "StructGuard TestGen heurístico")
    manifest = write_cpp_tests(root, args.headers_only, Path(args.test_dir), seeds=args.seeds, steps=args.steps, structure_filter=args.structure, only_failures=not args.include_smoke_tests)
    print(f"Candidatos de pruebas C++ generados en: {manifest}")
    if args.fuzz_json:
        write_fuzz_json(root, cases, Path(args.fuzz_json)); print(f"JSON de casos fuzz escrito en: {args.fuzz_json}")
    if args.replay:
        write_replay_script(root, cases, Path(args.replay)); print(f"Script de reproducción escrito en: {args.replay}")
    return print_report(report, verbose=args.verbose)


def cmd_security(args: argparse.Namespace) -> int:
    root = Path(args.path)
    report = security_project(root, headers_only=args.headers_only, deep=args.deep)
    _write_outputs(report, args, "StructGuard Deep Security heurístico" if args.deep else "Reporte de seguridad StructGuard")
    if args.security_json:
        write_security_json(report, Path(args.security_json))
        print(f"JSON de seguridad escrito en: {args.security_json}")
    if args.rules_json:
        write_security_rules_json(Path(args.rules_json))
        print(f"JSON de reglas de seguridad escrito en: {args.rules_json}")
    return print_report(report, verbose=args.verbose)


def cmd_ci(args: argparse.Namespace) -> int:
    apply_profile_defaults(args)
    root = Path(args.path)
    try:
        report = ci_project(root, headers_only=args.headers_only, max_cases=args.max_cases, fuzz_seeds=args.seeds, fuzz_steps=args.steps, fail_on_warnings=args.fail_on_warnings, dsl_paths=getattr(args, "dsl", None), deep_security=getattr(args, "deep_security", False), policy_path=getattr(args, "policy", None), fail_on_unknown=getattr(args, "fail_on_unknown", None), strict_ast=getattr(args, "strict_ast", False), clang=getattr(args, "clang", None), std=getattr(args, "std", "c++17"), max_files=getattr(args, "max_files", 30), timeout=getattr(args, "timeout", 12), ast_filter=None)
    except ValueError as exc:
        print(str(exc))
        return 1
    _write_outputs(report, args, "Gate de política CI/CD de StructGuard")
    if args.junit:
        write_junit(report, Path(args.junit)); print(f"XML JUnit escrito en: {args.junit}")
    if args.sarif:
        write_sarif(report, Path(args.sarif)); print(f"SARIF escrito en: {args.sarif}")
    if args.summary_md:
        write_summary_markdown(report, Path(args.summary_md)); print(f"Resumen Markdown escrito en: {args.summary_md}")
    if args.github_annotations:
        print_github_annotations(report)
    code = print_report(report, verbose=args.verbose)
    return 1 if any(d.code == "CI_GATE_FAILED" for d in report.diagnostics) else code


def cmd_ci_init(args: argparse.Namespace) -> int:
    out = Path(args.path); out.mkdir(parents=True, exist_ok=True)
    policy_path = out / args.policy_name
    workflow_path = out / ".github" / "workflows" / args.workflow_name
    if policy_path.exists() and not args.force:
        print(f"La política ya existe: {policy_path} (usa --force para sobrescribir)")
    else:
        policy_path.write_text(default_policy_text(args.project_path), encoding="utf-8"); print(f"Política escrita en: {policy_path}")
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    if workflow_path.exists() and not args.force:
        print(f"El workflow ya existe: {workflow_path} (usa --force para sobrescribir)")
    else:
        workflow_path.write_text(github_actions_workflow_text(args.project_path, args.policy_name), encoding="utf-8"); print(f"Workflow de GitHub Actions escrito en: {workflow_path}")
    return 0



def cmd_dsl(args: argparse.Namespace) -> int:
    report = dsl_report(args.dsl_files)
    _write_outputs(report, args, "Reporte DSL de StructGuard")
    if args.dsl_json:
        write_dsl_json(args.dsl_files, Path(args.dsl_json))
        print(f"JSON DSL escrito en: {args.dsl_json}")
    return print_report(report, verbose=args.verbose)


def cmd_frontend(args: argparse.Namespace) -> int:
    root = Path(args.path)
    report = frontend_project(root, headers_only=args.headers_only)
    _write_outputs(report, args, "Reporte del frontend C++ de StructGuard")
    if args.frontend_json:
        write_frontend_json(summarize_frontend(root, headers_only=args.headers_only), Path(args.frontend_json))
        print(f"JSON del frontend escrito en: {args.frontend_json}")
    return print_report(report, verbose=args.verbose)


def cmd_clang(args: argparse.Namespace) -> int:
    root = Path(args.path)
    report = clang_frontend_project(root, headers_only=args.headers_only, clang=args.clang, std=args.std, max_files=args.max_files, timeout=args.timeout, ast_filter=None if args.no_ast_filter else "auto")
    _write_outputs(report, args, "Reporte del frontend AST Clang de StructGuard")
    if args.clang_json:
        write_clang_json(clang_summaries(root, headers_only=args.headers_only, clang=args.clang, std=args.std, max_files=args.max_files, timeout=args.timeout, ast_filter=None if args.no_ast_filter else "auto"), Path(args.clang_json))
        print(f"JSON del frontend Clang escrito en: {args.clang_json}")
    return print_report(report, verbose=args.verbose)


def cmd_formal(args: argparse.Namespace) -> int:
    root = Path(args.path)
    _, report = write_formal_artifacts(root, Path(args.out_dir), backend=args.backend, headers_only=args.headers_only, infer=not args.no_infer, dsl_paths=getattr(args, "dsl", None), run_solver=args.run_solver)
    _write_outputs(report, args, "Reporte del backend formal de StructGuard")
    return print_report(report, verbose=args.verbose)


def cmd_pipeline(args: argparse.Namespace) -> int:
    root = Path(args.path)
    report = pipeline_report(root, headers_only=args.headers_only, clang=args.clang, std=args.std, max_files=args.max_files, timeout=args.timeout, dsl_paths=getattr(args, "dsl", None), infer=not args.no_infer)
    _write_outputs(report, args, "Pipeline StructGuard Clang AST → CFG/SSA")
    if args.pipeline_json:
        units = build_pipeline_units(root, headers_only=args.headers_only, clang=args.clang, std=args.std, max_files=args.max_files, timeout=args.timeout, dsl_paths=getattr(args, "dsl", None), infer=not args.no_infer)
        write_pipeline_json(units, Path(args.pipeline_json))
        print(f"JSON del pipeline escrito en: {args.pipeline_json}")
    return print_report(report, verbose=args.verbose)

def cmd_pipeline_formal(args: argparse.Namespace) -> int:
    root = Path(args.path)
    _, report = write_pipeline_artifacts(root, Path(args.out_dir), backend=args.backend, run_solver=args.run_solver, headers_only=args.headers_only, clang=args.clang, std=args.std, max_files=args.max_files, timeout=args.timeout, dsl_paths=getattr(args, "dsl", None), infer=not args.no_infer)
    _write_outputs(report, args, "Artefactos formales del pipeline StructGuard")
    return print_report(report, verbose=args.verbose)

def cmd_rust(args: argparse.Namespace) -> int:
    root = Path(args.path); report = rust_frontend_project(root); _write_outputs(report, args, "Reporte del frontend Rust de StructGuard")
    if args.rust_json:
        write_rust_json(root, Path(args.rust_json)); print(f"JSON del frontend Rust escrito en: {args.rust_json}")
    return print_report(report, verbose=args.verbose)

def cmd_python_front(args: argparse.Namespace) -> int:
    root = Path(args.path); report = python_frontend_project(root); _write_outputs(report, args, "Reporte del frontend Python de StructGuard")
    if args.python_json:
        write_python_json(root, Path(args.python_json)); print(f"JSON del frontend Python escrito en: {args.python_json}")
    return print_report(report, verbose=args.verbose)

def cmd_assist(args: argparse.Namespace) -> int:
    root = Path(args.path); report = assist_project(root, headers_only=args.headers_only, dsl_paths=getattr(args, "dsl", None), seeds=args.seeds, steps=args.steps); _write_outputs(report, args, "Recomendaciones heurísticas de StructGuard")
    if args.assist_json:
        write_assist_json(report, Path(args.assist_json)); print(f"JSON de asistencia escrito en: {args.assist_json}")
    return print_report(report, verbose=args.verbose)

def cmd_advanced(args: argparse.Namespace) -> int:
    report = advanced_report(); _write_outputs(report, args, "Estructuras avanzadas de StructGuard")
    if args.dsl_out:
        write_advanced_dsl(Path(args.dsl_out)); print(f"DSL avanzado escrito en: {args.dsl_out}")
    if args.advanced_json:
        write_advanced_json(Path(args.advanced_json)); print(f"JSON avanzado escrito en: {args.advanced_json}")
    return print_report(report, verbose=args.verbose)


def cmd_docs(args: argparse.Namespace) -> int:
    root = Path(args.path)
    model = build_documentation_model(root, headers_only=args.headers_only, dsl_paths=getattr(args, "dsl", None), infer=not args.no_infer)
    report = docs_report(model)
    _write_outputs(report, args, "Reporte de documentación de StructGuard")
    if args.docs_json:
        write_docs_json(model, Path(args.docs_json))
        print(f"JSON de documentación escrito en: {args.docs_json}")
    if args.markdown_dir:
        index = write_docs_markdown(model, Path(args.markdown_dir))
        print(f"Documentación Markdown escrita en: {index}")
    if args.docs_html:
        write_docs_html(model, Path(args.docs_html), title="Documentación de API y contratos de StructGuard")
        print(f"HTML de documentación escrito en: {args.docs_html}")
    return print_report(report, verbose=args.verbose)


def cmd_perf(args: argparse.Namespace) -> int:
    root = Path(args.path)
    baseline = Path(args.baseline) if args.baseline else None
    profiles = build_performance_profiles(root, headers_only=args.headers_only)
    report = performance_report(root, headers_only=args.headers_only, baseline=baseline, regression_threshold=args.regression_threshold)
    _write_outputs(report, args, "Ingeniería de rendimiento StructGuard 4.5")
    if args.perf_json:
        write_performance_json(profiles, Path(args.perf_json))
        print(f"JSON de perfil de rendimiento escrito en: {args.perf_json}")
    if args.perf_html:
        write_performance_html(profiles, Path(args.perf_html))
        print(f"HTML de rendimiento escrito en: {args.perf_html}")
    if args.perf_md:
        write_performance_markdown(profiles, Path(args.perf_md))
        print(f"Markdown de rendimiento escrito en: {args.perf_md}")
    if args.harness:
        write_perf_harness(profiles, Path(args.harness))
        print(f"Harness de rendimiento escrito en: {args.harness}")
    if args.growth_json:
        write_growth_json(profiles, Path(args.growth_json))
        print(f"JSON del modelo de crecimiento escrito en: {args.growth_json}")
    return print_report(report, verbose=args.verbose)



def cmd_report(args: argparse.Namespace) -> int:
    if args.report_action != "derive":
        raise ValueError(f"Acción de report no soportada: {args.report_action}")
    document = load_canonical_report(Path(args.input))
    written = derive_reports_from_canonical(
        document,
        html=Path(args.html) if args.html else None,
        markdown=Path(args.markdown) if args.markdown else None,
        sarif=Path(args.sarif) if args.sarif else None,
        junit=Path(args.junit) if args.junit else None,
        json_out=Path(args.json) if args.json else None,
    )
    if not written:
        print("No se solicitó ningún reporte derivado.")
        return 0
    for path in written:
        print(f"Reporte derivado escrito en: {path}")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    out = Path(args.path)
    out.mkdir(parents=True, exist_ok=True)
    policy = out / "structguard.yml"
    policy.write_text(
        """project: CC-232
version: 4.5.6
paths:
  - Libreria_cc232
scan:
  headers_only: true
verification:
  mode: bounded
  infer_cc232_contracts: true
  max_cases: 300
  strict_ast: false
lint:
  require_invariants_for_data_structures: true
bench:
  mode: static-profile
performance:
  mode: engineering-profile
  regression_threshold_percent: 20
  report: report/performance.html
trace:
  mode: source-and-abstract
fuzz:
  seeds: 20
  steps: 50
security:
  deep: true
  fail_on_missing_preconditions: false
  rules_json: report/security_rules.json
ci:
  fail_on_failed_contract: true
  fail_on_warnings: false
  deep_security: true
dsl:
  files:
    - contracts/cc232_core.sgdsl
report:
  html: report/structguard.html
  json: report/structguard.json
formal:
  backend: both
  out_dir: formal_out
clang:
  std: c++17
  max_files: 30
  timeout: 12
pipeline:
  out_dir: pipeline_formal
  backend: both
frontends:
  rust: false
  python: false
assist:
  mode: heuristic
advanced:
  dsl: contracts/advanced_structures.sgdsl
docs:
  html: report/docs.html
  markdown_dir: report/docs_md
  json: report/docs.json
""",
        encoding="utf-8",
    )
    print(f"Creado {policy}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="structguard", description="Verificación acotada de contratos, análisis heurístico, lint, reportes y gates CI para implementaciones de estructuras de datos en cabeceras C++ .h.")
    p.add_argument("--version", action="version", version=f"StructGuard {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("doctor", help="Verifica el entorno local y la salud del árbol fuente para demos/releases de StructGuard")
    sp.add_argument("path", nargs="?", default=".", help="Raíz del repositorio a inspeccionar")
    sp.add_argument("--json", help="Escribe el reporte doctor en JSON")
    sp.add_argument("--strict", action="store_true", help="Devuelve código distinto de cero ante advertencias y requisitos obligatorios ausentes")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("profiles", help="Lista y valida perfiles de dominio de StructGuard")
    profiles_sub = sp.add_subparsers(dest="profiles_action", required=True)
    list_sp = profiles_sub.add_parser("list", help="Lista perfiles encontrados bajo profiles/")
    list_sp.add_argument("--profiles-root", default=str(default_profiles_root()), help="Directorio que contiene perfiles de dominio")
    list_sp.set_defaults(func=cmd_profiles)
    validate_sp = profiles_sub.add_parser("validate", help="Valida un profile.yml")
    validate_sp.add_argument("profile_path", help="Ruta a profile.yml o al directorio del perfil")
    validate_sp.set_defaults(func=cmd_profiles)


    sp = sub.add_parser("policy", help="Valida structguard.yml con esquema estricto")
    policy_sub = sp.add_subparsers(dest="policy_action", required=True)
    validate_sp = policy_sub.add_parser("validate", help="Valida una política YAML o JSON")
    validate_sp.add_argument("policy_path", help="Ruta a structguard.yml o a una política JSON")
    validate_sp.add_argument("--json", action="store_true", help="Imprime el resultado de validación como JSON")
    validate_sp.set_defaults(func=cmd_policy)

    sp = sub.add_parser("contract", help="Valida SGDSL estable y emite ContractIR")
    contract_sub = sp.add_subparsers(dest="contract_action", required=True)
    check_sp = contract_sub.add_parser("check", help="Valida contratos .sgdsl y reporta errores semánticos")
    check_sp.add_argument("contract_paths", nargs="+", help="Archivos o directorios de contratos .sgdsl")
    check_sp.set_defaults(func=cmd_contract)
    dump_sp = contract_sub.add_parser("dump-ir", help="Muestra ContractIR a partir de contratos .sgdsl")
    dump_sp.add_argument("contract_paths", nargs="+", help="Archivos o directorios de contratos .sgdsl")
    dump_sp.add_argument("--json", action="store_true", help="Imprime ContractIR como JSON en stdout")
    dump_sp.add_argument("--output", help="Escribe ContractIR JSON en una ruta")
    dump_sp.set_defaults(func=cmd_contract)
    bind_sp = contract_sub.add_parser("bind", help="Valida que contratos .sgdsl existan en el código fuente")
    bind_sp.add_argument("path", help="Archivo o directorio C++ a vincular con contratos externos")
    bind_sp.add_argument("--contract", dest="contract_paths", action="append", required=True, help="Archivo o directorio .sgdsl; se puede repetir")
    bind_sp.add_argument("--headers-only", action="store_true", help="Analiza solo cabeceras .h/.hh/.hpp/.hxx")
    bind_sp.add_argument("--language", choices=["cpp"], help="Lenguaje de entrada para construir SourceIR")
    bind_sp.add_argument("--compile-commands", help="Ruta a compile_commands.json para el frontend C++ con Clang")
    bind_sp.add_argument("--frontend", choices=["auto", "clang", "lightweight"], default="auto", help="Frontend C++ usado para el binding")
    bind_sp.add_argument("--fallback-allowed", action="store_true", help="Permite usar frontend ligero si Clang falla")
    bind_sp.add_argument("--clang", help="Ruta al binario clang++/clang")
    bind_sp.add_argument("--std", default="c++17", help="Estándar C++ pasado a Clang")
    bind_sp.add_argument("--timeout", type=int, default=12, help="Tiempo límite por archivo para Clang")
    bind_sp.add_argument("--source-ir-json", help="Escribe SourceIR JSON en esta ruta")
    bind_sp.add_argument("--json", action="store_true", help="Imprime BindingIR y diagnósticos como JSON")
    bind_sp.add_argument("--output", help="Escribe BindingIR JSON en una ruta")
    bind_sp.set_defaults(func=cmd_contract)

    def common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("path", help="Archivo .h de C++ o directorio a analizar")
        sp.add_argument("--headers-only", action="store_true", help="Analiza solo cabeceras .h/.hh/.hpp/.hxx")
        sp.add_argument("--no-infer", action="store_true", help="Desactiva contratos inferidos basados en CC-232/assert cuando aplique")
        sp.add_argument("--dsl", action="append", help="Carga un archivo o directorio de contratos DSL de StructGuard; se puede repetir")
        sp.add_argument("--contract", dest="contract_paths", action="append", help="Limita el análisis a este contrato .sgdsl; se puede repetir")
        sp.add_argument("--max-cases", type=int, default=300, help="Máximo de estados acotados por método")
        sp.add_argument("--profile", help="Perfil de dominio o ejecución: cc232, generic-cpp, stl-adapters, student, ci, strict, formal o security")
        sp.add_argument("--preset", choices=available_presets(), help="Preset del motor para scan: source, contracts, security, ci o full")
        sp.add_argument("--language", choices=["cpp"], help="Lenguaje de entrada para el frontend canónico")
        sp.add_argument("--compile-commands", help="Ruta a compile_commands.json para el frontend C++ con Clang")
        sp.add_argument("--frontend", choices=["auto", "clang", "lightweight"], default="auto", help="Frontend C++ a usar cuando se solicita --language cpp")
        sp.add_argument("--fallback-allowed", action="store_true", help="Permite degradar a frontend ligero si Clang no está disponible o falla")
        sp.add_argument("--source-ir-json", help="Escribe SourceIR JSON en esta ruta")
        sp.add_argument("--json", help="Escribe el reporte JSON heredado en esta ruta")
        sp.add_argument("--html", help="Escribe el reporte HTML heredado en esta ruta")
        sp.add_argument("--findings-json", help="Escribe FindingIR en JSON")
        sp.add_argument("--findings-html", help="Escribe FindingIR en HTML")
        sp.add_argument("--findings-md", help="Escribe FindingIR en Markdown")
        sp.add_argument("--findings-junit", help="Escribe FindingIR en JUnit XML")
        sp.add_argument("--findings-sarif", help="Escribe FindingIR en SARIF")
        sp.add_argument("--report-json", help="Escribe report.json canónico como fuente de verdad")
        sp.add_argument("--lockfile", help="Escribe structguard.lock con hashes y entorno mínimo")
        sp.add_argument("--cache", action="store_true", help="Activa cache incremental por archivo para scan")
        sp.add_argument("--cache-dir", default=".structguard/cache", help="Directorio local para entradas de cache incremental")
        sp.add_argument("--cache-clear", action="store_true", help="Limpia la cache antes de ejecutar scan")
        sp.add_argument("-v", "--verbose", action="store_true", help="Imprime detalles de diagnóstico")

    def strict_ast_options(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--strict-ast", action="store_true", help="Exige parseo AST con Clang antes de confiar en diagnósticos acotados/heurísticos")
        sp.add_argument("--clang", help="Ruta al binario clang++/clang usado por --strict-ast")
        sp.add_argument("--std", default="c++17", help="Estándar C++ pasado a Clang en modo --strict-ast")
        sp.add_argument("--max-files", type=int, default=30, help="Cantidad máxima de archivos parseados por Clang en modo --strict-ast")
        sp.add_argument("--timeout", type=int, default=12, help="Tiempo límite por archivo para el parseo AST de Clang")

    sp = sub.add_parser("verify", help="Verifica de forma acotada contratos // requires, // ensures y // invariant")
    common(sp); strict_ast_options(sp); sp.set_defaults(func=cmd_verify)

    sp = sub.add_parser("lint", help="Ejecuta comprobaciones lint de contratos/invariantes")
    common(sp); sp.set_defaults(func=cmd_lint)

    sp = sub.add_parser("analyze", help="Ejecuta verificación acotada de contratos y lint de contratos en una sola pasada")
    common(sp); strict_ast_options(sp); sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("scan", help="Ejecuta el análisis principal usando perfiles de dominio explícitos")
    common(sp); strict_ast_options(sp); sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("suggest", help="Sugiere anotaciones // invariant, // requires y // ensures para cabeceras .h")
    common(sp)
    sp.add_argument("--patch", help="Escribe un diff unificado que inserta comentarios sugeridos")
    sp.add_argument("--apply-to", help="Escribe una copia anotada de las cabeceras analizadas en este directorio")
    sp.add_argument("--suggestions-json", help="Escribe sugerencias crudas de contratos en JSON")
    sp.set_defaults(func=cmd_suggest)

    sp = sub.add_parser("bench", help="Genera perfiles estáticos de benchmark y un esqueleto opcional de harness C++")
    common(sp)
    sp.add_argument("--metrics-json", help="Escribe métricas crudas de benchmark en JSON")
    sp.add_argument("--harness", help="Escribe un harness inicial de benchmark C++")
    sp.set_defaults(func=cmd_bench)

    sp = sub.add_parser("trace", help="Encuentra puntos de traza fuente y genera trazas abstractas de operaciones")
    common(sp)
    sp.add_argument("--ops", help="Secuencia de operaciones, por ejemplo: 'push:1,push:2,pop,top'")
    sp.add_argument("--structure", default="stack", help="Nombre de la estructura abstracta para la traza generada")
    sp.add_argument("--trace-json", help="Escribe eventos de traza abstracta en JSON")
    sp.set_defaults(func=cmd_trace)

    sp = sub.add_parser("fuzz", help="Alias deprecado: genera secuencias abstractas; use testgen para generación de pruebas")
    common(sp)
    sp.add_argument("--seeds", type=int, default=20)
    sp.add_argument("--steps", type=int, default=50)
    sp.add_argument("--structure", help="Limita la generación abstracta a estructuras cuyo nombre contiene este texto")
    sp.add_argument("--fuzz-json", help="Escribe casos testgen generados en JSON crudo")
    sp.add_argument("--fuzz-html", help="Escribe un reporte HTML autónomo de TestGen")
    sp.add_argument("--replay", help="Escribe un script Python de reproducción para secuencias abstractas fallidas")
    sp.add_argument("--seed-corpus", help="Escribe un archivo JSON por cada semilla/caso testgen generado")
    sp.add_argument("--emit-tests", action="store_true", help="Genera candidatos de pruebas de regresión C++ para contraejemplos")
    sp.add_argument("--test-dir", help="Directorio para candidatos de pruebas de regresión C++ generados")
    sp.add_argument("--include-smoke-tests", action="store_true", help="También emite pruebas smoke cuando no se encuentra ninguna falla")
    sp.set_defaults(func=cmd_fuzz)

    sp = sub.add_parser("testgen", help="Genera candidatos de pruebas de regresión C++ a partir de secuencias abstractas de StructGuard")
    common(sp)
    sp.add_argument("--seeds", type=int, default=30)
    sp.add_argument("--steps", type=int, default=60)
    sp.add_argument("--structure", help="Limita la generación de pruebas a estructuras cuyo nombre contiene este texto")
    sp.add_argument("--test-dir", default="generated_tests", help="Directorio para pruebas C++ generadas")
    sp.add_argument("--include-smoke-tests", action="store_true", help="También emite pruebas smoke cuando no se encuentra ninguna falla")
    sp.add_argument("--fuzz-json", help="Escribe casos testgen generados en JSON crudo")
    sp.add_argument("--replay", help="Escribe un script Python de reproducción para secuencias abstractas fallidas")
    sp.set_defaults(func=cmd_testgen)

    sp = sub.add_parser("security", help="Ejecuta comprobaciones estáticas orientadas a seguridad para estructuras de datos C++")
    common(sp)
    sp.add_argument("--deep", action="store_true", help="Activa comprobaciones heurísticas profundas de seguridad: límites, underflow, overflow, ownership e inicialización")
    sp.add_argument("--security-json", help="Escribe el reporte de seguridad con catálogo de reglas en JSON")
    sp.add_argument("--rules-json", help="Escribe el catálogo de reglas de seguridad en JSON")
    sp.set_defaults(func=cmd_security)

    sp = sub.add_parser("ci", help="Ejecuta verify + lint + security + testgen abstracto como gate configurable de política CI/CD")
    common(sp)
    sp.add_argument("--seeds", type=int, default=10)
    sp.add_argument("--steps", type=int, default=25)
    sp.add_argument("--fail-on-warnings", action="store_true")
    sp.add_argument("--fail-on-unknown", action="store_true", default=None)
    sp.add_argument("--policy", help="Carga una política structguard.yml/.json para umbrales y comportamiento del gate")
    sp.add_argument("--deep-security", action="store_true", help="Usa comprobaciones heurísticas profundas de seguridad en el gate CI")
    strict_ast_options(sp)
    sp.add_argument("--junit", help="Escribe XML JUnit para reportes de pruebas CI")
    sp.add_argument("--sarif", help="Escribe SARIF 2.1.0 para code scanning/paneles de seguridad")
    sp.add_argument("--summary-md", help="Escribe un resumen CI en Markdown")
    sp.add_argument("--github-annotations", action="store_true", help="Imprime anotaciones ::error/::warning de GitHub Actions")
    sp.set_defaults(func=cmd_ci)

    sp = sub.add_parser("ci-init", help="Crea structguard.yml y un workflow de GitHub Actions para StructGuard")
    sp.add_argument("path", nargs="?", default=".", help="Raíz del repositorio donde se crearán los archivos")
    sp.add_argument("--project-path", default="Libreria_cc232", help="Ruta del proyecto analizada por CI")
    sp.add_argument("--policy-name", default="structguard.yml")
    sp.add_argument("--workflow-name", default="structguard.yml")
    sp.add_argument("--force", action="store_true", help="Sobrescribe la política/workflow existente")
    sp.set_defaults(func=cmd_ci_init)

    sp = sub.add_parser("dsl", help="Valida y resume archivos de contratos DSL de StructGuard")
    sp.add_argument("dsl_files", nargs="+", help="Archivos o directorios .sgdsl/.sg/.structguard")
    sp.add_argument("--json", help="Escribe el reporte JSON en esta ruta")
    sp.add_argument("--html", help="Escribe el reporte HTML avanzado en esta ruta")
    sp.add_argument("--dsl-json", help="Escribe el modelo DSL parseado en JSON")
    sp.add_argument("-v", "--verbose", action="store_true", help="Imprime detalles de diagnóstico")
    sp.set_defaults(func=cmd_dsl)

    sp = sub.add_parser("frontend", help="Ejecuta el frontend mejorado de cabeceras C++ y resume la cobertura del escaneo")
    common(sp)
    sp.add_argument("--frontend-json", help="Escribe el resumen crudo del frontend C++ en JSON")
    sp.set_defaults(func=cmd_frontend)


    sp = sub.add_parser("clang", help="Ejecuta un frontend AST real de Clang sobre cabeceras/fuentes C++")
    common(sp)
    sp.add_argument("--clang", help="Ruta al binario clang++/clang")
    sp.add_argument("--std", default="c++17", help="Estándar C++ pasado a Clang; por defecto c++17")
    sp.add_argument("--max-files", type=int, default=30, help="Cantidad máxima de archivos a parsear con Clang")
    sp.add_argument("--timeout", type=int, default=12, help="Tiempo límite por archivo para el dump AST de Clang")
    sp.add_argument("--clang-json", help="Escribe el resumen crudo del frontend Clang en JSON")
    sp.add_argument("--no-ast-filter", action="store_true", help="Desactiva ast-dump-filter de Clang; útil para archivos pequeños, lento para cabeceras grandes")
    sp.set_defaults(func=cmd_clang)

    sp = sub.add_parser("formal", help="Exporta artefactos formales SMT-LIB y/o puente Viper desde contratos")
    common(sp)
    sp.add_argument("--backend", choices=["smt", "viper", "both"], default="both")
    sp.add_argument("--out-dir", default="formal_out", help="Directorio donde se escriben artefactos .smt2/.vpr")
    sp.add_argument("--run-solver", action="store_true", help="Ejecuta z3 sobre archivos SMT-LIB generados cuando z3 esté instalado")
    sp.set_defaults(func=cmd_formal)

    sp = sub.add_parser("pipeline", help="Ejecuta el pipeline Clang AST → CFG/SSA y resume la IR de métodos")
    common(sp)
    sp.add_argument("--clang", help="Ruta al binario clang++/clang")
    sp.add_argument("--std", default="c++17")
    sp.add_argument("--max-files", type=int, default=20)
    sp.add_argument("--timeout", type=int, default=15)
    sp.add_argument("--pipeline-json", help="Escribe la IR del pipeline Clang en JSON")
    sp.set_defaults(func=cmd_pipeline)

    sp = sub.add_parser("pipeline-formal", help="Exporta SMT-LIB/Viper desde el pipeline Clang AST → CFG/SSA")
    common(sp)
    sp.add_argument("--clang", help="Ruta al binario clang++/clang")
    sp.add_argument("--std", default="c++17")
    sp.add_argument("--max-files", type=int, default=20)
    sp.add_argument("--timeout", type=int, default=15)
    sp.add_argument("--backend", choices=["smt", "viper", "both"], default="both")
    sp.add_argument("--out-dir", default="pipeline_formal")
    sp.add_argument("--run-solver", action="store_true")
    sp.set_defaults(func=cmd_pipeline_formal)

    sp = sub.add_parser("rust", help="Escanea archivos Rust para estructuras, métodos impl y contratos")
    sp.add_argument("path")
    sp.add_argument("--json", help="Escribe el reporte JSON en esta ruta")
    sp.add_argument("--html", help="Escribe el reporte HTML en esta ruta")
    sp.add_argument("--rust-json", help="Escribe el modelo crudo del frontend Rust en JSON")
    sp.add_argument("-v", "--verbose", action="store_true")
    sp.set_defaults(func=cmd_rust)

    sp = sub.add_parser("python", help="Escanea archivos Python para clases, funciones y contratos")
    sp.add_argument("path")
    sp.add_argument("--json", help="Escribe el reporte JSON en esta ruta")
    sp.add_argument("--html", help="Escribe el reporte HTML en esta ruta")
    sp.add_argument("--python-json", help="Escribe el modelo crudo del frontend Python en JSON")
    sp.add_argument("-v", "--verbose", action="store_true")
    sp.set_defaults(func=cmd_python_front)

    sp = sub.add_parser("assist", help="Revisión heurística y recomendaciones de siguientes acciones")
    common(sp)
    sp.add_argument("--seeds", type=int, default=8)
    sp.add_argument("--steps", type=int, default=20)
    sp.add_argument("--assist-json", help="Escribe recomendaciones heurísticas en JSON")
    sp.set_defaults(func=cmd_assist)

    sp = sub.add_parser("advanced", help="Genera plantillas avanzadas de contratos para estructuras de datos")
    sp.add_argument("--json", help="Escribe el reporte JSON en esta ruta")
    sp.add_argument("--html", help="Escribe el reporte HTML en esta ruta")
    sp.add_argument("--dsl-out", help="Escribe una plantilla .sgdsl de estructuras avanzadas")
    sp.add_argument("--advanced-json", help="Escribe el catálogo crudo de estructuras avanzadas en JSON")
    sp.add_argument("-v", "--verbose", action="store_true")
    sp.set_defaults(func=cmd_advanced)


    sp = sub.add_parser("docs", help="Genera documentación automática de API, contratos y costo empírico")
    common(sp)
    sp.add_argument("--docs-html", help="Escribe documentación HTML autónoma de la API")
    sp.add_argument("--markdown-dir", help="Escribe un directorio de documentación Markdown con páginas por estructura")
    sp.add_argument("--docs-json", help="Escribe el modelo crudo de documentación en JSON")
    sp.set_defaults(func=cmd_docs)


    sp = sub.add_parser("perf", help="Ingeniería de rendimiento de StructGuard: planes de carga, contadores, modelos de crecimiento y gates de regresión")
    common(sp)
    sp.add_argument("--perf-json", help="Escribe el perfil de rendimiento en JSON")
    sp.add_argument("--perf-html", help="Escribe un HTML autónomo de ingeniería de rendimiento")
    sp.add_argument("--perf-md", help="Escribe el reporte de rendimiento en Markdown")
    sp.add_argument("--harness", help="Escribe un esqueleto de harness C++ para benchmark/instrumentación")
    sp.add_argument("--growth-json", help="Escribe curvas esperadas de crecimiento empírico en JSON")
    sp.add_argument("--baseline", help="Compara contra un JSON de rendimiento previo o baseline compacto")
    sp.add_argument("--regression-threshold", type=float, default=20.0, help="Falla si el puntaje estático de rendimiento regresa en este porcentaje")
    sp.set_defaults(func=cmd_perf)

    sp = sub.add_parser("report", help="Deriva reportes secundarios desde report.json canónico")
    report_sub = sp.add_subparsers(dest="report_action", required=True)
    derive_sp = report_sub.add_parser("derive", help="Genera HTML, SARIF, JUnit, Markdown o JSON desde report.json")
    derive_sp.add_argument("input", help="Ruta a report.json canónico")
    derive_sp.add_argument("--html", help="Escribe reporte HTML derivado")
    derive_sp.add_argument("--markdown", help="Escribe reporte Markdown derivado")
    derive_sp.add_argument("--sarif", help="Escribe reporte SARIF derivado")
    derive_sp.add_argument("--junit", help="Escribe reporte JUnit XML derivado")
    derive_sp.add_argument("--json", help="Escribe una copia normalizada del reporte canónico")
    derive_sp.set_defaults(func=cmd_report)

    sp = sub.add_parser("init", help="Crea un structguard.yml inicial")
    sp.add_argument("path", nargs="?", default=".")
    sp.set_defaults(func=cmd_init)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
