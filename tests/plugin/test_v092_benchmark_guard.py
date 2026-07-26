from pathlib import Path

from pydantic import JsonValue

from .conftest import HookEnvironmentRunner, HookRunner, hook_input, read_textual_state


def _pre_patch(path: str) -> dict[str, JsonValue]:
    return hook_input(
        "PreToolUse",
        tool_name="apply_patch",
        tool_use_id="patch-one",
        tool_input={"patch": f"*** Update File: {path}\n@@\n-old\n+new"},
    )


def _guard_env(roots: str) -> dict[str, str]:
    return {
        "SUPER_SOL_BENCHMARK_GUARD": "1",
        "SUPER_SOL_TEST_ROOTS": roots,
    }


def _permission(output: dict[str, JsonValue] | None) -> str | None:
    if output is None:
        return None
    specific = output.get("hookSpecificOutput")
    assert isinstance(specific, dict)
    value = specific.get("permissionDecision")
    return value if isinstance(value, str) else None


def test_benchmark_guard_denies_test_patch(
    run_hook_with_env: HookEnvironmentRunner,
    plugin_data: Path,
) -> None:
    result = run_hook_with_env(_pre_patch("tests/test_cache.py"), _guard_env("tests"))

    assert _permission(result.stdout) == "deny"
    assert "tests/test_cache.py" not in result.stdout_text
    assert "tests/test_cache.py" not in read_textual_state(plugin_data)


def test_normal_session_allows_test_patch(run_hook: HookRunner) -> None:
    assert run_hook(_pre_patch("tests/test_cache.py")).stdout is None


def test_benchmark_guard_allows_source_patch(
    run_hook_with_env: HookEnvironmentRunner,
) -> None:
    result = run_hook_with_env(_pre_patch("src/cache.py"), _guard_env("tests,test"))

    assert result.stdout is None


def test_benchmark_guard_fails_closed_for_parent_root(
    run_hook_with_env: HookEnvironmentRunner,
) -> None:
    result = run_hook_with_env(_pre_patch("src/cache.py"), _guard_env("../tests"))

    assert _permission(result.stdout) == "deny"


def test_benchmark_guard_fails_closed_for_unreadable_edit_target(
    run_hook_with_env: HookEnvironmentRunner,
) -> None:
    payload = hook_input(
        "PreToolUse",
        tool_name="write",
        tool_use_id="write-one",
        tool_input={"content": "replacement"},
    )

    result = run_hook_with_env(payload, _guard_env("tests"))

    assert _permission(result.stdout) == "deny"


def test_benchmark_guard_rejects_absolute_or_parent_target(
    run_hook_with_env: HookEnvironmentRunner,
) -> None:
    for path in ("/workspace/test_cache.py", "src/../tests/test_cache.py"):
        result = run_hook_with_env(_pre_patch(path), _guard_env("tests"))
        assert _permission(result.stdout) == "deny"
