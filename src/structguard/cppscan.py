from __future__ import annotations

from pathlib import Path
import re
from .model import ClassModel, Contract, MethodModel

CONTRACT_RE = re.compile(r"//\s*(requires|ensures|invariant)\s*:?\s*(.+)", re.I)
HEADER_EXTS = {".h", ".hh", ".hpp", ".hxx"}
CPP_EXTS = HEADER_EXTS | {".cpp", ".cc", ".cxx"}
CONTROL_KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "sizeof"}
CLASS_RE = re.compile(r"\b(class|struct)\s+([A-Za-z_]\w*)\b")


def iter_cpp_files(root: Path, headers_only: bool = False) -> list[Path]:
    if root.is_file():
        return [root]
    exts = HEADER_EXTS if headers_only else CPP_EXTS
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in exts)


def line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def find_matching_brace(text: str, open_pos: int) -> int:
    depth = 0
    i = open_pos
    n = len(text)
    in_line = in_block = in_str = False
    quote = ""
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_line:
            if ch == "\n":
                in_line = False
            i += 1; continue
        if in_block:
            if ch == "*" and nxt == "/":
                in_block = False; i += 2; continue
            i += 1; continue
        if in_str:
            if ch == "\\":
                i += 2; continue
            if ch == quote:
                in_str = False
            i += 1; continue
        if ch == "/" and nxt == "/":
            in_line = True; i += 2; continue
        if ch == "/" and nxt == "*":
            in_block = True; i += 2; continue
        if ch in {'"', "'"}:
            in_str = True; quote = ch; i += 1; continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _line_start(text: str, pos: int) -> int:
    return text.rfind("\n", 0, pos) + 1


def _is_false_class_match(text: str, m: re.Match) -> bool:
    ls = _line_start(text, m.start())
    line_prefix = text[ls:m.start()]
    if "friend" in line_prefix:
        return True
    left = text[max(0, m.start() - 40):m.start()]
    right = text[m.end():m.end()+10].lstrip()
    if "template" in left and "<" in left and ">" not in left:
        return True
    if right.startswith((">", ",")):
        return True
    return False


def strip_templates(sig: str) -> str:
    prev = None
    while prev != sig:
        prev = sig
        sig = re.sub(r"<[^<>]*>", "", sig)
    return sig


def method_name_from_signature(signature: str, class_name: str) -> str | None:
    if "(" not in signature:
        return None
    before = signature.split("(", 1)[0].strip()
    before = re.sub(r"\b(inline|virtual|static|constexpr|consteval|constinit|explicit|friend)\b", " ", before)
    before = strip_templates(before)
    parts = [p for p in re.split(r"\s+", before) if p]
    if not parts:
        return None
    name = parts[-1].split("::")[-1].strip("*&~")
    raw = parts[-1].split("::")[-1].strip("*&")
    if raw.startswith("~"):
        return "~" + name
    if name in CONTROL_KEYWORDS or name == "operator":
        return None
    return name or None


def _extract_contract_lines(lines: list[str], base_line: int) -> tuple[list[Contract], list[Contract], list[Contract]]:
    req: list[Contract] = []
    ens: list[Contract] = []
    inv: list[Contract] = []
    for i, raw in enumerate(lines):
        cm = CONTRACT_RE.search(raw)
        if cm:
            c = Contract(kind=cm.group(1).lower(), expression=cm.group(2).strip(), line=base_line + i)
            if c.kind == "requires": req.append(c)
            elif c.kind == "ensures": ens.append(c)
            else: inv.append(c)
    return req, ens, inv


def contiguous_contracts_before(text: str, pos: int) -> tuple[list[Contract], list[Contract], list[Contract]]:
    prefix = text[:pos]
    lines = prefix.splitlines()
    collected: list[tuple[int, str]] = []
    for i in range(len(lines)-1, max(-1, len(lines)-10), -1):
        s = lines[i].strip()
        if not s:
            continue
        if CONTRACT_RE.search(s):
            collected.append((i+1, lines[i])); continue
        if s.startswith("template") or s in {"inline", "template<class T>", "template <class T>"}:
            continue
        break
    collected.reverse()
    req: list[Contract] = []; ens: list[Contract] = []; inv: list[Contract] = []
    for ln, raw in collected:
        cm = CONTRACT_RE.search(raw)
        if not cm: continue
        c = Contract(kind=cm.group(1).lower(), expression=cm.group(2).strip(), line=ln)
        if c.kind == "requires": req.append(c)
        elif c.kind == "ensures": ens.append(c)
        else: inv.append(c)
    return req, ens, inv


def extract_assertions(body: str | None, base_line: int, source: str = "inferred-assert") -> list[Contract]:
    if not body:
        return []
    out: list[Contract] = []
    for m in re.finditer(r"\bassert\s*\((.*?)\)\s*;", body, re.S):
        expr = " ".join(m.group(1).split())
        out.append(Contract(kind="requires", expression=expr, line=base_line + body.count("\n", 0, m.start()), source=source))
    return out


def _mask_brace_blocks(text: str) -> str:
    out=[]; depth=0
    for ch in text:
        if ch == "{":
            depth += 1; out.append(" ")
        elif ch == "}":
            depth = max(0, depth-1); out.append(" ")
        elif depth:
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def extract_fields(body: str) -> set[str]:
    rough = _mask_brace_blocks(body)
    fields: set[str] = set()
    # Campo simple de C++: soporta declaraciones con inicializador por defecto,
    # por ejemplo `int size_ = 0;`, `std::vector<int> data_{};` o `T* p_(nullptr);`.
    decl_re = re.compile(
        r"^\s*(?:protected|private|public)?\s*"
        r"(?:mutable\s+)?(?:const\s+)?"
        r"(?:[A-Za-z_:][\w:<>]*[\s*&]+)+"
        r"([A-Za-z_]\w*)\s*(?:\[[^]]*\])?"
        r"(?:\s*(?:=\s*[^;]+|\{[^;{}]*\}|\([^;()]*\)))?\s*;",
        re.M,
    )
    for m in decl_re.finditer(rough):
        line = m.group(0)
        name = m.group(1)
        if "friend" not in line and name not in {"public", "private", "protected"}:
            fields.add(name)

    # También soporta declaraciones compactas frecuentes en código docente:
    # `int size_, capacity_;`, `T *data_, *tmp_;`, `size_t head_ = 0, tail_ = 0;`.
    for raw in rough.splitlines():
        line = raw.strip()
        if not line or not line.endswith(";"):
            continue
        if line in {"public:", "private:", "protected:"}:
            continue
        if re.search(r"\b(friend|using|typedef|return|if|for|while|switch|static_assert)\b", line):
            continue
        if "(" in line and not re.search(r"\w+\s*\([^;()]*\)\s*;", line):
            continue
        stmt = line[:-1].strip()
        stmt = re.sub(r"^(?:mutable\s+)?(?:const\s+)?", "", stmt)
        parts = [p.strip() for p in stmt.split(",") if p.strip()]
        if len(parts) < 2:
            continue
        for part in parts:
            part = re.split(r"=|\{|\(", part, maxsplit=1)[0].strip()
            part = re.sub(r"\[[^]]*\]", "", part).strip()
            m = re.search(r"(?:^|[\s*&])([A-Za-z_]\w*)$", part)
            if m:
                name = m.group(1)
                if name not in {"public", "private", "protected"} and not name[0].isupper():
                    fields.add(name)
    return fields


def _collect_inline_body(lines: list[str], start: int) -> tuple[str, int]:
    collected = []
    depth = 0
    i = start
    started = False
    while i < len(lines):
        collected.append(lines[i])
        depth += lines[i].count("{") - lines[i].count("}")
        if "{" in lines[i]:
            started = True
        if started and depth <= 0:
            break
        i += 1
    text = "\n".join(collected)
    a = text.find("{"); b = text.rfind("}")
    body = text[a+1:b] if a != -1 and b != -1 and b > a else ""
    return body, i


def parse_class_body(cls: ClassModel, body: str, base_line: int) -> None:
    cls.fields |= extract_fields(body)
    lines = body.splitlines()
    pending_req: list[Contract] = []
    pending_ens: list[Contract] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        current_line = base_line + i
        cm = CONTRACT_RE.search(raw)
        if cm:
            c = Contract(kind=cm.group(1).lower(), expression=cm.group(2).strip(), line=current_line)
            if c.kind == "requires": pending_req.append(c)
            elif c.kind == "ensures": pending_ens.append(c)
            else: cls.invariants.append(c)
            i += 1; continue
        s = raw.strip()
        if not s or s.startswith(("//", "#")) or s in {"public:", "private:", "protected:"}:
            i += 1; continue
        # Combina firmas multilínea hasta que aparezca ; o {.
        sig_lines = [s]
        j = i
        while "(" in " ".join(sig_lines) and not re.search(r"[;{]", " ".join(sig_lines)) and j + 1 < len(lines):
            j += 1; sig_lines.append(lines[j].strip())
        sig = " ".join(sig_lines)
        if "(" in sig and not sig.startswith(("if", "for", "while", "switch")):
            name = method_name_from_signature(sig, cls.name)
            if name:
                body_text = None
                end_i = j
                if "{" in sig:
                    body_text, end_i = _collect_inline_body(lines, i)
                cls.methods.append(MethodModel(class_name=cls.name, name=name, signature=sig, body=body_text, start_line=current_line, requires=pending_req, ensures=pending_ens, assertions=extract_assertions(body_text, current_line)))
                pending_req=[]; pending_ens=[]
                i = end_i + 1; continue
        i += 1


def scan_classes_only(path: Path, text: str) -> list[ClassModel]:
    classes: list[ClassModel] = []
    for cm in CLASS_RE.finditer(text):
        if _is_false_class_match(text, cm):
            continue
        name = cm.group(2)
        semi = text.find(";", cm.end())
        brace = text.find("{", cm.end())
        if brace == -1 or (semi != -1 and semi < brace):
            continue
        end = find_matching_brace(text, brace)
        if end == -1:
            continue
        body = text[brace+1:end]
        cls = ClassModel(name=name, file=path, start_line=line_no(text, cm.start()))
        parse_class_body(cls, body, line_no(text, brace+1))
        classes.append(cls)
    return classes


def attach_external_definitions(classes: list[ClassModel], text: str) -> None:
    for cls in classes:
        # Patrón seguro por líneas: coincide Class<T>::method(args) ... { sin llaves anidadas en args.
        pat = re.compile(rf"(?:template\s*<[^>]+>\s*)?(?:inline\s+)?(?:[\w:<>~*&\s]+\s+)?{re.escape(cls.name)}\s*(?:<[^>]+>)?\s*::\s*(~?[A-Za-z_]\w*)\s*\([^{{;}}]*\)\s*(?:const\s*)?(?:noexcept\s*)?(?:\:[^{{;]*)?\{{", re.M)
        for m in pat.finditer(text):
            name = m.group(1)
            brace = text.find("{", m.end()-1)
            end = find_matching_brace(text, brace)
            if end == -1:
                continue
            body = text[brace+1:end]
            start_line = line_no(text, m.start())
            req, ens, inv = contiguous_contracts_before(text, m.start())
            cls.invariants.extend(inv)
            line_start = text.rfind("\n", 0, m.start()) + 1
            signature = " ".join(text[line_start:brace].split()) + " {"
            existing = next((x for x in cls.methods if x.name == name and x.body is None), None)
            if existing:
                existing.body = body; existing.start_line = start_line; existing.signature = signature
                existing.requires.extend(req); existing.ensures.extend(ens); existing.assertions = extract_assertions(body, start_line)
            else:
                cls.methods.append(MethodModel(class_name=cls.name, name=name, signature=signature, body=body, start_line=start_line, requires=req, ensures=ens, assertions=extract_assertions(body, start_line)))


def scan_file(path: Path) -> list[ClassModel]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    classes = scan_classes_only(path, text)
    attach_external_definitions(classes, text)
    return classes


def scan_project(root: Path, headers_only: bool = False) -> list[ClassModel]:
    out: list[ClassModel] = []
    for f in iter_cpp_files(root, headers_only=headers_only):
        try:
            out.extend(scan_file(f))
        except OSError:
            continue
    return out
