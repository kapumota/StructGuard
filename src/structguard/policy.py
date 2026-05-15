from __future__ import annotations
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

@dataclass
class CIPolicy:
    path: Path | None = None
    project: str = "StructGuard Project"
    scan_headers_only: bool = True
    dsl_files: list[str] = field(default_factory=list)
    max_cases: int = 300
    fuzz_seeds: int = 10
    fuzz_steps: int = 25
    deep_security: bool = True
    fail_on_failed_contract: bool = True
    fail_on_warnings: bool = False
    fail_on_unknown: bool = False
    fail_on_security_warnings: bool = False
    fail_on_fuzz_failures: bool = True
    max_failures: int = 0
    max_warnings: int | None = None
    max_unknown: int | None = None
    required_modules: list[str] = field(default_factory=lambda: ["verify", "lint", "security", "fuzz"])
    strict_ast: bool = False
    clang: str | None = None
    clang_std: str = "c++17"
    clang_max_files: int | None = 30
    clang_timeout: int = 12

    @classmethod
    def from_mapping(cls, data: dict[str, Any], path: Path | None = None) -> "CIPolicy":
        def getn(*keys: str, default: Any = None) -> Any:
            cur: Any = data
            for key in keys:
                if not isinstance(cur, dict) or key not in cur: return default
                cur = cur[key]
            return cur
        def section(name: str) -> dict[str, Any]:
            val = data.get(name, {})
            return val if isinstance(val, dict) else {}
        dsl = getn("dsl", "files", default=[])
        dsl_files = [dsl] if isinstance(dsl, str) else [str(x) for x in dsl] if isinstance(dsl, list) else []
        ci, scan, verification, fuzz, security, thresholds, clang_cfg = (section(x) for x in ["ci","scan","verification","fuzz","security","thresholds","clang"])
        reqmods = ci.get("required_modules", ["verify", "lint", "security", "fuzz"])
        if isinstance(reqmods, str): reqmods = [x.strip() for x in reqmods.split(",") if x.strip()]
        return cls(
            path=path, project=str(data.get("project", "StructGuard Project")), scan_headers_only=bool(scan.get("headers_only", True)), dsl_files=dsl_files,
            max_cases=int(verification.get("max_cases", 300)), fuzz_seeds=int(fuzz.get("seeds", ci.get("fuzz_seeds", 10))), fuzz_steps=int(fuzz.get("steps", ci.get("fuzz_steps", 25))),
            deep_security=bool(security.get("deep", ci.get("deep_security", True))), fail_on_failed_contract=bool(verification.get("fail_on_failed_contract", ci.get("fail_on_failed_contract", True))),
            fail_on_warnings=bool(ci.get("fail_on_warnings", False)), fail_on_unknown=bool(ci.get("fail_on_unknown", False)),
            fail_on_security_warnings=bool(security.get("fail_on_warnings", ci.get("fail_on_security_warnings", False))), fail_on_fuzz_failures=bool(fuzz.get("fail_on_failures", ci.get("fail_on_fuzz_failures", True))),
            max_failures=int(thresholds.get("max_failures", ci.get("max_failures", 0))), max_warnings=_maybe_int(thresholds.get("max_warnings", ci.get("max_warnings"))), max_unknown=_maybe_int(thresholds.get("max_unknown", ci.get("max_unknown"))),
            required_modules=[str(x) for x in reqmods],
            strict_ast=bool(clang_cfg.get("strict_ast", verification.get("strict_ast", False))),
            clang=str(clang_cfg.get("binary")) if clang_cfg.get("binary") else None,
            clang_std=str(clang_cfg.get("std", "c++17")),
            clang_max_files=_maybe_int(clang_cfg.get("max_files", 30)),
            clang_timeout=int(clang_cfg.get("timeout", 12)))

def _maybe_int(value: Any) -> int | None:
    if value is None or value == "": return None
    try: return int(value)
    except Exception: return None

def _parse_scalar(value: str) -> Any:
    value=value.strip()
    if not value: return ""
    if value in {"true","True","yes","on"}: return True
    if value in {"false","False","no","off"}: return False
    if value in {"null","None","~"}: return None
    if value.startswith("[") and value.endswith("]"):
        try: return json.loads(value.replace("'", '"'))
        except Exception: return [x.strip().strip('"\'') for x in value[1:-1].split(",") if x.strip()]
    try: return int(value)
    except Exception: return value.strip('"\'')

def _minimal_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}; stack: list[tuple[int, Any]] = [(-1, root)]; last: dict[int, tuple[dict[str, Any], str]] = {}
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"): continue
        indent=len(raw)-len(raw.lstrip(" ")); line=raw.strip()
        while stack and indent <= stack[-1][0]: stack.pop()
        parent=stack[-1][1]
        if line.startswith("- "):
            target=last.get(indent-2) or last.get(indent)
            if target:
                mapping,key=target
                if not isinstance(mapping.get(key), list): mapping[key]=[]
                mapping[key].append(_parse_scalar(line[2:].strip()))
            continue
        if ":" not in line or not isinstance(parent, dict): continue
        key,val=line.split(":",1); key=key.strip(); val=val.strip()
        if val == "": parent[key]={}; last[indent]=(parent,key); stack.append((indent,parent[key]))
        else: parent[key]=_parse_scalar(val); last[indent]=(parent,key)
    return root

def load_policy(path: str | Path | None) -> CIPolicy:
    if not path: return CIPolicy()
    p=Path(path)
    if not p.exists(): raise FileNotFoundError(f"Archivo de política no encontrado: {p}")
    text=p.read_text(encoding="utf-8", errors="ignore")
    data=json.loads(text) if p.suffix.lower()==".json" else _minimal_yaml(text)
    return CIPolicy.from_mapping(data, path=p)

def default_policy_text(project_path: str = "Libreria_cc232") -> str:
    return f"""# Política CI de StructGuard
project: CC-232
version: 4.5.6
paths:
  - {project_path}
scan:
  headers_only: true
verification:
  mode: bounded
  max_cases: 300
  strict_ast: false
  fail_on_failed_contract: true
lint:
  require_invariants_for_data_structures: true
security:
  deep: true
  fail_on_warnings: false
fuzz:
  seeds: 20
  steps: 50
  fail_on_failures: true
thresholds:
  max_failures: 0
  max_warnings: 250
  max_unknown: 250
clang:
  std: c++17
  max_files: 30
  timeout: 12
ci:
  required_modules: [verify, lint, security, fuzz]
  fail_on_warnings: false
  fail_on_unknown: false
  fail_on_security_warnings: false
  fail_on_fuzz_failures: true
report:
  html: report/structguard-ci.html
  json: report/structguard-ci.json
  junit: report/structguard-junit.xml
  sarif: report/structguard.sarif
  summary_md: report/structguard-summary.md
"""

def github_actions_workflow_text(project_path: str = "Libreria_cc232", policy_path: str = "structguard.yml") -> str:
    return f"""name: StructGuard CI

on:
  push:
  pull_request:

jobs:
  quality:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Instalar paquete con herramientas de desarrollo
        run: python -m pip install -e '.[dev]'
      - name: Ejecutar pruebas
        run: pytest -q
      - name: Ejecutar lint crítico con Ruff
        run: ruff check .
      - name: Ejecutar verificación básica de tipos con mypy
        run: mypy
      - name: Ejecutar gate de política de StructGuard
        run: |
          mkdir -p report
          structguard ci {project_path} \
            --headers-only \
            --strict-ast \
            --policy {policy_path} \
            --deep-security \
            --html report/structguard-ci.html \
            --json report/structguard-ci.json \
            --junit report/structguard-junit.xml \
            --sarif report/structguard.sarif \
            --summary-md report/structguard-summary.md \
            --github-annotations
      - name: Validar salidas de reportes
        run: python scripts/validate_outputs.py
      - name: Subir reportes de StructGuard
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: structguard-reports
          path: report/
      - name: Subir SARIF
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: report/structguard.sarif
"""
