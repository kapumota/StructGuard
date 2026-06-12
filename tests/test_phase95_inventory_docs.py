from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_scripts_inventory_documents_active_and_retired_scripts() -> None:
    text = (ROOT / "docs" / "SCRIPTS_INVENTORY.md").read_text(encoding="utf-8")

    assert "scripts/demo.sh" in text
    assert "scripts/demo_full.sh" in text
    assert "scripts/smoke_new_user.sh" in text
    assert "scripts/demo_v4_4.sh" in text
    assert "scripts/demo_v4_5.sh" in text
    assert "Retirado" in text
    assert "No se deben eliminar scripts" in text
    assert not (ROOT / "scripts" / "demo_v4_4.sh").exists()
    assert not (ROOT / "scripts" / "demo_v4_5.sh").exists()


def test_legacy_modules_documents_modules_kept_by_compatibility() -> None:
    text = (ROOT / "docs" / "LEGACY_MODULES.md").read_text(encoding="utf-8")

    assert "src/structguard/frontend.py" in text
    assert "src/structguard/cppscan.py" in text
    assert "src/structguard/clang_frontend.py" in text
    assert "src/structguard/fuzz.py" in text
    assert "testgen" in text
    assert "report derive" in text
    assert "La Fase 18 no elimina módulos" in text
