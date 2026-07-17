import importlib
import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol, cast

import prompt_dispatcher
import pytest
import super_sol_hook
import super_sol_loop_state
import super_sol_routes
from pydantic import JsonValue
from super_sol_loop_state import LoopLedger, load_loop_ledger, mutate_loop_ledger
from super_sol_state import turn_root

from .conftest import HOOK_SCRIPT, PLUGIN_ROOT, PROMPT_DISPATCHER, hook_input


class _SignalView(Protocol):
    phrases: tuple[str, ...]


def _production_signal_phrases() -> Iterator[str]:
    module_values = vars(super_sol_routes)
    tables = (
        cast("dict[object, tuple[_SignalView, ...]]", module_values["_CONTRACT_SIGNALS"]),
        cast("dict[object, tuple[_SignalView, ...]]", module_values["_SIGNALS"]),
    )
    for table in tables:
        for signals in table.values():
            for signal in signals:
                yield from signal.phrases


def _delegated(
    payload: dict[str, JsonValue] | str,
    *,
    environment: dict[str, str] | None = None,
) -> bool:
    raw = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
    calls: list[bytes] = []

    def delegate(value: bytes) -> None:
        calls.append(value)

    dispatch = cast(
        "Callable[[bytes, dict[str, str], Callable[[bytes], None]], None]",
        prompt_dispatcher.dispatch,
    )
    dispatch(raw, environment or {}, delegate)
    return bool(calls)


def test_every_production_contract_signal_delegates_to_full_hook() -> None:
    phrases = tuple(dict.fromkeys(_production_signal_phrases()))
    missed = [
        phrase
        for phrase in phrases
        if not _delegated(
            hook_input("UserPromptSubmit", prompt=f"Please consider {phrase}"),
        )
    ]

    assert phrases
    assert missed == []


@pytest.mark.parametrize(
    "prompt",
    [
        "use sk-abcdefghijklmnopqrst for this request",
        "SUPER SOL OFF\nrename this variable",
        "SUPER SOL ROUTE failure_atomicity\nrename this variable",
        "SUPER SOL BILLABLE RUN APPROVED",
        "SUPER SOL 유료 실행 승인",
        "do not call api for this task",
        "과금 없이 진행해",
    ],
)
def test_safety_and_control_prompts_always_delegate(
    prompt: str,
) -> None:
    assert _delegated(hook_input("UserPromptSubmit", prompt=prompt))


@pytest.mark.parametrize(
    "environment",
    [
        {"SUPER_SOL_DIAGNOSTIC_MODE": "observe"},
        {"SUPER_SOL_FORCED_ROUTE": "failure_atomicity"},
    ],
)
def test_diagnostic_environment_always_delegates(
    environment: dict[str, str],
) -> None:
    assert _delegated(
        hook_input("UserPromptSubmit", prompt="rename this variable"),
        environment=environment,
    )


def test_clearly_generic_prompts_exit_without_full_hook() -> None:
    prompts = (
        "rename this variable",
        "summarize this README",
        "format the response as a table",
    )

    assert all(
        not _delegated(hook_input("UserPromptSubmit", model="gpt-5.6-terra", prompt=prompt))
        for prompt in prompts
    )


def test_clean_generic_sol_is_silent_without_writes_or_heavy_imports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module_names = {
        "super_sol_commands",
        "super_sol_evidence_hook",
        "super_sol_hook",
        "super_sol_loop_policy",
        "super_sol_routes",
        "super_sol_state",
    }
    plugin_data = tmp_path / "plugin-data"
    with monkeypatch.context() as isolated:
        for name in module_names:
            isolated.delitem(sys.modules, name, raising=False)
        isolated.setenv("PLUGIN_DATA", str(plugin_data))
        _ = importlib.reload(prompt_dispatcher)
        calls: list[bytes] = []

        assert (
            prompt_dispatcher.dispatch(
                json.dumps(hook_input("UserPromptSubmit", prompt="rename this variable")).encode(),
                os.environ,
                calls.append,
            )
            is None
        )
        assert calls == []
        assert not (module_names & set(sys.modules))
    assert not plugin_data.exists()
    assert importlib.import_module("super_sol_loop_state") is super_sol_loop_state


def test_generic_sol_prompt_resets_only_an_existing_same_turn_ledger(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plugin_data = tmp_path / "plugin-data"
    payload = hook_input("UserPromptSubmit", prompt="rename this variable")
    unrelated = hook_input("UserPromptSubmit", turn_id="unrelated", prompt="rename this variable")
    monkeypatch.setenv("PLUGIN_DATA", str(plugin_data))
    root = turn_root(cast("dict[str, object]", payload))
    unrelated_root = turn_root(cast("dict[str, object]", unrelated))
    assert root is not None
    assert unrelated_root is not None
    _ = mutate_loop_ledger(root, lambda state: LoopLedger.fresh(1))
    _ = mutate_loop_ledger(unrelated_root, lambda state: LoopLedger.fresh(2))
    calls: list[bytes] = []

    assert (
        prompt_dispatcher.dispatch(json.dumps(payload).encode(), os.environ, calls.append) is None
    )
    assert calls == []
    assert load_loop_ledger(root).last_event_ns > 1
    assert load_loop_ledger(unrelated_root).last_event_ns == 2


@pytest.mark.parametrize(
    "prompt",
    [
        "use sk-abcdefghijklmnopqrst for this request",
        "SUPER SOL OFF\nrename this variable",
        "Fix concurrent refresh race conditions",
    ],
)
def test_guarded_sol_prompts_still_delegate_to_the_full_processor(prompt: str) -> None:
    assert _delegated(hook_input("UserPromptSubmit", prompt=prompt))


@pytest.mark.parametrize(
    "prompt",
    [
        "Fix the implementation and run tests",
        "Update the command help",
        "구현을 수정해줘",
    ],
)
def test_action_prompts_delegate_without_specialist_signals(prompt: str) -> None:
    assert _delegated(hook_input("UserPromptSubmit", prompt=prompt))


def test_generic_sol_without_loop_state_skips_event_modules(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module_names = {
        "super_sol_commands",
        "super_sol_evidence_hook",
        "super_sol_loop_hook",
        "super_sol_loop_policy",
    }
    plugin_data = tmp_path / "plugin-data"
    with monkeypatch.context() as isolated:
        for name in module_names:
            isolated.delitem(sys.modules, name, raising=False)
        isolated.setenv("PLUGIN_DATA", str(plugin_data))
        _ = importlib.reload(super_sol_hook)
        payload = json.dumps(hook_input("UserPromptSubmit", prompt="rename this variable")).encode()

        assert super_sol_hook.process_raw(payload) is None
        assert not (module_names & set(sys.modules))
    assert not (tmp_path / "plugin-data").exists()


def test_non_prompt_malformed_and_oversized_input_delegate_safely() -> None:
    assert _delegated(hook_input("PreToolUse", tool_input={}))
    assert _delegated("not-json")
    assert _delegated("{" + ("x" * 1_048_576))


def test_default_dispatcher_delegates_non_prompt_event_to_full_hook() -> None:
    raw = json.dumps(hook_input("PreToolUse", tool_input={})).encode()

    assert prompt_dispatcher.dispatch(raw, {}) is None


@pytest.mark.parametrize("raw", [b"[]", b"null", b"1"])
def test_full_hook_warns_for_non_object_json(raw: bytes) -> None:
    assert super_sol_hook.process_raw(raw) == {
        "continue": True,
        "systemMessage": "Super SOL: 로컬 상태를 읽지 못해 자동 절차 없이 계속합니다.",
    }


def test_hook_shaped_top_level_array_delegates_and_fails_open() -> None:
    raw = json.dumps([hook_input("UserPromptSubmit", prompt="rename this variable")])

    assert _delegated(raw)
    assert super_sol_hook.process_raw(raw.encode()) == {
        "continue": True,
        "systemMessage": "Super SOL: 로컬 상태를 읽지 못해 자동 절차 없이 계속합니다.",
    }


def test_full_hook_warns_for_unknown_event() -> None:
    unknown = json.dumps(hook_input("UnknownEvent")).encode()

    assert super_sol_hook.process_raw(unknown) == {
        "continue": True,
        "systemMessage": "Super SOL: 알 수 없는 훅 이벤트라 자동 절차 없이 계속합니다.",
    }


@pytest.mark.parametrize(
    "payload",
    [
        hook_input("UserPromptSubmit", prompt="rename this variable"),
        hook_input("UserPromptSubmit", prompt="Fix concurrent refresh race conditions"),
        hook_input("UserPromptSubmit", prompt="SUPER SOL ROUTE unknown\nFix this conversion"),
        hook_input("UserPromptSubmit", prompt="use sk-abcdefghijklmnopqrst now"),
        hook_input("UserPromptSubmit", model="gpt-5.6-terra", prompt="rename this variable"),
        json.dumps([hook_input("UserPromptSubmit", prompt="rename this variable")]),
        "not-json",
        "null",
        "1",
    ],
)
def test_prompt_dispatcher_matches_full_hook_output(
    tmp_path: Path,
    payload: dict[str, JsonValue] | str,
) -> None:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)

    def invoke(script: Path) -> subprocess.CompletedProcess[str]:
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PLUGIN_DATA": str(tmp_path / f"plugin-data-{script.stem}"),
            "PLUGIN_ROOT": str(PLUGIN_ROOT),
            "PYTHONUTF8": "1",
        }
        return subprocess.run(  # noqa: S603
            ["/usr/bin/python3", "-S", str(script)],
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )

    expected = invoke(HOOK_SCRIPT)
    actual = invoke(PROMPT_DISPATCHER)

    assert actual.returncode == expected.returncode == 0
    assert actual.stdout == expected.stdout
    assert actual.stderr == expected.stderr == ""
