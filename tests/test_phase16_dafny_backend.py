from __future__ import annotations

from pathlib import Path

from structguard.exporters.dafny import export_dafny_contracts, write_dafny_manifest
from structguard.cli import main


def test_dafny_export_generates_supported_model(tmp_path: Path) -> None:
    contract = tmp_path / "array_stack.sgdsl"
    contract.write_text(
        """
package formal.dafny;

structure ArrayStack {
  invariant n >= 0;
  invariant n <= capacity();
  method add { requires 0 <= i && i <= n; ensures n == old(n) + 1; }
  method remove { requires 0 <= i && i < n; ensures n == old(n) - 1; }
}
""".strip(),
        encoding="utf-8",
    )

    results = export_dafny_contracts([str(contract)], tmp_path / "out")

    assert len(results) == 1
    result = results[0]
    assert result.structure == "formal.dafny.ArrayStack"
    assert result.status == "GENERATED"
    assert result.file is not None

    generated = Path(result.file)
    text = generated.read_text(encoding="utf-8")
    assert "trait ArrayStackModel" in text
    assert "predicate Valid()" in text
    assert "requires 0 <= i && i <= n" in text
    assert "ensures n == old(n) + 1" in text


def test_dafny_export_marks_unsupported_structure(tmp_path: Path) -> None:
    contract = tmp_path / "tree.sgdsl"
    contract.write_text(
        """
package formal.dafny;

structure RedBlackTree {
  invariant n >= 0;
  method insert { ensures n == old(n) + 1; }
}
""".strip(),
        encoding="utf-8",
    )

    results = export_dafny_contracts([str(contract)], tmp_path / "out")

    assert len(results) == 1
    assert results[0].status == "UNSUPPORTED"
    assert results[0].file is None


def test_dafny_manifest_lists_status_values(tmp_path: Path) -> None:
    contract = tmp_path / "array_queue.sgdsl"
    contract.write_text(
        """
package formal.dafny;

structure ArrayQueue {
  invariant n >= 0;
  invariant n <= capacity();
  invariant j >= 0;
  invariant j < capacity();
  method add { requires n < capacity(); ensures n == old(n) + 1; }
}
""".strip(),
        encoding="utf-8",
    )

    results = export_dafny_contracts([str(contract)], tmp_path / "out")
    manifest = tmp_path / "out" / "dafny_manifest.json"
    write_dafny_manifest(results, manifest)
    text = manifest.read_text(encoding="utf-8")

    assert "GENERATED" in text
    assert "PARSED" in text
    assert "VERIFIED" in text
    assert "FAILED" in text
    assert "UNKNOWN" in text
    assert "UNSUPPORTED" in text


def test_cli_formal_dafny_backend_writes_manifest(tmp_path: Path) -> None:
    contract = tmp_path / "array_stack.sgdsl"
    contract.write_text(
        """
package formal.dafny;

structure ArrayStack {
  invariant n >= 0;
  invariant n <= capacity();
  method push { ensures n == old(n) + 1; }
}
""".strip(),
        encoding="utf-8",
    )
    out_dir = tmp_path / "formal"

    rc = main(["formal", str(tmp_path), "--backend", "dafny", "--dsl", str(contract), "--out-dir", str(out_dir)])

    assert rc == 0
    assert (out_dir / "dafny" / "ArrayStackModel.dfy").exists()
    assert (out_dir / "dafny_manifest.json").exists()
