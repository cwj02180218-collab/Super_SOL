"""Privacy-minimized lifecycle dispatcher for the Super SOL Codex plugin."""

from __future__ import annotations

import json
import sys
import time

_MAX_INPUT_BYTES = 1_048_576


def _warning(message: str) -> dict[str, object]:
    return {"continue": True, "systemMessage": f"Super SOL: {message}"}


def _benchmark_guard(payload: dict[str, object]) -> dict[str, object] | None:
    from super_sol_benchmark_guard import benchmark_guard_decision  # noqa: PLC0415

    decision = benchmark_guard_decision(payload)
    if not decision.deny or decision.reason is None:
        return None
    from super_sol_audit import record_incident  # noqa: PLC0415
    from super_sol_state import turn_root  # noqa: PLC0415

    root = turn_root(payload)
    if root is not None:
        _ = record_incident(
            root,
            event="PreToolUse",
            reason=decision.reason,
            decision="deny",
            observed_at=time.time_ns(),
        )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "벤치마크 무결성 보호로 이 편집을 차단했습니다. 제품 코드만 수정하세요."
            ),
        }
    }


def _decode_object(raw: bytes) -> dict[str, object] | None:
    value = json.loads(raw.decode("utf-8"))  # pyright: ignore[reportAny]
    return value if isinstance(value, dict) else None  # pyright: ignore[reportUnknownVariableType]


def _dispatch(payload: dict[str, object]) -> dict[str, object] | None:  # noqa: PLR0911
    event = payload.get("hook_event_name")
    if event == "UserPromptSubmit":
        from super_sol_prompt_hook import process_prompt, reset_for_prompt  # noqa: PLC0415

        output = process_prompt(payload)
        reset_for_prompt(payload)
        return output
    if event == "PreToolUse":
        from super_sol_commands import billable_pre_tool  # noqa: PLC0415
        from super_sol_loop_hook import process_pre_tool  # noqa: PLC0415
        from super_sol_state import load_state  # noqa: PLC0415

        return (
            _benchmark_guard(payload)
            or billable_pre_tool(payload, load_state(payload) or {})
            or process_pre_tool(payload)
        )
    if event == "PostToolUse":
        from super_sol_evidence_hook import process_evidence  # noqa: PLC0415
        from super_sol_loop_hook import process_post_tool  # noqa: PLC0415

        return process_post_tool(payload) or process_evidence(payload)
    if event == "SubagentStart":
        from super_sol_loop_hook import process_subagent_start  # noqa: PLC0415

        process_subagent_start(payload)
        return None
    if event == "SubagentStop":
        from super_sol_loop_hook import process_subagent_stop  # noqa: PLC0415

        process_subagent_stop(payload)
        return None
    if event in {"PreCompact", "PostCompact"}:
        from super_sol_loop_hook import process_compact  # noqa: PLC0415

        return process_compact(payload)
    return _warning("알 수 없는 훅 이벤트라 자동 절차 없이 계속합니다.")


def _decode_raw(raw: bytes) -> dict[str, object]:
    if len(raw) > _MAX_INPUT_BYTES:
        raise ValueError
    decoded = _decode_object(raw)
    if decoded is None:
        raise TypeError
    return decoded


def process_raw(raw: bytes) -> dict[str, object] | None:
    """Process one bounded raw hook payload without reading global standard input."""
    try:
        return _dispatch(_decode_raw(raw))
    except (
        json.JSONDecodeError,
        OSError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
    ):
        return _warning("로컬 상태를 읽지 못해 자동 절차 없이 계속합니다.")


def main() -> int:
    """Read one hook event and emit one documented Codex hook response."""
    output = process_raw(sys.stdin.buffer.read(_MAX_INPUT_BYTES + 1))
    if output is not None:
        json.dump(output, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
