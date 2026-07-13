import json
import os
import shlex
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import JsonValue, TypeAdapter

REPO_ROOT = Path(__file__).parents[2]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "super-sol"
HOOK_SCRIPT = PLUGIN_ROOT / "hooks" / "super_sol_hook.py"
PROMPT_DISPATCHER = PLUGIN_ROOT / "hooks" / "prompt_dispatcher.py"
HOOK_CONFIG = PLUGIN_ROOT / "hooks" / "hooks.json"
sys.path.insert(0, str(PLUGIN_ROOT / "hooks"))
_OBJECT_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])


def configured_prompt_argv() -> list[str]:
    """Return the installed UserPromptSubmit command as an argument vector."""
    payload = _OBJECT_ADAPTER.validate_json(HOOK_CONFIG.read_text(encoding="utf-8"))
    hooks = payload["hooks"]
    assert isinstance(hooks, dict)
    prompt_submit = hooks["UserPromptSubmit"]
    assert isinstance(prompt_submit, list)
    group = prompt_submit[0]
    assert isinstance(group, dict)
    handlers = group["hooks"]
    assert isinstance(handlers, list)
    handler = handlers[0]
    assert isinstance(handler, dict)
    command = handler["command"]
    assert isinstance(command, str)
    return shlex.split(command.replace("$PLUGIN_ROOT", str(PLUGIN_ROOT)))


@dataclass(frozen=True, slots=True)
class HookResult:
    returncode: int
    stdout: dict[str, JsonValue] | None
    stdout_text: str
    stderr: str


type HookInput = dict[str, JsonValue] | str
type HookRunner = Callable[[HookInput], HookResult]
type HookEnvironmentRunner = Callable[[HookInput, dict[str, str]], HookResult]


@pytest.fixture
def plugin_data(tmp_path: Path) -> Path:
    return tmp_path / "plugin-data"


@pytest.fixture
def run_hook(plugin_data: Path) -> HookRunner:
    argv = configured_prompt_argv()

    def invoke(payload: HookInput) -> HookResult:
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PLUGIN_DATA": str(plugin_data),
            "PLUGIN_ROOT": str(PLUGIN_ROOT),
            "PYTHONUTF8": "1",
        }
        completed = subprocess.run(  # noqa: S603
            argv,
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        output = completed.stdout.strip()
        parsed = _OBJECT_ADAPTER.validate_json(output) if output else None
        return HookResult(completed.returncode, parsed, output, completed.stderr)

    return invoke


@pytest.fixture
def run_hook_with_env(plugin_data: Path) -> HookEnvironmentRunner:
    argv = configured_prompt_argv()

    def invoke(payload: HookInput, overrides: dict[str, str]) -> HookResult:
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PLUGIN_DATA": str(plugin_data),
            "PLUGIN_ROOT": str(PLUGIN_ROOT),
            "PYTHONUTF8": "1",
            **overrides,
        }
        completed = subprocess.run(  # noqa: S603
            argv,
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        output = completed.stdout.strip()
        parsed = _OBJECT_ADAPTER.validate_json(output) if output else None
        return HookResult(completed.returncode, parsed, output, completed.stderr)

    return invoke


def hook_input(event: str, **fields: JsonValue) -> dict[str, JsonValue]:
    return {
        "session_id": "session-one",
        "turn_id": "turn-one",
        "cwd": "/workspace",
        "hook_event_name": event,
        "model": "gpt-5.6-sol",
        "permission_mode": "default",
        **fields,
    }
