from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

from structguard.findings import Finding, Location, findings_from_report
from structguard.model import Diagnostic, ProjectReport
from structguard.reporters.html_reporter import render_html
from structguard.reporters.json_reporter import render_json, write_json_report
from structguard.reporters.junit_reporter import write_junit_report
from structguard.reporters.markdown_reporter import render_markdown
from structguard.reporters.sarif_reporter import sarif_document, write_sarif_report


def sample_report() -> ProjectReport:
    return ProjectReport(
        root="examples/generic_cpp",
        diagnostics=[
            Diagnostic(
                level="FAILED",
                code="BINDING_ORPHAN_METHOD",
                message="El contrato declara un método inexistente.",
                file="examples/generic_cpp/Stack.hpp",
                line=12,
                symbol="Stack::add",
                details={"confidence": "high", "evidence": "binding", "remediation": "Renombrar el contrato o el método."},
            ),
            Diagnostic(
                level="WARNING",
                code="SEC_BOUNDS_RISK",
                message="Riesgo de índice fuera de rango.",
                file="examples/generic_cpp/Stack.hpp",
                line=21,
                symbol="Stack::push",
                details={"cwe": "CWE-787"},
            ),
        ],
    )


def test_finding_model_normalizes_diagnostics() -> None:
    findings = findings_from_report(sample_report())

    assert len(findings) == 2
    assert findings[0].rule_id == "BINDING_ORPHAN_METHOD"
    assert findings[0].severity == "error"
    assert findings[0].confidence == "high"
    assert findings[0].location == Location(file="examples/generic_cpp/Stack.hpp", line=12)
    assert findings[1].cwe == "CWE-787"
    assert "security" in findings[1].tags


def test_json_reporter_uses_findings_document(tmp_path: Path) -> None:
    out = tmp_path / "findings.json"
    write_json_report(sample_report(), out)
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "structguard-findings/v1"
    assert payload["counts"]["error"] == 1
    assert payload["findings"][0]["rule_id"] == "BINDING_ORPHAN_METHOD"
    assert "BINDING_ORPHAN_METHOD" in render_json(sample_report())


def test_text_reporters_render_without_engine_dependency() -> None:
    markdown = render_markdown(sample_report())
    html = render_html(sample_report())

    assert "BINDING_ORPHAN_METHOD" in markdown
    assert "SEC_BOUNDS_RISK" in html
    assert "Reporte de hallazgos StructGuard" in markdown


def test_junit_and_sarif_reporters_write_files(tmp_path: Path) -> None:
    junit_path = tmp_path / "findings.xml"
    sarif_path = tmp_path / "findings.sarif"

    write_junit_report(sample_report(), junit_path)
    write_sarif_report(sample_report(), sarif_path)

    suite = ET.parse(junit_path).getroot()
    assert suite.attrib["failures"] == "1"

    sarif = json.loads(sarif_path.read_text(encoding="utf-8"))
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"][0]["ruleId"] == "BINDING_ORPHAN_METHOD"
    assert sarif_document(sample_report())["runs"][0]["tool"]["driver"]["name"] == "StructGuard"


def test_manual_reporter_can_use_finding_without_analysis_engine() -> None:
    finding = Finding(
        rule_id="CUSTOM_RULE",
        title="Regla personalizada",
        message="Mensaje personalizado",
        severity="warning",
        confidence="medium",
        location=Location(file="x.hpp", line=1),
        evidence=["prueba"],
        tags=["custom"],
    )

    assert finding.as_dict()["rule_id"] == "CUSTOM_RULE"
    assert finding.location.display == "x.hpp:1"
