import json
from pathlib import Path

from pydantic import JsonValue

from .conftest import HookRunner, hook_input


def _context(output: dict[str, JsonValue] | None) -> str:
    assert output is not None
    specific = output["hookSpecificOutput"]
    assert isinstance(specific, dict)
    context = specific["additionalContext"]
    assert isinstance(context, str)
    return context


def _state_payloads(plugin_data: Path) -> list[dict[str, object]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in plugin_data.rglob("*.json")]


def test_session_start_injects_minimal_beginner_context(run_hook: HookRunner) -> None:
    result = run_hook(hook_input("SessionStart", source="startup"))

    assert result.returncode == 0
    context = _context(result.stdout)
    assert "추가 과금" in context
    assert "검증" in context
    assert "초보자" in context


def test_korean_debug_prompt_routes_without_persisting_prompt(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    prompt = "버그를 고치고 테스트까지 해줘"
    result = run_hook(hook_input("UserPromptSubmit", prompt=prompt))

    assert result.returncode == 0
    assert "재현" in _context(result.stdout)
    payloads = _state_payloads(plugin_data)
    assert payloads == [{"billable_authorized": False, "profile": "debug", "schema_version": 1}]
    assert prompt not in "".join(
        path.read_text(encoding="utf-8") for path in plugin_data.rglob("*.*")
    )


def test_explanation_prompt_uses_conversation_profile(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    result = run_hook(hook_input("UserPromptSubmit", prompt="Explain what this repository does"))

    assert result.returncode == 0
    assert "plain language" in _context(result.stdout)
    assert _state_payloads(plugin_data)[0]["profile"] == "conversation"


def test_likely_api_key_is_blocked_without_echo_or_storage(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    fake_key = "sk-example_abcdefghijklmnopqrstuvwxyz123456"
    result = run_hook(hook_input("UserPromptSubmit", prompt=f"use {fake_key}"))

    assert result.returncode == 0
    assert result.stdout is not None
    assert result.stdout["decision"] == "block"
    combined = result.stdout_text + result.stderr
    assert fake_key not in combined
    assert not plugin_data.exists()


def test_negative_billing_phrase_overrides_live_words(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    prompt = "live eval은 설명만 하고 API 호출하지 마. 과금 없이 진행해"
    result = run_hook(hook_input("UserPromptSubmit", prompt=prompt))

    assert result.returncode == 0
    assert _state_payloads(plugin_data)[0]["billable_authorized"] is False


def test_malformed_and_oversized_input_fail_open_with_warning(run_hook: HookRunner) -> None:
    malformed = run_hook("not-json")
    oversized = run_hook("{" + ("x" * 1_048_576))

    for result in (malformed, oversized):
        assert result.returncode == 0
        assert result.stdout is not None
        assert result.stdout["continue"] is True
        assert "Super SOL" in str(result.stdout["systemMessage"])
