"""Isolated, no-billing latency gate for the configured prompt hook."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

from pydantic import JsonValue, TypeAdapter, ValidationError

from fablized_sol.eval.hook_latency_models import (
    ABSOLUTE_P95_THRESHOLD_MS,
    DEFAULT_FLOOR_SAMPLES,
    DEFAULT_HOOK_SAMPLES,
    INCREMENTAL_P95_THRESHOLD_MS,
    Clock,
    GateOptions,
    GateRuntime,
    HookLatencyError,
    LatencySamples,
    ProcessResult,
    ProcessRunner,
)
from fablized_sol.eval.hook_latency_report import run_and_write as _write_report

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = (
    "ABSOLUTE_P95_THRESHOLD_MS",
    "DEFAULT_FLOOR_SAMPLES",
    "DEFAULT_HOOK_SAMPLES",
    "INCREMENTAL_P95_THRESHOLD_MS",
    "GateOptions",
    "HookLatencyError",
    "ProcessResult",
    "collect_latency",
    "main",
    "percentile",
    "run_and_write",
    "select_prompt_command",
)

CHILD_TIMEOUT_SECONDS: Final = 5
_COMMAND_ARGV_LENGTH: Final = 3
_PERCENT_MAX: Final = 100
_MISSING_COMMAND: Final = "hooks.json has no usable UserPromptSubmit command"
_SINGLE_COMMAND: Final = "UserPromptSubmit must declare exactly one command hook"
_EMPTY_COMMAND: Final = "UserPromptSubmit command must be a non-empty string"
_INVALID_QUOTING: Final = "UserPromptSubmit command has invalid shell quoting"
_INVALID_COMMAND: Final = "UserPromptSubmit command must run one plugin hook with Python -S"
_CHILD_START_FAILURE: Final = "could not start latency child process"
_CHILD_TIMEOUT_FAILURE: Final = "latency child process exceeded the fixed 5 second timeout"
_INVALID_HOOK_TIMEOUT: Final = "UserPromptSubmit timeout must match the shipped 5 second timeout"
_INVALID_PERCENTILE: Final = "percentiles require samples and a value from zero through one hundred"
_OBJECT_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])


def _object(value: JsonValue, name: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        message = f"hooks.json {name} must be an object"
        raise HookLatencyError(message)
    return value


def _list(value: JsonValue, name: str) -> list[JsonValue]:
    if not isinstance(value, list):
        message = f"hooks.json {name} must be a list"
        raise HookLatencyError(message)
    return value


def select_prompt_command(plugin_root: Path) -> tuple[str, ...]:
    """Read the sole UserPromptSubmit command from the plugin hook manifest."""
    root = plugin_root.resolve()
    try:
        document = _OBJECT_ADAPTER.validate_json(
            (root / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )
        hooks = _object(document.get("hooks"), "hooks")
        groups = _list(hooks.get("UserPromptSubmit"), "UserPromptSubmit")
        group = _object(groups[0], "UserPromptSubmit[0]")
        handlers = _list(group.get("hooks"), "UserPromptSubmit[0].hooks")
        handler = _object(handlers[0], "UserPromptSubmit[0].hooks[0]")
        command = handler.get("command")
        configured_timeout = handler.get("timeout")
    except (IndexError, OSError, UnicodeDecodeError, ValidationError) as error:
        raise HookLatencyError(_MISSING_COMMAND) from error
    if len(groups) != 1 or len(handlers) != 1 or handler.get("type") != "command":
        raise HookLatencyError(_SINGLE_COMMAND)
    if not isinstance(command, str) or not command:
        raise HookLatencyError(_EMPTY_COMMAND)
    if (
        not isinstance(configured_timeout, int)
        or isinstance(configured_timeout, bool)
        or configured_timeout != CHILD_TIMEOUT_SECONDS
    ):
        raise HookLatencyError(_INVALID_HOOK_TIMEOUT)
    try:
        argv = tuple(shlex.split(command.replace("$PLUGIN_ROOT", str(root))))
    except ValueError as error:
        raise HookLatencyError(_INVALID_QUOTING) from error
    script = root / "hooks" / "prompt_dispatcher.py"
    expected = ("/usr/bin/python3", "-S", str(script))
    try:
        regular_script = (
            not script.is_symlink()
            and script.is_file()
            and stat.S_ISREG(script.stat().st_mode)
            and script.resolve() == script
        )
    except OSError as error:
        raise HookLatencyError(_INVALID_COMMAND) from error
    if len(argv) != _COMMAND_ARGV_LENGTH or argv != expected or not regular_script:
        raise HookLatencyError(_INVALID_COMMAND)
    return argv


def _payload() -> str:
    return json.dumps(
        {
            "cwd": "/latency-gate",
            "hook_event_name": "UserPromptSubmit",
            "model": "gpt-5.6-sol",
            "permission_mode": "default",
            "prompt": "rename this variable",
            "session_id": "super-sol-latency",
            "turn_id": "gate-0",
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _environment(
    plugin_root: Path, plugin_data: Path, inherited: Mapping[str, str]
) -> dict[str, str]:
    return {
        "PATH": inherited.get("PATH", ""),
        "PLUGIN_DATA": str(plugin_data),
        "PLUGIN_ROOT": str(plugin_root),
        "PYTHONUTF8": "1",
    }


def _run_process(
    command: tuple[str, ...], payload: str, environment: dict[str, str]
) -> ProcessResult:
    try:
        completed = subprocess.run(  # noqa: S603
            command,
            input=payload,
            text=True,
            capture_output=True,
            check=False,
            env=environment,
            timeout=CHILD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise HookLatencyError(_CHILD_TIMEOUT_FAILURE) from error
    except OSError as error:
        raise HookLatencyError(_CHILD_START_FAILURE) from error
    return ProcessResult(completed.returncode, completed.stderr)


def _measure(
    command: tuple[str, ...],
    payload: str,
    environment: dict[str, str],
    run_process: ProcessRunner,
    clock: Clock,
) -> float:
    started = clock()
    result = run_process(command, payload, environment)
    elapsed_ms = (clock() - started) * 1000
    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        message = f"latency child process failed: {detail}"
        raise HookLatencyError(message)
    return elapsed_ms


def collect_latency(
    options: GateOptions,
    run_process: ProcessRunner = _run_process,
    clock: Clock = time.perf_counter,
    inherited_environment: Mapping[str, str] | None = None,
) -> LatencySamples:
    """Run fresh hook and floor processes in a 2:1 interleaved schedule."""
    options.validate()
    root = options.plugin_root.resolve()
    command = select_prompt_command(root)
    floor_command = (*command[:2], "-c", "")
    payload = _payload()
    inherited = os.environ if inherited_environment is None else inherited_environment
    with tempfile.TemporaryDirectory(prefix="super-sol-hook-latency-") as temporary:
        environment = _environment(root, Path(temporary) / "plugin-data", inherited)
        hook_times: list[float] = []
        floor_times: list[float] = []
        for _index in range(options.floor_samples):
            hook_times.append(_measure(command, payload, environment, run_process, clock))
            hook_times.append(_measure(command, payload, environment, run_process, clock))
            floor_times.append(_measure(floor_command, "", environment, run_process, clock))
    return LatencySamples(command, payload, tuple(hook_times), tuple(floor_times))


def percentile(samples: Sequence[float], percent: int) -> float:
    """Return an inclusive linear-interpolated percentile for non-empty samples."""
    if not samples or not 0 <= percent <= _PERCENT_MAX:
        raise HookLatencyError(_INVALID_PERCENTILE)
    ordered = sorted(samples)
    rank = (len(ordered) - 1) * percent / _PERCENT_MAX
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


@dataclass(frozen=True, slots=True)
class _Arguments:
    options: GateOptions
    output: Path


def _arguments() -> _Arguments:
    parser = argparse.ArgumentParser(prog="super-sol-hook-latency")
    _ = parser.add_argument("--plugin-root", type=Path, required=True)
    _ = parser.add_argument("--output", type=Path, required=True)
    parsed = parser.parse_args()
    return _Arguments(
        GateOptions(cast("Path", parsed.plugin_root)),
        cast("Path", parsed.output),
    )


def run_and_write(
    options: GateOptions,
    output: Path,
    run_process: ProcessRunner = _run_process,
    clock: Clock = time.perf_counter,
    inherited_environment: Mapping[str, str] | None = None,
) -> bool:
    """Collect, record, and return one gate verdict with injectable test seams."""
    return _write_report(
        options,
        output,
        collect_latency,
        GateRuntime(run_process, clock, inherited_environment),
    )


def main() -> None:
    """Run the isolated hook latency gate and exit from its observed verdict."""
    arguments = _arguments()
    try:
        passed = run_and_write(arguments.options, arguments.output)
    except HookLatencyError as error:
        print(json.dumps({"passed": False, "error": str(error)}, sort_keys=True))  # noqa: T201
        raise SystemExit(2) from error
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
