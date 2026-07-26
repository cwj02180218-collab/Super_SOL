"""Bounded privacy-safe incident evidence for Super SOL hooks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from super_sol_state import claim_once, read_private_json, write_private_json

if TYPE_CHECKING:
    from pathlib import Path

_MAX_EVENTS = 64
_SCHEMA_VERSION = 1
_EVENTS = frozenset({"PostCompact", "PostToolUse", "PreCompact", "PreToolUse"})
_DECISIONS = frozenset({"deny", "stop", "warn"})
_REASONS = frozenset(
    {
        "loop_fuse_concurrent_agent_budget",
        "loop_fuse_nested_agent",
        "loop_fuse_no_progress_compaction",
        "loop_fuse_tool_replay",
        "loop_fuse_total_agent_budget",
        "loop_fuse_verifier_replay",
    }
)


def _valid(event: str, reason: str, decision: str, observed_at: int) -> bool:
    return (
        event in _EVENTS
        and reason in _REASONS
        and decision in _DECISIONS
        and type(observed_at) is int
        and observed_at >= 0
    )


def record_incident(
    root: Path,
    *,
    event: str,
    reason: str,
    decision: str,
    observed_at: int,
) -> bool:
    """Claim one bounded immutable slot and record only typed incident facts."""
    if not _valid(event, reason, decision, observed_at):
        return False
    for slot in range(_MAX_EVENTS):
        if not claim_once(root, f"audit-slot:{slot}"):
            continue
        write_private_json(
            root / "audit" / f"{slot:02}.json",
            {
                "decision": decision,
                "event": event,
                "observed_at": observed_at,
                "reason": reason,
                "schema_version": _SCHEMA_VERSION,
            },
        )
        return True
    return False


def audit_summary(root: Path) -> dict[str, int]:
    """Aggregate valid immutable audit events without exposing their source data."""
    summary = dict.fromkeys(sorted(_DECISIONS), 0)
    for path in sorted((root / "audit").glob("*.json")):
        payload = read_private_json(path)
        if payload is None or payload.get("schema_version") != _SCHEMA_VERSION:
            continue
        event = payload.get("event")
        reason = payload.get("reason")
        decision = payload.get("decision")
        observed_at = payload.get("observed_at")
        if (
            isinstance(event, str)
            and isinstance(reason, str)
            and isinstance(decision, str)
            and type(observed_at) is int
            and _valid(event, reason, decision, observed_at)
        ):
            summary[decision] += 1
    return summary
