from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import fnmatch, json, re
from .model import ClassModel, Contract, Diagnostic, ProjectReport

@dataclass
class DSLMethodSpec:
    name: str
    requires: list[Contract] = field(default_factory=list)
    ensures: list[Contract] = field(default_factory=list)
    line: int = 0

@dataclass
class DSLStructureSpec:
    name: str
    invariants: list[Contract] = field(default_factory=list)
    methods: dict[str, DSLMethodSpec] = field(default_factory=dict)
    line: int = 0

@dataclass
class DSLSpec:
    source: str
    package: str | None = None
    structures: dict[str, DSLStructureSpec] = field(default_factory=dict)
    def to_dict(self) -> dict:
        return asdict(self)

class DSLError(Exception):
    pass
COMMENT_RE = re.compile(r"(#|//).*?$", re.M)
PACKAGE_RE = re.compile(r"\b(?:package|module)\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*;?", re.I)
STRUCT_RE = re.compile(r"\b(?:structure|class|struct)\s+([A-Za-z_][\w*?]*)\s*\{", re.I)
METHOD_BLOCK_RE = re.compile(r"\bmethod\s+([~A-Za-z_]\w*)\s*\{", re.I)
METHOD_INLINE_RE = re.compile(r"\bmethod\s+([~A-Za-z_]\w*)\s+(requires|ensures)\s+(.+?);", re.I)
CONTRACT_RE = re.compile(r"\b(requires|ensures|invariant)\s+(.+?);", re.I | re.S)

def _strip_comments(text: str) -> str: return COMMENT_RE.sub("", text)
def _line_no(text: str, pos: int) -> int: return text.count("\n", 0, pos) + 1
def _find_matching_brace(text: str, open_pos: int) -> int:
    depth=0
    for i in range(open_pos, len(text)):
        if text[i] == "{": depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0: return i
    return -1
def _clean_expr(expr: str) -> str: return " ".join(expr.strip().split())

def parse_dsl_text(text: str, source: str = "<memory>") -> DSLSpec:
    text = _strip_comments(text)
    spec = DSLSpec(source=source)
    pm = PACKAGE_RE.search(text)
    if pm: spec.package = pm.group(1)
    pos = 0
    while True:
        sm = STRUCT_RE.search(text, pos)
        if not sm: break
        name = sm.group(1)
        open_brace = text.find("{", sm.end()-1)
        close = _find_matching_brace(text, open_brace)
        if close == -1:
            raise DSLError(f"Bloque de estructura sin cerrar para {name} en {source}:{_line_no(text, sm.start())}")
        body = text[open_brace+1:close]
        st = DSLStructureSpec(name=name, line=_line_no(text, sm.start()))
        spans=[]; bpos=0
        while True:
            mm = METHOD_BLOCK_RE.search(body, bpos)
            if not mm: break
            mname=mm.group(1); mopen=body.find("{", mm.end()-1); mclose=_find_matching_brace(body, mopen)
            if mclose == -1:
                raise DSLError(f"Bloque de método sin cerrar para {name}.{mname} en {source}:{st.line}")
            mbody=body[mopen+1:mclose]
            ms=st.methods.setdefault(mname, DSLMethodSpec(name=mname, line=st.line+body.count("\n",0,mm.start())))
            for cm in CONTRACT_RE.finditer(mbody):
                kind=cm.group(1).lower(); expr=_clean_expr(cm.group(2))
                c=Contract(kind=kind, expression=expr, line=ms.line+mbody.count("\n",0,cm.start()), source=f"dsl:{Path(source).name}")
                if kind == "requires": ms.requires.append(c)
                elif kind == "ensures": ms.ensures.append(c)
                elif kind == "invariant": st.invariants.append(c)
            spans.append((mm.start(), mclose+1)); bpos=mclose+1
        chars=list(body)
        for a,b in spans:
            for i in range(a,b): chars[i]=" "
        class_body="".join(chars)
        for cm in CONTRACT_RE.finditer(class_body):
            kind=cm.group(1).lower(); expr=_clean_expr(cm.group(2)); c=Contract(kind=kind, expression=expr, line=st.line+class_body.count("\n",0,cm.start()), source=f"dsl:{Path(source).name}")
            if kind == "invariant": st.invariants.append(c)
        for im in METHOD_INLINE_RE.finditer(class_body):
            mname, kind, expr = im.group(1), im.group(2).lower(), _clean_expr(im.group(3))
            ms = st.methods.setdefault(mname, DSLMethodSpec(name=mname, line=st.line+class_body.count("\n",0,im.start())))
            c=Contract(kind=kind, expression=expr, line=ms.line, source=f"dsl:{Path(source).name}")
            if kind == "requires": ms.requires.append(c)
            else: ms.ensures.append(c)
        spec.structures[name]=st; pos=close+1
    if not spec.structures:
        raise DSLError(f"No se encontraron bloques structure/class/struct en la fuente DSL {source}")
    return spec

def parse_dsl_file(path: Path) -> DSLSpec:
    return parse_dsl_text(path.read_text(encoding="utf-8"), source=str(path))

def load_dsl(paths: list[str|Path] | None) -> list[DSLSpec]:
    specs=[]
    for p in paths or []:
        path=Path(p)
        if path.is_dir():
            files=sorted(path.rglob("*.sgdsl"))+sorted(path.rglob("*.sg"))+sorted(path.rglob("*.structguard"))
            for f in files: specs.append(parse_dsl_file(f))
        else: specs.append(parse_dsl_file(path))
    return specs

def _add_unique(target: list[Contract], additions: list[Contract]) -> int:
    seen={(c.kind,c.expression) for c in target}; added=0
    for c in additions:
        if (c.kind,c.expression) not in seen:
            target.append(c); seen.add((c.kind,c.expression)); added+=1
    return added

def _matches(pattern: str, name: str) -> bool: return pattern == name or fnmatch.fnmatch(name, pattern)

def apply_dsl_contracts(classes: list[ClassModel], specs: list[DSLSpec]) -> list[Diagnostic]:
    diags=[]; matched=set()
    for cls in classes:
        for spec in specs:
            for pattern, st in spec.structures.items():
                if not _matches(pattern, cls.name): continue
                matched.add(pattern)
                inv_added=_add_unique(cls.invariants, st.invariants); method_added=0
                for m in cls.methods:
                    for mpat, ms in st.methods.items():
                        if _matches(mpat, m.name):
                            method_added += _add_unique(m.requires, ms.requires)
                            method_added += _add_unique(m.ensures, ms.ensures)
                diags.append(Diagnostic(level="INFO", code="DSL_CONTRACTS_APPLIED", message=f"Contratos DSL aplicados a {cls.name}: {inv_added} invariantes, {method_added} contratos de método.", file=str(cls.file), line=cls.start_line, symbol=cls.name, details={"structure_pattern": pattern, "dsl_sources":[s.source for s in specs]}))
    all_patterns={p for spec in specs for p in spec.structures}
    for pattern in sorted(all_patterns-matched):
        diags.append(Diagnostic(level="WARNING", code="DSL_STRUCTURE_UNMATCHED", message=f"El patrón de estructura DSL {pattern!r} no coincidió con ninguna clase C++ escaneada.", details={"pattern": pattern}))
    return diags

def dsl_report(paths: list[str|Path]) -> ProjectReport:
    report=ProjectReport(root=", ".join(str(p) for p in paths))
    try: specs=load_dsl(paths)
    except DSLError as e:
        report.diagnostics.append(Diagnostic(level="FAILED", code="DSL_PARSE_ERROR", message=str(e))); return report
    for spec in specs:
        total_methods=sum(len(st.methods) for st in spec.structures.values())
        total_invariants=sum(len(st.invariants) for st in spec.structures.values())
        total_requires=sum(len(ms.requires) for st in spec.structures.values() for ms in st.methods.values())
        total_ensures=sum(len(ms.ensures) for st in spec.structures.values() for ms in st.methods.values())
        report.diagnostics.append(Diagnostic(level="INFO", code="DSL_PARSED", message=f"Especificación DSL parseada con {len(spec.structures)} estructuras y {total_methods} métodos.", file=spec.source, details={"package": spec.package, "structures": sorted(spec.structures), "invariants": total_invariants, "requires": total_requires, "ensures": total_ensures}))
    return report

def write_dsl_json(paths: list[str|Path], out: Path) -> Path:
    specs=load_dsl(paths); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps([s.to_dict() for s in specs], indent=2, ensure_ascii=False), encoding="utf-8"); return out
