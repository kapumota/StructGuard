from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re

from .model import Diagnostic, ProjectReport


STRUCT_RE = re.compile(
    r"\b(?:pub\s+)?(?:struct|enum|trait)\s+([A-Za-z_]\w*)"
)
IMPL_RE = re.compile(
    r"\bimpl(?:\s*<[^>]*>)?\s+([A-Za-z_]\w*)"
)
FN_RE = re.compile(
    r"\b(?:pub\s+)?fn\s+([A-Za-z_]\w*)\s*\(([^)]*)\)"
)
CONTRACT_RE = re.compile(
    r"//\s*(requires|ensures|invariant)\s*:\s*(.+)",
    re.I,
)


@dataclass
class RustFunction:
    name: str
    line: int
    receiver: str | None
    requires: list[str]
    ensures: list[str]


@dataclass
class RustUnit:
    file: str
    structures: list[str]
    functions: list[RustFunction]
    invariants: list[str]


def iter_rs(root: Path):
    if root.is_file() and root.suffix == ".rs":
        yield root
    elif root.is_dir():
        yield from sorted(root.rglob("*.rs"))


def scan_rust_file(path: Path) -> RustUnit:
    text = path.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    structures = [
        m.group(1)
        for m in STRUCT_RE.finditer(text)
    ]

    functions = []
    invariants = []
    pending_req = []
    pending_ens = []
    current_impl = None

    for i, line in enumerate(
        text.splitlines(),
        start=1,
    ):
        im = IMPL_RE.search(line)

        if im:
            current_impl = im.group(1)

        cm = CONTRACT_RE.search(line)

        if cm:
            kind = cm.group(1).lower()
            expr = cm.group(2).strip()

            if kind == "requires":
                pending_req.append(expr)
            elif kind == "ensures":
                pending_ens.append(expr)
            elif kind == "invariant":
                invariants.append(expr)

            continue

        fm = FN_RE.search(line)

        if fm:
            functions.append(
                RustFunction(
                    fm.group(1),
                    i,
                    current_impl,
                    pending_req,
                    pending_ens,
                )
            )

            pending_req = []
            pending_ens = []

    return RustUnit(
        str(path),
        structures,
        functions,
        invariants,
    )


def rust_frontend_project(root: Path) -> ProjectReport:
    units = [
        scan_rust_file(p)
        for p in iter_rs(root)
    ]

    report = ProjectReport(root=str(root))

    report.diagnostics.append(
        Diagnostic(
            level="INFO" if units else "WARNING",
            code="RUST_FRONTEND_SUMMARY",
            message="Escaneo del frontend de Rust completado.",
            file=str(root),
            details={
                "files": len(units),
                "structures": sum(len(u.structures) for u in units),
                "functions": sum(len(u.functions) for u in units),
                "invariants": sum(len(u.invariants) for u in units),
            },
        )
    )

    for u in units:
        for fn in u.functions:
            report.diagnostics.append(
                Diagnostic(
                    level="INFO",
                    code="RUST_FUNCTION",
                    message=(
                        f"Función de Rust {fn.name} "
                        f"con {len(fn.requires)} requires y "
                        f"{len(fn.ensures)} ensures."
                    ),
                    file=u.file,
                    line=fn.line,
                    symbol=(
                        f"{fn.receiver}::{fn.name}"
                        if fn.receiver
                        else fn.name
                    ),
                    details=asdict(fn),
                )
            )

    return report


def write_rust_json(
    root: Path,
    out: Path,
) -> Path:
    data = [
        asdict(scan_rust_file(p))
        for p in iter_rs(root)
    ]

    out.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    out.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return out
