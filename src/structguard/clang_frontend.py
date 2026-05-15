from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
import json
import shutil
import subprocess
from typing import Any

from .cppscan import iter_cpp_files
from .model import Diagnostic, ProjectReport


@dataclass
class ClangRecordModel:
    name: str
    kind: str
    file: str | None = None
    line: int | None = None
    fields: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)


@dataclass
class ClangUnitSummary:
    file: str
    ok: bool
    clang: str
    exit_code: int
    ast_nodes: int = 0
    records: int = 0
    classes: int = 0
    methods: int = 0
    fields: int = 0
    functions: int = 0
    templates: int = 0
    record_models: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: str = ""
    command: list[str] | None = None


def find_clang(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit

    for name in ("clang++", "clang-18", "clang-17", "clang-16", "clang"):
        found = shutil.which(name)
        if found:
            return found

    return None


def default_include_dirs(root: Path) -> list[Path]:
    root = root.resolve()
    dirs = {root}

    for child in root.rglob("include") if root.is_dir() else []:
        if child.is_dir():
            dirs.add(child.resolve())

    # CC-232 tiene directorios include por semana.
    # También se agregan padres de archivos .h.
    if root.is_dir():
        for f in root.rglob("*.h"):
            dirs.add(f.parent.resolve())

    return sorted(dirs)


def _loc_file(node: dict[str, Any]) -> str | None:
    loc = node.get("loc") or {}
    if isinstance(loc, dict) and loc.get("file"):
        return str(loc.get("file"))

    rng = node.get("range") or {}
    if isinstance(rng, dict):
        begin = rng.get("begin") or {}
        if isinstance(begin, dict) and begin.get("file"):
            return str(begin.get("file"))

    return None


def _loc_line(node: dict[str, Any]) -> int | None:
    loc = node.get("loc") or {}
    if isinstance(loc, dict) and isinstance(loc.get("line"), int):
        return loc.get("line")

    rng = node.get("range") or {}
    if isinstance(rng, dict):
        begin = rng.get("begin") or {}
        if isinstance(begin, dict) and isinstance(begin.get("line"), int):
            return begin.get("line")

    return None


def _node_in_target(node: dict[str, Any], target: Path) -> bool:
    loc = _loc_file(node)
    if not loc:
        return True

    try:
        return Path(loc).resolve() == target.resolve()
    except Exception:
        return str(target) in loc or loc.endswith(target.name)


def extract_ast_record_models(
    ast: dict[str, Any],
    target: Path,
) -> list[ClangRecordModel]:
    """Construye un índice ligero de clases/structs directamente desde el AST JSON de Clang.

    Esto entrega a los reportes posteriores un modelo real basado en AST para
    registros, campos y métodos, en lugar de usar Clang únicamente como puerta
    de validación sintáctica. Los cuerpos de métodos siguen viniendo del
    intérprete/frontend acotado existente.
    """
    records: list[ClangRecordModel] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return

        kind = node.get("kind")

        if (
            kind == "CXXRecordDecl"
            and node.get("name")
            and _node_in_target(node, target)
        ):
            rec = ClangRecordModel(
                name=str(node.get("name")),
                kind=str(node.get("tagUsed") or "record"),
                file=_loc_file(node),
                line=_loc_line(node),
            )

            for child in node.get("inner") or []:
                if not isinstance(child, dict):
                    continue

                ckind = child.get("kind")
                cname = child.get("name")

                if ckind == "FieldDecl" and cname:
                    rec.fields.append(str(cname))

                elif (
                    ckind
                    in {
                        "CXXMethodDecl",
                        "CXXConstructorDecl",
                        "CXXDestructorDecl",
                        "CXXConversionDecl",
                    }
                    and cname
                ):
                    rec.methods.append(str(cname))

                elif ckind == "CXXBaseSpecifier":
                    qtype = child.get("type") or {}
                    if isinstance(qtype, dict) and qtype.get("qualType"):
                        rec.bases.append(str(qtype.get("qualType")))

            records.append(rec)

        for child in node.get("inner") or []:
            walk(child)

    walk(ast)

    # Eliminar duplicados de declaraciones forward y especializaciones repetidas de plantillas.
    dedup: dict[tuple[str, str | None, int | None], ClangRecordModel] = {}

    for rec in records:
        key = (rec.name, rec.file, rec.line)
        old = dedup.get(key)

        if not old or len(rec.fields) + len(rec.methods) > len(old.fields) + len(old.methods):
            dedup[key] = rec

    return list(dedup.values())


def _count_ast(node: Any, target: Path, counts: dict[str, int]) -> None:
    if not isinstance(node, dict):
        return

    kind = node.get("kind")
    loc = _loc_file(node)

    in_target = False
    if loc:
        try:
            in_target = Path(loc).resolve() == target.resolve()
        except Exception:
            in_target = str(target) in loc or loc.endswith(target.name)

    # Algunas declaraciones en dumps AST de cabeceras no tienen archivo en hijos;
    # se cuentan nodos nombrados de forma conservadora.
    if in_target or loc is None:
        counts["ast_nodes"] += 1

        if kind == "CXXRecordDecl":
            counts["records"] += 1
            if node.get("name"):
                counts["classes"] += 1

        elif kind in {
            "CXXMethodDecl",
            "CXXConstructorDecl",
            "CXXDestructorDecl",
            "CXXConversionDecl",
        }:
            counts["methods"] += 1

        elif kind == "FieldDecl":
            counts["fields"] += 1

        elif kind in {"FunctionDecl"}:
            counts["functions"] += 1

        elif kind in {
            "FunctionTemplateDecl",
            "ClassTemplateDecl",
            "TypeAliasTemplateDecl",
        }:
            counts["templates"] += 1

    for child in node.get("inner") or []:
        _count_ast(child, target, counts)


def run_clang_ast(
    file: Path,
    *,
    clang: str | None = None,
    include_dirs: list[Path] | None = None,
    std: str = "c++17",
    timeout: int = 12,
    ast_filter: str | None = "auto",
) -> tuple[ClangUnitSummary, dict[str, Any] | None]:
    clang_bin = find_clang(clang)

    if not clang_bin:
        return (
            ClangUnitSummary(
                file=str(file),
                ok=False,
                clang="",
                exit_code=127,
                diagnostics="No se encontró clang++.",
            ),
            None,
        )

    include_dirs = include_dirs or []

    cmd = [
        clang_bin,
        f"-std={std}",
        "-x",
        "c++",
        "-fsyntax-only",
        "-fno-color-diagnostics",
        "-Wno-everything",
    ]

    for inc in include_dirs:
        cmd.extend(["-I", str(inc)])

    cmd.extend(["-Xclang", "-ast-dump=json"])

    if ast_filter:
        filt = file.stem if ast_filter == "auto" else ast_filter
        cmd.extend(["-Xclang", "-ast-dump-filter", "-Xclang", filt])

    cmd.append(str(file))

    try:
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout,
        )

    except subprocess.TimeoutExpired:
        return (
            ClangUnitSummary(
                file=str(file),
                ok=False,
                clang=clang_bin,
                exit_code=124,
                diagnostics=f"El dump AST de Clang excedió el tiempo límite de {timeout}s.",
                command=cmd,
            ),
            None,
        )

    except OSError as e:
        return (
            ClangUnitSummary(
                file=str(file),
                ok=False,
                clang=clang_bin,
                exit_code=126,
                diagnostics=str(e),
                command=cmd,
            ),
            None,
        )

    ast = None
    record_models: list[dict[str, Any]] = []
    counts = {
        "ast_nodes": 0,
        "records": 0,
        "classes": 0,
        "methods": 0,
        "fields": 0,
        "functions": 0,
        "templates": 0,
    }

    if proc.stdout.strip():
        try:
            ast = json.loads(proc.stdout)
            _count_ast(ast, file, counts)
            record_models = [
                asdict(r)
                for r in extract_ast_record_models(ast, file)
            ]

        except Exception as e:
            ast = None
            proc_stderr = (
                (proc.stderr or "")
                + f"\nNo se pudo interpretar el AST JSON de Clang: {e}"
            )

        else:
            proc_stderr = proc.stderr or ""

    else:
        proc_stderr = proc.stderr or "No se emitió AST."

    summary = ClangUnitSummary(
        file=str(file),
        ok=proc.returncode == 0 and ast is not None,
        clang=clang_bin,
        exit_code=proc.returncode,
        diagnostics=proc_stderr.strip(),
        command=cmd,
        record_models=record_models,
        **counts,
    )

    return summary, ast


def clang_summaries(
    root: Path,
    *,
    headers_only: bool = False,
    clang: str | None = None,
    std: str = "c++17",
    max_files: int | None = 30,
    timeout: int = 12,
    ast_filter: str | None = "auto",
) -> list[ClangUnitSummary]:
    files = list(iter_cpp_files(root, headers_only=headers_only))

    if max_files is not None:
        files = files[:max_files]

    include_dirs = default_include_dirs(root if root.is_dir() else root.parent)

    out: list[ClangUnitSummary] = []

    for f in files:
        s, _ = run_clang_ast(
            f,
            clang=clang,
            include_dirs=include_dirs,
            std=std,
            timeout=timeout,
            ast_filter=ast_filter,
        )
        out.append(s)

    return out


def clang_frontend_project(
    root: Path,
    *,
    headers_only: bool = False,
    clang: str | None = None,
    std: str = "c++17",
    max_files: int | None = 30,
    timeout: int = 12,
    ast_filter: str | None = None,
) -> ProjectReport:
    report = ProjectReport(root=str(root))

    summaries = clang_summaries(
        root,
        headers_only=headers_only,
        clang=clang,
        std=std,
        max_files=max_files,
        timeout=timeout,
        ast_filter=ast_filter,
    )

    if not summaries:
        report.diagnostics.append(
            Diagnostic(
                level="WARNING",
                code="CLANG_NO_FILES",
                message="No se encontraron archivos C++ para el frontend de Clang.",
                file=str(root),
            )
        )
        return report

    totals = {
        "files": len(summaries),
        "ok": sum(1 for s in summaries if s.ok),
        "failed": sum(1 for s in summaries if not s.ok),
        "classes": sum(s.classes for s in summaries),
        "methods": sum(s.methods for s in summaries),
        "fields": sum(s.fields for s in summaries),
        "templates": sum(s.templates for s in summaries),
        "functions": sum(s.functions for s in summaries),
        "ast_nodes": sum(s.ast_nodes for s in summaries),
        "ast_record_models": sum(len(s.record_models) for s in summaries),
        "clang": summaries[0].clang if summaries else find_clang(clang),
    }

    report.diagnostics.append(
        Diagnostic(
            level="INFO",
            code="CLANG_FRONTEND_SUMMARY",
            message="Frontend AST real de Clang completado.",
            file=str(root),
            details=totals,
        )
    )

    for s in summaries:
        level = "INFO" if s.ok else "WARNING"
        code = "CLANG_FILE_OK" if s.ok else "CLANG_FILE_FAILED"

        msg = (
            f"{Path(s.file).name}: "
            f"{s.classes} clases, "
            f"{s.methods} métodos, "
            f"{s.fields} campos, "
            f"{s.templates} plantillas."
        )

        if not s.ok:
            msg = (
                f"{Path(s.file).name}: "
                "Clang no pudo analizar completamente esta unidad de traducción."
            )

        report.diagnostics.append(
            Diagnostic(
                level=level,
                code=code,
                message=msg,
                file=s.file,
                details=asdict(s),
            )
        )

    return report


def strict_ast_project(
    root: Path,
    *,
    headers_only: bool = False,
    clang: str | None = None,
    std: str = "c++17",
    max_files: int | None = 30,
    timeout: int = 12,
    ast_filter: str | None = None,
) -> ProjectReport:
    """Ejecuta Clang como puerta estricta de parseo antes del análisis acotado/heurístico.

    Esto no prueba contratos. Solo asegura que el C++ analizado pueda ser
    parseado por un frontend real de Clang. Los resultados de StructGuard
    basados en regex deben tomarse con menor confianza cuando esta puerta
    no está habilitada o no puede ejecutarse.
    """
    report = ProjectReport(root=str(root))

    summaries = clang_summaries(
        root,
        headers_only=headers_only,
        clang=clang,
        std=std,
        max_files=max_files,
        timeout=timeout,
        ast_filter=ast_filter,
    )

    if not summaries:
        report.diagnostics.append(
            Diagnostic(
                level="FAILED",
                code="STRICT_AST_NO_FILES",
                message="El modo AST estricto no encontró archivos C++ para analizar.",
                file=str(root),
            )
        )
        return report

    missing_clang = any(s.exit_code == 127 for s in summaries)
    failed = [s for s in summaries if not s.ok]

    totals = {
        "files": len(summaries),
        "failed_files": len(failed),
        "classes": sum(s.classes for s in summaries),
        "methods": sum(s.methods for s in summaries),
        "fields": sum(s.fields for s in summaries),
        "templates": sum(s.templates for s in summaries),
        "clang": summaries[0].clang if summaries else find_clang(clang),
        "std": std,
        "max_files": max_files,
        "ast_record_models": sum(len(s.record_models) for s in summaries),
    }

    if missing_clang:
        report.diagnostics.append(
            Diagnostic(
                level="FAILED",
                code="STRICT_AST_CLANG_NOT_FOUND",
                message=(
                    "El modo AST estricto requiere clang++/clang, "
                    "pero no se encontró ninguno."
                ),
                file=str(root),
                details=totals,
            )
        )

    elif failed:
        report.diagnostics.append(
            Diagnostic(
                level="FAILED",
                code="STRICT_AST_FAILED",
                message=(
                    f"El modo AST estricto falló: {len(failed)} archivo(s) C++ "
                    "no pudieron ser analizados por Clang."
                ),
                file=str(root),
                details=totals,
            )
        )

    else:
        report.diagnostics.append(
            Diagnostic(
                level="INFO",
                code="STRICT_AST_PASSED",
                message=(
                    f"El modo AST estricto pasó: "
                    f"Clang analizó {len(summaries)} archivo(s) C++."
                ),
                file=str(root),
                details=totals,
            )
        )

    for s in summaries:
        if s.ok:
            report.diagnostics.append(
                Diagnostic(
                    level="INFO",
                    code="STRICT_AST_FILE_OK",
                    message=f"{Path(s.file).name}: Clang analizó este archivo.",
                    file=s.file,
                    details=asdict(s),
                )
            )
        else:
            report.diagnostics.append(
                Diagnostic(
                    level="FAILED",
                    code="STRICT_AST_FILE_FAILED",
                    message=(
                        f"{Path(s.file).name}: Clang no pudo analizar este archivo "
                        "en modo AST estricto."
                    ),
                    file=s.file,
                    details=asdict(s),
                )
            )

    return report


def write_clang_json(summaries: list[ClangUnitSummary], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            [asdict(s) for s in summaries],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return out