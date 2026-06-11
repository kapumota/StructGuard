from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CompileCommand:
    directory: Path
    file: Path
    arguments: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "directory": str(self.directory),
            "file": str(self.file),
            "arguments": self.arguments,
        }


@dataclass(frozen=True)
class CompileDatabase:
    path: Path
    commands: list[CompileCommand]

    def files(self) -> list[Path]:
        return sorted({command.file for command in self.commands})

    def command_for(self, source: Path) -> CompileCommand | None:
        resolved = source.resolve()
        for command in self.commands:
            if command.file.resolve() == resolved:
                return command
        for command in self.commands:
            if command.file.name == source.name:
                return command
        return None

    def as_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "commands": [command.as_dict() for command in self.commands],
        }


class CompileCommandsError(ValueError):
    pass


def _entry_arguments(entry: dict[str, object]) -> list[str]:
    arguments = entry.get("arguments")
    if isinstance(arguments, list):
        return [str(item) for item in arguments]
    command = entry.get("command")
    if isinstance(command, str):
        return shlex.split(command)
    raise CompileCommandsError("Entrada de compile_commands.json sin arguments ni command")


def _resolve_path(base: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def load_compile_commands(path: Path) -> CompileDatabase:
    if path.is_dir():
        path = path / "compile_commands.json"
    if not path.exists():
        raise CompileCommandsError(f"No existe compile_commands.json en: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CompileCommandsError(f"compile_commands.json inválido: {exc}") from exc
    if not isinstance(raw, list):
        raise CompileCommandsError("compile_commands.json debe contener una lista")
    commands: list[CompileCommand] = []
    for entry in raw:
        if not isinstance(entry, dict):
            raise CompileCommandsError("Cada entrada de compile_commands.json debe ser un objeto")
        directory_value = str(entry.get("directory") or path.parent)
        directory = _resolve_path(path.parent, directory_value)
        file_value = entry.get("file")
        if not isinstance(file_value, str):
            raise CompileCommandsError("Entrada de compile_commands.json sin campo file")
        commands.append(
            CompileCommand(
                directory=directory,
                file=_resolve_path(directory, file_value),
                arguments=_entry_arguments(entry),
            )
        )
    return CompileDatabase(path=path.resolve(), commands=commands)


def flags_for_clang(command: CompileCommand | None) -> list[str]:
    if command is None:
        return []
    out: list[str] = []
    skip_next = False
    source = command.file.resolve()
    for index, arg in enumerate(command.arguments):
        if index == 0:
            continue
        if skip_next:
            skip_next = False
            continue
        if arg in {"-c", "-S", "-E"}:
            continue
        if arg in {"-o", "--output"}:
            skip_next = True
            continue
        if Path(arg).name == source.name or Path(arg).resolve() == source:
            continue
        out.append(arg)
    return out
