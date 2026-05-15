from pathlib import Path
from structguard.ci import ci_project
from structguard.ci_outputs import write_junit, write_sarif, write_summary_markdown
from structguard.policy import load_policy, default_policy_text

def test_policy_loader(tmp_path):
    p = tmp_path / "structguard.yml"
    p.write_text(default_policy_text("examples"), encoding="utf-8")
    policy = load_policy(p)
    assert policy.project == "CC-232"
    assert policy.scan_headers_only is True
    assert policy.deep_security is True
    assert "verify" in policy.required_modules

def test_ci_outputs(tmp_path):
    policy = tmp_path / "structguard.yml"
    policy.write_text(default_policy_text("examples"), encoding="utf-8")
    report = ci_project(Path("examples"), headers_only=True, policy_path=policy)
    junit = write_junit(report, tmp_path / "structguard.xml")
    sarif = write_sarif(report, tmp_path / "structguard.sarif")
    md = write_summary_markdown(report, tmp_path / "summary.md")
    assert junit.exists() and "testsuite" in junit.read_text(encoding="utf-8")
    assert sarif.exists() and '"version": "2.1.0"' in sarif.read_text(encoding="utf-8")
    assert md.exists() and "Resumen CI de StructGuard" in md.read_text(encoding="utf-8")
