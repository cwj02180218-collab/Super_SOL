from pathlib import Path

from super_sol_audit import audit_summary, record_incident

from .conftest import HookRunner, hook_input, read_textual_state


def _repeat_read(run_hook: HookRunner, index: int, command: str = "rg cache src") -> object:
    return run_hook(
        hook_input(
            "PostToolUse",
            tool_name="Bash",
            tool_use_id=f"read-{index}",
            tool_input={"command": command},
            tool_response={"exit_code": 0},
        )
    ).stdout


def test_soft_warning_is_silent_but_audited(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    outputs = [_repeat_read(run_hook, index) for index in range(3)]

    assert outputs == [None, None, None]
    root = next(plugin_data.rglob("loop.json")).parent
    assert audit_summary(root) == {"deny": 0, "stop": 0, "warn": 1}
    event = next((root / "audit").glob("*.json")).read_text(encoding="utf-8")
    assert '"decision":"warn"' in event
    assert '"reason":"loop_fuse_tool_replay"' in event


def test_hard_deny_is_audited_without_changing_response(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    verifier = hook_input(
        "PostToolUse",
        tool_name="Bash",
        tool_use_id="verify-one",
        tool_input={"command": "pytest tests/cache -q"},
        tool_response={"exit_code": 0},
    )
    _ = run_hook(verifier)
    denied = run_hook(
        hook_input(
            "PreToolUse",
            tool_name="Bash",
            tool_use_id="verify-two",
            tool_input={"command": "pytest tests/cache -q"},
        )
    ).stdout

    assert denied is not None
    root = next(plugin_data.rglob("loop.json")).parent
    assert audit_summary(root)["deny"] == 1


def test_audit_tree_excludes_sensitive_command_sentinel(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    command = "rg PRIVATE_COMMAND_SENTINEL src"
    for index in range(3):
        _ = _repeat_read(run_hook, index, command)

    assert "PRIVATE_COMMAND_SENTINEL" not in read_textual_state(plugin_data)


def test_incident_ledger_is_bounded_to_sixty_four_events(tmp_path: Path) -> None:
    root = tmp_path / "turn"

    results = [
        record_incident(
            root,
            event="PostToolUse",
            reason="loop_fuse_tool_replay",
            decision="warn",
            observed_at=index,
        )
        for index in range(70)
    ]

    assert results == ([True] * 64) + ([False] * 6)
    assert len(tuple((root / "audit").glob("*.json"))) == 64


def test_invalid_incident_is_rejected_without_state(tmp_path: Path) -> None:
    root = tmp_path / "turn"

    recorded = record_incident(
        root,
        event="UnknownEvent",
        reason="raw user content",
        decision="continue",
        observed_at=1,
    )

    assert recorded is False
    assert not root.exists()
