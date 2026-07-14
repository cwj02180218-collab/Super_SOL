"""Report construction and atomic evidence writing for hook latency gates."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final, Literal, cast

from pydantic import BaseModel, ConfigDict, ValidationError

from fablized_sol.eval.hook_latency_models import (
    ABSOLUTE_P95_THRESHOLD_MS,
    INCREMENTAL_P95_THRESHOLD_MS,
    GateOptions,
    GateRuntime,
    HookLatencyError,
    LatencyCollector,
    LatencySamples,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

_SCHEMA: Final = "super-sol-hook-latency.v1"
_DIGEST_FAILURE: Final = "could not digest plugin tree"
_WRITE_FAILURE: Final = "could not atomically write fresh latency report"
_NON_OFFICIAL_REPORT: Final = "official latency report has a non-default contract"
_PORTABLE_COMMAND: Final = (
    "/usr/bin/python3",
    "-S",
    "$PLUGIN_ROOT/hooks/prompt_dispatcher.py",
)
_PORTABLE_COMMAND_SHA256: Final = hashlib.sha256("\0".join(_PORTABLE_COMMAND).encode()).hexdigest()


class _OfficialCounts(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", strict=True)

    hook: Literal[300]
    floor: Literal[150]


class _OfficialThresholds(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", strict=True)

    absolute_hook_p95_lt: float
    incremental_p95_lt: float


class _OfficialCommand(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", strict=True)

    argv: list[str]
    sha256: str


class _OfficialFields(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore", strict=True)

    command: _OfficialCommand
    sample_counts: _OfficialCounts
    thresholds_ms: _OfficialThresholds


def _summary(samples: tuple[float, ...]) -> dict[str, float]:
    ordered = sorted(samples)

    def percentile(percent: int) -> float:
        rank = (len(ordered) - 1) * percent / 100
        lower = int(rank)
        upper = min(lower + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)

    return {
        "p50": percentile(50),
        "p95": percentile(95),
        "p99": percentile(99),
        "min": min(samples),
        "max": max(samples),
    }


def paired_incremental_samples(samples: LatencySamples) -> tuple[float, ...]:
    """Pair both hooks in each hook-hook-floor triplet with that local floor."""
    if len(samples.hook_samples) != len(samples.floor_samples) * 2:
        message = "latency samples do not form hook-hook-floor triplets"
        raise HookLatencyError(message)
    differences: list[float] = []
    for index, floor_ms in enumerate(samples.floor_samples):
        differences.extend(
            (
                samples.hook_samples[index * 2] - floor_ms,
                samples.hook_samples[index * 2 + 1] - floor_ms,
            )
        )
    return tuple(differences)


def _digest_path(root: Path) -> str:
    digest = hashlib.sha256()
    try:
        files = sorted(path for path in root.rglob("*") if path.is_file())
        for path in files:
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    except OSError as error:
        raise HookLatencyError(_DIGEST_FAILURE) from error
    return digest.hexdigest()


def _loadavg() -> list[float] | None:
    try:
        return list(os.getloadavg())
    except (AttributeError, OSError):
        return None


def validate_official_report(document: Mapping[str, object]) -> None:
    """Reject report fields that do not match the frozen release gate."""
    try:
        official = _OfficialFields.model_validate(document)
    except ValidationError as error:
        raise HookLatencyError(_NON_OFFICIAL_REPORT) from error
    if (
        tuple(official.command.argv) != _PORTABLE_COMMAND
        or official.command.sha256 != _PORTABLE_COMMAND_SHA256
        or official.thresholds_ms.absolute_hook_p95_lt != ABSOLUTE_P95_THRESHOLD_MS
        or official.thresholds_ms.incremental_p95_lt != INCREMENTAL_P95_THRESHOLD_MS
    ):
        raise HookLatencyError(_NON_OFFICIAL_REPORT)


def _portable_command(command: tuple[str, ...]) -> tuple[str, ...]:
    script = Path(command[-1]) if command else Path()
    if (
        len(command) != len(_PORTABLE_COMMAND)
        or command[:2] != _PORTABLE_COMMAND[:2]
        or script.name != "prompt_dispatcher.py"
        or script.parent.name != "hooks"
    ):
        raise HookLatencyError(_NON_OFFICIAL_REPORT)
    return _PORTABLE_COMMAND


def _report(
    options: GateOptions,
    samples: LatencySamples,
    loadavg_before: list[float] | None,
    loadavg_after: list[float] | None,
) -> dict[str, object]:
    hook_ms = _summary(samples.hook_samples)
    floor_ms = _summary(samples.floor_samples)
    incremental_summary = _summary(paired_incremental_samples(samples))
    incremental_ms = {key: incremental_summary[key] for key in ("p50", "p95", "p99")}
    passed = (
        hook_ms["p95"] < options.absolute_threshold_ms
        and incremental_ms["p95"] < options.incremental_threshold_ms
    )
    command = _portable_command(samples.command)
    report: dict[str, object] = {
        "schema": _SCHEMA,
        "command": {
            "argv": list(command),
            "sha256": _PORTABLE_COMMAND_SHA256,
        },
        "plugin": {"sha256": _digest_path(options.plugin_root.resolve())},
        "sample_counts": {"hook": len(samples.hook_samples), "floor": len(samples.floor_samples)},
        "hook_ms": hook_ms,
        "floor_ms": floor_ms,
        "incremental_ms": incremental_ms,
        "host": {
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "loadavg_before": loadavg_before,
            "loadavg_after": loadavg_after,
        },
        "thresholds_ms": {
            "absolute_hook_p95_lt": ABSOLUTE_P95_THRESHOLD_MS,
            "incremental_p95_lt": INCREMENTAL_P95_THRESHOLD_MS,
        },
        "passed": passed,
    }
    validate_official_report(report)
    return report


def _ensure_fresh_output(output: Path) -> None:
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise HookLatencyError(_WRITE_FAILURE) from error
    if output.exists() or output.is_symlink():
        raise HookLatencyError(_WRITE_FAILURE)


def _write_atomic(output: Path, report: dict[str, object]) -> None:
    descriptor = -1
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
        )
        temporary = output.parent / Path(name).name
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = -1
            json.dump(report, stream, indent=2, sort_keys=True)
            _ = stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
        temporary.unlink()
    except (OSError, TypeError, ValueError) as error:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise HookLatencyError(_WRITE_FAILURE) from error


def run_and_write(
    options: GateOptions,
    output: Path,
    collect_latency: LatencyCollector,
    runtime: GateRuntime,
) -> bool:
    """Collect one official gate report and atomically publish its verdict."""
    options.validate_official()
    _ensure_fresh_output(output)
    before = _loadavg()
    samples = collect_latency(
        options, runtime.run_process, runtime.clock, runtime.inherited_environment
    )
    report = _report(options, samples, before, _loadavg())
    _write_atomic(output, report)
    return cast("bool", report["passed"])
