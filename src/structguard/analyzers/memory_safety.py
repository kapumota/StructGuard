from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from structguard.analyzers.contracts import RuleDefinition
from structguard.memory import ClassMemoryModel, MemoryAllocation, MemoryRelease, build_memory_models
from structguard.model import Diagnostic, ProjectReport


MEMORY_RULES: dict[str, RuleDefinition] = {
    "SG-MEMORY-OWNERSHIP-RISK": RuleDefinition(
        rule_id="SG-MEMORY-OWNERSHIP-RISK",
        description="Reserva manual sin ownership y liberación compatibles.",
        default_severity="error",
        good_example="data = new int[n]; ~Vector() { delete[] data; }",
        bad_example="data = new int[n]; ~Vector() { delete data; }",
        profiles=("cc232", "generic-cpp"),
        cwe="CWE-401",
        tags=("memory", "ownership", "cpp"),
    ),
}


def analyze_memory_safety_project(root: Path, headers_only: bool = False) -> ProjectReport:
    models = build_memory_models(root, headers_only=headers_only)
    report = ProjectReport(root=str(root), diagnostics=[])
    report.diagnostics.append(
        Diagnostic(
            level="INFO",
            code="MEM_MEMORY_SUMMARY",
            message=f"Modelo de memoria construido: {len(models)} clases analizadas.",
            file=str(root),
            details={"classes": [model.as_dict() for model in models]},
        )
    )
    for model in models:
        _check_allocations(report, model)
        _check_double_delete(report, model)
        _check_null_dereferences(report, model)
        _check_capacity_relations(report, model)
    return report


def _check_allocations(report: ProjectReport, model: ClassMemoryModel) -> None:
    releases_by_target: dict[str, list[MemoryRelease]] = defaultdict(list)
    for release in model.releases:
        releases_by_target[release.target].append(release)

    for allocation in model.allocations:
        releases = releases_by_target.get(allocation.target, [])
        matching = [release for release in releases if release.kind == allocation.kind]
        mismatched = [release for release in releases if release.kind != allocation.kind]
        if matching:
            _add(
                report,
                level="INFO",
                code="MEM_ARRAY_OWNERSHIP_OK" if allocation.kind == "array" else "MEM_SINGLE_OWNERSHIP_OK",
                message=f"{allocation.target} usa {allocation.expression} y tiene liberación compatible.",
                file=allocation.location.file,
                line=allocation.location.line,
                symbol=allocation.symbol,
                evidence=allocation.expression,
                remediation="Mantén el par ownership/liberación documentado y cubierto por pruebas.",
                confidence="medium",
                metadata={"target": allocation.target, "kind": allocation.kind},
            )
            continue
        if mismatched:
            release = mismatched[0]
            _add(
                report,
                level="FAILED",
                code="MEM_DELETE_KIND_MISMATCH",
                message=f"{allocation.target} se reserva como {allocation.kind}, pero se libera como {release.kind}.",
                file=release.location.file,
                line=release.location.line,
                symbol=release.symbol,
                evidence=release.expression,
                remediation="Usa delete[] para new[] y delete para new.",
                confidence="high",
                metadata={"target": allocation.target, "allocation_kind": allocation.kind, "release_kind": release.kind},
            )
            _add_structural_ownership_risk(report, release.location.file, release.location.line, release.symbol, release.expression, allocation.target)
            continue
        _add(
            report,
            level="WARNING",
            code="MEM_ARRAY_NEW_WITHOUT_DELETE_ARRAY" if allocation.kind == "array" else "MEM_NEW_WITHOUT_DELETE",
            message=f"{allocation.target} tiene reserva manual sin liberación compatible visible.",
            file=allocation.location.file,
            line=allocation.location.line,
            symbol=allocation.symbol,
            evidence=allocation.expression,
            remediation="Agrega destructor o wrapper RAII que libere el recurso exactamente una vez.",
            confidence="medium",
            metadata={"target": allocation.target, "kind": allocation.kind},
        )
        _add_structural_ownership_risk(report, allocation.location.file, allocation.location.line, allocation.symbol, allocation.expression, allocation.target)


def _check_double_delete(report: ProjectReport, model: ClassMemoryModel) -> None:
    per_method: Counter[tuple[str, str, str]] = Counter((release.method_name, release.target, release.kind) for release in model.releases)
    for method_name, target, kind in sorted(key for key, count in per_method.items() if count > 1):
        first = next(release for release in model.releases if release.method_name == method_name and release.target == target and release.kind == kind)
        _add(
            report,
            level="FAILED",
            code="MEM_DOUBLE_DELETE",
            message=f"{target} se libera más de una vez en {model.class_name}::{method_name}.",
            file=first.location.file,
            line=first.location.line,
            symbol=first.symbol,
            evidence=first.expression,
            remediation="Asegura ownership único, asigna nullptr después de liberar o elimina la liberación duplicada.",
            confidence="high",
            metadata={"target": target, "kind": kind},
        )
        _add_structural_ownership_risk(report, first.location.file, first.location.line, first.symbol, first.expression, target)


def _check_null_dereferences(report: ProjectReport, model: ClassMemoryModel) -> None:
    nullable = {field.name for field in model.pointer_fields if field.initialized_null}
    nullable.update(assignment.target for assignment in model.null_assignments)
    for dereference in model.dereferences:
        if dereference.target not in nullable or dereference.guarded:
            continue
        _add(
            report,
            level="WARNING",
            code="MEM_NULL_DEREF_RISK",
            message=f"{dereference.target} puede ser nullptr antes de una desreferencia.",
            file=dereference.location.file,
            line=dereference.location.line,
            symbol=dereference.symbol,
            evidence=f"{dereference.access}:{dereference.target}",
            remediation="Agrega una guarda local o una precondición explícita de no nulidad.",
            confidence="medium",
            metadata={"target": dereference.target, "access": dereference.access},
        )


def _check_capacity_relations(report: ProjectReport, model: ClassMemoryModel) -> None:
    for relation in model.capacity_relations:
        _add(
            report,
            level="FAILED",
            code="MEM_CAPACITY_SIZE_MISMATCH",
            message=f"{relation.size_field} puede quedar fuera de sincronía con {relation.capacity_field}.",
            file=relation.location.file,
            line=relation.location.line,
            symbol=relation.symbol,
            evidence=relation.expression,
            remediation="Mantén el invariante 0 <= size <= capacity después de cada operación.",
            confidence="high",
            metadata=relation.as_dict(),
        )


def _add_structural_ownership_risk(report: ProjectReport, file: str, line: int, symbol: str, evidence: str, target: str) -> None:
    rule = MEMORY_RULES["SG-MEMORY-OWNERSHIP-RISK"]
    report.diagnostics.append(
        Diagnostic(
            level="FAILED",
            code=rule.rule_id,
            message=f"{target} tiene un riesgo de ownership manual que requiere revisión.",
            file=file,
            line=line,
            symbol=symbol,
            details={
                "title": rule.description,
                "confidence": "medium",
                "evidence": evidence,
                "remediation": "Asegura una única responsabilidad de liberación y un par new/delete compatible.",
                "cwe": rule.cwe,
                "tags": list(rule.tags),
                "rule": rule.as_dict(),
            },
        )
    )


def _add(
    report: ProjectReport,
    *,
    level: str,
    code: str,
    message: str,
    file: str,
    line: int,
    symbol: str,
    evidence: str,
    remediation: str,
    confidence: str,
    metadata: dict[str, object],
) -> None:
    report.diagnostics.append(
        Diagnostic(
            level=level,
            code=code,
            message=message,
            file=file,
            line=line,
            symbol=symbol,
            details={
                "evidence": evidence,
                "remediation": remediation,
                "confidence": confidence,
                "tags": ["memory", "cpp"],
                **metadata,
            },
        )
    )
