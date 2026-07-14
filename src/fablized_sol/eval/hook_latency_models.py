"""Shared immutable models for the isolated hook latency gate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

DEFAULT_HOOK_SAMPLES: Final = 300
DEFAULT_FLOOR_SAMPLES: Final = 150
ABSOLUTE_P95_THRESHOLD_MS: Final = 100.0
INCREMENTAL_P95_THRESHOLD_MS: Final = 70.0
_INVALID_SAMPLE_COUNTS: Final = "hook samples must be exactly twice floor samples and both positive"
_NON_OFFICIAL_OPTIONS: Final = "official latency gate requires frozen samples and thresholds"


class HookLatencyError(RuntimeError):
    """The latency gate could not collect or write valid evidence."""


@dataclass(frozen=True, slots=True)
class ProcessResult:
    """The small child-process result surface needed by the gate."""

    returncode: int
    stderr: str


type ProcessRunner = Callable[[tuple[str, ...], str, dict[str, str]], ProcessResult]
type Clock = Callable[[], float]


@dataclass(frozen=True, slots=True)
class GateOptions:
    """Immutable sample-count and threshold inputs for one gate invocation."""

    plugin_root: Path
    hook_samples: int = DEFAULT_HOOK_SAMPLES
    floor_samples: int = DEFAULT_FLOOR_SAMPLES
    absolute_threshold_ms: float = ABSOLUTE_P95_THRESHOLD_MS
    incremental_threshold_ms: float = INCREMENTAL_P95_THRESHOLD_MS

    def validate(self) -> None:
        """Require the approved 2:1 sampling layout and positive limits."""
        if (
            self.hook_samples <= 0
            or self.floor_samples <= 0
            or self.hook_samples != self.floor_samples * 2
        ):
            raise HookLatencyError(_INVALID_SAMPLE_COUNTS)
        if self.absolute_threshold_ms <= 0 or self.incremental_threshold_ms <= 0:
            message = "latency thresholds must be positive"
            raise HookLatencyError(message)

    def validate_official(self) -> None:
        """Reject any release gate configuration that weakens the frozen contract."""
        self.validate()
        observed = (
            self.hook_samples,
            self.floor_samples,
            self.absolute_threshold_ms,
            self.incremental_threshold_ms,
        )
        expected = (
            DEFAULT_HOOK_SAMPLES,
            DEFAULT_FLOOR_SAMPLES,
            ABSOLUTE_P95_THRESHOLD_MS,
            INCREMENTAL_P95_THRESHOLD_MS,
        )
        if observed != expected:
            raise HookLatencyError(_NON_OFFICIAL_OPTIONS)


@dataclass(frozen=True, slots=True)
class LatencySamples:
    """Fresh hook and baseline timings from one isolated measurement run."""

    command: tuple[str, ...]
    payload: str
    hook_samples: tuple[float, ...]
    floor_samples: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class GateRuntime:
    """Injected process and clock dependencies for one latency measurement."""

    run_process: ProcessRunner
    clock: Clock
    inherited_environment: Mapping[str, str] | None


type LatencyCollector = Callable[
    [GateOptions, ProcessRunner, Clock, Mapping[str, str] | None], LatencySamples
]
