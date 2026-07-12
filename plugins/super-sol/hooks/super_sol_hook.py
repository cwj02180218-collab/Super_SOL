"""Privacy-minimized lifecycle hooks for the Super SOL Codex plugin."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from typing import cast

from super_sol_routes import (
    REPAIR_CONTEXT,
    Route,
    context_for,
    route_prompt,
)
from super_sol_state import (
    HookInputError,
    claim_once,
    load_state,
    read_input,
    turn_root,
    write_private_json,
)

_SCHEMA_VERSION = 4
_DIAGNOSTIC_MODE = "SUPER_SOL_DIAGNOSTIC_MODE"
_FORCED_ROUTE = "SUPER_SOL_FORCED_ROUTE"
_SECRET = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
_NEGATIVE_BILLING = (
    "과금 없이",
    "과금하지",
    "api 호출하지",
    "api를 호출하지",
    "no api call",
    "no billing",
    "don't call api",
    "do not call api",
)
_BILLABLE_CONFIRMATIONS = (
    "super sol 유료 실행 승인",
    "super sol billable run approved",
)
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
_EVAL_COMMAND_NAMES = r"(?:super-sol-eval|fablized-sol-eval|super-sol-codex-ab)"
_EVAL_INVOCATION_PATTERN = (  # noqa: UP032 - avoids pyright implicit-concat error
    r"^\s*(?:(?:\S*/)?{0}|uv\s+run(?:\s+--with\s+\S+)?\s+(?:\S*/)?{0})(?:\s|$)"
).format(_EVAL_COMMAND_NAMES)
_EVAL_INVOCATION = re.compile(
    _EVAL_INVOCATION_PATTERN,
    re.IGNORECASE,
)


def _context(event: str, text: str) -> dict[str, object]:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def _warning(message: str) -> dict[str, object]:
    return {"continue": True, "systemMessage": f"Super SOL: {message}"}


def _billable_authorized(prompt: str) -> bool:
    lowered = prompt.casefold()
    if any(signal in lowered for signal in _NEGATIVE_BILLING):
        return False
    lines = {line.strip().casefold() for line in prompt.splitlines()}
    return any(confirmation in lines for confirmation in _BILLABLE_CONFIRMATIONS)


def _diagnostic_control() -> tuple[str, Route | None, str | None]:
    mode = os.environ.get(_DIAGNOSTIC_MODE, "").strip().casefold()
    if not mode:
        return "adaptive", None, None
    if mode == "observe":
        return "observe", None, None
    if mode != "forced":
        return "adaptive", None, "invalid_diagnostic_mode"
    forced = os.environ.get(_FORCED_ROUTE, "").strip().casefold()
    try:
        route = Route(forced)
    except ValueError:
        return "adaptive", None, "invalid_forced_route"
    if route is Route.PASS_THROUGH:
        return "adaptive", None, "invalid_forced_route"
    return "forced", route, None


def _user_prompt(payload: dict[str, object]) -> dict[str, object] | None:
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return _warning("요청 내용을 읽지 못해 자동 절차 없이 계속합니다.")
    if _SECRET.search(prompt):
        return {
            "decision": "block",
            "reason": "API 키로 보이는 값이 있습니다. 키를 폐기하고 채팅에서 제거하세요.",
        }
    decision = route_prompt(prompt)
    diagnostic_mode, forced_route, diagnostic_warning = _diagnostic_control()
    effective_route = Route.PASS_THROUGH
    if diagnostic_mode == "observe":
        effective_route = Route.PASS_THROUGH
    elif diagnostic_mode == "forced" and forced_route is not None:
        effective_route = forced_route
    elif decision.forced:
        effective_route = decision.route
    root = turn_root(payload)
    if root is not None:
        private_state: dict[str, object] = {
            "billable_authorized": _billable_authorized(prompt),
            "confidence": decision.confidence,
            "diagnostic_mode": diagnostic_mode,
            "effective_route": effective_route.value,
            "forced": decision.forced or diagnostic_mode == "forced",
            "natural_route": decision.route.value,
            "primary_contract": decision.contract.value if decision.contract is not None else None,
            "schema_version": _SCHEMA_VERSION,
            "signal_ids": list(decision.signal_ids),
        }
        if diagnostic_warning is not None:
            private_state["diagnostic_warning"] = diagnostic_warning
        write_private_json(
            root / "request.json",
            private_state,
        )
    if decision.warning is not None:
        return _warning(decision.warning)
    context = context_for(effective_route)
    return _context("UserPromptSubmit", context) if context is not None else None


def _deny(reason: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _command(payload: dict[str, object]) -> str | None:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    tool_input = cast("dict[object, object]", tool_input)
    command = tool_input.get("command")
    if isinstance(command, str):
        return command
    fallback = tool_input.get("cmd")
    return fallback if isinstance(fallback, str) else None


def _simple_argv(command: str) -> tuple[str, ...] | None:
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


def _eval_command(argv: tuple[str, ...]) -> bool:
    executable, _arguments = _command_parts(argv)
    return executable in {"super-sol-eval", "fablized-sol-eval", "super-sol-codex-ab"}


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


def _verification_command(argv: tuple[str, ...] | None) -> bool:
    if argv is None:
        return False
    executable, arguments = _command_parts(argv)
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


def _pre_tool(payload: dict[str, object]) -> dict[str, object] | None:
    command = _command(payload)
    if command is None:
        return None
    lowered = command.casefold()
    argv = _simple_argv(command)
    state = load_state(payload) or {}
    authorized = state.get("billable_authorized") is True
    if "api.openai.com" in lowered and not authorized:
        return _deny("사용자가 이 작업의 유료 API 호출을 명시적으로 승인하지 않았습니다.")
    is_eval = (argv is not None and _eval_command(argv)) or _EVAL_INVOCATION.search(
        command
    ) is not None
    has_dry_run = argv is not None and "--dry-run" in argv
    if is_eval and not has_dry_run:
        if not authorized:
            return _deny(
                "live 평가는 자동 실행하지 않습니다. 먼저 사용자의 명시적 과금 승인이 필요합니다."
            )
        if argv is None or not _eval_command(argv) or "--confirm-billable" not in argv:
            return _deny("승인된 live 평가에도 --confirm-billable 플래그가 필요합니다.")
    elif is_eval:
        safe_dry_run = (
            argv is not None
            and _eval_command(argv)
            and "--dry-run" in argv
            and "--no-dry-run" not in argv
        )
        if not safe_dry_run:
            return _deny("dry-run은 다른 명령과 연결하지 않은 단순 명령으로 실행해야 합니다.")
    return None


def _post_tool(payload: dict[str, object]) -> dict[str, object] | None:
    root = turn_root(payload)
    state = load_state(payload)
    if (
        root is None
        or state is None
        or state.get("diagnostic_mode") == "observe"
        or state.get("effective_route") == Route.PASS_THROUGH.value
    ):
        return None
    command = _command(payload) or ""
    verification = _verification_command(_simple_argv(command))
    response = payload.get("tool_response")
    if not verification or not isinstance(response, dict):
        return None
    response = cast("dict[object, object]", response)
    code = response.get("exit_code")
    if type(code) is not int or code == 0 or not claim_once(root, "repair-context"):
        return None
    return _context("PostToolUse", REPAIR_CONTEXT)


def _dispatch(payload: dict[str, object]) -> dict[str, object] | None:
    event = payload.get("hook_event_name")
    if event == "UserPromptSubmit":
        return _user_prompt(payload)
    if event == "PreToolUse":
        return _pre_tool(payload)
    if event == "PostToolUse":
        return _post_tool(payload)
    return _warning("알 수 없는 훅 이벤트라 자동 절차 없이 계속합니다.")


def main() -> int:
    """Read one hook event and emit one documented Codex hook response."""
    try:
        payload = read_input()
        output = _dispatch(payload)
    except (HookInputError, OSError, TypeError, ValueError):
        output = _warning("로컬 상태를 읽지 못해 자동 절차 없이 계속합니다.")
    if output is not None:
        json.dump(output, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
