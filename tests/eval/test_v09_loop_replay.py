from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from typing import TYPE_CHECKING, cast

import pytest

from .v09_loop_test_support import ROOT, replay_module

if TYPE_CHECKING:
    from pathlib import Path

MANIFEST = ROOT / "eval" / "v09_loop_sequences.json"
RUNNER = ROOT / "eval" / "v09_loop_replay.py"
REPORT = ROOT / "benchmarks" / "v0.9-loop-replay" / "report.json"
PLUGIN = ROOT / "plugins" / "super-sol"
CASE_IDS = (
    "passed-verifier-replay",
    "unchanged-failing-verifier-replay",
    "healthy-edit-verify-edit-verify",
    "generic-read-replay",
    "nested-spawn",
    "concurrent-child-exhaustion",
    "total-child-exhaustion",
    "repeated-wait",
    "three-no-progress-auto-compactions",
    "healthy-progress-separated-compactions",
    "terminal-internal-continuation",
    "non-sol-pass-through",
)
CREDENTIAL_KEYS = sorted(
    {
        "OPENAI_API_KEY",
        "CODEX_API_KEY",
        "SUPER_SOL_FORCED_ROUTE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    }
)


def _manifest() -> dict[str, object]:
    return cast("dict[str, object]", json.loads(MANIFEST.read_text(encoding="utf-8")))


def _cases(manifest: dict[str, object]) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", manifest["cases"])


def _case(manifest: dict[str, object], case_id: str) -> dict[str, object]:
    return next(case for case in _cases(manifest) if case["id"] == case_id)


def test_loop_replay_manifest_is_sealed() -> None:
    manifest = _manifest()
    cases = _cases(manifest)

    assert manifest["schema"] == "super-sol-loop-sequences/v1"
    assert tuple(case["id"] for case in cases) == CASE_IDS
    setup = _case(manifest, "healthy-progress-separated-compactions")["setup"]
    assert setup == {"kind": "corrupt_loop_state", "before_event": 0}
    assert "Kakao" not in MANIFEST.read_text(encoding="utf-8")


def test_all_twelve_ids_with_empty_events_fail_manifest_validation() -> None:
    manifest = _manifest()
    for case in _cases(manifest):
        case["events"] = []

    with pytest.raises(ValueError, match="manifest_contract"):
        _ = replay_module().build_report(manifest, PLUGIN)


def test_short_sequence_fails_manifest_validation() -> None:
    manifest = _manifest()
    events = cast("list[object]", _case(manifest, "generic-read-replay")["events"])
    _ = events.pop()

    with pytest.raises(ValueError, match="manifest_contract"):
        _ = replay_module().build_report(manifest, PLUGIN)


def test_altered_expected_action_fails_manifest_validation() -> None:
    manifest = _manifest()
    events = cast("list[dict[str, object]]", _case(manifest, "nested-spawn")["events"])
    events[0]["expected_action"] = {"kind": "pass"}

    with pytest.raises(ValueError, match="manifest_contract"):
        _ = replay_module().build_report(manifest, PLUGIN)


def test_altered_required_hook_event_fails_manifest_validation() -> None:
    manifest = _manifest()
    events = cast("list[dict[str, object]]", _case(manifest, "total-child-exhaustion")["events"])
    payload = cast("dict[str, object]", events[2]["payload"])
    payload["hook_event_name"] = "SubagentStart"

    with pytest.raises(ValueError, match="manifest_contract"):
        _ = replay_module().build_report(manifest, PLUGIN)


def test_loop_replay_report_is_immutable_and_passing(tmp_path: Path) -> None:
    generated = tmp_path / "report.json"
    completed = subprocess.run(  # noqa: S603
        (sys.executable, str(RUNNER), "--manifest", str(MANIFEST), "--output", str(generated)),
        capture_output=True,
        check=False,
        text=True,
        timeout=20,
    )

    assert completed.returncode == 0, completed.stderr
    assert generated.read_bytes() == REPORT.read_bytes()
    report = cast("dict[str, object]", json.loads(generated.read_text(encoding="utf-8")))
    summary = cast("dict[str, object]", report["summary"])
    cases = cast("list[dict[str, object]]", report["cases"])
    network = cast("dict[str, object]", report["network_isolation"])
    assert report["schema"] == "super-sol-loop-replay/v1"
    assert summary == {"total": 12, "passed": 12, "failed": 0, "unexpected_contexts": 0}
    assert report["network_calls"] == 0
    assert report["successful_network_calls"] == 0
    assert network["calls_counted"] is False
    assert network["launcher_env_keys"] == ["PATH", "PLUGIN_DATA", "PLUGIN_ROOT", "PYTHONUTF8"]
    assert network["credential_keys_absent"] == CREDENTIAL_KEYS
    assert "child_env" not in network
    assert network["kernel_network_deny"] == {
        "required": True,
        "enforced": True,
        "benign_child": "passed",
        "connect": "denied",
        "bind": "denied",
    }
    assert network["static_audit"] == "passed"
    assert len(cast("str", network["command_sha256"])) == 64
    assert report["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert len(cast("str", report["plugin_tree_sha256"])) == 64
    assert all(case["passed"] is True for case in cases)
    recovery = next(
        case for case in cases if case["id"] == "healthy-progress-separated-compactions"
    )
    assert recovery["setup"] == {"kind": "corrupt_loop_state", "evidenced": True}


def test_task6_python_files_stay_within_ncnb_limit() -> None:
    files = sorted({*ROOT.glob("eval/v09_loop_*.py"), *ROOT.glob("tests/eval/*v09_loop*.py")})
    counts = {
        path.relative_to(ROOT).as_posix(): sum(
            bool(line.strip()) and not line.lstrip().startswith("#")
            for line in path.read_text(encoding="utf-8").splitlines()
        )
        for path in files
    }

    assert files
    assert all(count <= 250 for count in counts.values()), counts
