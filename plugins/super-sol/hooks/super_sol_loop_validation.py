"""Bounded schema checks shared by loop-ledger loading and serialization."""

from __future__ import annotations

import re
from typing import cast

MAX_ACTIVE_AGENTS = 2
MAX_VERIFIER_RESULTS = 8
_FINGERPRINT = re.compile(r"[0-9a-f]{24}")
_OUTCOMES = frozenset({"ok", "pass", "fail", "same"})
_TERMINAL_REASONS = frozenset({"loop_fuse_no_progress_compaction"})


def valid_action(fingerprint: str, outcome: str) -> bool:
    """Return whether one persisted action has a safe fingerprint and outcome."""
    return _FINGERPRINT.fullmatch(fingerprint) is not None and outcome in _OUTCOMES


def fingerprints(value: object, limit: int) -> tuple[str, ...]:
    """Return a bounded tuple of canonical keyed fingerprints."""
    if not isinstance(value, list):
        raise TypeError
    items = cast("list[object]", value)
    if len(items) > limit or not all(
        isinstance(item, str) and _FINGERPRINT.fullmatch(item) is not None for item in items
    ):
        raise ValueError
    return tuple(cast("list[str]", items))


def terminal_reason(value: object) -> str | None:
    """Return one approved terminal reason or reject unbounded disk data."""
    if value is not None and (not isinstance(value, str) or value not in _TERMINAL_REASONS):
        raise ValueError
    return value
