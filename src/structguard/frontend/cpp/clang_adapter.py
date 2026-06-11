from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .compile_commands import CompileCommand, flags_for_clang


@dataclass(frozen=True)
class ClangFrontendConfig:
    clang: str | None = None
    std: str = "c++17"
    timeout: int = 12
    extra_args: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClangParseResult:
    file: Path
    ok: bool
    ast: dict[str, Any] | None = None
    command: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    error: str = ""


class ClangUnavailableError(RuntimeError):
    pass


def find_clang_binary(config: ClangFrontendConfig) -> str:
    if config.clang:
        resolved = shutil.which(config.clang) or config.clang
        if Path(resolved).exists() or shutil.which(resolved):
            return resolved
        raise ClangUnavailableError(f"No se encontró el binario Clang indicado: {config.clang}")
    for candidate in ["clang++", "clang"]:
        resolved = shutil.which(candidate) or candidate
        if Path(resolved).exists() or shutil.which(resolved):
            return resolved
    raise ClangUnavailableError("No se encontró clang++ ni clang en el entorno")


def build_ast_command(file: Path, config: ClangFrontendConfig, compile_command: CompileCommand | None = None) -> list[str]:
    clang = find_clang_binary(config)
    args = flags_for_clang(compile_command)
    if not any(arg.startswith("-std=") for arg in args):
        args.append(f"-std={config.std}")
    args.extend(config.extra_args)
    return [
        clang,
        *args,
        "-Xclang",
        "-ast-dump=json",
        "-fsyntax-only",
        str(file),
    ]


def parse_translation_unit(file: Path, config: ClangFrontendConfig, compile_command: CompileCommand | None = None) -> ClangParseResult:
    try:
        command = build_ast_command(file, config, compile_command)
    except ClangUnavailableError as exc:
        return ClangParseResult(file=file, ok=False, error=str(exc))
    cwd = compile_command.directory if compile_command else file.parent
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=config.timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return ClangParseResult(file=file, ok=False, command=command, error=f"Clang excedió el tiempo límite de {config.timeout} segundos", stdout=exc.stdout or "", stderr=exc.stderr or "")
    if completed.returncode != 0:
        return ClangParseResult(file=file, ok=False, command=command, stdout=completed.stdout, stderr=completed.stderr, error="Clang no pudo parsear la unidad de traducción")
    try:
        ast = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return ClangParseResult(file=file, ok=False, command=command, stdout=completed.stdout, stderr=completed.stderr, error=f"Clang produjo JSON inválido: {exc}")
    return ClangParseResult(file=file, ok=True, ast=ast, command=command, stdout=completed.stdout, stderr=completed.stderr)
