from __future__ import annotations

import re
from pathlib import Path

from structguard.cppscan import find_matching_brace, line_no, scan_project
from structguard.model import ClassModel, MethodModel

from .model import (
    CapacityRelation,
    ClassMemoryModel,
    MemoryAllocation,
    MemoryLocation,
    MemoryRelease,
    NullAssignment,
    PointerDereference,
    PointerField,
)

SIZE_FIELD_NAMES = {"n", "size", "size_", "_size", "length", "len", "count", "m_size"}
CAPACITY_FIELD_NAMES = {"capacity", "capacity_", "_capacity", "cap", "m_capacity"}


def build_memory_models(root: Path, headers_only: bool = False) -> list[ClassMemoryModel]:
    models: list[ClassMemoryModel] = []
    for cls in scan_project(root, headers_only=headers_only):
        models.append(build_class_memory_model(cls))
    return models


def build_class_memory_model(cls: ClassModel) -> ClassMemoryModel:
    text = _read_text(cls.file)
    class_body, class_start_line = _class_body(text, cls.name)
    pointer_fields = _extract_pointer_fields(cls, class_body, class_start_line)
    pointer_names = {field.name for field in pointer_fields}
    model = ClassMemoryModel(class_name=cls.name, file=str(cls.file), pointer_fields=pointer_fields)
    for method in cls.methods:
        method_source = _method_source(method)
        model.allocations.extend(_extract_allocations(cls.name, method, method_source, cls.file))
        model.releases.extend(_extract_releases(cls.name, method, method_source, cls.file))
        model.null_assignments.extend(_extract_null_assignments(cls.name, method, method_source, cls.file, pointer_names))
        model.dereferences.extend(_extract_dereferences(cls.name, method, method_source, cls.file, pointer_names))
        model.capacity_relations.extend(_extract_capacity_relations(cls.name, method, method_source, cls.file, cls.fields))
    return model


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _class_body(text: str, class_name: str) -> tuple[str, int]:
    pattern = re.compile(rf"\b(?:class|struct)\s+{re.escape(class_name)}\b")
    match = pattern.search(text)
    if not match:
        return "", 1
    brace = text.find("{", match.end())
    if brace == -1:
        return "", line_no(text, match.start())
    end = find_matching_brace(text, brace)
    if end == -1:
        return "", line_no(text, brace)
    return text[brace + 1 : end], line_no(text, brace + 1)


def _extract_pointer_fields(cls: ClassModel, class_body: str, base_line: int) -> list[PointerField]:
    fields: list[PointerField] = []
    for offset, raw in enumerate(class_body.splitlines()):
        line = raw.strip()
        if not line or not line.endswith(";"):
            continue
        if line in {"public:", "private:", "protected:"}:
            continue
        if "(" in line and ")" in line and "=" not in line:
            continue
        if "*" not in line:
            continue
        for name, initialized_null in _pointer_names_from_declaration(line):
            if name in cls.fields or name not in {"public", "private", "protected"}:
                fields.append(
                    PointerField(
                        class_name=cls.name,
                        name=name,
                        location=MemoryLocation(file=str(cls.file), line=base_line + offset),
                        initialized_null=initialized_null,
                    )
                )
    return fields


def _pointer_names_from_declaration(line: str) -> list[tuple[str, bool]]:
    statement = line.rstrip(";").strip()
    statement = re.sub(r"^(?:public|private|protected)\s*:\s*", "", statement)
    parts = [part.strip() for part in statement.split(",") if part.strip()]
    out: list[tuple[str, bool]] = []
    for part in parts:
        if "*" not in part:
            continue
        name_part = re.split(r"=|\{|\(", part, maxsplit=1)[0].strip()
        name_part = re.sub(r"\[[^]]*\]", "", name_part).strip()
        match = re.search(r"(?:^|[\s*])([A-Za-z_]\w*)$", name_part)
        if match:
            name = match.group(1)
            initialized_null = bool(re.search(r"=\s*(?:nullptr|NULL|0)\b|\(\s*(?:nullptr|NULL|0)\s*\)", part))
            out.append((name, initialized_null))
    return out


def _method_source(method: MethodModel) -> str:
    return "\n".join(part for part in [method.signature, method.body or ""] if part)


def _clean_target(target: str) -> str:
    return target.replace("this->", "").strip()


def _line_for(source: str, start_line: int, offset: int) -> int:
    return start_line + source.count("\n", 0, max(0, offset))


def _extract_allocations(class_name: str, method: MethodModel, source: str, file: Path) -> list[MemoryAllocation]:
    allocations: list[MemoryAllocation] = []
    pattern = re.compile(
        r"(?P<target>(?:this->)?[A-Za-z_]\w*)\s*(?:=|\()\s*new\s+"
        r"(?P<type>[A-Za-z_:][\w:<>\s]*)\s*(?P<array>\[[^\]]*\])?"
    )
    for match in pattern.finditer(source):
        kind = "array" if match.group("array") else "single"
        allocations.append(
            MemoryAllocation(
                class_name=class_name,
                method_name=method.name,
                target=_clean_target(match.group("target")),
                kind=kind,
                location=MemoryLocation(file=str(file), line=_line_for(source, method.start_line, match.start())),
                expression=" ".join(match.group(0).split()),
            )
        )
    return allocations


def _extract_releases(class_name: str, method: MethodModel, source: str, file: Path) -> list[MemoryRelease]:
    releases: list[MemoryRelease] = []
    pattern = re.compile(r"\bdelete\s*(?P<array>\[\])?\s*(?P<target>(?:this->)?[A-Za-z_]\w*)\b")
    for match in pattern.finditer(source):
        kind = "array" if match.group("array") else "single"
        releases.append(
            MemoryRelease(
                class_name=class_name,
                method_name=method.name,
                target=_clean_target(match.group("target")),
                kind=kind,
                location=MemoryLocation(file=str(file), line=_line_for(source, method.start_line, match.start())),
                expression=" ".join(match.group(0).split()),
            )
        )
    return releases


def _extract_null_assignments(class_name: str, method: MethodModel, source: str, file: Path, pointer_names: set[str]) -> list[NullAssignment]:
    assignments: list[NullAssignment] = []
    for pointer in pointer_names:
        pattern = re.compile(rf"\b(?:this->)?{re.escape(pointer)}\s*=\s*(?:nullptr|NULL|0)\b")
        for match in pattern.finditer(source):
            assignments.append(
                NullAssignment(
                    class_name=class_name,
                    method_name=method.name,
                    target=pointer,
                    location=MemoryLocation(file=str(file), line=_line_for(source, method.start_line, match.start())),
                )
            )
    return assignments


def _extract_dereferences(class_name: str, method: MethodModel, source: str, file: Path, pointer_names: set[str]) -> list[PointerDereference]:
    dereferences: list[PointerDereference] = []
    for pointer in pointer_names:
        patterns = [
            ("star", re.compile(rf"(?<![\w])\*\s*(?:this->)?{re.escape(pointer)}\b")),
            ("arrow", re.compile(rf"\b(?:this->)?{re.escape(pointer)}\s*->")),
            ("index", re.compile(rf"\b(?:this->)?{re.escape(pointer)}\s*\[")),
        ]
        guarded = _has_null_guard(source, pointer)
        for access, pattern in patterns:
            for match in pattern.finditer(source):
                dereferences.append(
                    PointerDereference(
                        class_name=class_name,
                        method_name=method.name,
                        target=pointer,
                        access=access,
                        location=MemoryLocation(file=str(file), line=_line_for(source, method.start_line, match.start())),
                        guarded=guarded,
                    )
                )
    return dereferences


def _has_null_guard(source: str, pointer: str) -> bool:
    normalized = source.replace(" ", "")
    return any(
        guard in normalized
        for guard in (
            f"{pointer}!=nullptr",
            f"nullptr!={pointer}",
            f"{pointer}!=NULL",
            f"NULL!={pointer}",
            f"if({pointer})",
            f"if(this->{pointer})",
        )
    )


def _is_multiplication_context(source: str, start: int) -> bool:
    left = source[max(0, start - 3) : start]
    return bool(re.search(r"[A-Za-z0-9_)]\s*$", left))


def _extract_capacity_relations(class_name: str, method: MethodModel, source: str, file: Path, fields: set[str]) -> list[CapacityRelation]:
    relations: list[CapacityRelation] = []
    size_fields = [field for field in fields if field in SIZE_FIELD_NAMES]
    capacity_fields = [field for field in fields if field in CAPACITY_FIELD_NAMES]
    for size_field in size_fields:
        for capacity_field in capacity_fields:
            patterns = [
                ("size_may_exceed_capacity", re.compile(rf"\b(?:this->)?{re.escape(size_field)}\s*=\s*(?:this->)?{re.escape(capacity_field)}\s*\+")),
                ("capacity_below_size", re.compile(rf"\b(?:this->)?{re.escape(capacity_field)}\s*=\s*(?:this->)?{re.escape(size_field)}\s*-")),
                ("explicit_size_greater_than_capacity", re.compile(rf"\b(?:this->)?{re.escape(size_field)}\s*>\s*(?:this->)?{re.escape(capacity_field)}\b")),
            ]
            for relation, pattern in patterns:
                for match in pattern.finditer(source):
                    relations.append(
                        CapacityRelation(
                            class_name=class_name,
                            method_name=method.name,
                            size_field=size_field,
                            capacity_field=capacity_field,
                            relation=relation,
                            location=MemoryLocation(file=str(file), line=_line_for(source, method.start_line, match.start())),
                            expression=" ".join(match.group(0).split()),
                        )
                    )
    return relations
