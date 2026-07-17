import pytest
import super_sol_routes
from pydantic import JsonValue
from super_sol_routes import Contract, Route, context_for, residual_context
from super_sol_state import next_context_kind

from .conftest import HookRunner, hook_input


def _context(output: dict[str, JsonValue] | None) -> str | None:
    if output is None:
        return None
    specific = output["hookSpecificOutput"]
    assert isinstance(specific, dict)
    value = specific["additionalContext"]
    assert isinstance(value, str)
    return value


def _successful_bash(
    model: JsonValue,
    *,
    command: str,
    tool_use_id: str,
) -> dict[str, JsonValue]:
    return hook_input(
        "PostToolUse",
        model=model,
        tool_name="Bash",
        tool_use_id=tool_use_id,
        tool_input={"command": command},
        tool_response={"exit_code": 0},
    )


def _verification(model: JsonValue) -> dict[str, JsonValue]:
    return _successful_bash(
        model,
        command="uv run pytest -q",
        tool_use_id="verify-one",
    )


def _prompt(model: JsonValue) -> dict[str, JsonValue]:
    return hook_input(
        "UserPromptSubmit",
        model=model,
        prompt="Fix concurrent refresh cancellation and race conditions",
    )


def _edit(model: JsonValue) -> dict[str, JsonValue]:
    return hook_input(
        "PostToolUse",
        model=model,
        tool_name="apply_patch",
        tool_use_id="edit-one",
        tool_input={"patch": "bounded fixture"},
        tool_response={"success": True},
    )


@pytest.mark.parametrize(
    ("state", "events", "verification_success", "expected"),
    [
        (
            {"diagnostic_mode": "adaptive", "primary_contract": "retry_state"},
            ({"kind": "edit", "success": True},),
            True,
            "residual",
        ),
        (
            {"diagnostic_mode": "adaptive", "primary_contract": "retry_state"},
            ({"kind": "edit", "success": True},),
            False,
            "repair",
        ),
        (
            {"diagnostic_mode": "adaptive", "primary_contract": None},
            ({"kind": "edit", "success": True},),
            True,
            None,
        ),
        (
            {"diagnostic_mode": "observe", "primary_contract": "retry_state"},
            ({"kind": "edit", "success": True},),
            True,
            None,
        ),
        (
            {"diagnostic_mode": "adaptive", "primary_contract": "retry_state"},
            (),
            True,
            None,
        ),
        (
            {"diagnostic_mode": "adaptive", "primary_contract": "retry_state"},
            ({"kind": "edit", "success": False},),
            True,
            None,
        ),
    ],
)
def test_each_context_guard_blocks_its_mutation(
    state: dict[str, object],
    events: tuple[dict[str, object], ...],
    verification_success: bool,
    expected: str | None,
) -> None:
    assert next_context_kind(state, events, verification_success) == expected


def test_mutation_removing_model_gating_emits_no_context_for_an_observe_model(
    run_hook: HookRunner,
) -> None:
    assert _context(run_hook(_prompt("gpt-5.6-luna")).stdout) is None
    assert _context(run_hook(_edit("gpt-5.6-luna")).stdout) is None
    assert _context(run_hook(_verification("gpt-5.6-luna")).stdout) is None


def test_mutation_accepting_a_181_code_point_residual_raises_budget_error() -> None:
    with pytest.raises(super_sol_routes.ResidualContextBudgetError):
        _ = super_sol_routes.validate_residual_context("x" * 181)


def test_prompt_and_evidence_channels_each_emit_once(run_hook: HookRunner) -> None:
    assert _context(run_hook(_prompt("gpt-5.6-sol")).stdout) == context_for(Route.CONCURRENCY_STATE)
    assert _context(run_hook(_edit("gpt-5.6-sol")).stdout) is None
    assert _context(run_hook(_verification("gpt-5.6-sol")).stdout) == residual_context(
        Contract.CONCURRENCY_CANCELLATION
    )
    assert _context(run_hook(_verification("gpt-5.6-sol")).stdout) is None


def test_mutation_emitting_context_before_verification_is_blocked(run_hook: HookRunner) -> None:
    assert _context(run_hook(_prompt("gpt-5.6-sol")).stdout) == context_for(Route.CONCURRENCY_STATE)
    assert _context(run_hook(_edit("gpt-5.6-sol")).stdout) is None
    non_verification = run_hook(
        _successful_bash(
            "gpt-5.6-sol",
            command="git status --short",
            tool_use_id="non-verification",
        )
    )

    assert non_verification.returncode == 0
    assert _context(non_verification.stdout) is None
    assert _context(run_hook(_verification("gpt-5.6-sol")).stdout) == residual_context(
        Contract.CONCURRENCY_CANCELLATION
    )
