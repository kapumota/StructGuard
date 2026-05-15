from pathlib import Path
from structguard.security import security_project, security_rules_catalog, write_security_json, write_security_rules_json


def test_deep_security_detects_bounds_and_summary(tmp_path):
    root = Path(__file__).resolve().parents[1] / "examples"
    report = security_project(root, headers_only=True, deep=True)
    codes = {d.code for d in report.diagnostics}
    assert "SEC_SECURITY_SUMMARY" in codes
    assert any(c.startswith("SEC_") for c in codes)
    out = tmp_path / "security.json"
    write_security_json(report, out)
    assert out.exists()
    assert "SEC_SECURITY_SUMMARY" in out.read_text()


def test_security_rules_catalog_json(tmp_path):
    rules = security_rules_catalog()
    assert any(r["code"] == "SEC_BOUNDS_RISK" for r in rules)
    out = tmp_path / "rules.json"
    write_security_rules_json(out)
    assert "SEC_BOUNDS_RISK" in out.read_text()
