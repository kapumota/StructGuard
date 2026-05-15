from pathlib import Path

from structguard.suggest import collect_suggestions, write_patch, write_annotated_copy


def test_suggest_finds_buggy_stack_precondition(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    suggestions = collect_suggestions(root / "examples" / "stack_bug.h", headers_only=True)
    assert any(s.kind == "requires" and s.expression == "!empty()" and "pop" in s.symbol for s in suggestions)


def test_suggest_writes_patch(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    suggestions = collect_suggestions(root / "examples" / "stack_bug.h", headers_only=True)
    patch = tmp_path / "contracts.patch"
    write_patch(root / "examples" / "stack_bug.h", suggestions, patch)
    text = patch.read_text(encoding="utf-8")
    assert "// requires: !empty()" in text


def test_suggest_writes_annotated_copy(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    src = root / "examples" / "stack_bug.h"
    suggestions = collect_suggestions(src, headers_only=True)
    out = write_annotated_copy(src, suggestions, tmp_path / "annotated")
    text = (out / "stack_bug.h").read_text(encoding="utf-8")
    assert "// requires: !empty()" in text
