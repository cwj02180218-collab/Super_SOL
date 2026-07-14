"""No-billing compatibility checks for Codex lifecycle hooks."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import JsonValue, TypeAdapter, ValidationError

if TYPE_CHECKING:
    from collections.abc import Iterator

REQUIRED_EVENTS = frozenset(
    {"preToolUse", "postToolUse", "preCompact", "postCompact", "subagentStart", "subagentStop"}
)
_SCHEMA_NAME = "codex_app_server_protocol.v2.schemas.json"
_SUBPROCESS_TIMEOUT_SECONDS = 10
_SCHEMA_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])
_MISSING_BUNDLE = "Codex schema bundle is missing the v2 protocol schema"
_MALFORMED_HOOK_EVENT = "Codex schema does not declare HookEventName"
_MALFORMED_ENUM = "Codex HookEventName enum is malformed"
_INSPECTION_FAILED = "Codex local inspection failed"
_MISSING_EXECUTABLE = "Codex executable is missing or not executable"
_SCHEMA_GENERATION_FAILED = "Codex schema generation failed"


@dataclass(frozen=True, slots=True)
class HookCompatibility:
    """Observed local Codex hook-schema compatibility."""

    codex_version: str
    observed_events: frozenset[str]
    missing_events: frozenset[str]
    compatible: bool


class HookCompatibilityError(RuntimeError):
    """Local Codex inspection could not produce a valid schema bundle."""


def _schema_file(bundle: Path) -> Path:
    if bundle.is_file():
        return bundle
    candidate = bundle / _SCHEMA_NAME
    if candidate.is_file():
        return candidate
    raise HookCompatibilityError(_MISSING_BUNDLE)


def _definition_maps(value: JsonValue) -> Iterator[dict[str, JsonValue]]:
    if isinstance(value, list):
        for item in value:
            yield from _definition_maps(item)
        return
    if not isinstance(value, dict):
        return
    for key in ("definitions", "$defs"):
        definitions = value.get(key)
        if isinstance(definitions, dict):
            yield definitions
    for child in value.values():
        yield from _definition_maps(child)


def _hook_event_enum(definitions: dict[str, JsonValue]) -> frozenset[str] | None:
    hook_event = definitions.get("HookEventName")
    if hook_event is None:
        return None
    if not isinstance(hook_event, dict):
        raise HookCompatibilityError(_MALFORMED_HOOK_EVENT)
    values = hook_event.get("enum")
    if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
        raise HookCompatibilityError(_MALFORMED_ENUM)
    return frozenset(cast("list[str]", values))


def read_hook_events(bundle: Path) -> frozenset[str]:
    """Read the declared lifecycle event names from one generated schema bundle."""
    try:
        document = _SCHEMA_ADAPTER.validate_json(_schema_file(bundle).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValidationError) as error:
        raise HookCompatibilityError(_MALFORMED_HOOK_EVENT) from error
    enums: list[frozenset[str]] = []
    for definitions in _definition_maps(document):
        enum = _hook_event_enum(definitions)
        if enum is not None:
            enums.append(enum)
    if not enums or any(values != enums[0] for values in enums[1:]):
        raise HookCompatibilityError(_MALFORMED_HOOK_EVENT)
    return enums[0]


def _run(command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(  # noqa: S603
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise HookCompatibilityError(_INSPECTION_FAILED) from error


def _successful_output(command: tuple[str, ...]) -> str:
    completed = _run(command)
    output = completed.stdout.strip()
    if completed.returncode != 0 or not output:
        raise HookCompatibilityError(_INSPECTION_FAILED)
    return output


def probe_codex_hooks(codex: Path) -> HookCompatibility:
    """Inspect a local Codex executable without starting a model turn."""
    if not codex.is_file() or not os.access(codex, os.X_OK):
        raise HookCompatibilityError(_MISSING_EXECUTABLE)
    version = _successful_output((str(codex), "--version"))
    with tempfile.TemporaryDirectory(prefix="super-sol-codex-schema-") as temporary:
        output = Path(temporary) / _SCHEMA_NAME
        command = (
            str(codex),
            "app-server",
            "generate-json-schema",
            "--experimental",
            "--out",
            str(output),
        )
        completed = _run(command)
        if completed.returncode != 0:
            raise HookCompatibilityError(_SCHEMA_GENERATION_FAILED)
        observed_events = read_hook_events(output)
    missing_events = REQUIRED_EVENTS - observed_events
    return HookCompatibility(version, observed_events, missing_events, not missing_events)


def _arguments() -> Path:
    parser = argparse.ArgumentParser(prog="super-sol-hook-doctor")
    _ = parser.add_argument("--codex", type=Path, required=True)
    return cast("Path", parser.parse_args().codex)


def _print(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")))  # noqa: T201


def main() -> None:
    """Emit one JSON compatibility result and exit with the prescribed status."""
    codex = _arguments()
    try:
        compatibility = probe_codex_hooks(codex)
    except HookCompatibilityError as error:
        _print({"compatible": False, "error": str(error)})
        raise SystemExit(2) from error
    payload = cast("dict[str, object]", asdict(compatibility))
    payload["missing_events"] = sorted(compatibility.missing_events)
    payload["observed_events"] = sorted(compatibility.observed_events)
    _print(payload)
    raise SystemExit(0 if compatibility.compatible else 1)


if __name__ == "__main__":
    main()
