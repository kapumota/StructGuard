from __future__ import annotations
from pathlib import Path
import json
from .model import Diagnostic, ProjectReport
ADVANCED_STRUCTURES={
 'FenwickTree':{'area':'range-query','contracts':['invariant n >= 0;','method update requires 0 <= index && index < n;','method query requires 0 <= index && index < n; ensures result >= 0;']},
 'SegmentTree':{'area':'range-query','contracts':['invariant n >= 0;','method query requires 0 <= left && left <= right && right < n;']},
 'DisjointSetUnion':{'area':'dynamic-connectivity','contracts':['invariant forall x in [0, n): 0 <= parent[x] && parent[x] < n;','method find requires 0 <= x && x < n;','method unite requires 0 <= a && a < n && 0 <= b && b < n;']},
 'BinaryHeap':{'area':'priority-queue','contracts':['invariant forall i in [1, n): data[parent(i)] <= data[i];','method pop requires n > 0; ensures n == old(n) - 1;']},
 'BTree':{'area':'external-memory','contracts':['invariant keys_sorted(root);','invariant all_leaves_same_depth(root);','method search ensures result == contains(old(root), key);']},
 'BPlusTree':{'area':'database-index','contracts':['invariant leaves_linked_in_order(root);','invariant all_values_in_leaves(root);','method range_query requires low <= high;']},
 'WaveletTree':{'area':'succinct-strings','contracts':['invariant bitvectors_have_rank_support(root);','method rank requires 0 <= index && index <= n;','method select requires kth > 0;']},
 'SuffixAutomaton':{'area':'string-algorithms','contracts':['invariant suffix_links_form_dag();','invariant transitions_are_deterministic();','method extend ensures accepts(old(text) + c);']},
 'RMQ':{'area':'range-minimum-query','contracts':['method query requires 0 <= left && left <= right && right < n;','method query ensures result >= left && result <= right;']},
 'DynamicGraph':{'area':'dynamic-graph-algorithms','contracts':['invariant vertices_valid();','method add_edge requires valid(u) && valid(v);','method connected requires valid(u) && valid(v);']},
}
def advanced_report()->ProjectReport:
    report=ProjectReport(root='advanced-structures')
    for name,meta in ADVANCED_STRUCTURES.items(): report.diagnostics.append(Diagnostic(level='INFO',code='ADVANCED_STRUCTURE_TEMPLATE',message=f"{name}: {meta['area']} contract template available.",symbol=name,details=meta))
    return report
def write_advanced_dsl(out:Path)->Path:
    out.parent.mkdir(parents=True,exist_ok=True); lines=['package structguard.advanced;','']
    for name,meta in ADVANCED_STRUCTURES.items():
        lines.append(f'structure {name} {{')
        for c in meta['contracts']:
            if c.startswith('method '):
                parts=c.split(maxsplit=2); method=parts[1]; rest=parts[2] if len(parts)>2 else ''
                lines.append(f'  method {method} {{')
                for clause in [x.strip() for x in rest.split(';') if x.strip()]: lines.append(f'    {clause};')
                lines.append('  }')
            else: lines.append(f'  {c}')
        lines.append('}'); lines.append('')
    out.write_text('\n'.join(lines),encoding='utf-8'); return out
def write_advanced_json(out:Path)->Path:
    out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(ADVANCED_STRUCTURES,indent=2,ensure_ascii=False),encoding='utf-8'); return out
