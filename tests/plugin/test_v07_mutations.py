import pytest
from pydantic import JsonValue

from super_sol_routes import CONTEXT_CODEPOINT_LIMIT, Contract, residual_context
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


def _verification(model: JsonValue) -> dict[str, JsonValue]:
    return hook_input(
        "PostToolUse",
        model=model,
        tool_name="Bash",
        tool_use_id="verify-one",
        tool_input={"command": "uv run pytest -q"},
        tool_response={"exit_code": 0},
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
    assert _context(run_hook(_prompt("gpt-5.6-terra")).stdout) is None
    assert _context(run_hook(_edit("gpt-5.6-terra")).stdout) is None
    assert _context(run_hook(_verification("gpt-5.6-terra")).stdout) is None


def test_mutation_accepting_a_181_code_point_context_exceeds_the_frozen_limit() -> None:
    assert len("x" * 181) > CONTEXT_CODEPOINT_LIMIT


def test_mutation_allowing_a_second_context_injection_is_blocked(run_hook: HookRunner) -> None:
    assert _context(run_hook(_prompt("gpt-5.6-sol")).stdout) is None
    assert _context(run_hook(_edit("gpt-5.6-sol")).stdout) is None
    assert _context(run_hook(_verification("gpt-5.6-sol")).stdout) == residual_context(
        Contract.CONCURRENCY_CANCELLATION
    )
    assert _context(run_hook(_verification("gpt-5.6-sol")).stdout) is None


def test_mutation_emitting_context_before_verification_is_blocked(run_hook: HookRunner) -> None:
    assert _context(run_hook(_prompt("gpt-5.6-sol")).stdout) is None
    assert _context(run_hook(_edit("gpt-5.6-sol")).stdout) is None
