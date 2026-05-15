from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from typing import Any

from . import __version__


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str  
    message: str
    details: dict[str, Any]


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _version_of(cmd: list[str], timeout: int = 5) -> str | None:
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        out = (proc.stdout or proc.stderr).strip().splitlines()
        return out[0] if out else None
    except Exception:
        return None


def collect_doctor_checks(root: Path | None = None) -> list[DoctorCheck]:
    root = root or Path.cwd()
    checks: list[DoctorCheck] = []
    checks.append(DoctorCheck(
        "python",
        "ok" if sys.version_info >= (3, 10) else "missing",
        f"Python {platform.python_version()} ejecutando StructGuard {__version__}.",
        {"executable": sys.executable, "platform": platform.platform()},
    ))
    clang = shutil.which("clang++") or shutil.which("clang")
    checks.append(DoctorCheck(
        "clang",
        "ok" if clang else "warning",
        "Clang disponible para --strict-ast." if clang else "Clang no está disponible; --strict-ast fallará o se omitirá según el script.",
        {"path": clang, "version": _version_of([clang, "--version"]) if clang else None},
    ))
    z3 = shutil.which("z3")
    checks.append(DoctorCheck(
        "z3",
        "ok" if z3 else "warning",
        "Z3 disponible para formal --run-solver." if z3 else "Z3 CLI no está disponible; el modo formal podrá exportar SMT pero no probarlo localmente.",
        {"path": z3, "version": _version_of([z3, "--version"]) if z3 else None},
    ))
    for mod in ("pytest", "ruff", "mypy"):
        checks.append(DoctorCheck(
            mod,
            "ok" if _module_available(mod) else "warning",
            f"Módulo {mod} disponible." if _module_available(mod) else f"Módulo {mod} no instalado; instalar dev extras con python -m pip install -e '.[dev]'.",
            {"module": mod},
        ))
    expected = ["pyproject.toml", "src/structguard", "tests", "examples"]
    missing = [item for item in expected if not (root / item).exists()]
    checks.append(DoctorCheck(
        "source-tree",
        "ok" if not missing else "warning",
        "Árbol fuente esperado presente." if not missing else f"Faltan rutas esperadas: {', '.join(missing)}",
        {"root": str(root), "missing": missing},
    ))
    generated = ["src/structguard.egg-info", "__pycache__", ".pytest_cache", "build", "dist"]
    present = [item for item in generated if (root / item).exists()]
    checks.append(DoctorCheck(
        "clean-source",
        "ok" if not present else "warning",
        "No se detectaron artefactos generados comunes en la raíz del código fuente." if not present else f"Artefactos generados detectados: {', '.join(present)}",
        {"root": str(root), "generated_artifacts": present},
    ))
    return checks


def doctor_report(root: Path | None = None) -> dict[str, Any]:
    checks = collect_doctor_checks(root)
    counts: dict[str, int] = {}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    return {"tool": {"name": "StructGuard", "version": __version__}, "counts": counts, "checks": [asdict(c) for c in checks]}


def write_doctor_json(root: Path | None, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doctor_report(root), indent=2, ensure_ascii=False), encoding="utf-8")
    return path
