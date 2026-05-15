from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .cppscan import extract_assertions, scan_project
from .verifier import extract_initializer_assignments
from .lint import UNSAFE_METHOD_NAMES
from .model import Diagnostic, ProjectReport


@dataclass
class SecurityRule:
    code: str
    title: str
    severity: str
    category: str
    description: str
    remediation: str


@dataclass
class SecurityFinding:
    rule: str
    severity: str
    file: str
    line: int
    symbol: str
    message: str
    evidence: str = ""
    remediation: str = ""
    confidence: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)


SECURITY_RULES: list[SecurityRule] = [
    SecurityRule("SEC_MISSING_PRECONDITION", "Precondición ausente en operación insegura", "WARNING", "contract", "Métodos de acceso/eliminación como pop/top/front/remove deberían declarar una precondición de no vacío o de límites.", "Agrega un // requires: explícito con !empty(), n > 0 o límites de índice válidos."),
    SecurityRule("SEC_RAW_INDEX_WITHOUT_GUARD", "Acceso indexado directo sin guarda", "WARNING", "bounds", "El método usa indexación [] pero no tiene una guarda visible mediante contrato/assert.", "Agrega precondiciones de límites o asserts locales antes del acceso indexado."),
    SecurityRule("SEC_BOUNDS_RISK", "Posible índice fuera de límites", "WARNING", "bounds", "La expresión de índice parece depender de estado mutable de tamaño/capacidad sin una guarda evidente.", "Prueba o documenta 0 <= índice < tamaño/capacidad; agrega requires/invariant."),
    SecurityRule("SEC_CAPACITY_GUARD_MISSING", "Guarda de capacidad ausente antes de escritura", "WARNING", "capacity", "El método escribe en almacenamiento interno, pero no tiene una precondición visible de capacidad ni evidencia de redimensionamiento.", "Agrega requires: n < capacity() o asegura que el redimensionamiento ocurra antes de escribir."),
    SecurityRule("SEC_UNDERFLOW_RISK", "Posible underflow de tamaño", "WARNING", "arithmetic", "Una variable tipo tamaño se decrementa sin una precondición visible de no vacío.", "Agrega requires: n > 0 / !empty() y preserva el invariante n >= 0."),
    SecurityRule("SEC_OVERFLOW_RISK", "Posible overflow entero en aritmética de índice/capacidad", "INFO", "arithmetic", "La aritmética de índice/capacidad puede desbordar en contenedores grandes.", "Usa aritmética verificada o documenta cotas superiores de capacidad/tamaño."),
    SecurityRule("SEC_MODULO_ZERO_RISK", "Posible módulo/división por cero", "WARNING", "arithmetic", "Una operación módulo o división por una expresión tipo capacidad/tamaño no tiene guarda de no cero.", "Agrega invariant/requires: capacity() > 0 o divisor != 0."),
    SecurityRule("SEC_NULL_DEREF_RISK", "Posible desreferencia nula", "WARNING", "pointers", "Aparece una desreferencia de puntero sin una comprobación visible de no nulidad.", "Agrega requires: ptr != nullptr o una guarda local."),
    SecurityRule("SEC_MANUAL_ALLOCATION", "Asignación manual", "INFO", "memory", "Se encontró new/new[] manual.", "Revisa el invariante de ownership, destructor, operaciones copy/move y seguridad ante excepciones."),
    SecurityRule("SEC_MANUAL_DEALLOCATION", "Liberación manual", "INFO", "memory", "Se encontró delete/delete[] manual.", "Verifica que no haya rutas double-free/use-after-free y enlázalo con reglas de ownership."),
    SecurityRule("SEC_RESOURCE_RULE_OF_THREE", "Ownership crudo requiere revisión de miembros especiales", "WARNING", "memory", "La clase parece poseer memoria cruda, pero podría no definir destructor/copy/move de forma consistente.", "Usa contenedores RAII o implementa deliberadamente destructor/copy/move."),
    SecurityRule("SEC_ASSERT_ONLY_PRECONDITION", "Precondición solo con assert", "INFO", "contract", "assert() es una comprobación de depuración en tiempo de ejecución y puede desaparecer en builds release.", "Promueve supuestos esenciales de seguridad a contratos // requires."),
    SecurityRule("SEC_UNSAFE_C_API", "API C insegura", "WARNING", "api", "APIs C como strcpy/sprintf/memcpy requieren revisión explícita de límites.", "Usa alternativas acotadas o verifica la capacidad del destino."),
    SecurityRule("SEC_UNINITIALIZED_FIELD", "Campo posiblemente no inicializado", "INFO", "initialization", "El cuerpo del constructor no inicializa visiblemente un campo detectado.", "Inicializa todos los campos en la lista de inicialización del constructor o en el cuerpo."),
    SecurityRule("SEC_SECURITY_SUMMARY", "Resumen de seguridad", "INFO", "summary", "Inventario agregado de seguridad profunda para el proyecto analizado.", "Usa los hallazgos para priorizar contratos y guardas."),
]
RULE_BY_CODE = {r.code: r for r in SECURITY_RULES}

SIZE_NAMES = {"n", "size", "size_", "_size", "length", "len", "count", "m_size"}
CAP_NAMES = {"capacity", "capacity_", "_capacity", "cap", "m_capacity"}
EMPTY_GUARDS = ["!empty()", "n>0", "size_>0", "_size>0", "size()>0", "len>0", "length>0", "count>0"]
CAPACITY_GUARDS = ["n<capacity", "n<capacity()", "size_<capacity", "_size<_capacity", "size()<capacity", "i<n", "i<size", "i<size()", "0<=i", "i>=0"]


def _norm(exprs: list[str]) -> str:
    return " ".join(exprs).replace(" ", "").replace("this->", "")


def _has_nonempty_precondition(reqs: list[str]) -> bool:
    norm = _norm(reqs)
    return any(x in norm for x in EMPTY_GUARDS)


def _has_index_or_capacity_guard(reqs: list[str]) -> bool:
    norm = _norm(reqs)
    return _has_nonempty_precondition(reqs) or any(x in norm for x in CAPACITY_GUARDS)


def _method_contracts(method) -> list[str]:
    return [c.expression for c in method.requires] + [a.expression for a in extract_assertions(method.body or "", method.start_line)]


def _add(report: ProjectReport, finding: SecurityFinding) -> None:
    report.diagnostics.append(Diagnostic(
        level=finding.severity,
        code=finding.rule,
        message=finding.message,
        file=finding.file,
        line=finding.line,
        symbol=finding.symbol,
        details={
            "evidence": finding.evidence,
            "remediation": finding.remediation or RULE_BY_CODE.get(finding.rule, SecurityRule(finding.rule,"",finding.severity,"","","")).remediation,
            "confidence": finding.confidence,
            **finding.metadata,
        },
    ))


def _line_for(body: str, base_line: int, offset: int) -> int:
    return base_line + body.count("\n", 0, max(0, offset))


def _constructor_names(cls_name: str) -> set[str]:
    return {cls_name, f"~{cls_name}"}


def _assigned_fields(body: str, fields: set[str], signature: str = "") -> set[str]:
    assigned = set()
    for f in fields:
        if re.search(rf"(?:this->)?{re.escape(f)}\s*=", body):
            assigned.add(f)
    # Los constructores suelen inicializar campos mediante listas de inicialización de miembros C++.
    # Reutiliza el parser del verificador para que los hallazgos de seguridad coincidan con el análisis de contratos.
    if signature:
        dummy = type("MethodLike", (), {"name": "", "class_name": ""})()
        # Infiere el nombre del constructor desde el prefijo de la firma cuando sea posible.
        m = re.search(r"(?:^|\s)([A-Za-z_]\w*)\s*\(", signature)
        if m:
            dummy.name = m.group(1)
            dummy.class_name = m.group(1)
            for field, _ in extract_initializer_assignments(signature, dummy)[0]:
                if field in fields:
                    assigned.add(field)
    return assigned


def _class_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _class_has_raw_ownership(text: str, cls_name: str) -> bool:
    # Heurística: campos de puntero crudo o new[]/delete[] cerca de la clase.
    class_pat = re.compile(rf"\b(class|struct)\s+{re.escape(cls_name)}\b[\s\S]{{0,4000}}?\}}\s*;", re.M)
    m = class_pat.search(text)
    chunk = m.group(0) if m else text
    return bool(re.search(r"\b[A-Za-z_:][\w:<>]*\s*\*\s*[A-Za-z_]\w*\s*;", chunk) or re.search(r"\bnew\s+[^;\n]+\[", chunk) or re.search(r"\bdelete\s*\[\]", chunk))


def _special_members_present(cls) -> set[str]:
    names = {m.name for m in cls.methods}
    present = set()
    if f"~{cls.name}" in names:
        present.add("destructor")
    # El escáner no modela completamente constructores copy/move, por eso usa firmas.
    for m in cls.methods:
        sig = m.signature.replace(" ", "")
        if f"{cls.name}(const{cls.name}&" in sig or f"{cls.name}(const{cls.name}<" in sig:
            present.add("copy_constructor")
        if "operator=" in sig and f"{cls.name}&" in sig:
            present.add("assignment")
    return present


def _detect_uninitialized_fields(report: ProjectReport, cls, deep: bool) -> None:
    if not deep or not cls.fields:
        return
    constructors = [m for m in cls.methods if m.name == cls.name and m.body]
    for ctor in constructors:
        assigned = _assigned_fields(ctor.body or "", cls.fields, ctor.signature)
        missing = sorted(f for f in cls.fields if f not in assigned and f not in {"public", "private", "protected"})
        if missing:
            _add(report, SecurityFinding(
                rule="SEC_UNINITIALIZED_FIELD", severity="INFO", file=str(cls.file), line=ctor.start_line, symbol=ctor.qualified_name,
                message=f"{ctor.qualified_name} podría dejar campos sin inicializar: {', '.join(missing[:6])}.",
                evidence=ctor.signature, confidence="low", metadata={"fields": missing},
            ))


def _detect_resource_rule(report: ProjectReport, cls, deep: bool) -> None:
    if not deep:
        return
    text = _class_text(cls.file)
    if not _class_has_raw_ownership(text, cls.name):
        return
    present = _special_members_present(cls)
    missing = sorted({"destructor", "copy_constructor", "assignment"} - present)
    if missing:
        _add(report, SecurityFinding(
            rule="SEC_RESOURCE_RULE_OF_THREE", severity="WARNING", file=str(cls.file), line=cls.start_line, symbol=cls.name,
            message=f"{cls.name} parece gestionar recursos crudos; revisa miembros especiales faltantes: {', '.join(missing)}.",
            evidence="raw pointer/new/delete pattern near class", confidence="medium", metadata={"present": sorted(present), "missing": missing},
        ))


def _detect_method_security(report: ProjectReport, cls, method, deep: bool) -> dict[str, int]:
    body = method.body or ""
    reqs = _method_contracts(method)
    norm_reqs = _norm(reqs)
    mlower = method.name.lower().replace("~", "")
    stats = {"raw_indexes": 0, "asserts": len(extract_assertions(body, method.start_line)), "allocations": 0, "deep_findings": 0}

    def add(rule: str, severity: str, msg: str, offset: int = 0, evidence: str = "", confidence: str = "medium", **meta: Any) -> None:
        stats["deep_findings"] += 1
        _add(report, SecurityFinding(rule=rule, severity=severity, file=str(cls.file), line=_line_for(body, method.start_line, offset), symbol=method.qualified_name, message=msg, evidence=evidence, confidence=confidence, metadata=meta))

    if mlower in UNSAFE_METHOD_NAMES and not _has_nonempty_precondition(reqs):
        add("SEC_MISSING_PRECONDITION", "WARNING", f"{method.qualified_name} es un método de acceso/eliminación sin una precondición explícita de no vacío/límites.", evidence=method.signature, suggested="requires: !empty() o límites de índice")

    index_matches = list(re.finditer(r"([A-Za-z_]\w*(?:->|\.)?)?([A-Za-z_]\w*)\s*\[\s*([^\]]+)\s*\]", body))
    stats["raw_indexes"] = len(index_matches)
    if index_matches and not reqs:
        add("SEC_RAW_INDEX_WITHOUT_GUARD", "WARNING", f"{method.qualified_name} usa indexación [] sin una guarda cercana de contrato/assert.", offset=index_matches[0].start(), evidence=index_matches[0].group(0))
    if deep:
        for im in index_matches[:12]:
            idx = im.group(3).strip()
            evidence = im.group(0).strip()
            size_like = re.search(r"\b(i|j|k|n|size|size_|_size|capacity|capacity_)\b", idx)
            arithmetic = re.search(r"[+\-*/%]", idx)
            if (size_like or arithmetic) and not _has_index_or_capacity_guard(reqs):
                add("SEC_BOUNDS_RISK", "WARNING", f"Posible expresión de índice fuera de límites `{idx}` en {method.qualified_name}.", offset=im.start(), evidence=evidence, index=idx)

    writes_to_index = bool(re.search(r"\[[^\]]+\]\s*=", body))
    mutator_name = mlower in {"add", "push", "pushback", "push_back", "insert", "enqueue", "set", "update"}
    has_resize = bool(re.search(r"\b(resize|reserve|grow|ensure|increase|expand)\s*\(", body, re.I))
    if deep and (writes_to_index or mutator_name) and not _has_index_or_capacity_guard(reqs) and not has_resize:
        add("SEC_CAPACITY_GUARD_MISSING", "WARNING", f"{method.qualified_name} podría escribir en almacenamiento sin una guarda visible de capacidad o ruta de redimensionamiento.", evidence=method.signature, confidence="medium")

    if re.search(r"\bnew\b", body):
        stats["allocations"] += 1
        add("SEC_MANUAL_ALLOCATION", "INFO", f"{method.qualified_name} usa asignación manual; vincúlala con un invariante de ownership y revisión de destructor.", evidence="new", confidence="high")
    if re.search(r"\bdelete\b", body):
        add("SEC_MANUAL_DEALLOCATION", "INFO", f"{method.qualified_name} usa liberación manual; verifica que no haya rutas double-free/use-after-free.", evidence="delete", confidence="high")
    if re.search(r"assert\s*\(", body) and not method.requires:
        add("SEC_ASSERT_ONLY_PRECONDITION", "INFO", f"{method.qualified_name} depende de assert(); los builds release pueden eliminarlo. Prefiere // requires explícitos.", evidence="assert(...)" , confidence="high")
    if re.search(r"\b(memcpy|memmove|strcpy|strncpy|sprintf|gets)\s*\(", body):
        add("SEC_UNSAFE_C_API", "WARNING", f"{method.qualified_name} usa una API C que necesita revisión de límites.", evidence="C API call", confidence="high")

    if deep:
        dec_pat = re.compile(r"(?:--\s*(n|size_|_size|size|len|length|count)\b|\b(n|size_|_size|size|len|length|count)\s*--|\b(n|size_|_size|size|len|length|count)\s*=\s*\3\s*-\s*1)")
        dm = dec_pat.search(body)
        if dm and not _has_nonempty_precondition(reqs):
            add("SEC_UNDERFLOW_RISK", "WARNING", f"{method.qualified_name} decrementa una variable tipo tamaño sin una precondición visible de no vacío.", offset=dm.start(), evidence=dm.group(0))

        ov_pat = re.compile(r"\b(capacity|capacity_|_capacity|n|size_|_size|i|j)\b\s*(?:\*\s*2|\+\s*\d+)|(?:2\s*\*\s*\b(capacity|capacity_|_capacity|n|size_|_size|i|j)\b)")
        om = ov_pat.search(body)
        if om and not re.search(r"max|limit|overflow|numeric_limits", body, re.I):
            add("SEC_OVERFLOW_RISK", "INFO", f"{method.qualified_name} realiza aritmética de tamaño/capacidad que puede desbordar con tamaños grandes.", offset=om.start(), evidence=om.group(0), confidence="low")

        div_pat = re.compile(r"(?:%|/)\s*(capacity\s*\(\)|capacity_|_capacity|n|size_|_size|size\s*\(\))")
        div = div_pat.search(body)
        if div and not any(x in norm_reqs for x in ["capacity()>0", "capacity_>0", "_capacity>0", "n>0", "size_>0", "size()>0"]):
            add("SEC_MODULO_ZERO_RISK", "WARNING", f"{method.qualified_name} usa módulo/división por una expresión de capacidad/tamaño sin una guarda visible de no cero.", offset=div.start(), evidence=div.group(0))

        ptr_pat = re.compile(r"\b([A-Za-z_]\w*)\s*->")
        for pm in ptr_pat.finditer(body):
            ptr = pm.group(1)
            if ptr not in {"this"} and f"{ptr}!=nullptr" not in norm_reqs and f"{ptr}!=NULL" not in norm_reqs and f"{ptr}" not in {"root", "u", "v"}:
                add("SEC_NULL_DEREF_RISK", "WARNING", f"{method.qualified_name} desreferencia `{ptr}` sin un contrato visible de no nulidad.", offset=pm.start(), evidence=pm.group(0), confidence="low", pointer=ptr)
                break
    return stats


def security_rules_catalog() -> list[dict[str, Any]]:
    return [asdict(r) for r in SECURITY_RULES]


def security_project(root: Path, headers_only: bool = False, deep: bool = False) -> ProjectReport:
    report = ProjectReport(root=str(root))
    classes = scan_project(root, headers_only=headers_only)
    if not classes:
        report.diagnostics.append(Diagnostic(level="WARNING", code="NO_SECURITY_TARGETS", message="No se detectaron clases C++.", file=str(root)))
        return report

    totals = {"classes": len(classes), "methods": 0, "raw_indexes": 0, "asserts": 0, "allocations": 0, "deep_findings": 0}
    for cls in classes:
        _detect_resource_rule(report, cls, deep=deep)
        _detect_uninitialized_fields(report, cls, deep=deep)
        for method in cls.methods:
            totals["methods"] += 1
            stats = _detect_method_security(report, cls, method, deep=deep)
            for k, v in stats.items():
                totals[k] += v

    report.diagnostics.insert(0, Diagnostic(
        level="INFO",
        code="SEC_SECURITY_SUMMARY",
        message=f"Escaneo de seguridad completado: {totals['classes']} clases, {totals['methods']} métodos, {totals['raw_indexes']} accesos indexados, deep={deep}.",
        file=str(root),
        details={**totals, "deep": deep, "rules": len(SECURITY_RULES)},
    ))
    if len(report.diagnostics) == 1:
        report.diagnostics.append(Diagnostic(level="INFO", code="SEC_NO_FINDINGS", message="No se encontraron hallazgos orientados a seguridad en el escaneo actual.", file=str(root)))
    return report


def write_security_json(report: ProjectReport, path: Path) -> Path:
    payload = {
        "root": report.root,
        "counts": report.counts(),
        "rules": security_rules_catalog(),
        "diagnostics": [asdict(d) for d in report.diagnostics],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_security_rules_json(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"rules": security_rules_catalog()}, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
