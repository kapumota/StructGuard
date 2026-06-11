from __future__ import annotations

from .binder import BindingIR, build_binding_ir
from .contract_matcher import match_contracts_to_source
from .symbol_table import SourceSymbolTable, build_source_symbol_table, build_source_symbol_table_from_source_ir

__all__ = [
    "BindingIR",
    "SourceSymbolTable",
    "build_binding_ir",
    "build_source_symbol_table",
    "build_source_symbol_table_from_source_ir",
    "match_contracts_to_source",
]
