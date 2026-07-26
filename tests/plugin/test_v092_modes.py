from pathlib import Path

from pydantic import JsonValue
from super_sol_routes import Route, context_for

from .conftest import HookEnvironmentRunner, HookRunner, hook_input


def _additional_context(output: dict[str, JsonValue] | None) -> str | None:
    if output is None:
        return None
    specific = output.get("hookSpecificOutput")
    assert isinstance(specific, dict)
    value = specific.get("additionalContext")
    return value if isinstance(value, str) else None


def test_natural_route_is_silent_and_stateless_by_default(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    result = run_hook(
        hook_input(
            "UserPromptSubmit",
            prompt="Fix concurrent refresh cancellation and race conditions",
        )
    )

    assert result.stdout is None
    assert not plugin_data.exists()


def test_selective_mode_restores_bounded_route(
    run_hook_with_env: HookEnvironmentRunner,
) -> None:
    result = run_hook_with_env(
        hook_input(
            "UserPromptSubmit",
            prompt="Fix concurrent refresh cancellation and race conditions",
        ),
        {"SUPER_SOL_QUALITY_MODE": "selective"},
    )

    assert _additional_context(result.stdout) == context_for(Route.CONCURRENCY_STATE)


def test_unknown_quality_mode_fails_closed_to_safety(
    run_hook_with_env: HookEnvironmentRunner,
    plugin_data: Path,
) -> None:
    result = run_hook_with_env(
        hook_input(
            "UserPromptSubmit",
            prompt="Fix concurrent refresh cancellation and race conditions",
        ),
        {"SUPER_SOL_QUALITY_MODE": "maximum"},
    )

    assert result.stdout is None
    assert not plugin_data.exists()
