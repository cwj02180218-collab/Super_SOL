import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pytest
from pydantic import JsonValue

sys.path.insert(0, str(Path(__file__).parent))
from fake_codex_responses import (  # pyright: ignore[reportImplicitRelativeImport]
    AdapterRecord,
    CodexAppServer,
    FakeCodexResponses,
    RecordedResponseRequest,
    is_compaction_request,
    read_adapter_records,
)

_CODEX = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
_REPO_ROOT = Path(__file__).parents[2]
_PLUGIN_SOURCE = _REPO_ROOT / "plugins" / "super-sol"
_TIMEOUT_SECONDS = 10
_OBSERVATION_SECONDS = 0.4
_TERMINAL_OUTPUT: dict[str, JsonValue] = {
    "continue": False,
    "stopReason": "loop_fuse_no_progress_compaction",
}
type CompactPhase = Literal["PreCompact", "PostCompact"]


@dataclass(frozen=True, slots=True)
class _RuntimeResult:
    observation_seconds: float
    records: tuple[AdapterRecord, ...]
    hooks: dict[str, JsonValue]
    requests: tuple[RecordedResponseRequest, ...]
    rejected_targets: tuple[str, ...]
    setup_requests: tuple[RecordedResponseRequest, ...]


def _environment(home: Path, phase: CompactPhase, events: Path) -> dict[str, str]:
    return {
        "CODEX_HOME": str(home),
        "HOME": str(home),
        "LOCAL_FIXTURE_KEY": "local-fixture",
        "NO_PROXY": "*",
        "PATH": os.environ["PATH"],
        "SUPER_SOL_PROBE_EVENTS": str(events),
        "SUPER_SOL_PROBE_PHASE": phase,
    }


def _write_adapter(plugin: Path, phase: CompactPhase, events: Path) -> None:
    adapter = plugin / "hooks" / "probe_compact_adapter.py"
    _ = adapter.write_text(
        """import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

from super_sol_loop_hook import process_compact
from super_sol_loop_state import LoopLedger, mutate_loop_ledger
from super_sol_state import turn_root

payload = json.load(sys.stdin)
event = payload.get(\"hook_event_name\")
events = Path("""
        + repr(str(events))
        + ")\nphase = "
        + repr(phase)
        + """
if event == phase:
    root = turn_root(payload)
    if root is not None:
        _ = mutate_loop_ledger(
            root,
            lambda _state: replace(
                LoopLedger.fresh(time.time_ns()),
                terminal_reason=\"loop_fuse_no_progress_compaction\",
            ),
        )
output = process_compact(payload)
with events.open(\"a\", encoding=\"utf-8\") as stream:
    json.dump({\"event\": event, \"output\": output}, stream, separators=(\",\", \":\"))
    stream.write(\"\\n\")
if output is not None:
    json.dump(output, sys.stdout, separators=(\",\", \":\"))
""",
        encoding="utf-8",
    )
    command = "/usr/bin/python3 -S " + '"$PLUGIN_ROOT/hooks/probe_compact_adapter.py"'
    hooks = {
        "hooks": {
            event: [
                {
                    "hooks": [
                        {
                            "command": command,
                            "timeout": 5,
                            "type": "command",
                        }
                    ]
                }
            ]
            for event in ("PreCompact", "PostCompact")
        }
    }
    _ = (plugin / "hooks" / "hooks.json").write_text(json.dumps(hooks), encoding="utf-8")


def _install_plugin(home: Path, environment: dict[str, str], source: Path) -> None:
    host = "127.0.0.1"
    _ = (home / "config.toml").write_text(
        f"""model = "gpt-5.6-sol"
model_provider = "local-fixture"
model_auto_compact_token_limit = 1

[features]
plugin_hooks = true

[model_providers.local-fixture]
name = "Local fixture"
base_url = "http://{host}:1/v1"
env_key = "LOCAL_FIXTURE_KEY"
wire_api = "responses"
""",
        encoding="utf-8",
    )
    commands = (
        ("plugin", "marketplace", "add", str(source), "--json"),
        ("plugin", "add", "super-sol@super-sol", "--json"),
    )
    for arguments in commands:
        completed = subprocess.run(  # noqa: S603
            (_CODEX, *arguments),
            capture_output=True,
            check=False,
            env=environment,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
        assert completed.returncode == 0, completed.stderr


def _run_case(tmp_path: Path, phase: CompactPhase, provider: FakeCodexResponses) -> _RuntimeResult:
    home = tmp_path / phase / "home"
    home.mkdir(parents=True)
    events = tmp_path / phase / "events.txt"
    environment = _environment(home, phase, events)
    source = tmp_path / phase / "marketplace"
    plugin = source / "plugins" / "super-sol"
    _ = shutil.copytree(_PLUGIN_SOURCE, plugin)
    _ = (source / ".agents" / "plugins").mkdir(parents=True)
    _ = (source / ".agents" / "plugins" / "marketplace.json").write_text(
        json.dumps(
            {
                "interface": {"displayName": "Probe"},
                "name": "super-sol",
                "plugins": [
                    {
                        "category": "Productivity",
                        "name": "super-sol",
                        "policy": {"authentication": "ON_INSTALL", "installation": "AVAILABLE"},
                        "source": {"path": "./plugins/super-sol", "source": "local"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _write_adapter(plugin, phase, events)
    _install_plugin(home, environment, source)
    config = home / "config.toml"
    _ = config.write_text(
        config.read_text(encoding="utf-8").replace(
            "127.0.0.1:1", provider.origin.removeprefix("http://")
        ),
        encoding="utf-8",
    )
    with CodexAppServer(_CODEX, environment) as server:
        _ = server.call(
            "initialize",
            {
                "capabilities": {"experimentalApi": True},
                "clientInfo": {"name": "super-sol-runtime-test", "version": "1"},
            },
        )
        hooks = server.call("hooks/list", {"cwds": [str(tmp_path)]})
        started = server.call(
            "thread/start",
            {
                "cwd": str(tmp_path),
                "config": {"bypass_hook_trust": True},
                "ephemeral": True,
                "model": "gpt-5.6-sol",
                "modelProvider": "local-fixture",
            },
        )
        thread = started["thread"]
        assert isinstance(thread, dict)
        thread_id = thread["id"]
        assert isinstance(thread_id, str)
        _ = server.call(
            "turn/start",
            {"input": [{"text": "prepare compaction", "type": "text"}], "threadId": thread_id},
        )
        server.wait_for_thread_settled(thread_id)
        setup_requests = tuple(provider.requests)
        provider.requests.clear()
        _ = server.call("thread/compact/start", {"threadId": thread_id})
        _ = server.wait_for("hook/completed")
        if phase == "PostCompact":
            _ = server.wait_for("hook/completed")
        expected_requests = tuple(provider.requests)
        expected_rejections = tuple(provider.rejected_targets)
        server.wait_for_thread_settled(thread_id)
        assert tuple(provider.requests) == expected_requests
        assert tuple(provider.rejected_targets) == expected_rejections
        observation_started = time.monotonic()
        time.sleep(_OBSERVATION_SECONDS)
        observation_seconds = time.monotonic() - observation_started
        assert tuple(provider.requests) == expected_requests
        assert tuple(provider.rejected_targets) == expected_rejections
    observed = read_adapter_records(events)
    return _RuntimeResult(
        observation_seconds=observation_seconds,
        records=observed,
        hooks=hooks,
        requests=tuple(provider.requests),
        rejected_targets=tuple(provider.rejected_targets),
        setup_requests=setup_requests,
    )


def _assert_loopback_compaction(request: RecordedResponseRequest) -> None:
    assert request.target == "/v1/responses"
    assert request.body["model"] == "gpt-5.6-sol"
    assert is_compaction_request(request)


@pytest.mark.parametrize("phase", ["PreCompact", "PostCompact"])
def test_terminal_compact_hook_stops_before_normal_sampling(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, phase: CompactPhase
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    with FakeCodexResponses() as provider:
        result = _run_case(tmp_path, phase, provider)

    assert result.rejected_targets == ()
    assert result.observation_seconds >= _OBSERVATION_SECONDS
    assert all(not is_compaction_request(request) for request in result.setup_requests)
    if phase == "PreCompact":
        assert result.requests == ()
        assert result.records == (AdapterRecord("PreCompact", _TERMINAL_OUTPUT),)
    else:
        assert len(result.requests) == 1
        _assert_loopback_compaction(result.requests[0])
        assert result.records == (
            AdapterRecord("PreCompact", None),
            AdapterRecord("PostCompact", _TERMINAL_OUTPUT),
        )
