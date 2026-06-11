from __future__ import annotations

import json
from pathlib import Path

from structguard.model import Diagnostic, ProjectReport
from structguard.reporting import derive_reports_from_canonical, load_canonical_report, write_canonical_report, write_lockfile
from structguard.reporting.canonical_report import build_canonical_report
from structguard.reporting.lockfile import build_lockfile


def sample_report() -> ProjectReport:
    return ProjectReport(
        root="examples/generic_cpp",
        diagnostics=[
            Diagnostic(
                level="WARNING",
                code="SG-BOUNDS-INDEX-RISK",
                message="Riesgo de acceso fuera de rango.",
                file="examples/generic_cpp/Stack.hpp",
                line=17,
                symbol="Stack::top",
                details={"confidence": "medium", "evidence": "regla estructural"},
            )
        ],
    )


def test_canonical_report_contains_summary_rules_and_findings() -> None:
    document = build_canonical_report(sample_report(), context={"profile": "generic-cpp", "preset": "security"})

    assert document["schema_version"] == "structguard-canonical-report/v1"
    assert document["run"]["profile"] == "generic-cpp"
    assert document["run"]["preset"] == "security"
    assert document["summary"]["total_findings"] == 1
    assert document["rules"][0]["rule_id"] == "SG-BOUNDS-INDEX-RISK"
    assert document["findings"][0]["guarantee"]["level"] == "G2_STRUCTURAL"


def test_canonical_report_can_be_written_loaded_and_derived(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    write_canonical_report(sample_report(), report_path, context={"preset": "security"})

    document = load_canonical_report(report_path)
    html = tmp_path / "report.html"
    sarif = tmp_path / "report.sarif"
    junit = tmp_path / "junit.xml"
    markdown = tmp_path / "report.md"

    written = derive_reports_from_canonical(document, html=html, sarif=sarif, junit=junit, markdown=markdown)

    assert sorted(path.name for path in written) == ["junit.xml", "report.html", "report.md", "report.sarif"]
    assert "SG-BOUNDS-INDEX-RISK" in html.read_text(encoding="utf-8")
    assert json.loads(sarif.read_text(encoding="utf-8"))["version"] == "2.1.0"
    assert "Reporte canónico StructGuard" in markdown.read_text(encoding="utf-8")


def test_lockfile_records_hashes_and_environment(tmp_path: Path) -> None:
    source = tmp_path / "Stack.hpp"
    source.write_text("class Stack {};\n", encoding="utf-8")

    document = build_lockfile(source, context={"preset": "security"})

    assert document["schema_version"] == "structguard-lock/v1"
    assert document["context"]["preset"] == "security"
    assert document["input_hashes"][0]["path"] == "Stack.hpp"
    assert len(document["input_hashes"][0]["sha256"]) == 64
    assert "python" in document["environment"]


def test_lockfile_can_be_written(tmp_path: Path) -> None:
    source = tmp_path / "Queue.hpp"
    source.write_text("class Queue {};\n", encoding="utf-8")
    out = tmp_path / "structguard.lock"

    write_lockfile(source, out, context={"profile": "generic-cpp"})

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["context"]["profile"] == "generic-cpp"
    assert payload["input_hashes"][0]["path"] == "Queue.hpp"
