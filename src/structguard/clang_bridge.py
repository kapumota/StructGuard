from __future__ import annotations

from pathlib import Path
from typing import Any

from .clang_frontend import clang_summaries
from .model import ClassModel


def merge_clang_structural_model(
    classes: list[ClassModel],
    root: Path,
    *,
    headers_only: bool = False,
    clang: str | None = None,
    std: str = "c++17",
    max_files: int | None = 30,
    timeout: int = 12,
) -> tuple[list[ClassModel], dict[str, Any]]:
    """Prefiere los hechos estructurales del AST de Clang cuando estén disponibles, preservando cuerpos/contratos detectados por regex.

    El verificador acotado todavía necesita el escáner ligero para comentarios y cuerpos
    de métodos. Este puente hace que Clang tenga prioridad para hechos estructurales:
    nombres de clases, campos, métodos y conteos de plantillas. Si Clang no está
    disponible o no puede parsear, las clases originales se devuelven sin cambios
    junto con metadatos que explican el fallback.
    """
    summaries = clang_summaries(
        root,
        headers_only=headers_only,
        clang=clang,
        std=std,
        max_files=max_files,
        timeout=timeout,
        ast_filter=None,
    )

    metadata = {
        "enabled": True,
        "files": len(summaries),
        "ok": sum(1 for s in summaries if s.ok),
        "failed": sum(1 for s in summaries if not s.ok),
        "merged_records": 0,
        "fallback": False,
    }

    if not summaries or not any(s.ok for s in summaries):
        metadata["fallback"] = True
        return classes, metadata

    by_name = {c.name.split("::")[-1]: c for c in classes}

    for summary in summaries:
        if not summary.ok:
            continue

        for rec in summary.record_models:
            name = str(rec.get("name") or "")
            if not name:
                continue

            cls = by_name.get(name)

            if cls is None:
                cls = ClassModel(
                    name=name,
                    file=Path(rec.get("file") or summary.file),
                    start_line=int(rec.get("line") or 0),
                )
                classes.append(cls)
                by_name[name] = cls

            before = set(cls.fields)
            cls.fields |= {str(f) for f in rec.get("fields") or []}

            if set(cls.fields) != before or rec.get("methods"):
                metadata["merged_records"] += 1

            # Manteniene los cuerpos de métodos provenientes de cppscan;
            # los stubs con solo nombres de métodos no bastan para la verificación.
            cls.__dict__.setdefault("clang_methods", list(rec.get("methods") or []))
            cls.__dict__.setdefault("clang_bases", list(rec.get("bases") or []))

    return classes, metadata