import json
import os
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
_OBJECT_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])


@dataclass(frozen=True, slots=True)
class HookResult:
    returncode: int
    stdout: dict[str, JsonValue] | None
    stdout_text: str
    stderr: str


type HookInput = dict[str, JsonValue] | str
type HookRunner = Callable[[HookInput], HookResult]


@pytest.fixture
def plugin_data(tmp_path: Path) -> Path:
    return tmp_path / "plugin-data"


@pytest.fixture
def run_hook(plugin_data: Path) -> HookRunner:
    def invoke(payload: HookInput) -> HookResult:
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PLUGIN_DATA": str(plugin_data),
            "PLUGIN_ROOT": str(PLUGIN_ROOT),
            "PYTHONUTF8": "1",
        }
        completed = subprocess.run(  # noqa: S603
            [sys.executable, str(HOOK_SCRIPT)],
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
        "model": "gpt-5.6-terra",
        "permission_mode": "default",
        **fields,
    }
