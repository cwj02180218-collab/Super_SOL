"""Codex lifecycle adapters for the bounded v0.9 loop-fuse policy."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, cast

from super_sol_commands import CommandKind, classify_command, command_text
from super_sol_loop_policy import (
    FuseAction,
    FuseDecision,
    after_tool,
    before_tool,
    on_compact,
    on_subagent_start,
    on_subagent_stop,
)
from super_sol_loop_state import LoopLedger, keyed_fingerprint, mutate_loop_ledger
from super_sol_prompt_hook import model_profile
from super_sol_state import claim_context, turn_root

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_EDIT_TOOLS = frozenset({"apply_patch", "edit", "write"})
_VERIFIER_DENY = (
    "이미 확인한 검증 결과입니다. 추가 도구 호출 없이 완료 근거와 남은 작업을 정리하세요."
)
_DENY_REASONS: dict[str, str] = {
    "loop_fuse_tool_replay": (
        "같은 도구 호출이 반복됩니다. 새 증거를 만들거나 완료 근거와 남은 작업을 정리하세요."
    ),
    "loop_fuse_nested_agent": (
        "하위 에이전트는 추가 에이전트를 만들 수 없습니다. 현재 작업의 근거와 남은 작업을 "
        "정리하세요."
    ),
    "loop_fuse_concurrent_agent_budget": (
        "동시에 실행할 수 있는 에이전트 한도에 도달했습니다. 현재 작업의 근거와 남은 작업을 "
        "정리하세요."
    ),
    "loop_fuse_total_agent_budget": (
        "이 요청의 에이전트 생성 한도에 도달했습니다. 현재 작업의 근거와 남은 작업을 정리하세요."
    ),
}
_WARNINGS = {
    "PreToolUse": "반복된 도구 요청입니다. 새 증거를 만들거나 완료 근거와 남은 작업을 정리하세요.",
    "PostToolUse": (
        "같은 도구 결과가 반복됩니다. 새 증거를 만들거나 완료 근거와 남은 작업을 정리하세요."
    ),
    "PreCompact": "진행 없는 자동 압축이 반복됩니다. 완료 근거와 남은 작업을 정리하세요.",
    "PostCompact": "진행 없는 자동 압축이 반복됩니다. 완료 근거와 남은 작업을 정리하세요.",
}


def _root(payload: dict[str, object]) -> Path | None:
    return turn_root(payload) if model_profile(payload) == "sol" else None


def _transition(
    root: Path, transition: Callable[[LoopLedger], tuple[LoopLedger, FuseDecision]]
) -> FuseDecision:
    decision = FuseDecision(FuseAction.PASS)
    initialize = not (root / "loop.json").exists()

    def apply(state: LoopLedger) -> LoopLedger:
        nonlocal decision
        if initialize:
            state = LoopLedger.fresh(time.time_ns())
        updated, decision = transition(state)
        return updated

    _ = mutate_loop_ledger(root, apply)
    return decision


def _tool(payload: dict[str, object]) -> tuple[str, str] | None:
    tool_name = payload.get("tool_name")
    normalized = tool_name.casefold() if isinstance(tool_name, str) else ""
    if normalized in _EDIT_TOOLS:
        return "edit", normalized
    if normalized != "bash":
        return None
    command = command_text(payload)
    if command is None:
        return None
    info = classify_command(command)
    if info.kind is CommandKind.UNKNOWN:
        return None
    return info.kind.value, f"{info.kind.value}:{info.normalized}:{command}"


def _outcome(payload: dict[str, object]) -> str | None:
    response = payload.get("tool_response")
    if not isinstance(response, dict):
        return None
    values = cast("dict[object, object]", response)
    code = values.get("exit_code")
    if type(code) is int:
        return "pass" if code == 0 else "fail"
    success = values.get("success")
    if isinstance(success, bool):
        return "pass" if success else "fail"
    is_error = values.get("is_error")
    return "fail" if is_error is True else ("pass" if isinstance(is_error, bool) else None)


def _deny(reason: str | None) -> dict[str, object]:
    message = (
        _VERIFIER_DENY
        if reason == "loop_fuse_verifier_replay"
        else _DENY_REASONS.get(reason or "", _DENY_REASONS["loop_fuse_tool_replay"])
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": message,
        }
    }


def _response(event: str, root: Path, decision: FuseDecision) -> dict[str, object] | None:
    if decision.action is FuseAction.BLOCK_ACTION:
        return _deny(decision.reason)
    if decision.action is FuseAction.STOP_TURN and decision.reason is not None:
        return {"continue": False, "stopReason": decision.reason}
    if decision.action is FuseAction.WARN_ONCE and claim_context(root, "evidence"):
        return {
            "hookSpecificOutput": {"hookEventName": event, "additionalContext": _WARNINGS[event]}
        }
    return None


def process_pre_tool(payload: dict[str, object]) -> dict[str, object] | None:
    """Apply pre-tool replay and subagent-budget policy without raw persistence."""
    root = _root(payload)
    tool = _tool(payload)
    if root is None or tool is None:
        return None
    kind, source = tool
    fingerprint = keyed_fingerprint(root, source)
    decision = _transition(
        root,
        lambda state: before_tool(
            state,
            fingerprint,
            kind,
            is_child=payload.get("is_subagent") is True,
            now_ns=time.time_ns(),
        ),
    )
    return _response("PreToolUse", root, decision)


def process_post_tool(payload: dict[str, object]) -> dict[str, object] | None:
    """Record a completed normalized tool action and emit one soft warning when needed."""
    root = _root(payload)
    tool = _tool(payload)
    outcome = _outcome(payload)
    if root is None or tool is None or outcome is None:
        return None
    kind, source = tool
    fingerprint = keyed_fingerprint(root, source)
    decision = _transition(
        root, lambda state: after_tool(state, fingerprint, kind, outcome, now_ns=time.time_ns())
    )
    return _response("PostToolUse", root, decision)


def _agent_id(payload: dict[str, object]) -> str | None:
    value = payload.get("agent_id")
    return value if isinstance(value, str) else None


def process_subagent_start(payload: dict[str, object]) -> None:
    """Persist a keyed child identifier without producing model-visible context."""
    root = _root(payload)
    agent_id = _agent_id(payload)
    if root is not None and agent_id is not None:
        fingerprint = keyed_fingerprint(root, agent_id)
        _ = _transition(
            root, lambda state: on_subagent_start(state, fingerprint, now_ns=time.time_ns())
        )


def process_subagent_stop(payload: dict[str, object]) -> None:
    """Remove a keyed child identifier without producing model-visible context."""
    root = _root(payload)
    agent_id = _agent_id(payload)
    if root is not None and agent_id is not None:
        fingerprint = keyed_fingerprint(root, agent_id)
        _ = _transition(
            root, lambda state: on_subagent_stop(state, fingerprint, now_ns=time.time_ns())
        )


def process_compact(payload: dict[str, object]) -> dict[str, object] | None:
    """Apply the automatic compaction breaker on supported lifecycle events."""
    root = _root(payload)
    event = payload.get("hook_event_name")
    trigger = payload.get("trigger")
    if (
        root is None
        or not isinstance(event, str)
        or event not in {"PreCompact", "PostCompact"}
        or not isinstance(trigger, str)
    ):
        return None
    decision = _transition(
        root, lambda state: on_compact(state, event, trigger, now_ns=time.time_ns())
    )
    return _response(event, root, decision)
