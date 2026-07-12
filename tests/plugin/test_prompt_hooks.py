import json
from pathlib import Path

from pydantic import JsonValue
from super_sol_routes import Route, context_for

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


def test_pass_through_prompt_emits_no_model_context(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    result = run_hook(hook_input("UserPromptSubmit", prompt="rename this variable"))

    assert result.returncode == 0
    assert result.stdout is None
    assert _state_payloads(plugin_data) == [
        {
            "billable_authorized": False,
            "forced": False,
            "route": "pass_through",
            "schema_version": 2,
            "signal_ids": [],
        }
    ]


def test_specialist_prompt_emits_only_selected_pack(run_hook: HookRunner) -> None:
    result = run_hook(
        hook_input(
            "UserPromptSubmit",
            prompt="Fix concurrent refresh cancellation and race conditions",
        )
    )

    assert result.returncode == 0
    assert _context(result.stdout) == context_for(Route.CONCURRENCY_STATE)
    assert "same-key coalescing" in _context(result.stdout)
    assert "migration" not in _context(result.stdout).casefold()


def test_korean_security_prompt_routes_without_persisting_prompt(
    run_hook: HookRunner,
    plugin_data: Path,
) -> None:
    prompt = "심볼릭 링크와 경로 순회를 차단해줘"
    result = run_hook(hook_input("UserPromptSubmit", prompt=prompt))

    assert result.returncode == 0
    assert _context(result.stdout) == context_for(Route.SECURITY_BOUNDARY)
    combined = "".join(path.read_text(encoding="utf-8") for path in plugin_data.rglob("*.*"))
    assert prompt not in combined
    assert _state_payloads(plugin_data)[0]["route"] == "security_boundary"


def test_ambiguous_and_mixed_prompts_pass_through(run_hook: HookRunner) -> None:
    prompts = (
        "Explain what race conditions and migrations are",
        "Add path traversal protection and migrate schema versions",
        "Explain this module and update README.md with the explanation",
    )

    for prompt in prompts:
        result = run_hook(hook_input("UserPromptSubmit", prompt=prompt))
        assert result.returncode == 0
        assert result.stdout is None


def test_first_line_route_controls_are_sanitized(run_hook: HookRunner) -> None:
    off = run_hook(
        hook_input(
            "UserPromptSubmit",
            prompt="SUPER SOL OFF\nFix concurrent refresh race conditions",
        )
    )
    forced = run_hook(
        hook_input(
            "UserPromptSubmit",
            prompt="SUPER SOL ROUTE migration_compatibility\nFix this conversion",
        )
    )
    invalid = run_hook(
        hook_input("UserPromptSubmit", prompt="SUPER SOL ROUTE unknown\nFix this conversion")
    )

    assert off.stdout is None
    assert _context(forced.stdout) == context_for(Route.MIGRATION_COMPATIBILITY)
    assert invalid.stdout is not None
    assert "pass-through" in str(invalid.stdout["systemMessage"])


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
