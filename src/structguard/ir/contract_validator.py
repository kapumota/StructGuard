from __future__ import annotations

from collections import Counter
import re

from structguard.ir.contract_ir import ContractIR, MethodIR, PredicateIR, StructureIR
from structguard.sgdsl.diagnostics import SGDSLDiagnostic

IDENTIFIER_RE = re.compile(r"\b[A-Za-z_]\w*\b")
CALL_RE = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
ALLOWED_WORDS = {"and", "or", "not", "old", "result", "true", "false", "True", "False"}
ALLOWED_CALLS = {"old", "capacity", "size", "length", "empty", "abs", "min", "max"}
NUMERIC_TYPES = {"int", "nat", "size", "size_t", "usize", "uint", "long", "float", "double"}
BOOLEAN_TYPES = {"bool", "boolean"}
COMPARISON_RE = re.compile(r"(<=|>=|==|!=|<|>)")
NUMERIC_COMPARISON_RE = re.compile(r"(<|>|<=|>=)")
TRAILING_OPERATOR_RE = re.compile(r"(\+|-|\*|/|&&|\|\||==|!=|<=|>=|<|>)\s*$")
INVALID_TOKEN_RE = re.compile(r"[^A-Za-z0-9_\s<>=!&|+\-*/%().,\[\]]")


def _diag(level: str, code: str, message: str, predicate: PredicateIR | None = None, structure: StructureIR | None = None, symbol: str | None = None) -> SGDSLDiagnostic:
    source = predicate.source if predicate else (structure.source if structure else None)
    line = predicate.line if predicate else (structure.line if structure else None)
    return SGDSLDiagnostic(level=level, code=code, message=message, source=source, line=line, symbol=symbol or (structure.name if structure else None))


def _is_balanced(expression: str) -> bool:
    stack: list[str] = []
    pairs = {")": "(", "]": "["}
    for char in expression:
        if char in "([":
            stack.append(char)
        elif char in ")]":
            if not stack or stack[-1] != pairs[char]:
                return False
            stack.pop()
    return not stack


def _identifiers(expression: str) -> set[str]:
    return {name for name in IDENTIFIER_RE.findall(expression) if name not in ALLOWED_WORDS}


def _calls(expression: str) -> set[str]:
    return set(CALL_RE.findall(expression))


def _validate_expression_shape(predicate: PredicateIR, structure: StructureIR) -> list[SGDSLDiagnostic]:
    diagnostics: list[SGDSLDiagnostic] = []
    expression = predicate.expression.strip()
    if not expression:
        diagnostics.append(_diag("FAILED", "SGDSL_EMPTY_EXPRESSION", "La expresión del contrato está vacía.", predicate, structure))
        return diagnostics
    if not _is_balanced(expression):
        diagnostics.append(_diag("FAILED", "SGDSL_UNBALANCED_EXPRESSION", "La expresión tiene paréntesis o corchetes sin balancear.", predicate, structure))
    if INVALID_TOKEN_RE.search(expression):
        diagnostics.append(_diag("FAILED", "SGDSL_INVALID_TOKEN", "La expresión contiene caracteres no admitidos por SGDSL estable.", predicate, structure))
    if TRAILING_OPERATOR_RE.search(expression):
        diagnostics.append(_diag("FAILED", "SGDSL_TRAILING_OPERATOR", "La expresión termina con un operador incompleto.", predicate, structure))
    if predicate.kind in {"requires", "ensures", "invariant"} and not COMPARISON_RE.search(expression) and "&&" not in expression and "||" not in expression and expression not in {"true", "false", "True", "False"}:
        diagnostics.append(_diag("WARNING", "SGDSL_WEAK_BOOLEAN_SHAPE", "La expresión no parece una condición booleana explícita.", predicate, structure))
    return diagnostics


def _validate_duplicate_items(structure: StructureIR) -> list[SGDSLDiagnostic]:
    diagnostics: list[SGDSLDiagnostic] = []
    field_counts = Counter(field.name for field in structure.fields)
    for name, count in field_counts.items():
        if count > 1:
            diagnostics.append(_diag("FAILED", "SGDSL_DUPLICATE_FIELD", f"El campo {name} está declarado más de una vez.", structure=structure, symbol=f"{structure.name}.{name}"))
    method_counts = Counter(method.name for method in structure.methods)
    for name, count in method_counts.items():
        if count > 1:
            diagnostics.append(_diag("FAILED", "SGDSL_DUPLICATE_METHOD", f"El método {name} está declarado más de una vez en el contrato.", structure=structure, symbol=f"{structure.name}.{name}"))
    invariant_counts = Counter(predicate.expression for predicate in structure.invariants)
    for expression, count in invariant_counts.items():
        if count > 1:
            diagnostics.append(_diag("WARNING", "SGDSL_DUPLICATE_CONTRACT", f"El invariante aparece duplicado: {expression}", structure=structure, symbol=structure.name))
    for method in structure.methods:
        for kind, predicates in (("requires", method.requires), ("ensures", method.ensures)):
            counts = Counter(predicate.expression for predicate in predicates)
            for expression, count in counts.items():
                if count > 1:
                    diagnostics.append(_diag("WARNING", "SGDSL_DUPLICATE_CONTRACT", f"El contrato {kind} aparece duplicado en {method.name}: {expression}", structure=structure, symbol=f"{structure.name}.{method.name}"))
    return diagnostics


def _field_type_map(structure: StructureIR) -> dict[str, str]:
    return {field.name: field.type_name.lower() for field in structure.fields}


def _validate_names(predicate: PredicateIR, structure: StructureIR, method: MethodIR | None = None) -> list[SGDSLDiagnostic]:
    diagnostics: list[SGDSLDiagnostic] = []
    fields = _field_type_map(structure)
    if not fields:
        return diagnostics
    params = {param.name for param in method.params} if method else set()
    method_names = {candidate.name for candidate in structure.methods}
    allowed_identifiers = set(fields) | params | method_names | ALLOWED_WORDS | ALLOWED_CALLS
    calls = _calls(predicate.expression)
    for call in sorted(calls):
        if call not in ALLOWED_CALLS and call not in method_names:
            diagnostics.append(_diag("FAILED", "SGDSL_UNKNOWN_METHOD", f"La expresión llama a un método no declarado en el contrato: {call}().", predicate, structure, symbol=call))
    for identifier in sorted(_identifiers(predicate.expression)):
        if identifier in calls:
            continue
        if identifier not in allowed_identifiers:
            diagnostics.append(_diag("FAILED", "SGDSL_UNKNOWN_FIELD", f"La expresión referencia un campo o parámetro no declarado: {identifier}.", predicate, structure, symbol=identifier))
    return diagnostics


def _validate_simple_types(predicate: PredicateIR, structure: StructureIR) -> list[SGDSLDiagnostic]:
    diagnostics: list[SGDSLDiagnostic] = []
    fields = _field_type_map(structure)
    if not fields:
        return diagnostics
    for name, type_name in fields.items():
        if type_name in BOOLEAN_TYPES and re.search(rf"\b{name}\b\s*(<|>|<=|>=)|(<|>|<=|>=)\s*\b{name}\b", predicate.expression):
            diagnostics.append(_diag("FAILED", "SGDSL_TYPE_MISMATCH", f"El campo booleano {name} se usa en una comparación numérica.", predicate, structure, symbol=name))
        if type_name not in NUMERIC_TYPES and type_name not in BOOLEAN_TYPES and NUMERIC_COMPARISON_RE.search(predicate.expression) and re.search(rf"\b{name}\b", predicate.expression):
            diagnostics.append(_diag("WARNING", "SGDSL_UNKNOWN_FIELD_TYPE", f"El tipo de {name} no tiene reglas de validación numérica: {type_name}.", predicate, structure, symbol=name))
    return diagnostics


def _validate_unused_contracts(structure: StructureIR) -> list[SGDSLDiagnostic]:
    diagnostics: list[SGDSLDiagnostic] = []
    if not structure.invariants and all(not method.requires and not method.ensures for method in structure.methods):
        diagnostics.append(_diag("WARNING", "SGDSL_NO_CONTRACTS", f"La estructura {structure.name} no declara invariantes ni contratos de método.", structure=structure, symbol=structure.name))
    for method in structure.methods:
        if not method.requires and not method.ensures:
            diagnostics.append(_diag("WARNING", "SGDSL_UNUSED_METHOD_DECLARATION", f"El método {method.name} no declara requires ni ensures.", structure=structure, symbol=f"{structure.name}.{method.name}"))
    return diagnostics


def validate_contract_ir(ir: ContractIR) -> list[SGDSLDiagnostic]:
    diagnostics: list[SGDSLDiagnostic] = []
    structure_counts = Counter(structure.qualified_name for structure in ir.structures)
    for qualified_name, count in structure_counts.items():
        if count > 1:
            diagnostics.append(SGDSLDiagnostic(level="FAILED", code="SGDSL_DUPLICATE_STRUCTURE", message=f"La estructura {qualified_name} está declarada más de una vez.", symbol=qualified_name))
    for structure in ir.structures:
        diagnostics.extend(_validate_duplicate_items(structure))
        all_predicates: list[tuple[PredicateIR, MethodIR | None]] = [(predicate, None) for predicate in structure.invariants]
        for method in structure.methods:
            all_predicates.extend((predicate, method) for predicate in method.requires)
            all_predicates.extend((predicate, method) for predicate in method.ensures)
        for predicate, method in all_predicates:
            diagnostics.extend(_validate_expression_shape(predicate, structure))
            diagnostics.extend(_validate_names(predicate, structure, method))
            diagnostics.extend(_validate_simple_types(predicate, structure))
        diagnostics.extend(_validate_unused_contracts(structure))
    if not diagnostics:
        diagnostics.append(SGDSLDiagnostic(level="INFO", code="SGDSL_CONTRACT_IR_VALID", message="ContractIR válido sin diagnósticos bloqueantes."))
    return diagnostics
