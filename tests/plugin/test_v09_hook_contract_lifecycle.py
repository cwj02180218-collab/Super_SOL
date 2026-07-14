from pathlib import Path
from typing import cast

from pydantic import TypeAdapter

from .conftest import HOOK_CONFIG, HookRunner, hook_input

_OBJECT_ADAPTER = TypeAdapter[dict[str, object]](dict[str, object])


def test_third_auto_post_compact_returns_terminal_json(run_hook: HookRunner) -> None:
    assert run_hook(hook_input("UserPromptSubmit", prompt="Fix the cache bug")).stdout is None
    output = None
    for index in range(3):
        output = run_hook(hook_input("PostCompact", trigger="auto", compaction_index=index)).stdout

    assert output == {
        "continue": False,
        "stopReason": "loop_fuse_no_progress_compaction",
    }


def test_new_user_prompt_resets_only_loop_fuse_state(run_hook: HookRunner) -> None:
    assert run_hook(hook_input("UserPromptSubmit", prompt="Fix the cache bug")).stdout is None
    for index in range(3):
        _ = run_hook(hook_input("PostCompact", trigger="auto", compaction_index=index))
    assert run_hook(hook_input("UserPromptSubmit", prompt="A new request")).stdout is None

    assert run_hook(hook_input("PostCompact", trigger="auto")).stdout is None


def test_subagent_events_update_private_state_without_context(
    run_hook: HookRunner, plugin_data: Path
) -> None:
    assert run_hook(hook_input("UserPromptSubmit", prompt="Fix the cache bug")).stdout is None
    for event in ("SubagentStart", "SubagentStop"):
        assert run_hook(hook_input(event, agent_id="child-private-id")).stdout is None

    ledger = next(plugin_data.rglob("loop.json"))
    stored = _OBJECT_ADAPTER.validate_json(ledger.read_text(encoding="utf-8"))
    assert "child-private-id" not in ledger.read_text(encoding="utf-8")
    active_agents = stored["active_agents"]
    assert isinstance(active_agents, list)
    identifiers = cast("list[object]", active_agents)
    assert all(isinstance(identifier, str) and len(identifier) == 24 for identifier in identifiers)


def test_manifest_has_no_stop_handler_and_korean_reasons_are_bounded(run_hook: HookRunner) -> None:
    manifest = _OBJECT_ADAPTER.validate_json(HOOK_CONFIG.read_text(encoding="utf-8"))
    hooks = manifest["hooks"]
    assert isinstance(hooks, dict)
    assert "Stop" not in hooks
    assert run_hook(hook_input("UserPromptSubmit", prompt="Fix the cache bug")).stdout is None
    _ = run_hook(
        hook_input(
            "PostToolUse",
            tool_name="Bash",
            tool_input={"command": "pytest tests/cache -q"},
            tool_response={"exit_code": 0},
        )
    )
    output = run_hook(
        hook_input(
            "PreToolUse",
            tool_name="Bash",
            tool_input={"command": "pytest tests/cache -q"},
        )
    ).stdout
    assert output is not None
    specific = output["hookSpecificOutput"]
    assert isinstance(specific, dict)
    reason = specific["permissionDecisionReason"]
    assert isinstance(reason, str)
    assert len(reason) <= 180
