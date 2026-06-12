from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase19_root_contracts_directory_was_removed() -> None:
    assert not (ROOT / "contracts").exists()


def test_phase19_canonical_contract_paths_exist() -> None:
    assert (ROOT / "profiles" / "cc232" / "contracts" / "cc232_core.sgdsl").is_file()
    assert (
        ROOT / "profiles" / "advanced-structures" / "contracts" / "advanced_structures.sgdsl"
    ).is_file()
    assert (ROOT / "profiles" / "generic-cpp" / "contracts" / "stack.sgdsl").is_file()


def test_phase19_contracts_layout_documents_canonical_profile_paths() -> None:
    text = (ROOT / "docs" / "CONTRACTS_LAYOUT.md").read_text(encoding="utf-8")

    assert "profiles/<perfil>/contracts/" in text
    assert "profiles/cc232/contracts/cc232_core.sgdsl" in text
    assert "profiles/advanced-structures/contracts/advanced_structures.sgdsl" in text
    assert "carpeta raíz `contracts/` fue retirada" in text


def test_phase19_readme_documents_badges_and_next_release() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "actions/workflows/structguard.yml/badge.svg" in text
    assert "actions/workflows/benchmark.yml/badge.svg" in text
    assert "### Lo que viene" in text
    assert "Fase 20" in text
    assert "v1.0.0" in text


def test_phase19_readme_does_not_recommend_root_contract_paths() -> None:
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "contracts/cc232_core.sgdsl" not in text.replace(
        "profiles/cc232/contracts/cc232_core.sgdsl", ""
    )
    assert "contracts/advanced_structures.sgdsl" not in text.replace(
        "profiles/advanced-structures/contracts/advanced_structures.sgdsl", ""
    )


def test_phase19_release_roadmap_documents_phase20() -> None:
    text = (ROOT / "docs" / "RELEASE_ROADMAP.md").read_text(encoding="utf-8")

    assert "Fase 20" in text
    assert "v1.0.0" in text
    assert "git tag -a v1.0.0" in text
    assert "GitHub Release" in text
    assert "StructGuard CI" in text
    assert "Benchmark" in text


def test_phase19_cc232_demo_uses_canonical_cli() -> None:
    text = (ROOT / "scripts" / "final_demo_cc232.sh").read_text(encoding="utf-8")

    assert "structguard.cli scan" in text
    assert "--profile cc232" in text
    assert "--preset ci" in text
    assert "structguard.cli report derive" in text
    assert "structguard.cli testgen" in text
    assert "--output-json" in text
    assert "--fuzz-json" not in text
    assert "structguard.cli ci" not in text
    assert "structguard.cli analyze" not in text
