from __future__ import annotations

import json
from pathlib import Path

from structguard.model import Diagnostic, ProjectReport
from structguard.report import report_to_dict
from structguard.reporters.html_reporter import render_html
from structguard.reporters.json_reporter import render_json
from structguard.reporters.markdown_reporter import render_markdown
from structguard.reporters.sarif_reporter import sarif_document


def sample_report() -> ProjectReport:
    return ProjectReport(
        root="examples",
        diagnostics=[
            Diagnostic(
                level="WARNING",
                code="SG-STACK-POP-EMPTY",
                message="pop puede ejecutarse sin precondición de no vacío.",
                file="examples/Stack.hpp",
                line=10,
            ),
            Diagnostic(
                level="BOUNDED_VERIFIED",
                code="INVARIANT_HOLDS",
                message="No se encontró contraejemplo acotado.",
                file="examples/Stack.hpp",
                line=20,
            ),
        ],
    )


def test_findings_json_contains_guarantee_counts_and_guarantee_objects() -> None:
    payload = json.loads(render_json(sample_report()))

    assert payload["guarantee_counts"]["G2_STRUCTURAL"] == 1
    assert payload["guarantee_counts"]["G3_BOUNDED"] == 1
    assert payload["findings"][0]["guarantee"]["level"] in {"G2_STRUCTURAL", "G3_BOUNDED"}


def test_text_and_html_reporters_show_guarantee_badges() -> None:
    markdown = render_markdown(sample_report())
    html = render_html(sample_report())

    assert "[G2 Estructural]" in markdown
    assert "[G3 Acotado]" in markdown
    assert "G2_STRUCTURAL" in html
    assert "G3_BOUNDED" in html


def test_sarif_contains_guarantee_properties() -> None:
    sarif = sarif_document(sample_report())
    result = sarif["runs"][0]["results"][0]

    assert "guarantee" in result["properties"]
    assert "guarantee_level" in result["properties"]


def test_legacy_report_keeps_internal_level_but_adds_display_and_guarantee() -> None:
    payload = report_to_dict(sample_report())
    bounded = [item for item in payload["diagnostics"] if item["level"] == "BOUNDED_VERIFIED"][0]

    assert bounded["display_level"] == "BOUNDED_CHECK_PASSED"
    assert bounded["guarantee"]["level"] == "G3_BOUNDED"


def test_docs_are_present() -> None:
    root = Path(__file__).resolve().parents[1]

    assert (root / "docs" / "GUARANTEE_LEVELS.md").exists()
    assert (root / "docs" / "V1_SUCCESS_CRITERIA.md").exists()
