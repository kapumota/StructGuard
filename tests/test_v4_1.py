from pathlib import Path
from structguard.docs import build_documentation_model, write_docs_html, write_docs_json, write_docs_markdown


def test_docs_model_examples(tmp_path: Path):
    root = Path('examples')
    model = build_documentation_model(root, headers_only=True)
    assert model.summary()['structures'] >= 1
    assert model.summary()['operations'] >= 1
    html = write_docs_html(model, tmp_path / 'docs.html')
    js = write_docs_json(model, tmp_path / 'docs.json')
    md = write_docs_markdown(model, tmp_path / 'md')
    assert html.exists() and 'StructGuard' in html.read_text()
    assert js.exists() and 'structures' in js.read_text()
    assert md.exists() and '# Documentación StructGuard' in md.read_text()
