from pathlib import Path

from structguard import __version__


def test_stable_version_label():
    assert __version__.endswith("stable")


def test_release_code_assets_present():
    root = Path(__file__).resolve().parents[1]
    for rel in [
        "pyproject.toml",
        "src/structguard/cli.py",
        "src/structguard/verifier.py",
        "src/structguard/cppscan.py",
        "scripts/final_demo.sh",
        "scripts/demo_clean_ci.sh",
        "scripts/demo_bug_detection.sh",
        "scripts/smoke_test.sh",
    ]:
        assert (root / rel).exists(), rel
