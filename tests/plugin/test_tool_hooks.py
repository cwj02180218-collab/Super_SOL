import pytest
from pydantic import JsonValue
from super_sol_routes import REPAIR_CONTEXT

from .conftest import HookEnvironmentRunner, HookRunner, hook_input


def _prime(run_hook: HookRunner, prompt: str = "이 파일을 수정해줘") -> None:
    result = run_hook(hook_input("UserPromptSubmit", prompt=prompt))
    assert result.returncode == 0


def _post_tool_result(
    run_hook: HookRunner,
    command: str,
    exit_code: int,
    tool_use_id: str,
) -> dict[str, JsonValue] | None:
    result = run_hook(
        hook_input(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id=tool_use_id,
            tool_input={"command": command},
            tool_response={"exit_code": exit_code},
        )
    )
    assert result.returncode == 0
    return result.stdout


def _post_edit(run_hook: HookRunner, tool_use_id: str = "edit-before-verification") -> None:
    result = run_hook(
        hook_input(
            "PostToolUse",
            tool_name="apply_patch",
            tool_use_id=tool_use_id,
            tool_input={"patch": "bounded fixture"},
            tool_response={"success": True},
        )
    )
    assert result.returncode == 0
    assert result.stdout is None


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


def test_unapproved_cleanroom_codex_ab_is_denied(run_hook: HookRunner) -> None:
    _prime(run_hook)
    result = run_hook(
        hook_input(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="pre-cleanroom",
            tool_input={"command": "uv run super-sol-codex-ab --tasks tasks.json"},
        )
    )

    assert result.stdout is not None
    specific = result.stdout["hookSpecificOutput"]
    assert isinstance(specific, dict)
    assert specific["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "uv run --project . super-sol-eval --tasks tasks.json",
        "uv run --locked super-sol-eval --tasks tasks.json",
        "uv run --with typer --with pydantic super-sol-eval --tasks tasks.json",
        "uv run --config-file uv.toml super-sol-eval --tasks tasks.json",
        "uv run --env-file .env super-sol-eval --tasks tasks.json",
        "uv run --default-index https://pypi.org/simple super-sol-eval --tasks tasks.json",
    ],
)
def test_uv_run_options_cannot_bypass_live_eval_consent(
    run_hook: HookRunner,
    command: str,
) -> None:
    _prime(run_hook)
    result = run_hook(
        hook_input(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="pre-uv-options",
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


@pytest.mark.parametrize(
    "command",
    [
        "rg super-sol-eval README.md",
        "echo super-sol-eval",
        "ls docs/super-sol-eval-notes.md",
    ],
)
def test_non_eval_commands_that_mention_executable_are_allowed(
    run_hook: HookRunner,
    command: str,
) -> None:
    _prime(run_hook)
    result = run_hook(
        hook_input(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="pre-mention",
            tool_input={"command": command},
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


def test_failed_verification_emits_repair_context_once(run_hook: HookRunner) -> None:
    _prime(run_hook, "Fix concurrent refresh cancellation and race conditions")
    _post_edit(run_hook)

    first = _post_tool_result(run_hook, "uv run pytest -q", 1, "failed-one")
    second = _post_tool_result(run_hook, "uv run pytest -q", 1, "failed-two")

    assert first is not None
    specific = first["hookSpecificOutput"]
    assert isinstance(specific, dict)
    assert specific["hookEventName"] == "PostToolUse"
    assert specific["additionalContext"] == REPAIR_CONTEXT
    assert second is None


def test_cmd_alias_verification_emits_repair_context(run_hook: HookRunner) -> None:
    _prime(run_hook, "Fix concurrent refresh cancellation and race conditions")
    _post_edit(run_hook)

    result = run_hook(
        hook_input(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="failed-cmd-alias",
            tool_input={"cmd": "uv run pytest -q"},
            tool_response={"exit_code": 1},
        )
    )

    assert result.stdout is not None
    specific = result.stdout["hookSpecificOutput"]
    assert isinstance(specific, dict)
    assert specific["additionalContext"] == REPAIR_CONTEXT


def test_success_unrecognized_and_pass_through_failures_emit_no_context(
    run_hook: HookRunner,
) -> None:
    _prime(run_hook, "Reject path traversal and symlink parents")
    assert _post_tool_result(run_hook, "uv run pytest -q", 0, "pass") is None
    assert _post_tool_result(run_hook, "echo pytest", 1, "mention") is None
    assert _post_tool_result(run_hook, "pytest -q || true", 1, "chain") is None

    _prime(run_hook, "rename this variable")
    assert _post_tool_result(run_hook, "uv run pytest -q", 1, "generic-fail") is None


@pytest.mark.parametrize(
    "command",
    ["python3 -m pytest -q", "python -m mypy src", "python3 -m basedpyright"],
)
def test_python_module_failures_are_recognized_once(
    run_hook: HookRunner,
    command: str,
) -> None:
    _prime(run_hook, "Validate before mutation and roll back this atomic batch")
    _post_edit(run_hook, f"edit-{command}")
    result = _post_tool_result(run_hook, command, 1, f"failure-{command}")
    assert result is not None


def test_observe_mode_never_emits_repair_context(
    run_hook_with_env: HookEnvironmentRunner,
) -> None:
    environment = {"SUPER_SOL_DIAGNOSTIC_MODE": "observe"}
    prompt = run_hook_with_env(
        hook_input(
            "UserPromptSubmit",
            prompt="Fix concurrent refresh cancellation and race conditions",
        ),
        environment,
    )
    failure = run_hook_with_env(
        hook_input(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id="observe-failure",
            tool_input={"command": "uv run pytest -q"},
            tool_response={"exit_code": 1},
        ),
        environment,
    )

    assert prompt.stdout is None
    assert failure.stdout is None
