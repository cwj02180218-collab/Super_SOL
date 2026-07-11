"""Privacy-minimized lifecycle hooks for the Super SOL Codex plugin."""

from __future__ import annotations

import json
import re
import shlex
import sys
import time
from typing import cast

from super_sol_state import (  # pyright: ignore[reportImplicitRelativeImport]
    HookInputError,
    event_path,
    load_events,
    load_state,
    read_input,
    turn_root,
    write_private_json,
)

_SCHEMA_VERSION = 1
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
_RELEASE_SIGNALS = (
    "release",
    "deploy",
    "security",
    "stability",
    "배포",
    "릴리즈",
    "보안",
    "안정성",
    "공급망",
)
_DEBUG_SIGNALS = ("bug", "error", "fail", "debug", "버그", "오류", "실패", "디버그", "고장")
_CONVERSATION_SIGNALS = (
    "explain",
    "what is",
    "tell me about",
    "설명만",
    "무엇인지",
    "뭐야",
    "알려줘",
)
_ACTION_SIGNALS = (
    "add",
    "change",
    "create",
    "edit",
    "fix",
    "implement",
    "remove",
    "update",
    "고쳐",
    "만들",
    "삭제",
    "수정",
    "추가",
)
_SHELL_OPERATORS = {"&", "&&", ";", "|", "||"}
_EVAL_COMMAND_NAMES = r"(?:super-sol-eval|fablized-sol-eval)"
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


def _profile(prompt: str) -> str:
    lowered = prompt.casefold()
    if any(signal in lowered for signal in _RELEASE_SIGNALS):
        return "release"
    if any(signal in lowered for signal in _DEBUG_SIGNALS):
        return "debug"
    if any(signal in lowered for signal in _CONVERSATION_SIGNALS) and not any(
        signal in lowered for signal in _ACTION_SIGNALS
    ):
        return "conversation"
    return "action"


def _billable_authorized(prompt: str) -> bool:
    lowered = prompt.casefold()
    if any(signal in lowered for signal in _NEGATIVE_BILLING):
        return False
    lines = {line.strip().casefold() for line in prompt.splitlines()}
    return any(confirmation in lines for confirmation in _BILLABLE_CONFIRMATIONS)


def _session_start() -> dict[str, object]:
    text = (
        "Super SOL은 현재 Codex 작업 안에서만 동작하며 추가 과금 API를 자동 호출하지 않는다. "
        "행동을 바꾸면 가장 좁은 검증을 실행하고 결과를 읽는다. "
        "검증 누락 시 경고만 하며 모델을 자동으로 다시 호출하지 않는다. "
        "초보자가 이해할 말로 결론부터 설명한다."
    )
    return _context("SessionStart", text)


def _user_prompt(payload: dict[str, object]) -> dict[str, object]:
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return _warning("요청 내용을 읽지 못해 자동 절차 없이 계속합니다.")
    if _SECRET.search(prompt):
        return {
            "decision": "block",
            "reason": "API 키로 보이는 값이 있습니다. 키를 폐기하고 채팅에서 제거하세요.",
        }
    profile = _profile(prompt)
    root = turn_root(payload)
    if root is not None:
        write_private_json(
            root / "request.json",
            {
                "billable_authorized": _billable_authorized(prompt),
                "profile": profile,
                "schema_version": _SCHEMA_VERSION,
            },
        )
    contexts = {
        "conversation": "Answer in plain language first. Do not edit files unless the user asks.",
        "action": "요청 범위 안에서 직접 작업하고, 변경 후 가장 좁은 검증 결과를 확인한다.",
        "debug": "문제를 먼저 재현하고 원인을 고친 뒤 같은 실패 경로와 관련 테스트를 확인한다.",
        "release": "배포 경로, 보안, 재현성, 테스트를 확인하고 관찰한 결과와 남은 위험을 구분한다.",
    }
    return _context("UserPromptSubmit", contexts[profile])


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
    return executable in {"super-sol-eval", "fablized-sol-eval"}


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
    if arguments[:1] == ("--with",):
        arguments = arguments[2:]
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


def _exit_code_zero(value: object) -> bool:
    if not isinstance(value, dict):
        return False
    response = cast("dict[object, object]", value)
    code = response.get("exit_code")
    return type(code) is int and code == 0


def _post_tool(payload: dict[str, object]) -> dict[str, object] | None:
    root = turn_root(payload)
    state = load_state(payload)
    if root is None or state is None:
        return None
    tool_name = payload.get("tool_name")
    command = _command(payload) or ""
    mutation = isinstance(tool_name, str) and tool_name.casefold() in {
        "apply_patch",
        "edit",
        "write",
    }
    verification = _verification_command(_simple_argv(command))
    if not mutation and not verification:
        return None
    observed_at = time.time_ns()
    event: dict[str, object] = {
        "mutation": mutation,
        "observed_at_ns": observed_at,
        "schema_version": _SCHEMA_VERSION,
        "verification": verification,
        "verification_passed": verification and _exit_code_zero(payload.get("tool_response")),
    }
    path, identifier = event_path(root, payload.get("tool_use_id"), observed_at)
    event["tool_use_id"] = identifier
    write_private_json(path, event)
    return None


def _stop(payload: dict[str, object]) -> dict[str, object]:
    root = turn_root(payload)
    state = load_state(payload)
    if root is None or state is None or state.get("profile") == "conversation":
        return {"continue": True}
    events = load_events(root)
    mutations = [event["observed_at_ns"] for event in events if event.get("mutation") is True]
    passes = [
        event["observed_at_ns"] for event in events if event.get("verification_passed") is True
    ]
    latest_mutation = max((value for value in mutations if isinstance(value, int)), default=None)
    latest_pass = max((value for value in passes if isinstance(value, int)), default=None)
    if latest_mutation is None or (latest_pass is not None and latest_pass > latest_mutation):
        return {"continue": True}
    return {
        "continue": True,
        "systemMessage": (
            "Super SOL: 변경 후 성공한 검증은 확인되지 않았습니다. "
            "추가 사용량을 만들지 않도록 자동으로 계속하지 않습니다."
        ),
    }


def _dispatch(payload: dict[str, object]) -> dict[str, object] | None:
    event = payload.get("hook_event_name")
    if event == "SessionStart":
        return _session_start()
    if event == "UserPromptSubmit":
        return _user_prompt(payload)
    if event == "PreToolUse":
        return _pre_tool(payload)
    if event == "PostToolUse":
        return _post_tool(payload)
    if event == "Stop":
        return _stop(payload)
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
