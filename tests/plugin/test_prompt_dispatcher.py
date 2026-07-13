import json
import os
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol, cast

import prompt_dispatcher
import pytest
import super_sol_routes
from pydantic import JsonValue

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

    assert all(not _delegated(hook_input("UserPromptSubmit", prompt=prompt)) for prompt in prompts)


def test_non_prompt_malformed_and_oversized_input_delegate_safely() -> None:
    assert _delegated(hook_input("PreToolUse", tool_input={}))
    assert _delegated("not-json")
    assert _delegated("{" + ("x" * 1_048_576))


@pytest.mark.parametrize(
    "payload",
    [
        hook_input("UserPromptSubmit", prompt="rename this variable"),
        hook_input("UserPromptSubmit", prompt="Fix concurrent refresh race conditions"),
        hook_input("UserPromptSubmit", prompt="SUPER SOL ROUTE unknown\nFix this conversion"),
        hook_input("UserPromptSubmit", prompt="use sk-abcdefghijklmnopqrst now"),
        "not-json",
    ],
)
def test_prompt_dispatcher_matches_full_hook_output(
    tmp_path: Path,
    payload: dict[str, JsonValue] | str,
) -> None:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PLUGIN_DATA": str(tmp_path / "plugin-data"),
        "PLUGIN_ROOT": str(PLUGIN_ROOT),
        "PYTHONUTF8": "1",
    }

    def invoke(script: Path) -> subprocess.CompletedProcess[str]:
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
