from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from typing import TYPE_CHECKING, cast

from .v09_loop_test_support import ROOT

if TYPE_CHECKING:
    from pathlib import Path

MANIFEST = ROOT / "eval" / "v092_loop_sequences.json"
RUNNER = ROOT / "eval" / "v09_loop_replay.py"
REPORT = ROOT / "benchmarks" / "v0.9-loop-replay" / "v092-report.json"


def test_v092_manifest_encodes_silent_warning_transitions() -> None:
    manifest = cast("dict[str, object]", json.loads(MANIFEST.read_text(encoding="utf-8")))
    cases = cast("list[dict[str, object]]", manifest["cases"])

    assert manifest["schema"] == "super-sol-loop-sequences/v2"
    for case_id in ("generic-read-replay", "repeated-wait"):
        case = next(case for case in cases if case["id"] == case_id)
        events = cast("list[dict[str, object]]", case["events"])
        expected = cast("dict[str, object]", events[5]["expected_action"])
        assert expected == {"kind": "pass"}


def test_v092_loop_replay_is_immutable_and_passing(tmp_path: Path) -> None:
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
    network = cast("dict[str, object]", report["network_isolation"])
    assert summary == {"total": 12, "passed": 12, "failed": 0, "unexpected_contexts": 0}
    assert report["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert report["network_calls"] == 0
    assert report["successful_network_calls"] == 0
    assert network["static_audit"] == "passed"
