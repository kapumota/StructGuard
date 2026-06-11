from __future__ import annotations

from pathlib import Path
import re

from .ast import SGDSLContract, SGDSLField, SGDSLMethod, SGDSLModule, SGDSLParam, SGDSLStructure, SourceLocation
from .diagnostics import SGDSLParseError

COMMENT_RE = re.compile(r"(#|//).*?$", re.M)
PACKAGE_RE = re.compile(r"\b(?:package|module)\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*;?", re.I)
STRUCT_RE = re.compile(r"\b(?:structure|class|struct)\s+([*?]?[A-Za-z_][\w*?]*)\s*\{", re.I)
FIELD_RE = re.compile(r"\bfield\s+([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*(?:<[^;{}]+>)?)\s*;", re.I)
METHOD_BLOCK_RE = re.compile(r"\bmethod\s+([~A-Za-z_]\w*)\s*(?:\(([^)]*)\))?\s*\{", re.I)
METHOD_INLINE_RE = re.compile(r"\bmethod\s+([~A-Za-z_]\w*)\s*(?:\(([^)]*)\))?\s+(requires|ensures)\s+(.+?);", re.I | re.S)
CONTRACT_RE = re.compile(r"\b(requires|ensures|invariant)\s+(.+?);", re.I | re.S)


def strip_comments(text: str) -> str:
    return COMMENT_RE.sub("", text)


def line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def find_matching_brace(text: str, open_pos: int) -> int:
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def clean_expr(expr: str) -> str:
    return " ".join(expr.strip().split())


def parse_params(raw_params: str | None) -> list[SGDSLParam]:
    if not raw_params or not raw_params.strip():
        return []
    params: list[SGDSLParam] = []
    for raw in raw_params.split(","):
        item = raw.strip()
        if not item:
            continue
        if ":" in item:
            name, type_name = item.split(":", 1)
            params.append(SGDSLParam(name=name.strip(), type_name=type_name.strip()))
        else:
            params.append(SGDSLParam(name=item.strip()))
    return params


def _parse_method_block(body: str, method_match: re.Match[str], structure_line: int, source: str) -> tuple[SGDSLMethod, int]:
    name = method_match.group(1)
    params = parse_params(method_match.group(2))
    open_brace = body.find("{", method_match.end() - 1)
    close = find_matching_brace(body, open_brace)
    if close == -1:
        raise SGDSLParseError(f"Bloque de método sin cerrar para {name}.", source=source, line=structure_line)
    method_line = structure_line + body.count("\n", 0, method_match.start())
    method = SGDSLMethod(name=name, params=params, location=SourceLocation(source, method_line))
    method_body = body[open_brace + 1:close]
    for contract_match in CONTRACT_RE.finditer(method_body):
        kind = contract_match.group(1).lower()
        expr = clean_expr(contract_match.group(2))
        contract = SGDSLContract(kind=kind, expression=expr, location=SourceLocation(source, method_line + method_body.count("\n", 0, contract_match.start())))
        if kind == "requires":
            method.requires.append(contract)
        elif kind == "ensures":
            method.ensures.append(contract)
    return method, close + 1


def parse_sgdsl_text(text: str, source: str = "<memoria>") -> SGDSLModule:
    clean = strip_comments(text)
    module = SGDSLModule(source=source)
    package_match = PACKAGE_RE.search(clean)
    if package_match:
        module.package = package_match.group(1)

    pos = 0
    while True:
        structure_match = STRUCT_RE.search(clean, pos)
        if not structure_match:
            break
        name = structure_match.group(1)
        open_brace = clean.find("{", structure_match.end() - 1)
        close = find_matching_brace(clean, open_brace)
        struct_line = line_no(clean, structure_match.start())
        if close == -1:
            raise SGDSLParseError(f"Bloque de estructura sin cerrar para {name}.", source=source, line=struct_line)
        body = clean[open_brace + 1:close]
        structure = SGDSLStructure(name=name, location=SourceLocation(source, struct_line))

        spans: list[tuple[int, int]] = []
        method_pos = 0
        while True:
            method_match = METHOD_BLOCK_RE.search(body, method_pos)
            if not method_match:
                break
            method, end_pos = _parse_method_block(body, method_match, struct_line, source)
            structure.methods.append(method)
            spans.append((method_match.start(), end_pos))
            method_pos = end_pos

        chars = list(body)
        for start, end in spans:
            for i in range(start, end):
                chars[i] = " "
        structure_body = "".join(chars)

        for field_match in FIELD_RE.finditer(structure_body):
            field_line = struct_line + structure_body.count("\n", 0, field_match.start())
            structure.fields.append(SGDSLField(name=field_match.group(1), type_name=field_match.group(2).strip(), location=SourceLocation(source, field_line)))

        structure_body_without_fields = FIELD_RE.sub(" ", structure_body)
        for contract_match in CONTRACT_RE.finditer(structure_body_without_fields):
            kind = contract_match.group(1).lower()
            if kind != "invariant":
                continue
            contract_line = struct_line + structure_body_without_fields.count("\n", 0, contract_match.start())
            structure.invariants.append(SGDSLContract(kind=kind, expression=clean_expr(contract_match.group(2)), location=SourceLocation(source, contract_line)))

        for inline_match in METHOD_INLINE_RE.finditer(structure_body_without_fields):
            method_line = struct_line + structure_body_without_fields.count("\n", 0, inline_match.start())
            method = SGDSLMethod(name=inline_match.group(1), params=parse_params(inline_match.group(2)), location=SourceLocation(source, method_line))
            contract = SGDSLContract(
                kind=inline_match.group(3).lower(),
                expression=clean_expr(inline_match.group(4)),
                location=SourceLocation(source, method_line),
            )
            if contract.kind == "requires":
                method.requires.append(contract)
            else:
                method.ensures.append(contract)
            structure.methods.append(method)

        module.structures.append(structure)
        pos = close + 1

    if not module.structures:
        raise SGDSLParseError("No se encontraron bloques structure, class o struct en el contrato.", source=source)
    return module


def parse_sgdsl_file(path: Path) -> SGDSLModule:
    return parse_sgdsl_text(path.read_text(encoding="utf-8"), source=str(path))


def load_sgdsl(paths: list[str | Path]) -> list[SGDSLModule]:
    modules: list[SGDSLModule] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            files = sorted(path.rglob("*.sgdsl")) + sorted(path.rglob("*.sg")) + sorted(path.rglob("*.structguard"))
            for file in files:
                modules.append(parse_sgdsl_file(file))
        else:
            modules.append(parse_sgdsl_file(path))
    return modules
