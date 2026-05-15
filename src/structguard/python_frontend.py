from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import ast
import json
import re

from .model import Diagnostic, ProjectReport


CONTRACT_RE = re.compile(
    r'(?:#|//)\s*(requires|ensures|invariant)\s*:\s*(.+)',
    re.I,
)


@dataclass
class PyFunction:
    name: str
    line: int
    class_name: str | None
    args: list[str]
    requires: list[str]
    ensures: list[str]


@dataclass
class PyUnit:
    file: str
    classes: list[str]
    functions: list[PyFunction]
    invariants: list[str]


def iter_py(root: Path):
    if root.is_file() and root.suffix == '.py':
        yield root

    elif root.is_dir():
        yield from sorted(root.rglob('*.py'))


def _contracts_before(
    lines: list[str],
    lineno: int,
):
    req = []
    ens = []
    inv = []

    i = lineno - 2

    while i >= 0 and lines[i].strip().startswith('#'):
        cm = CONTRACT_RE.search(lines[i])

        if cm:
            kind = cm.group(1).lower()
            expr = cm.group(2).strip()

            if kind == 'requires':
                req.append(expr)

            elif kind == 'ensures':
                ens.append(expr)

            elif kind == 'invariant':
                inv.append(expr)

        i -= 1

    return (
        list(reversed(req)),
        list(reversed(ens)),
        list(reversed(inv)),
    )


def scan_python_file(path: Path) -> PyUnit:
    text = path.read_text(
        encoding='utf-8',
        errors='ignore',
    )

    lines = text.splitlines()

    try:
        tree = ast.parse(text)

    except SyntaxError:
        return PyUnit(
            str(path),
            [],
            [],
            [],
        )

    classes = []
    funcs = []
    invariants = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)

            _, _, inv = _contracts_before(
                lines,
                node.lineno,
            )

            invariants.extend(inv)

            for ch in node.body:
                if isinstance(
                    ch,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                ):
                    req, ens, inv2 = _contracts_before(
                        lines,
                        ch.lineno,
                    )

                    invariants.extend(inv2)

                    funcs.append(
                        PyFunction(
                            ch.name,
                            ch.lineno,
                            node.name,
                            [a.arg for a in ch.args.args],
                            req,
                            ens,
                        )
                    )

        elif isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            req, ens, inv = _contracts_before(
                lines,
                node.lineno,
            )

            invariants.extend(inv)

            funcs.append(
                PyFunction(
                    node.name,
                    node.lineno,
                    None,
                    [a.arg for a in node.args.args],
                    req,
                    ens,
                )
            )

    return PyUnit(
        str(path),
        classes,
        funcs,
        invariants,
    )


def python_frontend_project(
    root: Path,
) -> ProjectReport:
    units = [
        scan_python_file(p)
        for p in iter_py(root)
    ]

    report = ProjectReport(root=str(root))

    report.diagnostics.append(
        Diagnostic(
            level='INFO' if units else 'WARNING',
            code='PYTHON_FRONTEND_SUMMARY',
            message='Escaneo del frontend de Python completado.',
            file=str(root),
            details={
                'files': len(units),
                'classes': sum(len(u.classes) for u in units),
                'functions': sum(len(u.functions) for u in units),
                'invariants': sum(len(u.invariants) for u in units),
            },
        )
    )

    for u in units:
        for fn in u.functions:
            report.diagnostics.append(
                Diagnostic(
                    level='INFO',
                    code='PYTHON_FUNCTION',
                    message=(
                        f'Funcion python {fn.name} '
                        f'con {len(fn.requires)} requires y '
                        f'{len(fn.ensures)} ensures.'
                    ),
                    file=u.file,
                    line=fn.line,
                    symbol=(
                        f'{fn.class_name}.{fn.name}'
                        if fn.class_name
                        else fn.name
                    ),
                    details=asdict(fn),
                )
            )

    return report


def write_python_json(
    root: Path,
    out: Path,
) -> Path:
    data = [
        asdict(scan_python_file(p))
        for p in iter_py(root)
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
        encoding='utf-8',
    )

    return out