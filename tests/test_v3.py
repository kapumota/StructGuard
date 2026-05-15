from pathlib import Path
from structguard.clang_frontend import clang_frontend_project
from structguard.formal import write_formal_artifacts


def test_clang_frontend_examples():
    report = clang_frontend_project(Path('examples'), headers_only=True, max_files=2, timeout=8)
    assert any(d.code == 'CLANG_FRONTEND_SUMMARY' for d in report.diagnostics)


def test_formal_exports_examples(tmp_path):
    artifacts, report = write_formal_artifacts(Path('examples'), tmp_path, backend='both', headers_only=True)
    assert artifacts
    assert any(a.backend == 'smt' for a in artifacts)
    assert any(a.backend == 'viper' for a in artifacts)
    assert (tmp_path / 'formal_manifest.json').exists()
