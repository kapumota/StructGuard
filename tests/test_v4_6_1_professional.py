from __future__ import annotations

import json
from pathlib import Path

from structguard.cli import main
from structguard.doctor import doctor_report
from structguard.metadata import diagnostic_to_dict
from structguard.model import Diagnostic, ProjectReport
from structguard.report import write_json
from structguard.cppscan import scan_project


def test_doctor_report_contains_release_checks() -> None:
    data = doctor_report(Path(__file__).resolve().parents[1])
    names = {check["name"] for check in data["checks"]}
    assert {"python", "source-tree", "clean-source", "clang", "z3"} <= names
    assert data["tool"]["version"].endswith("stable")


def test_doctor_cli_writes_json(tmp_path: Path) -> None:
    out = tmp_path / "doctor.json"
    rc = main(["doctor", str(Path(__file__).resolve().parents[1]), "--json", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "checks" in data and data["counts"]


def test_report_json_enriches_professional_metadata(tmp_path: Path) -> None:
    report = ProjectReport(root=str(tmp_path), diagnostics=[Diagnostic(level="FAILED", code="INVARIANT_NOT_PRESERVED", message="bad", details={"counterexample": {"explanation": "x"}})])
    out = tmp_path / "report.json"
    write_json(report, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    details = data["diagnostics"][0]["details"]
    assert details["confidence"] == "high"
    assert details["evidence"] == "bounded_symbolic_execution"
    assert "remediation" in details


def test_professional_examples_are_scannable() -> None:
    project = Path(__file__).resolve().parents[1]
    classes = scan_project(project / "examples" / "realistic", headers_only=True)
    names = {c.name for c in classes}
    assert {"RealisticStack", "RealisticVector", "CircularQueue"} <= names


def test_diagnostic_to_dict_keeps_existing_details_and_adds_metadata() -> None:
    d = Diagnostic(level="WARNING", code="SEC_OVERFLOW_RISK", message="risk", details={"custom": 1})
    data = diagnostic_to_dict(d)
    assert data["details"]["custom"] == 1
    assert data["details"]["category"] == "security"
    assert data["details"]["evidence"] == "security_heuristic"
