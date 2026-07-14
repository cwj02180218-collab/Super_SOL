import copy
import hashlib
import json
import os
from pathlib import Path
from typing import TextIO

import pytest
from pydantic import JsonValue, TypeAdapter

from fablized_sol.eval import hook_latency_report
from fablized_sol.eval.hook_latency_models import (
    GateOptions,
    GateRuntime,
    HookLatencyError,
    LatencySamples,
    ProcessResult,
)

from .hook_latency_test_support import plugin_root

_OBJECT_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])


def _runtime() -> GateRuntime:
    def unused_run(
        _command: tuple[str, ...], _payload: str, _environment: dict[str, str]
    ) -> ProcessResult:
        raise AssertionError

    return GateRuntime(unused_run, lambda: 0.0, {})


def _samples(root: Path, hook_ms: float = 89.0, floor_ms: float = 20.0) -> LatencySamples:
    return LatencySamples(
        ("/usr/bin/python3", "-S", str(root / "hooks" / "prompt_dispatcher.py")),
        "{}",
        (hook_ms,) * 300,
        (floor_ms,) * 150,
    )


def _write_samples(root: Path, output: Path, samples: LatencySamples) -> bool:
    def collect(
        _options: GateOptions,
        _run_process: object,
        _clock: object,
        _environment: object,
    ) -> LatencySamples:
        return samples

    return hook_latency_report.run_and_write(GateOptions(root), output, collect, _runtime())


def test_incremental_p95_uses_triplet_local_paired_differences(tmp_path: Path) -> None:
    root = plugin_root(tmp_path)
    floors = (10.0,) * 141 + (20.0,) * 9
    hooks = tuple(
        value
        for index, floor in enumerate(floors)
        for value in ((89.0, 89.0) if index < 10 else (floor, floor))
    )
    output = tmp_path / "latency.json"

    passed = _write_samples(
        root,
        output,
        LatencySamples(
            ("/usr/bin/python3", "-S", str(root / "hooks" / "prompt_dispatcher.py")),
            "{}",
            hooks,
            floors,
        ),
    )

    report = _OBJECT_ADAPTER.validate_json(output.read_text(encoding="utf-8"))
    incremental = report["incremental_ms"]
    assert isinstance(incremental, dict)
    assert passed is False
    assert incremental["p95"] == 79.0


def test_report_records_the_frozen_release_evidence_contract(tmp_path: Path) -> None:
    root = plugin_root(tmp_path)
    output = tmp_path / "latency.json"

    assert _write_samples(root, output, _samples(root)) is True

    report = _OBJECT_ADAPTER.validate_json(output.read_text(encoding="utf-8"))
    command = report["command"]
    plugin = report["plugin"]
    host = report["host"]
    hook_ms = report["hook_ms"]
    floor_ms = report["floor_ms"]
    incremental_ms = report["incremental_ms"]
    assert isinstance(command, dict)
    assert isinstance(plugin, dict)
    assert isinstance(host, dict)
    assert isinstance(hook_ms, dict)
    assert isinstance(floor_ms, dict)
    assert isinstance(incremental_ms, dict)
    assert report["schema"] == "super-sol-hook-latency.v1"
    assert report["sample_counts"] == {"hook": 300, "floor": 150}
    assert command["argv"] == [
        "/usr/bin/python3",
        "-S",
        "$PLUGIN_ROOT/hooks/prompt_dispatcher.py",
    ]
    assert (
        command["sha256"]
        == hashlib.sha256(
            b"/usr/bin/python3\0-S\0$PLUGIN_ROOT/hooks/prompt_dispatcher.py"
        ).hexdigest()
    )
    assert str(tmp_path) not in output.read_text(encoding="utf-8")
    assert len(str(plugin["sha256"])) == 64
    assert set(hook_ms) == {"p50", "p95", "p99", "min", "max"}
    assert set(floor_ms) == {"p50", "p95", "p99", "min", "max"}
    assert set(incremental_ms) == {"p50", "p95", "p99"}
    assert set(host) == {"platform", "cpu_count", "loadavg_before", "loadavg_after"}
    assert report["thresholds_ms"] == {
        "absolute_hook_p95_lt": 100.0,
        "incremental_p95_lt": 70.0,
    }
    assert report["passed"] is True


def test_nondefault_gate_options_are_rejected_before_collection(tmp_path: Path) -> None:
    root = plugin_root(tmp_path)
    output = tmp_path / "latency.json"
    collected = False

    def collect(
        _options: GateOptions,
        _run_process: object,
        _clock: object,
        _environment: object,
    ) -> LatencySamples:
        nonlocal collected
        collected = True
        return _samples(root)

    with pytest.raises(HookLatencyError, match="official"):
        _ = hook_latency_report.run_and_write(GateOptions(root, 2, 1), output, collect, _runtime())

    assert collected is False
    assert not output.exists()


def test_existing_output_is_never_overwritten_or_collected(tmp_path: Path) -> None:
    root = plugin_root(tmp_path)
    output = tmp_path / "latency.json"
    _ = output.write_text("sentinel", encoding="utf-8")
    collected = False

    def collect(
        _options: GateOptions,
        _run_process: object,
        _clock: object,
        _environment: object,
    ) -> LatencySamples:
        nonlocal collected
        collected = True
        return _samples(root)

    with pytest.raises(HookLatencyError):
        _ = hook_latency_report.run_and_write(GateOptions(root), output, collect, _runtime())

    assert collected is False
    assert output.read_text(encoding="utf-8") == "sentinel"


def test_interrupted_write_leaves_no_final_or_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = plugin_root(tmp_path)
    output_dir = tmp_path / "evidence"
    output = output_dir / "latency.json"

    def interrupted_dump(_value: object, stream: TextIO, **_kwargs: object) -> None:
        _ = stream.write("{partial")
        message = "interrupted write"
        raise OSError(message)

    monkeypatch.setattr(json, "dump", interrupted_dump)

    with pytest.raises(HookLatencyError):
        _ = _write_samples(root, output, _samples(root))

    assert not output.exists()
    assert not tuple(output_dir.iterdir())


def test_report_is_fsynced_and_published_without_temp_residue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = plugin_root(tmp_path)
    output_dir = tmp_path / "evidence"
    output = output_dir / "latency.json"
    synced: list[int] = []

    monkeypatch.setattr(os, "fsync", synced.append)

    assert _write_samples(root, output, _samples(root)) is True
    assert output.is_file()
    assert len(synced) >= 1
    assert tuple(output_dir.iterdir()) == (output,)


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("sample_counts", "hook", 2),
        ("sample_counts", "floor", 1),
        ("thresholds_ms", "absolute_hook_p95_lt", 101.0),
        ("thresholds_ms", "incremental_p95_lt", 71.0),
    ],
)
def test_official_report_audit_rejects_nondefault_fields(
    tmp_path: Path, section: str, field: str, value: float
) -> None:
    root = plugin_root(tmp_path)
    output = tmp_path / "latency.json"
    assert _write_samples(root, output, _samples(root)) is True
    report = _OBJECT_ADAPTER.validate_json(output.read_text(encoding="utf-8"))
    tampered = copy.deepcopy(report)
    fields = tampered[section]
    assert isinstance(fields, dict)
    fields[field] = value

    with pytest.raises(HookLatencyError, match="official"):
        hook_latency_report.validate_official_report(tampered)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("argv", ["/usr/bin/python3", "-S", "/private/tmp/prompt_dispatcher.py"]),
        ("sha256", "0" * 64),
    ],
)
def test_official_report_audit_rejects_nonportable_command_evidence(
    tmp_path: Path, field: str, value: JsonValue
) -> None:
    root = plugin_root(tmp_path)
    output = tmp_path / "latency.json"
    assert _write_samples(root, output, _samples(root)) is True
    report = _OBJECT_ADAPTER.validate_json(output.read_text(encoding="utf-8"))
    command = report["command"]
    assert isinstance(command, dict)
    command[field] = value

    with pytest.raises(HookLatencyError, match="official"):
        hook_latency_report.validate_official_report(report)
