"""Privacy-minimized lifecycle hooks for the Super SOL Codex plugin."""

import json
import re
import sys
import time

from super_sol_state import (
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
_POSITIVE_BILLING = (
    "과금 승인",
    "유료 실행",
    "billable approved",
    "confirm billable",
    "live eval 실행",
    "run live eval",
    "api 호출해",
    "call the api",
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
_VERIFICATION = re.compile(
    r"(?:\bpytest\b|\bruff\b|\bbasedpyright\b|\bmypy\b|\bcargo\s+test\b|"
    r"\bgo\s+test\b|\b(?:npm|pnpm|yarn)\s+(?:run\s+)?(?:test|lint|build)\b|"
    r"\buv\s+build\b|\bgit\s+diff\s+--check\b)",
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
    if any(signal in lowered for signal in _CONVERSATION_SIGNALS):
        return "conversation"
    return "action"


def _billable_authorized(prompt: str) -> bool:
    lowered = prompt.casefold()
    if any(signal in lowered for signal in _NEGATIVE_BILLING):
        return False
    return any(signal in lowered for signal in _POSITIVE_BILLING)


def _session_start() -> dict[str, object]:
    text = (
        "Super SOL은 현재 Codex 작업 안에서만 동작하며 추가 과금 API를 자동 호출하지 않는다. "
        "행동을 바꾸면 가장 좁은 검증을 실행하고 결과를 읽는다. "
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
    command = tool_input.get("command")
    return command if isinstance(command, str) else None


def _pre_tool(payload: dict[str, object]) -> dict[str, object] | None:
    command = _command(payload)
    if command is None:
        return None
    lowered = command.casefold()
    state = load_state(payload) or {}
    authorized = state.get("billable_authorized") is True
    if "api.openai.com" in lowered and not authorized:
        return _deny("사용자가 이 작업의 유료 API 호출을 명시적으로 승인하지 않았습니다.")
    is_eval = "super-sol-eval" in lowered or "fablized-sol-eval" in lowered
    if is_eval and "--dry-run" not in lowered:
        if not authorized:
            return _deny(
                "live 평가는 자동 실행하지 않습니다. 먼저 사용자의 명시적 과금 승인이 필요합니다."
            )
        if "--confirm-billable" not in lowered:
            return _deny("승인된 live 평가에도 --confirm-billable 플래그가 필요합니다.")
    return None


def _exit_code_zero(value: object) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "exit_code" and type(nested) is int and nested == 0:
                return True
            if _exit_code_zero(nested):
                return True
    elif isinstance(value, list):
        return any(_exit_code_zero(item) for item in value)
    return False


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
    verification = bool(_VERIFICATION.search(command))
    if not mutation and not verification:
        return None
    observed_at = time.time_ns()
    event = {
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
    if payload.get("stop_hook_active") is True:
        return {
            "continue": True,
            "systemMessage": "Super SOL: 변경 후 성공한 검증은 확인되지 않았습니다.",
        }
    return {
        "decision": "block",
        "reason": "변경 사항을 확인할 수 있는 가장 좁은 테스트를 실행하고 결과를 읽어주세요.",
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
