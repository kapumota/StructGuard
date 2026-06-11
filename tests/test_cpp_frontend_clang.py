from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from structguard.frontend.cpp import build_cpp_source_ir, load_compile_commands


def test_compile_commands_loader_resolves_relative_paths() -> None:
    db = load_compile_commands(Path("examples/cpp_projects/compile_commands.json"))

    assert db.commands
    assert db.files()[0].name == "Stack.cpp"
    assert db.command_for(db.files()[0]) is not None


def test_cpp_source_ir_lightweight_fallback_without_clang(tmp_path: Path) -> None:
    header = tmp_path / "MiniStack.hpp"
    header.write_text(
        """
class MiniStack {
public:
    void push(int value);
    int pop();
private:
    int size_;
};
""".strip()
        + "\n",
        encoding="utf-8",
    )

    source_ir = build_cpp_source_ir(
        tmp_path,
        clang="clang-inexistente-structguard",
        headers_only=True,
        fallback_allowed=True,
    )

    assert source_ir.frontend == "lightweight"
    assert source_ir.structures[0].name == "MiniStack"
    assert any(diagnostic.code == "CPP_CLANG_PARSE_FAILED" for diagnostic in source_ir.diagnostics)


def test_scan_accepts_cpp_frontend_options() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "structguard.cli",
            "scan",
            "examples/cpp_projects",
            "--language",
            "cpp",
            "--compile-commands",
            "examples/cpp_projects/compile_commands.json",
            "--profile",
            "generic-cpp",
            "--fallback-allowed",
        ],
        text=True,
        capture_output=True,
        env={"PYTHONPATH": "src"},
        check=False,
    )

    assert result.returncode == 0
    assert "CPP_SOURCE_IR_SUMMARY" in result.stdout
    assert "Frontend C++ activo" in result.stdout


def test_contract_bind_can_use_cpp_source_ir_with_fallback() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "structguard.cli",
            "contract",
            "bind",
            "examples/cpp_projects",
            "--contract",
            "profiles/generic-cpp/contracts/stack.sgdsl",
            "--language",
            "cpp",
            "--compile-commands",
            "examples/cpp_projects/compile_commands.json",
            "--fallback-allowed",
        ],
        text=True,
        capture_output=True,
        env={"PYTHONPATH": "src"},
        check=False,
    )

    assert result.returncode == 0
    assert "Resultado: OK" in result.stdout
