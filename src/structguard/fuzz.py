from __future__ import annotations
import json
import random
import re
from dataclasses import dataclass, asdict
from html import escape
from pathlib import Path
from typing import Any
from .cppscan import scan_project, extract_assertions
from .model import Diagnostic, ProjectReport

@dataclass
class FuzzCase:
    structure: str
    seed: int
    operations: list[str]
    failure: str | None
    final_state: dict[str, Any]
    target_method: str | None = None
    minimized_operations: list[str] | None = None
    classification: str = "abstract-container"
@dataclass
class FuzzTarget:
    name: str
    file: str
    line: int
    methods: list[str]
    add_methods: list[str]
    remove_methods: list[str]
    access_methods: list[str]
    guarded_methods: list[str]
    fields: list[str]

def _canonical(methods:set[str]):
    add=[n for n in ['push','add','enqueue','insert','append','put'] if n in methods]
    rem=[n for n in ['pop','remove','dequeue','erase','delete','extract_min','extractmax','extract_max'] if n in methods]
    acc=[n for n in ['top','front','back','get','peek','find','contains','minimum','maximum','min','max'] if n in methods]
    return add,rem,acc

def _guarded_methods(cls)->set[str]:
    guarded=set()
    for m in cls.methods:
        reqs=[c.expression for c in m.requires]+[a.expression for a in extract_assertions(m.body or '', m.start_line)]
        joined=' '.join(reqs).replace(' ','')
        if reqs and any(tok in joined for tok in ['!empty()','>0','i<n','i<size()','index<n','size_>0','n>0','_size>0']): guarded.add(m.name.lower())
    return guarded

def _call(op:str, val:int=0)->str:
    if op in {'push','add','enqueue','insert','append','put'}: return f'{op}({val})'
    if op in {'get','find','contains'}: return f'{op}({max(0,val)})'
    return f'{op}()'

def _minimize(ops:list[str], failure:str|None):
    if not failure or not ops: return None
    return [ops[-1]] if ('size == 0' in failure or 'out of range' in failure) else ops[-5:]

def _fuzz_container(class_name:str, methods:set[str], seed:int, steps:int)->FuzzCase:
    rng=random.Random(seed); size=0; capacity=4; ops=[]; failure=None; target=None
    add,rem,acc=_canonical(methods); add=add or ['push']; rem=rem or ['pop']; acc=acc or ['top']
    choices=add*3+rem*4+acc*3
    for _ in range(steps):
        op=rng.choice(choices); val=rng.randint(-16,16)
        if op in add:
            if size>=capacity: capacity*=2
            size+=1; ops.append(_call(op,val))
        elif op in rem:
            ops.append(_call(op,val))
            if size==0: failure=f'{op}() llamado cuando size == 0'; target=op; break
            size-=1
        else:
            ops.append(_call(op,val if size else 0))
            if size==0 and op not in {'contains','find'}: failure=f'{op}() llamado cuando size == 0'; target=op; break
            if op=='get' and size>0 and val>=size: failure=f'get({val}) puede estar fuera de rango para size {size}'; target=op; break
    return FuzzCase(class_name,seed,ops,failure,{'size':size,'capacity':capacity},target,_minimize(ops,failure))

def collect_fuzz_targets(root:Path, headers_only:bool=False, structure_filter:str|None=None)->list[FuzzTarget]:
    out=[]
    for cls in scan_project(root, headers_only=headers_only):
        if structure_filter and structure_filter.lower() not in cls.name.lower(): continue
        methods={m.name.lower() for m in cls.methods}; add,rem,acc=_canonical(methods)
        if add and (rem or acc):
            out.append(FuzzTarget(cls.name,str(cls.file),cls.start_line,sorted(methods),add,rem,acc,sorted(_guarded_methods(cls)),sorted(cls.fields)))
    return out

def collect_fuzz_cases(root:Path, headers_only:bool=False, seeds:int=20, steps:int=50, structure_filter:str|None=None)->list[FuzzCase]:
    cases=[]
    for t in collect_fuzz_targets(root,headers_only,structure_filter):
        for seed in range(seeds): cases.append(_fuzz_container(t.name,set(t.methods),seed,steps))
    return cases

def fuzz_project(root:Path, headers_only:bool=False, seeds:int=20, steps:int=50, structure_filter:str|None=None)->ProjectReport:
    report=ProjectReport(root=str(root)); targets=collect_fuzz_targets(root,headers_only,structure_filter)
    if not targets:
        report.diagnostics.append(Diagnostic(level='WARNING', code='NO_FUZZ_TARGETS', message='No se encontraron clases tipo contenedor para fuzzing abstracto.', file=str(root))); return report
    report.diagnostics.append(Diagnostic(level='INFO', code='FUZZ_TESTGEN_SUMMARY', message=f'StructGuard fuzz/testgen heurístico escaneó {len(targets)} estructuras tipo contenedor con {seeds} semillas x {steps} pasos.', file=str(root), details={'targets':[asdict(t) for t in targets], 'seeds':seeds, 'steps':steps}))
    for t in targets:
        failures=[]; failing=None
        for seed in range(seeds):
            case=_fuzz_container(t.name,set(t.methods),seed,steps)
            if case.failure: failures.append(asdict(case)); failing=case.target_method; break
        if failures:
            guarded=failing in set(t.guarded_methods)
            report.diagnostics.append(Diagnostic(level='INFO' if guarded else 'FAILED', code='FUZZ_GUARDED_PRECONDITION_SEQUENCE' if guarded else 'FUZZ_MISSING_PRECONDITION_COUNTEREXAMPLE', message=(f'Fuzzing generó una secuencia cliente inválida para {t.name}, pero el método objetivo tiene guarda/contrato.' if guarded else f'Fuzzing encontró una secuencia cliente inválida para {t.name} y no encontró una guarda/contrato explícito en el método objetivo.'), file=t.file, line=t.line, symbol=t.name, details={'counterexamples':failures,'guarded_methods':t.guarded_methods,'target_method':failing}))
            if failures[0].get('minimized_operations'):
                report.diagnostics.append(Diagnostic(level='INFO', code='FUZZ_MINIMIZED_REPRODUCER', message=f"Reproductor minimizado para {t.name}: "+', '.join(failures[0]['minimized_operations']), file=t.file, line=t.line, symbol=t.name, details={'minimized_operations':failures[0]['minimized_operations'],'seed':failures[0]['seed']}))
        else:
            report.diagnostics.append(Diagnostic(level='HEURISTIC', code='FUZZ_NO_COUNTEREXAMPLE', message=f'El fuzzing abstracto heurístico no encontró contraejemplos de precondición para {t.name} en {seeds} semillas x {steps} pasos.', file=t.file, line=t.line, symbol=t.name, details={'seeds':seeds,'steps':steps,'targets':asdict(t)}))
    return report

def write_fuzz_json(root:Path, cases:list[FuzzCase], path:Path)->Path:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps({'root':str(root),'cases':[asdict(c) for c in cases],'failures':[asdict(c) for c in cases if c.failure],'count':len(cases)}, indent=2, ensure_ascii=False), encoding='utf-8'); return path

def _safe(name:str)->str: return re.sub(r'[^A-Za-z0-9_]+','_',name).strip('_') or 'structure'
def _include(t:FuzzTarget, base:Path|None=None):
    f=Path(t.file)
    if base:
        try: return str(f.resolve().relative_to(base.resolve())).replace('\\','/')
        except Exception: pass
    return f.name

def write_cpp_tests(root:Path, headers_only:bool, out_dir:Path, seeds:int=20, steps:int=50, structure_filter:str|None=None, only_failures:bool=True)->Path:
    out_dir.mkdir(parents=True, exist_ok=True); manifest=[]
    for t in collect_fuzz_targets(root,headers_only,structure_filter):
        chosen=None
        for seed in range(seeds):
            c=_fuzz_container(t.name,set(t.methods),seed,steps)
            if c.failure: chosen=c; break
            if not only_failures and chosen is None: chosen=c
        if not chosen: continue
        ops=chosen.minimized_operations or chosen.operations; calls='\n    '.join(f'ds.{op};' for op in ops)
        text=f'''// Generado por StructGuard TestGen heurístico.\n// Target: {t.name}\n// Seed: {chosen.seed}\n// Failure: {chosen.failure or "ninguna"}\n// Test de regresión candidato; ajusta constructores/argumentos template si es necesario.\n#include <cassert>\n#include <iostream>\n#include "{_include(t, root if root.is_dir() else root.parent)}"\n\nint main() {{\n    {t.name}<int> ds;\n    {calls}\n    std::cout << "StructGuard generated test completed for {t.name}\\n";\n    return 0;\n}}\n'''
        p=out_dir/f"test_{_safe(t.name).lower()}_{'failure' if chosen.failure else 'smoke'}.cpp"; p.write_text(text, encoding='utf-8')
        manifest.append({'structure':t.name,'file':str(p),'failure':chosen.failure,'seed':chosen.seed,'operations':chosen.operations,'minimized_operations':chosen.minimized_operations})
    mp=out_dir/'structguard_testgen_manifest.json'; mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8'); return mp

def write_replay_script(root:Path, cases:list[FuzzCase], path:Path)->Path:
    path.parent.mkdir(parents=True, exist_ok=True); failures=[asdict(c) for c in cases if c.failure]
    path.write_text('#!/usr/bin/env python3\n# Generado por StructGuard TestGen heurístico.\ncases = '+repr(failures)+'\nfor c in cases:\n    print(f"[{c[\'structure\']}] seed={c[\'seed\']} failure={c[\'failure\']}")\n    print("  ops:", " -> ".join(c.get("minimized_operations") or c["operations"]))\n', encoding='utf-8'); path.chmod(0o755); return path

def write_seed_corpus(root:Path, cases:list[FuzzCase], out_dir:Path)->Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    for c in cases: (out_dir/f"{_safe(c.structure)}_{c.seed}_{'fail' if c.failure else 'ok'}.json").write_text(json.dumps(asdict(c), indent=2, ensure_ascii=False), encoding='utf-8')
    mp=out_dir/'manifest.json'; mp.write_text(json.dumps({'root':str(root),'seeds':len(cases),'files':sorted(p.name for p in out_dir.glob('*.json'))}, indent=2, ensure_ascii=False), encoding='utf-8'); return mp

def write_fuzz_html(root:Path, cases:list[FuzzCase], path:Path)->Path:
    path.parent.mkdir(parents=True, exist_ok=True); failures=[c for c in cases if c.failure]
    rows=''.join(f"<tr><td>{escape(c.structure)}</td><td>{c.seed}</td><td>{escape(c.failure or 'OK')}</td><td><code>{escape(' -> '.join(c.minimized_operations or c.operations[:12]))}</code></td></tr>" for c in cases[:500])
    html=f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>StructGuard Fuzz/TestGen heurístico</title><style>body{{font-family:system-ui;margin:2rem;background:#f8fafc;color:#0f172a}}.card{{background:white;border:1px solid #e5e7eb;border-radius:1rem;padding:1rem;margin:.75rem 0;box-shadow:0 8px 20px #0f172a12}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{border-bottom:1px solid #e5e7eb;padding:.55rem;text-align:left}}code{{background:#eef2ff;padding:.1rem .25rem;border-radius:.25rem}}</style></head><body><h1>StructGuard Fuzz/TestGen heurístico</h1><div class='card'><b>Raíz:</b> {escape(str(root))}<br><b>Casos:</b> {len(cases)}<br><b>Fallas:</b> {len(failures)}</div><table><thead><tr><th>Estructura</th><th>Semilla</th><th>Falla</th><th>Reproductor</th></tr></thead><tbody>{rows}</tbody></table></body></html>"
    path.write_text(html, encoding='utf-8'); return path
