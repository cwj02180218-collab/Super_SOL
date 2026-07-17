from pathlib import Path

import pytest
from pydantic import JsonValue
from super_sol_routes import Contract, Route, context_for, residual_context

from .conftest import HookEnvironmentRunner, HookRunner, hook_input, read_textual_state


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
    prompt_context = _context(run_hook(prompt).stdout)
    if model in {"gpt-5.6-sol", "gpt-5.6-terra"}:
        assert prompt_context == context_for(Route.CONCURRENCY_STATE)
    else:
        assert prompt_context is None
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
    ("current_model", "remove_model"),
    [
        ("gpt-5.6-terra", False),
        (None, False),
        (17, False),
        ("gpt-5.6-sol", True),
    ],
    ids=["non-sol", "null", "malformed", "missing"],
)
def test_sol_state_records_verification_but_emits_no_context_after_model_drift(
    run_hook: HookRunner,
    plugin_data: Path,
    current_model: JsonValue,
    *,
    remove_model: bool,
) -> None:
    prompt = hook_input(
        "UserPromptSubmit",
        model="gpt-5.6-sol",
        prompt="Fix concurrent refresh cancellation and race conditions",
    )
    assert _context(run_hook(prompt).stdout) == context_for(Route.CONCURRENCY_STATE)
    edit = hook_input(
        "PostToolUse",
        model="gpt-5.6-sol",
        tool_name="apply_patch",
        tool_use_id="edit-one",
        tool_input={"patch": "bounded fixture"},
        tool_response={"success": True},
    )
    assert run_hook(edit).stdout is None
    verification = verification_payload(model=current_model)
    if remove_model:
        _ = verification.pop("model")

    assert _context(run_hook(verification).stdout) is None
    stored = read_textual_state(plugin_data)
    assert '"kind":"verification"' in stored


@pytest.mark.parametrize(
    "model",
    ["gpt-5.6-luna", "gpt-5.6-sol-preview", "", None, 17],
)
def test_observe_lifecycles_emit_no_context(run_hook: HookRunner, model: JsonValue) -> None:
    assert _lifecycle(run_hook, model) is None


def test_lifecycle_without_model_emits_no_context(run_hook: HookRunner) -> None:
    prompt = hook_input(
        "UserPromptSubmit",
        prompt="Fix concurrent refresh cancellation and race conditions",
    )
    _ = prompt.pop("model")
    assert run_hook(prompt).stdout is None
    edit = hook_input(
        "PostToolUse",
        tool_name="apply_patch",
        tool_use_id="edit-one",
        tool_input={"patch": "bounded fixture"},
        tool_response={"success": True},
    )
    _ = edit.pop("model")
    assert run_hook(edit).stdout is None
    verification = verification_payload(model="gpt-5.6-sol")
    _ = verification.pop("model")
    assert _context(run_hook(verification).stdout) is None


def test_forced_terra_prompt_emits_bounded_context(
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

    assert _context(result.stdout) == context_for(Route.FAILURE_ATOMICITY)


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


@pytest.mark.parametrize("model", ["gpt-5.6-terra", "gpt-5.6-luna", None, 17])
def test_non_sol_loop_events_are_observation_only(run_hook: HookRunner, model: JsonValue) -> None:
    prompt = hook_input("UserPromptSubmit", model=model, prompt="Fix the cache bug")
    assert run_hook(prompt).stdout is None
    events = (
        hook_input(
            "PreToolUse",
            model=model,
            tool_name="Bash",
            tool_input={"command": "pytest tests/cache -q"},
        ),
        hook_input(
            "PostToolUse",
            model=model,
            tool_name="Bash",
            tool_input={"command": "pytest tests/cache -q"},
            tool_response={"exit_code": 0},
        ),
        hook_input("SubagentStart", model=model, agent_id="child-private-id"),
        hook_input("SubagentStop", model=model, agent_id="child-private-id"),
        hook_input("PreCompact", model=model, trigger="auto"),
        hook_input("PostCompact", model=model, trigger="auto"),
    )

    assert all(run_hook(event).stdout is None for event in events)
