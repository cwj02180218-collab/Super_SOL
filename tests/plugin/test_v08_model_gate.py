import pytest
from pydantic import JsonValue
from super_sol_routes import Contract, residual_context

from .conftest import HookEnvironmentRunner, HookRunner, hook_input


def _context(output: dict[str, JsonValue] | None) -> str | None:
    if output is None:
        return None
    specific = output["hookSpecificOutput"]
    assert isinstance(specific, dict)
    value = specific["additionalContext"]
    assert isinstance(value, str)
    return value


def verification_payload(*, model: JsonValue) -> dict[str, JsonValue]:
    return hook_input(
        "PostToolUse",
        model=model,
        tool_name="Bash",
        tool_use_id="verify-one",
        tool_input={"command": "uv run pytest -q"},
        tool_response={"exit_code": 0},
    )


def _lifecycle(run_hook: HookRunner, model: JsonValue) -> str | None:
    prompt = hook_input(
        "UserPromptSubmit",
        model=model,
        prompt="Fix concurrent refresh cancellation and race conditions",
    )
    assert run_hook(prompt).stdout is None
    edit = hook_input(
        "PostToolUse",
        model=model,
        tool_name="apply_patch",
        tool_use_id="edit-one",
        tool_input={"patch": "bounded fixture"},
        tool_response={"success": True},
    )
    assert run_hook(edit).stdout is None
    return _context(run_hook(verification_payload(model=model)).stdout)


def test_sol_lifecycle_emits_one_residual_context(run_hook: HookRunner) -> None:
    assert _lifecycle(run_hook, "gpt-5.6-sol") == residual_context(
        Contract.CONCURRENCY_CANCELLATION
    )
    assert _context(run_hook(verification_payload(model="gpt-5.6-sol")).stdout) is None


@pytest.mark.parametrize(
    "model",
    ["gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.6-sol-preview", "", None, 17],
)
def test_non_sol_lifecycles_emit_no_context(run_hook: HookRunner, model: JsonValue) -> None:
    assert _lifecycle(run_hook, model) is None


def test_lifecycle_without_model_emits_no_context(run_hook: HookRunner) -> None:
    prompt = hook_input(
        "UserPromptSubmit",
        prompt="Fix concurrent refresh cancellation and race conditions",
    )
    prompt.pop("model")
    assert run_hook(prompt).stdout is None
    edit = hook_input(
        "PostToolUse",
        tool_name="apply_patch",
        tool_use_id="edit-one",
        tool_input={"patch": "bounded fixture"},
        tool_response={"success": True},
    )
    edit.pop("model")
    assert run_hook(edit).stdout is None
    verification = verification_payload(model="gpt-5.6-sol")
    verification.pop("model")
    assert _context(run_hook(verification).stdout) is None


def test_forced_terra_prompt_emits_no_context(
    run_hook_with_env: HookEnvironmentRunner,
) -> None:
    result = run_hook_with_env(
        hook_input(
            "UserPromptSubmit",
            model="gpt-5.6-terra",
            prompt="Fix concurrent refresh cancellation and race conditions",
        ),
        {
            "SUPER_SOL_DIAGNOSTIC_MODE": "forced",
            "SUPER_SOL_FORCED_ROUTE": "failure_atomicity",
        },
    )

    assert result.stdout is None


def test_terra_secret_is_blocked(run_hook: HookRunner) -> None:
    result = run_hook(
        hook_input(
            "UserPromptSubmit",
            model="gpt-5.6-terra",
            prompt="Use sk-abcdefghijklmnopqrst for this request",
        )
    )

    assert result.stdout is not None
    assert result.stdout["decision"] == "block"


def test_terra_unapproved_billable_command_is_denied(run_hook: HookRunner) -> None:
    prompt = run_hook(
        hook_input(
            "UserPromptSubmit",
            model="gpt-5.6-terra",
            prompt="Please run a billable Super SOL evaluation.",
        )
    )
    command = run_hook(
        hook_input(
            "PreToolUse",
            model="gpt-5.6-terra",
            tool_name="Bash",
            tool_use_id="pre-billable",
            tool_input={"command": "uv run super-sol-eval --tasks tasks.json"},
        )
    )

    assert prompt.stdout is None
    assert command.stdout is not None
    specific = command.stdout["hookSpecificOutput"]
    assert isinstance(specific, dict)
    assert specific["permissionDecision"] == "deny"
