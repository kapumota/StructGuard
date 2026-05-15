from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, re, subprocess, shutil
from typing import Any
from .clang_frontend import default_include_dirs, find_clang, run_clang_ast
from .cppscan import iter_cpp_files, scan_project
from .dsl import apply_dsl_contracts, load_dsl
from .formal import smt_expr, _to_viper_expr
from .model import ClassModel, Contract, Diagnostic, MethodModel, ProjectReport
from .verifier import infer_class_invariants, infer_method_ensures, infer_method_requires

@dataclass
class IRStep:
    id: str; kind: str; text: str; children: list[str]; source_kind: str|None=None
@dataclass
class SSAOp:
    target: str; version: int; expr: str; source: str
@dataclass
class MethodIR:
    qualified_name: str; file: str; line: int; clang_kind: str; cfg: list[IRStep]; ssa: list[SSAOp]; contracts: dict[str,list[str]]; notes: list[str]
@dataclass
class PipelineUnit:
    file: str; ok: bool; clang_available: bool; methods: list[MethodIR]; diagnostics: list[str]

def _loc_line(node: dict[str,Any])->int:
    loc=node.get('loc') or {}; return int(loc.get('line') or 0) if isinstance(loc,dict) else 0

def _node_text(node: dict[str,Any])->str:
    parts=[]
    for key in ('name','opcode','value','type'):
        val=node.get(key)
        if isinstance(val,dict):
            q=val.get('qualType') or val.get('desugaredQualType')
            if q: parts.append(str(q))
        elif val is not None: parts.append(str(val))
    return ' '.join(parts)[:160]

def _iter_nodes(node: Any):
    if isinstance(node,dict):
        yield node
        for ch in node.get('inner') or []: yield from _iter_nodes(ch)

def _node_file_matches(node: dict[str,Any], file: Path)->bool:
    wanted=file.resolve(); candidates=[]
    loc=node.get('loc') or {}
    if isinstance(loc,dict) and loc.get('file'): candidates.append(str(loc.get('file')))
    rng=node.get('range') or {}
    if isinstance(rng,dict):
        for k in ('begin','end'):
            part=rng.get(k) or {}
            if isinstance(part,dict) and part.get('file'): candidates.append(str(part.get('file')))
    if not candidates: return True
    for c in candidates:
        try:
            if Path(c).resolve()==wanted: return True
        except Exception:
            if c.endswith(file.name): return True
    return False

def _extract_methods_from_ast(ast: dict[str,Any], file: Path)->list[dict[str,Any]]:
    out=[]
    for node in _iter_nodes(ast):
        if isinstance(node,dict) and node.get('kind') in {'CXXMethodDecl','CXXConstructorDecl','CXXDestructorDecl','FunctionDecl'} and node.get('name') and _node_file_matches(node,file):
            out.append(node)
    return out

def _cfg_from_clang_method(node: dict[str,Any])->list[IRStep]:
    steps=[]; counter=0; interesting={'CompoundStmt','IfStmt','ForStmt','WhileStmt','DoStmt','ReturnStmt','BinaryOperator','UnaryOperator','CallExpr','CXXMemberCallExpr','CXXOperatorCallExpr','DeclStmt','VarDecl','CXXConstructExpr'}
    def walk(n,parent=None):
        nonlocal counter
        if not isinstance(n,dict): return
        kind=str(n.get('kind') or ''); sid=parent
        if kind in interesting:
            sid=f'n{counter}'; counter+=1; steps.append(IRStep(sid,kind,_node_text(n),[],kind))
            if parent:
                for s in steps:
                    if s.id==parent: s.children.append(sid); break
        for ch in n.get('inner') or []: walk(ch,sid)
    for ch in node.get('inner') or []: walk(ch,None)
    if not steps: steps.append(IRStep('n0','Entry','declaración de método sin cuerpo en AST de Clang',[]))
    return steps

def _expr_from_ast(n: dict[str,Any])->str:
    if not isinstance(n,dict): return '?'
    kind=n.get('kind')
    if kind in {'MemberExpr','DeclRefExpr'}: return str(n.get('name') or '?')
    if kind=='IntegerLiteral': return str(n.get('value') or '0')
    if kind in {'ImplicitCastExpr','ParenExpr','ExprWithCleanups','MaterializeTemporaryExpr'}:
        inner=n.get('inner') or []; return _expr_from_ast(inner[0]) if inner else '?'
    if kind=='UnaryOperator':
        op=str(n.get('opcode') or ''); inner=n.get('inner') or []
        if op in {'++','--'} and inner: return f'{_expr_from_ast(inner[0])}{op}'
        if inner: return f'({op}{_expr_from_ast(inner[0])})'
    if kind=='BinaryOperator':
        op=str(n.get('opcode') or '?'); inner=n.get('inner') or []
        if len(inner)>=2: return f'({_expr_from_ast(inner[0])} {op} {_expr_from_ast(inner[1])})'
    if kind in {'CallExpr','CXXMemberCallExpr'}:
        name=str(n.get('name') or 'call'); args=', '.join(_expr_from_ast(x) for x in (n.get('inner') or [])[1:]); return f'{name}({args})'
    return _node_text(n) or str(kind or '?')

def _ssa_from_ast_method(node: dict[str,Any])->list[SSAOp]:
    versions={}; out=[]; idx=0
    for n in _iter_nodes(node):
        if not isinstance(n,dict): continue
        kind=n.get('kind')
        if kind=='BinaryOperator' and n.get('opcode') in {'=','+=','-=','*=','/='}:
            inner=n.get('inner') or []
            if len(inner)>=2:
                target=_expr_from_ast(inner[0])
                if re.match(r'^[A-Za-z_]\w*$',target):
                    versions[target]=versions.get(target,0)+1; out.append(SSAOp(target,versions[target],_expr_from_ast(inner[1]),f'clang{idx}')); idx+=1
        elif kind=='UnaryOperator' and n.get('opcode') in {'++','--'}:
            inner=n.get('inner') or []
            if inner:
                target=_expr_from_ast(inner[0])
                if re.match(r'^[A-Za-z_]\w*$',target):
                    versions[target]=versions.get(target,0)+1; delta='+ 1' if n.get('opcode')=='++' else '- 1'; out.append(SSAOp(target,versions[target],f'{target} {delta}',f'clang{idx}')); idx+=1
    return out

def _contract_map(classes:list[ClassModel], infer=True)->dict[tuple[str,str],dict[str,list[Contract]]]:
    out={}
    for cls in classes:
        inv=list(cls.invariants)
        if infer: inv+=infer_class_invariants(cls)
        for m in cls.methods:
            req=list(m.requires); ens=list(m.ensures)
            if infer:
                req+=infer_method_requires(m, cls); ens+=infer_method_ensures(cls,m)
            out[(cls.name,m.name)]={'invariant':inv,'requires':req,'ensures':ens}
            out.setdefault((cls.name,cls.name),{'invariant':inv,'requires':[],'ensures':[]})
    return out

def _match_contracts(method_name:str, contracts)->dict[str,list[str]]:
    unq=method_name.split('::')[-1]
    for (cls,meth),c in contracts.items():
        if method_name==f'{cls}::{meth}' or unq==meth:
            return {k:[x.expression for x in v] for k,v in c.items()}
    return {'invariant':[],'requires':[],'ensures':[]}

def build_pipeline_units(root:Path,*,headers_only=False,clang=None,std='c++17',max_files=20,timeout=15,dsl_paths=None,infer=True)->list[PipelineUnit]:
    files=list(iter_cpp_files(root,headers_only=headers_only))
    if max_files is not None: files=files[:max_files]
    clang_bin=find_clang(clang); inc=default_include_dirs(root if root.is_dir() else root.parent)
    classes=scan_project(root,headers_only=headers_only)
    if dsl_paths:
        try: apply_dsl_contracts(classes,load_dsl(dsl_paths))
        except Exception: pass
    contracts=_contract_map(classes,infer=infer); units=[]
    for f in files:
        if not clang_bin:
            units.append(PipelineUnit(str(f),False,False,[],['clang++ no encontrado; instala clang o pasa --clang'])); continue
        summary,ast=run_clang_ast(f,clang=clang_bin,include_dirs=inc,std=std,timeout=timeout,ast_filter=None)
        methods=[]; diags=[]
        if summary.diagnostics: diags.append(summary.diagnostics[:1000])
        if ast:
            for mn in _extract_methods_from_ast(ast,f):
                name=str(mn.get('name') or '<anonymous>'); cfg=_cfg_from_clang_method(mn); ssa=_ssa_from_ast_method(mn)
                cm=_match_contracts(name,contracts); notes=[]
                if not any(cm.values()): notes.append('no se encontraron contratos, usa .sgdsl o comentarios // requires/ensures/invariant')
                if not ssa: notes.append('SSA es conservador: no se extrajeron nodos tipo asignación desde Clang')
                methods.append(MethodIR(name,str(f),_loc_line(mn),str(mn.get('kind') or ''),cfg,ssa,cm,notes))
        units.append(PipelineUnit(str(f),summary.ok and ast is not None,True,methods,diags))
    return units

def pipeline_report(root:Path,**kwargs)->ProjectReport:
    units=build_pipeline_units(root,**kwargs); report=ProjectReport(root=str(root))
    totals={'files':len(units),'ok':sum(1 for u in units if u.ok),'methods':sum(len(u.methods) for u in units),'cfg_nodes':sum(len(m.cfg) for u in units for m in u.methods),'ssa_ops':sum(len(m.ssa) for u in units for m in u.methods)}
    report.diagnostics.append(Diagnostic(level='INFO' if totals['methods'] else 'WARNING', code='PIPELINE_SUMMARY', message='Pipeline Clang AST → CFG/SSA completado.', file=str(root), details=totals))
    for u in units:
        if not u.clang_available:
            report.diagnostics.append(Diagnostic(level='WARNING',code='PIPELINE_CLANG_MISSING',message='Clang no está disponible; el pipeline no puede ejecutarse para este archivo.',file=u.file,details={'diagnostics':u.diagnostics})); continue
        for m in u.methods:
            report.diagnostics.append(Diagnostic(level='INFO',code='PIPELINE_METHOD_IR',message=f'{m.qualified_name}: {len(m.cfg)} nodos CFG, {len(m.ssa)} operaciones SSA.',file=m.file,line=m.line,symbol=m.qualified_name,details={'contracts':m.contracts,'notes':m.notes,'cfg_preview':[asdict(x) for x in m.cfg[:8]],'ssa':[asdict(x) for x in m.ssa[:12]]}))
    return report

def _smt_for_ir(m:MethodIR)->str:
    vars_=set(op.target for op in m.ssa)
    for exprs in m.contracts.values():
        for expr in exprs: vars_.update(re.findall(r'\b[A-Za-z_]\w*\b',expr))
    vars_={v for v in vars_ if v not in {'old','result','true','false','size','capacity','empty','forall','in'} and not v[0].isupper()} or {'n','capacity_'}
    lines=['; Generado por el pipeline Clang de StructGuard','(set-logic ALL)']
    for v in sorted(vars_): lines += [f'(declare-const old_{v} Int)',f'(declare-const {v} Int)']
    lines.append('(declare-const result Int)'); lines.append('; supuestos: invariantes y precondiciones')
    for expr in m.contracts.get('invariant',[])+m.contracts.get('requires',[]):
        s,_=smt_expr(expr,old_state=True); lines.append(f'(assert {s}) ; {expr}')
    lines.append('; SSA extraído desde CFG de Clang')
    for op in m.ssa: lines.append(f'; {op.target}_{op.version} := {op.expr} from {op.source}')
    goals=[]
    for expr in m.contracts.get('ensures',[])+m.contracts.get('invariant',[]):
        s,_=smt_expr(expr,old_state=False); goals.append(s)
    lines.append(f"(assert (not (and {' '.join(goals)})))" if goals else '(assert false) ; no hay objetivos disponibles')
    lines += ['(check-sat)','']; return '\n'.join(lines)

def _viper_for_ir(m:MethodIR)->str:
    method=re.sub(r'\W+','_',m.qualified_name or 'method')
    lines=[f'// Generado por el pipeline Clang de StructGuard para {m.qualified_name}',f'method {method}()']
    reqs=m.contracts.get('invariant',[])+m.contracts.get('requires',[]); enss=m.contracts.get('ensures',[])+m.contracts.get('invariant',[])
    if not reqs: lines.append('  requires true')
    for r in reqs: lines.append(f'  requires {_to_viper_expr(r)}')
    if not enss: lines.append('  ensures true')
    for e in enss: lines.append(f'  ensures {_to_viper_expr(e)}')
    lines.append('{'); lines.append('  // Nodos CFG extraídos desde AST de Clang')
    for step in m.cfg[:40]: lines.append(f'  // {step.id}: {step.kind} {step.text}')
    lines.append('  // Resumen SSA')
    for op in m.ssa[:40]: lines.append(f'  // {op.target}_{op.version} := {op.expr}')
    lines.append('}'); return '\n'.join(lines)+'\n'

def write_pipeline_artifacts(root:Path,out_dir:Path,*,backend='both',run_solver=False,**kwargs):
    units=build_pipeline_units(root,**kwargs); out_dir.mkdir(parents=True,exist_ok=True); manifest=[]; report=ProjectReport(root=str(root))
    smt_dir=out_dir/'smt'; viper_dir=out_dir/'viper'
    if backend in {'smt','both'}: smt_dir.mkdir(exist_ok=True)
    if backend in {'viper','both'}: viper_dir.mkdir(exist_ok=True)
    for u in units:
        for m in u.methods:
            safe=re.sub(r'\W+','_',Path(m.file).stem+'_'+m.qualified_name).strip('_') or 'method'; rec={'symbol':m.qualified_name,'file':m.file,'cfg_nodes':len(m.cfg),'ssa_ops':len(m.ssa),'artifacts':{}}
            if backend in {'smt','both'}:
                p=smt_dir/f'{safe}.smt2'; p.write_text(_smt_for_ir(m),encoding='utf-8'); rec['artifacts']['smt']=str(p)
                if run_solver and shutil.which('z3'):
                    z3_bin=shutil.which('z3')
                    z3=subprocess.run([z3_bin,str(p)],text=True,capture_output=True,timeout=10)
                    z3_details={'exit_code':z3.returncode,'stdout':z3.stdout[:2000],'stderr':z3.stderr[:2000]}
                    first=(z3.stdout.strip().splitlines() or [''])[0]
                    if first == 'sat':
                        model=subprocess.run([z3_bin,'-in'],input=p.read_text(encoding='utf-8')+'\n(get-model)\n',text=True,capture_output=True,timeout=10)
                        z3_details['model_stdout']=model.stdout[:2000]
                        z3_details['model_stderr']=model.stderr[:2000]
                    rec['z3']=z3_details
            if backend in {'viper','both'}:
                p=viper_dir/f'{safe}.vpr'; p.write_text(_viper_for_ir(m),encoding='utf-8'); rec['artifacts']['viper']=str(p)
            manifest.append(rec); report.diagnostics.append(Diagnostic(level='INFO',code='PIPELINE_FORMAL_ARTIFACT',message=f'Artefactos formales emitidos para {m.qualified_name}.',file=m.file,line=m.line,symbol=m.qualified_name,details=rec))
    (out_dir/'pipeline_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    if not manifest: report.diagnostics.append(Diagnostic(level='WARNING',code='PIPELINE_NO_ARTIFACTS',message='No se extrajeron métodos desde el AST de Clang; no se emitieron artefactos formales.',file=str(root)))
    return manifest, report

def write_pipeline_json(units:list[PipelineUnit],out:Path)->Path:
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps([asdict(u) for u in units],indent=2,ensure_ascii=False),encoding='utf-8'); return out
