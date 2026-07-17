import json
from pathlib import Path

import pytest
from pydantic import JsonValue
from super_sol_routes import Route, context_for, route_prompt

from .conftest import HookRunner, hook_input


def _context(output: dict[str, JsonValue] | None) -> str | None:
    if output is None:
        return None
    specific = output["hookSpecificOutput"]
    assert isinstance(specific, dict)
    context = specific["additionalContext"]
    assert isinstance(context, str)
    return context


def _state_payloads(plugin_data: Path) -> list[dict[str, object]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in plugin_data.rglob("*.json")]


@pytest.mark.parametrize(
    ("model", "turn_id"),
    [
        ("gpt-5.6-sol", "sol-route-turn"),
        ("gpt-5.6-terra", "terra-route-turn"),
    ],
)
def test_high_confidence_routes_are_active_for_exact_profiles(
    run_hook: HookRunner,
    model: str,
    turn_id: str,
) -> None:
    result = run_hook(
        hook_input(
            "UserPromptSubmit",
            model=model,
            turn_id=turn_id,
            prompt="Fix concurrent refresh cancellation and race conditions",
        )
    )

    assert _context(result.stdout) == context_for(Route.CONCURRENCY_STATE)


def test_ambiguous_action_is_silent_but_persists_action_marker(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    result = run_hook(
        hook_input(
            "UserPromptSubmit",
            prompt="Add path traversal protection and migrate schema versions",
        )
    )

    assert result.stdout is None
    state = _state_payloads(plugin_data)[0]
    assert state["actionable"] is True
    assert state["effective_route"] == "pass_through"


def test_same_prompt_turn_claim_emits_once(run_hook: HookRunner) -> None:
    payload = hook_input(
        "UserPromptSubmit",
        turn_id="duplicate-prompt-turn",
        prompt="Fix concurrent refresh cancellation and race conditions",
    )

    first = run_hook(payload)
    second = run_hook(payload)

    assert _context(first.stdout) == context_for(Route.CONCURRENCY_STATE)
    assert second.stdout is None


def test_unknown_model_never_receives_route_context(run_hook: HookRunner) -> None:
    result = run_hook(
        hook_input(
            "UserPromptSubmit",
            model="gpt-5.6-luna",
            prompt="Fix concurrent refresh cancellation and race conditions",
        )
    )

    assert result.stdout is None


def test_route_decisions_expose_actionability() -> None:
    confident = route_prompt("Fix concurrent refresh cancellation and race conditions")
    ambiguous = route_prompt("Add path traversal protection and migrate schema versions")
    explanation = route_prompt("Explain what race conditions are")

    assert confident.actionable is True
    assert ambiguous.actionable is True
    assert ambiguous.route is Route.PASS_THROUGH
    assert explanation.actionable is False


def test_specialist_contexts_fit_the_v091_budget() -> None:
    contexts = tuple(context_for(route) for route in Route if route is not Route.PASS_THROUGH)

    assert all(context is not None and len(context) <= 180 for context in contexts)
