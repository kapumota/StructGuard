from __future__ import annotations

from pathlib import Path

from structguard.cli import main


def _write_stack_header(path: Path) -> None:
    path.write_text(
        """
        template <typename T>
        class Stack {
        public:
          void push(T value) { data_[size_] = value; size_++; }
          void pop() { size_--; }
          T top() const { return data_[size_ - 1]; }
          bool empty() const { return size_ == 0; }
        private:
          T data_[8];
          int size_ = 0;
        };
        """,
        encoding="utf-8",
    )


def test_testgen_accepts_canonical_output_flags(tmp_path: Path) -> None:
    header = tmp_path / "Stack.hpp"
    output_json = tmp_path / "testgen.json"
    output_html = tmp_path / "testgen.html"
    replay_script = tmp_path / "replay.py"
    test_dir = tmp_path / "generated_tests"
    _write_stack_header(header)

    exit_code = main(
        [
            "testgen",
            str(tmp_path),
            "--headers-only",
            "--seeds",
            "1",
            "--steps",
            "3",
            "--output-json",
            str(output_json),
            "--output-html",
            str(output_html),
            "--replay-script",
            str(replay_script),
            "--test-dir",
            str(test_dir),
        ]
    )

    assert exit_code in {0, 1}
    assert output_json.exists()
    assert output_html.exists()
    assert replay_script.exists()


def test_testgen_keeps_legacy_fuzz_flags_as_hidden_aliases(tmp_path: Path) -> None:
    header = tmp_path / "Stack.hpp"
    output_json = tmp_path / "legacy.json"
    output_html = tmp_path / "legacy.html"
    replay_script = tmp_path / "legacy_replay.py"
    _write_stack_header(header)

    exit_code = main(
        [
            "testgen",
            str(tmp_path),
            "--headers-only",
            "--seeds",
            "1",
            "--steps",
            "3",
            "--fuzz-json",
            str(output_json),
            "--fuzz-html",
            str(output_html),
            "--replay",
            str(replay_script),
        ]
    )

    assert exit_code in {0, 1}
    assert output_json.exists()
    assert output_html.exists()
    assert replay_script.exists()


def test_readme_promotes_canonical_scan_surface() -> None:
    text = Path("README.md").read_text(encoding="utf-8")

    assert "structguard scan" in text
    assert "--preset ci" in text
    assert "structguard legacy list" in text
    assert "--output-json" in text
    assert "--output-html" in text
    assert "--replay-script" in text


def test_changelog_mentions_closed_phases() -> None:
    text = Path("CHANGELOG.md").read_text(encoding="utf-8")

    assert "Fase 14" in text
    assert "Fase 15" in text
    assert "Fase 16" in text
    assert "scan --preset" in text
