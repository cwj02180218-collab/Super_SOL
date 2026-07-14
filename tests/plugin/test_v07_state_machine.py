from pathlib import Path

import pytest
from pydantic import JsonValue
from super_sol_routes import Contract, residual_context

from .conftest import (
    HookEnvironmentRunner,
    HookRunner,
    hook_input,
    read_textual_state,
    textual_state_artifacts,
)


def _profile_payload(
    profile: str,
    model: JsonValue | None,
    *,
    event: str,
    **fields: JsonValue,
) -> dict[str, JsonValue]:
    payload = hook_input(
        event,
        session_id=f"SESSION_FIXTURE_{profile}",
        turn_id=f"TURN_FIXTURE_{profile}",
        model_fixture=f"MODEL_FIXTURE_{profile}",
        **fields,
    )
    if model is None:
        _ = payload.pop("model")
    else:
        payload["model"] = model
    return payload


def _context(output: dict[str, JsonValue] | None) -> str | None:
    if output is None:
        return None
    specific = output["hookSpecificOutput"]
    assert isinstance(specific, dict)
    value = specific["additionalContext"]
    assert isinstance(value, str)
    return value


def _prime(run_hook: HookRunner) -> None:
    result = run_hook(
        hook_input(
            "UserPromptSubmit",
            prompt="Fix concurrent refresh cancellation and race conditions",
        )
    )
    assert result.stdout is None


def _edit(run_hook: HookRunner, *, success: bool = True, tool_use_id: str = "edit-one") -> None:
    result = run_hook(
        hook_input(
            "PostToolUse",
            tool_name="apply_patch",
            tool_use_id=tool_use_id,
            tool_input={"patch": "secret source text"},
            tool_response={"success": success},
        )
    )
    assert result.stdout is None


def _verify(
    run_hook: HookRunner,
    *,
    exit_code: int,
    tool_use_id: str,
) -> dict[str, JsonValue] | None:
    result = run_hook(
        hook_input(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id=tool_use_id,
            tool_input={"command": "uv run pytest -q secret_test_name"},
            tool_response={"exit_code": exit_code, "output": "secret tool output"},
        )
    )
    assert result.returncode == 0
    return result.stdout


def test_edit_then_first_success_emits_one_residual_context(run_hook: HookRunner) -> None:
    _prime(run_hook)
    _edit(run_hook)

    first = _verify(run_hook, exit_code=0, tool_use_id="verify-one")
    second = _verify(run_hook, exit_code=0, tool_use_id="verify-two")

    assert _context(first) == residual_context(Contract.CONCURRENCY_CANCELLATION)
    assert second is None


def test_success_without_edit_and_failed_edit_are_silent(run_hook: HookRunner) -> None:
    _prime(run_hook)
    assert _verify(run_hook, exit_code=0, tool_use_id="before-edit") is None
    _edit(run_hook, success=False)
    assert _verify(run_hook, exit_code=0, tool_use_id="after-failed-edit") is None


def test_failure_emits_one_repair_and_suppresses_later_residual(run_hook: HookRunner) -> None:
    _prime(run_hook)
    _edit(run_hook)

    first = _verify(run_hook, exit_code=1, tool_use_id="failed-one")
    second = _verify(run_hook, exit_code=1, tool_use_id="failed-two")
    success = _verify(run_hook, exit_code=0, tool_use_id="success-after-repair")

    assert first is not None
    assert "Verification failed" in str(_context(first))
    assert second is None
    assert success is None


def test_pass_through_observe_and_unrecognized_commands_are_silent(
    run_hook: HookRunner,
    run_hook_with_env: HookEnvironmentRunner,
) -> None:
    generic = run_hook(hook_input("UserPromptSubmit", prompt="rename this variable"))
    assert generic.stdout is None
    _edit(run_hook)
    assert _verify(run_hook, exit_code=0, tool_use_id="generic-success") is None

    environment = {"SUPER_SOL_DIAGNOSTIC_MODE": "observe"}
    observed = run_hook_with_env(
        hook_input(
            "UserPromptSubmit",
            prompt="Fix concurrent refresh cancellation and race conditions",
        ),
        environment,
    )
    assert observed.stdout is None
    edit = run_hook_with_env(
        hook_input(
            "PostToolUse",
            tool_name="Edit",
            tool_use_id="observe-edit",
            tool_input={"file_path": "secret.py"},
            tool_response={"success": True},
        ),
        environment,
    )
    verify = run_hook_with_env(
        hook_input(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="observe-verify",
            tool_input={"command": "uv run pytest -q"},
            tool_response={"exit_code": 0},
        ),
        environment,
    )
    assert edit.stdout is None
    assert verify.stdout is None


def test_private_events_store_no_prompt_source_command_or_output(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    _prime(run_hook)
    _edit(run_hook)
    _ = _verify(run_hook, exit_code=0, tool_use_id="private-verify")

    stored = read_textual_state(plugin_data)
    assert "secret source text" not in stored
    assert "secret_test_name" not in stored
    assert "secret tool output" not in stored
    assert "race conditions" not in stored
    assert '"kind":"edit"' in stored
    assert '"kind":"verification"' in stored


@pytest.mark.parametrize(
    ("profile", "model"),
    [
        ("SOL", "gpt-5.6-sol"),
        ("TERRA", "gpt-5.6-terra"),
        ("LUNA", "gpt-5.6-luna"),
        ("MISSING", None),
        ("MALFORMED", {"fixture": "MODEL_FIXTURE_MALFORMED_VALUE"}),
    ],
)
def test_all_model_profiles_retain_no_raw_turn_fixtures(
    run_hook: HookRunner,
    plugin_data: Path,
    profile: str,
    model: JsonValue | None,
) -> None:
    prompt = f"PROMPT_FIXTURE_{profile} Fix concurrent refresh cancellation and race conditions"
    source = f"SOURCE_FIXTURE_{profile}"
    path = f"PATH_FIXTURE_{profile}.py"
    command = f"COMMAND_FIXTURE_{profile}"
    output = f"OUTPUT_FIXTURE_{profile}"
    fixtures = (prompt, source, path, command, output, f"MODEL_FIXTURE_{profile}")

    assert (
        run_hook(
            _profile_payload(
                profile,
                model,
                event="UserPromptSubmit",
                prompt=prompt,
            )
        ).stdout
        is None
    )
    assert (
        run_hook(
            _profile_payload(
                profile,
                model,
                event="PostToolUse",
                tool_name="apply_patch",
                tool_use_id=f"EDIT_FIXTURE_{profile}",
                tool_input={"file_path": path, "patch": source},
                tool_response={"success": True},
            )
        ).stdout
        is None
    )
    assert (
        run_hook(
            _profile_payload(
                profile,
                model,
                event="PostToolUse",
                tool_name="Bash",
                tool_use_id=f"VERIFY_FIXTURE_{profile}",
                tool_input={"command": f"uv run pytest -q {command}"},
                tool_response={"exit_code": 0, "output": output},
            )
        ).returncode
        == 0
    )

    files = textual_state_artifacts(plugin_data)
    assert files
    assert all(path.stat().st_size <= 4096 for path in files)
    stored = "".join(path.read_text(encoding="utf-8") for path in files)
    assert all(fixture not in stored for fixture in fixtures)
