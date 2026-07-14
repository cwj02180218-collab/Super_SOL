from __future__ import annotations

import ast
import hashlib
import json
import os
import shlex
from pathlib import Path
from typing import cast

from v09_loop_contract import (  # pyright: ignore[reportImplicitRelativeImport]
    as_dict,
    as_list,
    canonical,
)

NETWORK_ERROR = "network_capability"
FORBIDDEN_IMPORTS = frozenset(
    {"ctypes", "http", "importlib", "requests", "socket", "subprocess", "urllib"}
)
DYNAMIC_CALLS = frozenset({"__import__", "compile", "eval", "exec", "getattr"})
PROCESS_CALLS = frozenset(
    {
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
        "popen",
        "posix_spawn",
        "posix_spawnp",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
        "system",
    }
)


def plugin_files(root: Path) -> list[Path]:
    if root.is_symlink() or not root.is_dir():
        raise ValueError(NETWORK_ERROR)
    files: list[Path] = []
    for directory, directory_names, file_names in os.walk(root):
        current = Path(directory)
        if any((current / name).is_symlink() for name in directory_names):
            raise ValueError(NETWORK_ERROR)
        directory_names[:] = sorted(name for name in directory_names if name != "__pycache__")
        for name in sorted(file_names):
            path = current / name
            if path.is_symlink():
                raise ValueError(NETWORK_ERROR)
            files.append(path)
    return sorted(files)


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in plugin_files(root):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def _command_entries(raw_groups: object) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    for raw_group in as_list(raw_groups) or []:
        group = as_dict(raw_group)
        raw_hooks = as_list(group.get("hooks")) if group is not None else []
        for raw_hook in raw_hooks or []:
            hook = as_dict(raw_hook)
            command = hook.get("command") if hook is not None else None
            timeout = hook.get("timeout") if hook is not None else None
            if (
                hook is not None
                and hook.get("type") == "command"
                and isinstance(command, str)
                and type(timeout) is int
            ):
                entries.append((command, timeout))
    return entries


def selected_commands(plugin_root: Path) -> dict[str, tuple[str, int]]:
    raw = cast(
        "object",
        json.loads((plugin_root / "hooks" / "hooks.json").read_text(encoding="utf-8")),
    )
    config = as_dict(raw)
    groups = as_dict(config.get("hooks")) if config is not None else None
    if groups is None:
        raise ValueError(NETWORK_ERROR)
    selected: dict[str, tuple[str, int]] = {}
    for event, raw_groups in groups.items():
        entries = _command_entries(raw_groups)
        if len(entries) != 1:
            raise ValueError(NETWORK_ERROR)
        selected[event] = entries[0]
    return dict(sorted(selected.items()))


def _command_is_allowed(command: str, timeout: int) -> bool:
    argv = shlex.split(command)
    scripts = {
        "$PLUGIN_ROOT/hooks/prompt_dispatcher.py",
        "$PLUGIN_ROOT/hooks/super_sol_hook.py",
    }
    return (
        argv[:2] == ["/usr/bin/python3", "-S"]
        and len(argv) == 3
        and argv[2] in scripts
        and timeout > 0
    )


def _import_findings(
    nodes: tuple[ast.AST, ...], path: Path
) -> tuple[list[str], set[str], set[str], set[str]]:
    findings: list[str] = []
    builtins_aliases = {"builtins"}
    dynamic_aliases: set[str] = set()
    process_aliases: set[str] = set()
    for node in nodes:
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
            if roots & FORBIDDEN_IMPORTS:
                findings.append(f"import:{path.name}")
            builtins_aliases.update(
                alias.asname or alias.name for alias in node.names if alias.name == "builtins"
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in FORBIDDEN_IMPORTS:
                findings.append(f"import:{path.name}")
            for alias in node.names:
                local_name = alias.asname or alias.name
                if node.module == "builtins" and alias.name in DYNAMIC_CALLS:
                    dynamic_aliases.add(local_name)
                if node.module == "os" and alias.name in PROCESS_CALLS:
                    process_aliases.add(local_name)
    return findings, builtins_aliases, dynamic_aliases, process_aliases


def _call_findings(
    nodes: tuple[ast.AST, ...],
    path: Path,
    builtins_aliases: set[str],
    dynamic_aliases: set[str],
    process_aliases: set[str],
) -> list[str]:
    findings: list[str] = []
    for node in nodes:
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            if node.func.id in DYNAMIC_CALLS | dynamic_aliases:
                findings.append(f"dynamic:{path.name}")
            if node.func.id in PROCESS_CALLS | process_aliases:
                findings.append(f"process:{path.name}")
        elif isinstance(node.func, ast.Attribute):
            if (
                node.func.attr in DYNAMIC_CALLS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in builtins_aliases
            ):
                findings.append(f"dynamic:{path.name}")
            if node.func.attr in PROCESS_CALLS:
                findings.append(f"process:{path.name}")
    return findings


def _python_findings(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return [f"parse:{path.name}"]
    nodes = tuple(ast.walk(tree))
    findings, builtins_aliases, dynamic_aliases, process_aliases = _import_findings(nodes, path)
    findings.extend(_call_findings(nodes, path, builtins_aliases, dynamic_aliases, process_aliases))
    return findings


def audit_network_capabilities(plugin_root: Path) -> dict[str, object]:
    commands = selected_commands(plugin_root)
    findings = [
        f"command:{event}"
        for event, (command, timeout) in commands.items()
        if not _command_is_allowed(command, timeout)
    ]
    files = plugin_files(plugin_root)
    hook_root = plugin_root / "hooks"
    for path in files:
        if hook_root in path.parents and path.suffix != ".py" and path.stat().st_mode & 0o111:
            findings.append(f"executable:{path.name}")
        if path.suffix == ".py":
            findings.extend(_python_findings(path))
    if findings:
        raise ValueError(NETWORK_ERROR)
    inventory = [
        {"event": event, "command": command, "timeout": timeout}
        for event, (command, timeout) in commands.items()
    ]
    return {
        "calls_counted": False,
        "command_sha256": hashlib.sha256(canonical(inventory)).hexdigest(),
        "hook_files_audited": sum(path.suffix == ".py" for path in files),
        "static_audit": "passed",
    }
