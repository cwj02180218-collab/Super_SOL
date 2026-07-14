"""Bounded, private loop-fuse ledger persistence.

The shipped hook interpreter is macOS Python 3.9, so the frozen dataclasses
intentionally do not use ``slots=True``. Their public fields remain exactly
the v0.9 schema while preserving that runtime compatibility.
"""

from __future__ import annotations

import fcntl
import hmac
import json
import os
import time
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

from super_sol_loop_validation import (
    MAX_ACTIVE_AGENTS,
    MAX_VERIFIER_RESULTS,
    fingerprints,
    terminal_reason,
    valid_action,
)
from super_sol_state import read_private_json, write_private_json

_KEY_BYTES = 32
_LOCK_RETRY_SECONDS = 0.2
_LOCK_STALE_SECONDS = 5.0
_MAX_ACTIONS = 8
_MAX_LEDGER_BYTES = 4096


class _InvalidLedgerError(ValueError):
    pass


@dataclass(frozen=True)
class ActionRecord:
    """A privacy-safe record of one normalized loop action."""

    fingerprint: str
    outcome: str
    streak: int
    edit_epoch: int


@dataclass(frozen=True)
class LoopLedger:
    """The complete bounded state for one loop-fuse turn."""

    schema_version: int
    edit_epoch: int
    actions: tuple[ActionRecord, ...]
    verifier_results: tuple[str, ...]
    active_agents: tuple[str, ...]
    pending_spawns: int
    total_agents: int
    compact_streak: int
    warned: bool
    terminal_reason: "str | None"  # noqa: UP037
    last_progress_ns: int
    last_event_ns: int

    @classmethod
    def fresh(cls, now_ns: int = 0) -> LoopLedger:
        """Return an empty v0.9 loop ledger."""
        return cls(1, 0, (), (), (), 0, 0, 0, False, None, now_ns, now_ns)  # noqa: FBT003


def _create_key(path: Path) -> bytes:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        key = os.urandom(_KEY_BYTES)
        with os.fdopen(descriptor, "wb") as stream:
            _ = stream.write(key)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return key


def _installation_key(root: Path) -> bytes:
    key_path = root.parents[1] / ".loop-key"
    try:
        key = _create_key(key_path)
    except FileExistsError:
        deadline = time.monotonic() + _LOCK_RETRY_SECONDS
        key = b""
        while len(key) != _KEY_BYTES and time.monotonic() < deadline:
            with suppress(FileNotFoundError):
                key = key_path.read_bytes()
            time.sleep(0.002)
    if len(key) != _KEY_BYTES:
        raise _InvalidLedgerError
    key_path.chmod(0o600)
    return key


def keyed_fingerprint(root: Path, raw: str) -> str:
    """Return a keyed digest for raw input without persisting that input."""
    return hmac.digest(_installation_key(root), raw.encode(), "sha256").hex()[:24]


def _action_from_json(value: object) -> ActionRecord:
    if not isinstance(value, dict):
        raise _InvalidLedgerError
    fields = cast("dict[str, object]", value)
    if set(fields) != {"fingerprint", "outcome", "streak", "edit_epoch"}:
        raise _InvalidLedgerError
    fingerprint = fields["fingerprint"]
    outcome = fields["outcome"]
    streak = fields["streak"]
    edit_epoch = fields["edit_epoch"]
    if (
        not isinstance(fingerprint, str)
        or not isinstance(outcome, str)
        or not valid_action(fingerprint, outcome)
    ):
        raise _InvalidLedgerError
    if type(streak) is not int or type(edit_epoch) is not int:
        raise _InvalidLedgerError
    return ActionRecord(fingerprint, outcome, streak, edit_epoch)


def _ledger_from_json(payload: dict[str, object]) -> LoopLedger:
    if set(payload) != set(LoopLedger.__annotations__):
        raise _InvalidLedgerError
    values = payload
    actions = values["actions"]
    integer_fields = (
        "schema_version",
        "edit_epoch",
        "pending_spawns",
        "total_agents",
        "compact_streak",
        "last_progress_ns",
        "last_event_ns",
    )
    if not isinstance(actions, list):
        raise _InvalidLedgerError
    action_values = cast("list[object]", actions)
    if len(action_values) > _MAX_ACTIONS:
        raise _InvalidLedgerError
    if not all(type(values[name]) is int for name in integer_fields):
        raise _InvalidLedgerError
    if type(values["warned"]) is not bool:
        raise _InvalidLedgerError
    return LoopLedger(
        cast("int", values["schema_version"]),
        cast("int", values["edit_epoch"]),
        tuple(_action_from_json(action) for action in action_values),
        fingerprints(values["verifier_results"], MAX_VERIFIER_RESULTS),
        fingerprints(values["active_agents"], MAX_ACTIVE_AGENTS),
        cast("int", values["pending_spawns"]),
        cast("int", values["total_agents"]),
        cast("int", values["compact_streak"]),
        values["warned"],
        terminal_reason(values["terminal_reason"]),
        cast("int", values["last_progress_ns"]),
        cast("int", values["last_event_ns"]),
    )


def _quarantine(path: Path) -> None:
    with suppress(FileNotFoundError):
        _ = path.replace(path.with_name(f"loop.corrupt.{time.time_ns()}"))


def _load(root: Path) -> LoopLedger:
    path = root / "loop.json"
    payload = read_private_json(path)
    if payload is None:
        if path.exists():
            _quarantine(path)
        return LoopLedger.fresh()
    try:
        return _ledger_from_json(payload)
    except (TypeError, ValueError):
        _quarantine(path)
        return LoopLedger.fresh()


def load_loop_ledger(root: Path) -> LoopLedger:
    """Load one bounded ledger, quarantining invalid private state."""
    return _load(root)


def _acquire_lock(root: Path) -> tuple[int, Path]:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    guard = os.open(root / "loop.guard", os.O_RDWR | os.O_CREAT, 0o600)
    lock = root / "loop.lock"
    deadline = time.monotonic() + _LOCK_RETRY_SECONDS
    try:
        while True:
            try:
                fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError from None
                time.sleep(0.002)
        while True:
            try:
                descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                try:
                    if time.time() - lock.stat().st_mtime > _LOCK_STALE_SECONDS:
                        lock.unlink()
                        continue
                except FileNotFoundError:
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError from None
                time.sleep(0.002)
                continue
            os.close(descriptor)
            return guard, lock
    except BaseException:
        os.close(guard)
        raise


def _ledger_payload(ledger: object) -> dict[str, object]:
    if not isinstance(ledger, LoopLedger):
        raise TypeError
    if len(ledger.actions) > _MAX_ACTIONS:
        raise _InvalidLedgerError
    if any(not valid_action(action.fingerprint, action.outcome) for action in ledger.actions):
        raise _InvalidLedgerError
    _ = fingerprints(list(ledger.verifier_results), MAX_VERIFIER_RESULTS)
    _ = fingerprints(list(ledger.active_agents), MAX_ACTIVE_AGENTS)
    _ = terminal_reason(ledger.terminal_reason)
    return {
        "schema_version": ledger.schema_version,
        "edit_epoch": ledger.edit_epoch,
        "actions": [
            {
                "fingerprint": action.fingerprint,
                "outcome": action.outcome,
                "streak": action.streak,
                "edit_epoch": action.edit_epoch,
            }
            for action in ledger.actions
        ],
        "verifier_results": list(ledger.verifier_results),
        "active_agents": list(ledger.active_agents),
        "pending_spawns": ledger.pending_spawns,
        "total_agents": ledger.total_agents,
        "compact_streak": ledger.compact_streak,
        "warned": ledger.warned,
        "terminal_reason": ledger.terminal_reason,
        "last_progress_ns": ledger.last_progress_ns,
        "last_event_ns": ledger.last_event_ns,
    }


def _serialized_payload(ledger: LoopLedger) -> dict[str, object]:
    payload = _ledger_payload(ledger)
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(encoded) > _MAX_LEDGER_BYTES:
        raise ValueError(_MAX_LEDGER_BYTES)
    return payload


def mutate_loop_ledger(root: Path, transition: Callable[[LoopLedger], LoopLedger]) -> LoopLedger:
    """Atomically transition and persist one bounded private loop ledger."""
    guard, lock = _acquire_lock(root)
    try:
        updated = transition(_load(root))
        write_private_json(root / "loop.json", _serialized_payload(updated))
        return updated
    finally:
        lock.unlink(missing_ok=True)
        try:
            fcntl.flock(guard, fcntl.LOCK_UN)
        finally:
            os.close(guard)
