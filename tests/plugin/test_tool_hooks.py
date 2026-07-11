import pytest
from pydantic import JsonValue

from .conftest import HookRunner, hook_input


def _prime(run_hook: HookRunner, prompt: str = "이 파일을 수정해줘") -> None:
    result = run_hook(hook_input("UserPromptSubmit", prompt=prompt))
    assert result.returncode == 0


def _post_tool(
    run_hook: HookRunner,
    tool_name: str,
    command: str,
    response: dict[str, JsonValue],
    tool_use_id: str,
) -> None:
    result = run_hook(
        hook_input(
            "PostToolUse",
            tool_name=tool_name,
            tool_use_id=tool_use_id,
            tool_input={"command": command},
            tool_response=response,
        )
    )
    assert result.returncode == 0


def _stop(run_hook: HookRunner, *, active: bool = False) -> dict[str, JsonValue]:
    result = run_hook(
        hook_input("Stop", stop_hook_active=active, last_assistant_message="완료했습니다")
    )
    assert result.returncode == 0
    assert result.stdout is not None
    return result.stdout


def test_unapproved_live_eval_and_direct_api_are_denied(run_hook: HookRunner) -> None:
    _prime(run_hook)
    commands = (
        "uv run super-sol-eval --tasks eval/tasks.example.json",
        "curl https://api.openai.com/v1/responses",
    )

    for command in commands:
        result = run_hook(
            hook_input(
                "PreToolUse",
                tool_name="Bash",
                tool_use_id="pre-one",
                tool_input={"command": command},
            )
        )
        assert result.stdout is not None
        specific = result.stdout["hookSpecificOutput"]
        assert isinstance(specific, dict)
        assert specific["permissionDecision"] == "deny"


def test_dry_run_is_allowed_without_billing_authorization(run_hook: HookRunner) -> None:
    _prime(run_hook)
    result = run_hook(
        hook_input(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="pre-two",
            tool_input={"command": "uv run super-sol-eval --dry-run --tasks tasks.json"},
        )
    )

    assert result.returncode == 0
    assert result.stdout is None


def test_authorized_live_eval_still_requires_confirmation_flag(run_hook: HookRunner) -> None:
    _prime(run_hook, "SUPER SOL 유료 실행 승인")
    without_flag = run_hook(
        hook_input(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="pre-three",
            tool_input={"command": "uv run super-sol-eval --tasks tasks.json"},
        )
    )
    with_flag = run_hook(
        hook_input(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="pre-four",
            tool_input={"command": "uv run super-sol-eval --tasks tasks.json --confirm-billable"},
        )
    )

    assert without_flag.stdout is not None
    assert with_flag.stdout is None


@pytest.mark.parametrize(
    "command",
    [
        "uv run super-sol-eval --tasks tasks.json --confirm-billable # --dry-run",
        "uv run super-sol-eval --tasks tasks.json --no-dry-run",
        "uv run super-sol-eval --tasks tasks.json --dry-run && echo done",
    ],
)
def test_dry_run_allowance_rejects_comments_negation_and_shell_chains(
    run_hook: HookRunner,
    command: str,
) -> None:
    _prime(run_hook)
    result = run_hook(
        hook_input(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="pre-bypass",
            tool_input={"command": command},
        )
    )

    assert result.stdout is not None
    specific = result.stdout["hookSpecificOutput"]
    assert isinstance(specific, dict)
    assert specific["permissionDecision"] == "deny"


def test_mutation_without_verification_warns_without_automatic_continuation(
    run_hook: HookRunner,
) -> None:
    _prime(run_hook)
    _post_tool(run_hook, "apply_patch", "*** Begin Patch", {}, "mutation-one")

    result = _stop(run_hook)

    assert result["continue"] is True
    assert "자동으로 계속하지" in str(result["systemMessage"])


@pytest.mark.parametrize(
    "command",
    ["rg pytest pyproject.toml", "echo pytest", "pytest -q || true"],
)
def test_verifier_mentions_and_masked_failures_do_not_count(
    run_hook: HookRunner,
    command: str,
) -> None:
    _prime(run_hook)
    _post_tool(run_hook, "apply_patch", "*** Begin Patch", {}, "mutation-forged")
    _post_tool(run_hook, "Bash", command, {"exit_code": 0}, "verify-forged")

    result = _stop(run_hook)
    assert "확인되지" in str(result["systemMessage"])


def test_fresh_structured_verification_allows_stop(run_hook: HookRunner) -> None:
    _prime(run_hook, "버그를 수정해줘")
    _post_tool(run_hook, "apply_patch", "*** Begin Patch", {}, "mutation-two")
    _post_tool(run_hook, "Bash", "uv run pytest -q", {"exit_code": 0}, "verify-one")

    assert _stop(run_hook) == {"continue": True}


def test_stale_or_failed_verification_does_not_count(run_hook: HookRunner) -> None:
    _prime(run_hook)
    _post_tool(run_hook, "Bash", "uv run pytest -q", {"exit_code": 0}, "verify-old")
    _post_tool(run_hook, "apply_patch", "*** Begin Patch", {}, "mutation-three")
    assert "확인되지" in str(_stop(run_hook)["systemMessage"])

    _post_tool(run_hook, "Bash", "uv run pytest -q", {"exit_code": 1}, "verify-failed")
    assert "확인되지" in str(_stop(run_hook)["systemMessage"])


def test_conversation_profile_never_forces_verification(run_hook: HookRunner) -> None:
    _prime(run_hook, "이 코드가 무엇인지 설명만 해줘")
    _post_tool(run_hook, "apply_patch", "*** Begin Patch", {}, "mutation-four")

    assert _stop(run_hook) == {"continue": True}
