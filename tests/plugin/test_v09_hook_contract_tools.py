from pydantic import JsonValue

from .conftest import HookRunner, hook_input


def _context(output: dict[str, JsonValue] | None) -> str | None:
    if output is None:
        return None
    specific = output["hookSpecificOutput"]
    assert isinstance(specific, dict)
    value = specific.get("additionalContext")
    return value if isinstance(value, str) else None


def test_pre_tool_replay_returns_codex_deny(run_hook: HookRunner) -> None:
    assert run_hook(hook_input("UserPromptSubmit", prompt="Fix the cache bug")).stdout is None
    verifier = hook_input(
        "PostToolUse",
        tool_name="Bash",
        tool_use_id="verify-one",
        tool_input={"command": "pytest tests/cache -q"},
        tool_response={"exit_code": 0},
    )
    _ = run_hook(verifier)
    output = run_hook(
        hook_input(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="verify-two",
            tool_input={"command": "pytest tests/cache -q"},
        )
    ).stdout

    assert output == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "이미 확인한 검증 결과입니다. 추가 도구 호출 없이 완료 근거와 남은 작업을 "
                "정리하세요."
            ),
        }
    }


def test_loop_warning_claim_suppresses_v08_evidence_context(run_hook: HookRunner) -> None:
    assert (
        run_hook(
            hook_input(
                "UserPromptSubmit",
                prompt="Fix concurrent refresh cancellation and race conditions",
            )
        ).stdout
        is None
    )
    assert (
        run_hook(
            hook_input(
                "PostToolUse",
                tool_name="apply_patch",
                tool_use_id="edit-one",
                tool_input={"patch": "fixture"},
                tool_response={"success": True},
            )
        ).stdout
        is None
    )
    outputs = [
        run_hook(
            hook_input(
                "PostToolUse",
                tool_name="Bash",
                tool_use_id=f"read-{index}",
                tool_input={"command": "rg cache src"},
                tool_response={"exit_code": 0},
            )
        ).stdout
        for index in range(3)
    ]
    assert _context(outputs[-1]) is not None
    evidence = run_hook(
        hook_input(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="verify-after-warning",
            tool_input={"command": "pytest tests/cache -q"},
            tool_response={"exit_code": 0},
        )
    ).stdout

    assert evidence is None


def test_hard_deny_does_not_consume_soft_context_claim(run_hook: HookRunner) -> None:
    assert run_hook(hook_input("UserPromptSubmit", prompt="Fix the cache bug")).stdout is None
    verifier = hook_input(
        "PostToolUse",
        tool_name="Bash",
        tool_use_id="verify-one",
        tool_input={"command": "pytest tests/cache -q"},
        tool_response={"exit_code": 0},
    )
    assert run_hook(verifier).stdout is None
    assert (
        run_hook(
            hook_input(
                "PreToolUse",
                tool_name="Bash",
                tool_use_id="verify-two",
                tool_input={"command": "pytest tests/cache -q"},
            )
        ).stdout
        is not None
    )
    outputs = [
        run_hook(
            hook_input(
                "PostToolUse",
                tool_name="Bash",
                tool_use_id=f"read-{index}",
                tool_input={"command": "rg cache src"},
                tool_response={"exit_code": 0},
            )
        ).stdout
        for index in range(3)
    ]

    assert _context(outputs[-1]) is not None
