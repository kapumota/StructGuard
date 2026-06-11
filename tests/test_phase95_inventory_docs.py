from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_scripts_inventory_documents_active_and_legacy_scripts() -> None:
    text = (ROOT / "docs" / "SCRIPTS_INVENTORY.md").read_text(encoding="utf-8")

    assert "scripts/demo.sh" in text
    assert "scripts/demo_full.sh" in text
    assert "scripts/demo_v4_4.sh" in text
    assert "scripts/demo_v4_5.sh" in text
    assert "No se deben eliminar scripts" in text


def test_legacy_modules_documents_modules_kept_by_compatibility() -> None:
    text = (ROOT / "docs" / "LEGACY_MODULES.md").read_text(encoding="utf-8")

    assert "src/structguard/advanced.py" in text
    assert "src/structguard/assist.py" in text
    assert "src/structguard/bench.py" in text
    assert "src/structguard/clang_frontend.py" in text
    assert "No se elimina ningún módulo" in text
