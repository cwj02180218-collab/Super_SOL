"""Command normalization and billable-command safeguards for Super SOL hooks."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from enum import Enum
from typing import cast


class CommandKind(Enum):
    """Bounded command categories used by hook lifecycle processing."""

    BILLABLE_EVAL = "billable_eval"
    EDIT = "edit"
    VERIFIER = "verifier"
    WAIT = "wait"
    SPAWN = "spawn"
    READ = "read"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CommandInfo:
    """Classified command details without retaining command text."""

    kind: CommandKind
    normalized: str
    argv: tuple[str, ...] | None


_SHELL_OPERATORS = {"&", "&&", ";", "|", "||"}
_UV_RUN_VALUE_OPTIONS = {
    "--allow-insecure-host",
    "--cache-dir",
    "--color",
    "--config-file",
    "--config-setting",
    "--config-settings-package",
    "--default-index",
    "--directory",
    "--env-file",
    "--extra",
    "--extra-index-url",
    "--exclude-newer",
    "--exclude-newer-package",
    "--find-links",
    "--fork-strategy",
    "--group",
    "--index",
    "--index-strategy",
    "--index-url",
    "--keyring-provider",
    "--link-mode",
    "--no-binary-package",
    "--no-build-isolation-package",
    "--no-build-package",
    "--no-editable-package",
    "--no-extra",
    "--no-group",
    "--no-sources-package",
    "--only-group",
    "--package",
    "--prerelease",
    "--project",
    "--python",
    "--python-platform",
    "--refresh-package",
    "--reinstall-package",
    "--resolution",
    "--upgrade-group",
    "--upgrade-package",
    "--with",
    "--with-editable",
    "--with-requirements",
    "-C",
    "-P",
    "-f",
    "-i",
    "-p",
    "-w",
}
_EVAL_COMMANDS = {"super-sol-eval", "fablized-sol-eval", "super-sol-codex-ab"}
_EVAL_COMMAND_NAMES = r"(?:super-sol-eval|fablized-sol-eval|super-sol-codex-ab)"
_EVAL_INVOCATION_PATTERN = rf"^\s*(?:(?:\S*/)?{_EVAL_COMMAND_NAMES}|uv\s+run(?:\s+--with\s+\S+)?\s+(?:\S*/)?{_EVAL_COMMAND_NAMES})(?:\s|$)"  # noqa: E501
_EVAL_INVOCATION = re.compile(
    _EVAL_INVOCATION_PATTERN,
    re.IGNORECASE,
)
_EDIT_COMMANDS = {"apply_patch", "edit", "write"}
_WAIT_COMMANDS = {"sleep", "wait"}
_SPAWN_COMMANDS = {"agent", "spawn", "subagent"}
_READ_COMMANDS = {
    "cat",
    "find",
    "grep",
    "head",
    "less",
    "ls",
    "more",
    "rg",
    "sed",
    "tail",
    "tree",
    "wc",
}


def command_text(payload: dict[str, object]) -> str | None:
    """Return the supported command field from a hook payload."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    values = cast("dict[object, object]", tool_input)
    command = values.get("command")
    if isinstance(command, str):
        return command
    fallback = values.get("cmd")
    return fallback if isinstance(fallback, str) else None


def simple_argv(command: str) -> tuple[str, ...] | None:
    """Parse a single shell command, rejecting compound shell syntax."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = "#"
        argv = tuple(lexer)
    except ValueError:
        return None
    if not argv or any(token in _SHELL_OPERATORS for token in argv):
        return None
    return argv


def _command_parts(argv: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    executable = argv[0].rsplit("/", maxsplit=1)[-1].casefold()
    arguments = argv[1:]
    if executable != "uv":
        return executable, arguments
    if arguments[:1] == ("build",):
        return "uv-build", arguments[1:]
    if arguments[:1] != ("run",):
        return "", ()
    arguments = arguments[1:]
    index = 0
    while index < len(arguments) and arguments[index].startswith("-"):
        option = arguments[index]
        if option == "--":
            index += 1
            break
        if "=" in option:
            index += 1
            continue
        if option in _UV_RUN_VALUE_OPTIONS:
            if index + 1 >= len(arguments):
                return "", ()
            index += 2
            continue
        index += 1
    arguments = arguments[index:]
    if not arguments:
        return "", ()
    return arguments[0].rsplit("/", maxsplit=1)[-1].casefold(), arguments[1:]


def _is_verifier(executable: str, arguments: tuple[str, ...]) -> bool:
    script = (
        arguments[1]
        if arguments[:1] == ("run",) and len(arguments) > 1
        else (arguments[0] if arguments else "")
    )
    python_module = (
        arguments[1].casefold()
        if executable in {"python", "python3"} and len(arguments) > 1 and arguments[0] == "-m"
        else ""
    )
    return (
        executable in {"pytest", "basedpyright", "mypy", "uv-build"}
        or (
            executable == "ruff"
            and (
                arguments[:1] == ("check",)
                or (arguments[:1] == ("format",) and "--check" in arguments)
            )
        )
        or (executable in {"cargo", "go"} and arguments[:1] == ("test",))
        or (executable in {"npm", "pnpm", "yarn"} and script in {"test", "lint", "build"})
        or (executable == "git" and arguments[:1] == ("diff",) and "--check" in arguments)
        or python_module in {"pytest", "mypy", "basedpyright"}
    )


def classify_command(command: str) -> CommandInfo:
    """Classify a parsed command using bounded normalized operation names."""
    argv = simple_argv(command)
    if argv is None:
        return CommandInfo(CommandKind.UNKNOWN, "unknown", None)
    normalized, arguments = _command_parts(argv)
    if normalized in _EVAL_COMMANDS:
        kind = CommandKind.BILLABLE_EVAL
    elif _is_verifier(normalized, arguments):
        kind = CommandKind.VERIFIER
    elif normalized in _EDIT_COMMANDS:
        kind = CommandKind.EDIT
    elif normalized in _WAIT_COMMANDS:
        kind = CommandKind.WAIT
    elif normalized in _SPAWN_COMMANDS:
        kind = CommandKind.SPAWN
    elif normalized in _READ_COMMANDS:
        kind = CommandKind.READ
    else:
        kind = CommandKind.UNKNOWN
    return CommandInfo(kind, normalized or "unknown", argv)


def _deny(reason: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def billable_pre_tool(
    payload: dict[str, object], state: dict[str, object]
) -> dict[str, object] | None:
    """Return the existing denial response for unapproved billable commands."""
    command = command_text(payload)
    if command is None:
        return None
    info = classify_command(command)
    authorized = state.get("billable_authorized") is True
    if "api.openai.com" in command.casefold() and not authorized:
        return _deny("사용자가 이 작업의 유료 API 호출을 명시적으로 승인하지 않았습니다.")
    is_eval = info.kind is CommandKind.BILLABLE_EVAL or _EVAL_INVOCATION.search(command) is not None
    has_dry_run = info.argv is not None and "--dry-run" in info.argv
    if is_eval and not has_dry_run:
        if not authorized:
            return _deny(
                "live 평가는 자동 실행하지 않습니다. 먼저 사용자의 명시적 과금 승인이 필요합니다."
            )
        if (
            info.kind is not CommandKind.BILLABLE_EVAL
            or info.argv is None
            or "--confirm-billable" not in info.argv
        ):
            return _deny("승인된 live 평가에도 --confirm-billable 플래그가 필요합니다.")
    elif is_eval:
        safe_dry_run = (
            info.kind is CommandKind.BILLABLE_EVAL
            and info.argv is not None
            and "--dry-run" in info.argv
            and "--no-dry-run" not in info.argv
        )
        if not safe_dry_run:
            return _deny("dry-run은 다른 명령과 연결하지 않은 단순 명령으로 실행해야 합니다.")
    return None
