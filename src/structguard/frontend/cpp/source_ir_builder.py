from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from structguard.cppscan import iter_cpp_files, scan_project
from structguard.ir.source_ir import (
    SourceDiagnostic,
    SourceFieldIR,
    SourceFileIR,
    SourceIR,
    SourceLocation,
    SourceMethodIR,
    SourceStructureIR,
)

from .clang_adapter import ClangFrontendConfig, parse_translation_unit
from .compile_commands import CompileDatabase, CompileCommandsError, load_compile_commands


def _location(node: dict[str, Any], default_file: Path) -> SourceLocation:
    loc = node.get("loc") if isinstance(node.get("loc"), dict) else {}
    file_name = str(loc.get("file") or default_file)
    return SourceLocation(file=file_name, line=int(loc.get("line") or 0), column=int(loc.get("col") or 0))


def _extract_includes(text: str) -> list[str]:
    return re.findall(r'^\s*#\s*include\s+[<"]([^>"]+)[>"]', text, re.M)


def _extract_namespaces(text: str) -> list[str]:
    return sorted(set(re.findall(r"\bnamespace\s+([A-Za-z_]\w*)\s*\{", text)))


def _method_signature(node: dict[str, Any]) -> str:
    name = str(node.get("name") or "")
    return_type = str(node.get("type", {}).get("qualType") or "") if isinstance(node.get("type"), dict) else ""
    params: list[str] = []
    for child in node.get("inner", []) or []:
        if isinstance(child, dict) and child.get("kind") == "ParmVarDecl":
            param_type = ""
            if isinstance(child.get("type"), dict):
                param_type = str(child["type"].get("qualType") or "")
            param_name = str(child.get("name") or "")
            params.append(f"{param_type} {param_name}".strip())
    return f"{return_type} {name}({', '.join(params)})".strip()


def _field_from_node(node: dict[str, Any], default_file: Path) -> SourceFieldIR | None:
    name = node.get("name")
    if not isinstance(name, str) or not name:
        return None
    type_name = ""
    if isinstance(node.get("type"), dict):
        type_name = str(node["type"].get("qualType") or "")
    return SourceFieldIR(name=name, type_name=type_name, location=_location(node, default_file), access=str(node.get("access") or "unknown"))


def _method_from_node(node: dict[str, Any], default_file: Path, is_template: bool = False) -> SourceMethodIR | None:
    name = node.get("name")
    if not isinstance(name, str) or not name:
        return None
    return_type = ""
    if isinstance(node.get("type"), dict):
        return_type = str(node["type"].get("qualType") or "")
    params: list[str] = []
    for child in node.get("inner", []) or []:
        if isinstance(child, dict) and child.get("kind") == "ParmVarDecl":
            param_type = ""
            if isinstance(child.get("type"), dict):
                param_type = str(child["type"].get("qualType") or "")
            params.append(param_type)
    return SourceMethodIR(
        name=name,
        return_type=return_type,
        parameters=params,
        location=_location(node, default_file),
        signature=_method_signature(node),
        access=str(node.get("access") or "unknown"),
        is_const=" const" in return_type or str(node.get("type", {}).get("qualType", "")).endswith(" const"),
        is_template=is_template,
    )


def _record_from_node(node: dict[str, Any], default_file: Path, namespace: str = "", is_template: bool = False) -> SourceStructureIR | None:
    name = node.get("name")
    if not isinstance(name, str) or not name:
        return None
    if node.get("isImplicit"):
        return None
    if node.get("completeDefinition") is False:
        return None
    tag = str(node.get("tagUsed") or "class")
    structure = SourceStructureIR(name=name, kind=tag, location=_location(node, default_file), namespace=namespace, is_template=is_template)
    for child in node.get("inner", []) or []:
        if not isinstance(child, dict):
            continue
        kind = child.get("kind")
        if kind == "FieldDecl":
            field_ir = _field_from_node(child, default_file)
            if field_ir:
                structure.fields.append(field_ir)
        elif kind in {"CXXMethodDecl", "CXXConstructorDecl", "CXXDestructorDecl", "FunctionDecl"}:
            method_ir = _method_from_node(child, default_file)
            if method_ir:
                structure.methods.append(method_ir)
        elif kind == "FunctionTemplateDecl":
            for nested in child.get("inner", []) or []:
                if isinstance(nested, dict) and nested.get("kind") in {"CXXMethodDecl", "FunctionDecl"}:
                    method_ir = _method_from_node(nested, default_file, is_template=True)
                    if method_ir:
                        structure.methods.append(method_ir)
    return structure


def _walk_ast(node: dict[str, Any], default_file: Path, namespace_stack: list[str], out: list[SourceStructureIR]) -> None:
    kind = node.get("kind")
    if kind == "NamespaceDecl" and isinstance(node.get("name"), str):
        namespace_stack = [*namespace_stack, str(node["name"])]
    if kind == "CXXRecordDecl":
        structure = _record_from_node(node, default_file, "::".join(namespace_stack))
        if structure:
            out.append(structure)
            return
    if kind == "ClassTemplateDecl":
        for child in node.get("inner", []) or []:
            if isinstance(child, dict) and child.get("kind") == "CXXRecordDecl":
                structure = _record_from_node(child, default_file, "::".join(namespace_stack), is_template=True)
                if structure:
                    out.append(structure)
                    return
    for child in node.get("inner", []) or []:
        if isinstance(child, dict):
            _walk_ast(child, default_file, namespace_stack, out)


def _lightweight_source_ir(root: Path, headers_only: bool, reason: str = "") -> SourceIR:
    structures: list[SourceStructureIR] = []
    files: list[SourceFileIR] = []
    for path in iter_cpp_files(root, headers_only=headers_only):
        text = path.read_text(encoding="utf-8", errors="ignore")
        files.append(SourceFileIR(path=str(path), language="cpp", frontend="lightweight", includes=_extract_includes(text), namespaces=_extract_namespaces(text)))
    for cls in scan_project(root, headers_only=headers_only):
        structure = SourceStructureIR(name=cls.name, kind="class", location=SourceLocation(file=str(cls.file), line=cls.start_line), namespace="")
        for field_name in sorted(cls.fields):
            structure.fields.append(SourceFieldIR(name=field_name, type_name="", location=SourceLocation(file=str(cls.file))))
        for method in cls.methods:
            structure.methods.append(SourceMethodIR(name=method.name, return_type="", parameters=[], location=SourceLocation(file=str(cls.file), line=method.start_line), signature=method.signature))
        structures.append(structure)
    diagnostics: list[SourceDiagnostic] = []
    if reason:
        diagnostics.append(SourceDiagnostic(level="WARNING", code="CPP_FRONTEND_LIGHTWEIGHT_FALLBACK", message=reason))
    return SourceIR(root=str(root), language="cpp", frontend="lightweight", files=files, structures=structures, diagnostics=diagnostics)


def _source_files(root: Path, compile_db: CompileDatabase | None, headers_only: bool) -> list[Path]:
    if compile_db:
        return compile_db.files()
    return iter_cpp_files(root, headers_only=headers_only)


def build_cpp_source_ir(
    root: Path,
    compile_commands: Path | None = None,
    clang: str | None = None,
    std: str = "c++17",
    timeout: int = 12,
    headers_only: bool = False,
    fallback_allowed: bool = False,
) -> SourceIR:
    compile_db: CompileDatabase | None = None
    diagnostics: list[SourceDiagnostic] = []
    if compile_commands:
        try:
            compile_db = load_compile_commands(compile_commands)
        except CompileCommandsError as exc:
            diagnostics.append(SourceDiagnostic(level="FAILED", code="CPP_COMPILE_COMMANDS_INVALID", message=str(exc)))
            if not fallback_allowed:
                return SourceIR(root=str(root), language="cpp", frontend="clang", diagnostics=diagnostics)
            fallback = _lightweight_source_ir(root, headers_only=headers_only, reason=str(exc))
            fallback.diagnostics = [*diagnostics, *fallback.diagnostics]
            return fallback

    config = ClangFrontendConfig(clang=clang, std=std, timeout=timeout)
    structures: list[SourceStructureIR] = []
    files: list[SourceFileIR] = []
    source_files = _source_files(root, compile_db, headers_only=headers_only)
    if not source_files:
        return SourceIR(root=str(root), language="cpp", frontend="clang", diagnostics=[SourceDiagnostic(level="WARNING", code="CPP_FRONTEND_NO_FILES", message="No se encontraron archivos C++ para analizar")])

    failed = False
    for file_path in source_files:
        command = compile_db.command_for(file_path) if compile_db else None
        result = parse_translation_unit(file_path, config, command)
        if not result.ok or result.ast is None:
            failed = True
            diagnostics.append(
                SourceDiagnostic(
                    level="FAILED" if not fallback_allowed else "WARNING",
                    code="CPP_CLANG_PARSE_FAILED",
                    message=result.error or "Clang no pudo parsear el archivo C++",
                    location=SourceLocation(file=str(file_path)),
                    details={"stderr": result.stderr[-1200:], "command": result.command},
                )
            )
            continue
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        file_structures: list[SourceStructureIR] = []
        _walk_ast(result.ast, file_path, [], file_structures)
        structures.extend(file_structures)
        files.append(SourceFileIR(path=str(file_path), language="cpp", frontend="clang", includes=_extract_includes(text), namespaces=_extract_namespaces(text)))

    if failed and fallback_allowed:
        fallback = _lightweight_source_ir(root, headers_only=headers_only, reason="Se usó el frontend ligero porque Clang no pudo parsear todos los archivos")
        fallback.diagnostics = [*diagnostics, *fallback.diagnostics]
        return fallback

    return SourceIR(root=str(root), language="cpp", frontend="clang", files=files, structures=structures, diagnostics=diagnostics)
