from __future__ import annotations

import json
from pathlib import Path

from structguard.findings import findings_document
from structguard.model import ProjectReport


def render_json(report: ProjectReport) -> str:
    return json.dumps(findings_document(report), indent=2, ensure_ascii=False) + "\n"


def write_json_report(report: ProjectReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_json(report), encoding="utf-8")
    return path
