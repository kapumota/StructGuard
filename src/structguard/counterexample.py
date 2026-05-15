from __future__ import annotations

from typing import Any
from .model import Contract, MethodModel


def explain_counterexample(method: MethodModel, contract: Contract, old: dict[str, Any], after: dict[str, Any], result: Any = None, notes: list[str] | None = None) -> dict[str, Any]:
    changed = {k: {"before": old.get(k), "after": after.get(k)} for k in sorted(set(old) | set(after)) if old.get(k) != after.get(k)}
    lines = [
        "Estado inicial:",
        *[f"  {k} = {old[k]}" for k in sorted(old)],
        "Operación:",
        f"  {method.qualified_name}()",
        "Estado después:",
        *[f"  {k} = {after[k]}" for k in sorted(after)],
    ]
    if result is not None:
        lines.extend(["Resultado:", f"  result = {result}"])
    lines.extend(["Contrato violado:", f"  {contract.kind}: {contract.expression}"])
    if notes:
        lines.extend(["Notas del camino:", *[f"  - {n}" for n in notes]])
    return {
        "initial_state": dict(sorted(old.items())),
        "operation": method.qualified_name,
        "state_after": dict(sorted(after.items())),
        "result": result,
        "violated_contract": {"kind": contract.kind, "expression": contract.expression, "source": contract.source},
        "changed_variables": changed,
        "path_notes": list(notes or []),
        "explanation": "\n".join(lines),
    }
