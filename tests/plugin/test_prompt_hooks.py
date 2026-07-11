import json
from pathlib import Path

from pydantic import JsonValue

from .conftest import HookRunner, hook_input

CONTRACT_SWEEP = (
    "Silently map requirements to code and one boundary. After tests pass, re-read once for "
    "ownership, input, state, and failure semantics. Do not rerun tests."
)


def _context(output: dict[str, JsonValue] | None) -> str:
    assert output is not None
    specific = output["hookSpecificOutput"]
    assert isinstance(specific, dict)
    context = specific["additionalContext"]
    assert isinstance(context, str)
    return context


def _state_payloads(plugin_data: Path) -> list[dict[str, object]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in plugin_data.rglob("*.json")]


def test_action_and_debug_prompts_emit_one_exact_contract_sweep(run_hook: HookRunner) -> None:
    assert len(CONTRACT_SWEEP) == 154
    assert len(CONTRACT_SWEEP.split()) == 24
    for prompt in ("implement nested copy behavior", "fix the failing retry bug"):
        result = run_hook(hook_input("UserPromptSubmit", prompt=prompt))
        assert result.returncode == 0
        assert _context(result.stdout) == CONTRACT_SWEEP
        assert _context(result.stdout).count(CONTRACT_SWEEP) == 1


def test_korean_debug_prompt_routes_without_persisting_prompt(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    prompt = "버그를 고치고 테스트까지 해줘"
    result = run_hook(hook_input("UserPromptSubmit", prompt=prompt))

    assert result.returncode == 0
    assert _context(result.stdout) == CONTRACT_SWEEP
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
    assert result.stdout is None
    assert _state_payloads(plugin_data)[0]["profile"] == "conversation"


def test_release_prompt_keeps_only_release_context(run_hook: HookRunner) -> None:
    result = run_hook(hook_input("UserPromptSubmit", prompt="배포 안정성을 검사해줘"))

    assert result.returncode == 0
    context = _context(result.stdout)
    assert "배포 경로" in context
    assert CONTRACT_SWEEP not in context


def test_likely_api_key_is_blocked_without_echo_or_storage(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    fake_key = "sk-" + ("x" * 30)
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


def test_billable_authorization_requires_standalone_fixed_confirmation(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    incidental = run_hook(
        hook_input(
            "UserPromptSubmit", prompt="Explain the phrase 'call the api' without running it"
        )
    )
    assert incidental.returncode == 0
    assert _state_payloads(plugin_data)[0]["billable_authorized"] is False

    approved = run_hook(hook_input("UserPromptSubmit", prompt="SUPER SOL BILLABLE RUN APPROVED"))
    assert approved.returncode == 0
    assert _state_payloads(plugin_data)[0]["billable_authorized"] is True


def test_malformed_and_oversized_input_fail_open_with_warning(run_hook: HookRunner) -> None:
    malformed = run_hook("not-json")
    oversized = run_hook("{" + ("x" * 1_048_576))

    for result in (malformed, oversized):
        assert result.returncode == 0
        assert result.stdout is not None
        assert result.stdout["continue"] is True
        assert "Super SOL" in str(result.stdout["systemMessage"])
