"""Bounded private state operations for Super SOL hooks."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import cast

MAX_INPUT_BYTES = 1_048_576
MAX_INJECTIONS_PER_TURN = 1
_MAX_STATE_BYTES = 4096


class HookInputError(ValueError):
    """Bounded hook input could not be parsed."""


def _identifier(value: object) -> str:
    text = value if isinstance(value, str) else "missing"
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def read_input() -> dict[str, object]:
    """Read one bounded UTF-8 JSON object from standard input."""
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise HookInputError
    try:
        value = cast("object", json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HookInputError from error
    if not isinstance(value, dict):
        raise HookInputError
    return cast("dict[str, object]", value)


def turn_root(payload: dict[str, object]) -> "Path | None":  # noqa: UP037
    """Return the privacy-preserving state directory for one turn."""
    plugin_data = os.environ.get("PLUGIN_DATA")
    if not plugin_data:
        return None
    root = Path(plugin_data) / "super-sol" / "v3"
    return root / _identifier(payload.get("session_id")) / _identifier(payload.get("turn_id"))


def write_private_json(path: Path, payload: dict[str, object]) -> None:
    """Atomically write owner-only JSON under the plugin data directory."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, separators=(",", ":"), sort_keys=True)
        _ = temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def claim_once(root: Path, name: str) -> bool:
    """Create one owner-only marker and return whether this caller won."""
    marker = root / "claims" / hashlib.sha256(name.encode()).hexdigest()
    marker.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    os.close(descriptor)
    return True


def read_private_json(path: Path) -> dict[str, object] | None:
    """Read one small plugin-owned JSON object, rejecting invalid state."""
    try:
        if path.stat().st_size > _MAX_STATE_BYTES:
            return None
        value = cast("object", json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def load_state(payload: dict[str, object]) -> dict[str, object] | None:
    """Load the request classification for the current turn."""
    root = turn_root(payload)
    return read_private_json(root / "request.json") if root is not None else None


def load_events(root: Path) -> tuple[dict[str, object], ...]:
    """Load valid private evidence records for the current turn."""
    events: list[dict[str, object]] = []
    for path in (root / "events").glob("*.json"):
        event = read_private_json(path)
        if event is not None:
            events.append(event)
    return tuple(events)


def event_path(root: Path, tool_use_id: object, observed_at: int) -> tuple[Path, str]:
    """Build a hashed immutable event path and return its safe tool identifier."""
    identifier = _identifier(tool_use_id)
    return root / "events" / f"{observed_at}-{identifier}.json", identifier


def record_event(root: Path, tool_use_id: object, kind: str, success: bool) -> None:
    """Record one immutable privacy-safe tool outcome."""
    path, _identifier_value = event_path(root, tool_use_id, time.time_ns())
    write_private_json(path, {"kind": kind, "success": success})


def has_successful_event(events: tuple[dict[str, object], ...], kind: str) -> bool:
    """Return whether one successful event of the requested kind exists."""
    return any(event.get("kind") == kind and event.get("success") is True for event in events)


def next_context_kind(
    state: dict[str, object],
    events: tuple[dict[str, object], ...],
    verification_success: bool,
) -> str | None:
    """Return the one eligible model-visible context kind for a turn."""
    if state.get("diagnostic_mode") == "observe":
        return None
    if not isinstance(state.get("primary_contract"), str):
        return None
    if not has_successful_event(events, "edit"):
        return None
    return "residual" if verification_success else "repair"
