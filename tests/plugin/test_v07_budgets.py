from pathlib import Path

from super_sol_routes import (
    CONTEXT_CODEPOINT_LIMIT,
    REPAIR_CONTEXT,
    Contract,
    Route,
    context_for,
    residual_context,
)
from super_sol_state import MAX_INJECTIONS_PER_TURN

from fablized_sol.eval.hook_latency import (
    ABSOLUTE_P95_THRESHOLD_MS,
    DEFAULT_FLOOR_SAMPLES,
    DEFAULT_HOOK_SAMPLES,
    INCREMENTAL_P95_THRESHOLD_MS,
    select_prompt_command,
)

from .conftest import (
    PLUGIN_ROOT,
    HookRunner,
    hook_input,
    read_textual_state,
    textual_state_artifacts,
)


def test_public_context_and_injection_budgets_are_frozen() -> None:
    assert CONTEXT_CODEPOINT_LIMIT == 180
    assert len(REPAIR_CONTEXT) <= CONTEXT_CODEPOINT_LIMIT
    assert MAX_INJECTIONS_PER_TURN == 2
    assert all(
        len(context) <= CONTEXT_CODEPOINT_LIMIT
        for route in Route
        if (context := context_for(route)) is not None
    )
    assert all(len(residual_context(contract)) <= CONTEXT_CODEPOINT_LIMIT for contract in Contract)


def test_prompt_latency_gate_contract_is_frozen_without_running_processes() -> None:
    assert select_prompt_command(PLUGIN_ROOT) == (
        "/usr/bin/python3",
        "-S",
        str(PLUGIN_ROOT / "hooks" / "prompt_dispatcher.py"),
    )
    assert DEFAULT_HOOK_SAMPLES == 300
    assert DEFAULT_FLOOR_SAMPLES == 150
    assert ABSOLUTE_P95_THRESHOLD_MS == 100.0
    assert INCREMENTAL_P95_THRESHOLD_MS == 70.0


def test_stored_state_is_bounded_and_contains_no_raw_fixture_text(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    prompt = "Fix concurrent refresh cancellation and race conditions SECRET_PROMPT"
    command = "uv run pytest -q SECRET_COMMAND"
    source = "SECRET_SOURCE"
    output = "SECRET_OUTPUT"
    assert run_hook(hook_input("UserPromptSubmit", prompt=prompt)).stdout is not None
    assert (
        run_hook(
            hook_input(
                "PostToolUse",
                tool_name="Write",
                tool_use_id="budget-edit",
                tool_input={"content": source, "file_path": "SECRET_FILE"},
                tool_response={"success": True},
            )
        ).stdout
        is None
    )
    verification = run_hook(
        hook_input(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="budget-verification",
            tool_input={"command": command},
            tool_response={"exit_code": 0, "output": output},
        )
    )
    assert verification.stdout is not None

    files = textual_state_artifacts(plugin_data)
    assert files
    assert all(path.stat().st_size <= 4096 for path in files)
    stored = read_textual_state(plugin_data)
    for secret in (prompt, command, source, output, "SECRET_FILE"):
        assert secret not in stored
