from pathlib import Path
from structguard.pipeline import build_pipeline_units, pipeline_report, write_pipeline_artifacts
from structguard.rust_frontend import rust_frontend_project
from structguard.python_frontend import python_frontend_project
from structguard.advanced import write_advanced_dsl

ROOT = Path(__file__).resolve().parents[1]

def test_pipeline_report_examples():
    report = pipeline_report(ROOT / 'examples', headers_only=True, max_files=1)
    assert report.diagnostics

def test_pipeline_artifacts_examples(tmp_path):
    _, report = write_pipeline_artifacts(ROOT / 'examples', tmp_path, headers_only=True, max_files=1, backend='both')
    assert report.diagnostics
    assert (tmp_path / 'pipeline_manifest.json').exists()

def test_rust_and_python_frontends():
    assert rust_frontend_project(ROOT / 'examples' / 'rust').diagnostics
    assert python_frontend_project(ROOT / 'examples' / 'python').diagnostics

def test_advanced_dsl(tmp_path):
    out = tmp_path / 'advanced.sgdsl'
    write_advanced_dsl(out)
    assert out.exists() and 'WaveletTree' in out.read_text()
