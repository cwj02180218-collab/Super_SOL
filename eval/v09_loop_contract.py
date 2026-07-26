from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

MANIFEST_ERROR = "manifest_contract"
HOOK_EVENTS = frozenset(
    {"PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop", "PreCompact", "PostCompact"}
)
V1_CONTRACTS: dict[str, tuple[str, ...]] = {
    "passed-verifier-replay": ("PostToolUse/pass", "PreToolUse/deny"),
    "unchanged-failing-verifier-replay": ("PostToolUse/pass", "PreToolUse/deny"),
    "healthy-edit-verify-edit-verify": (
        "PreToolUse/pass",
        "PostToolUse/pass",
        "PreToolUse/pass",
        "PostToolUse/pass",
        "PreToolUse/pass",
        "PostToolUse/pass",
        "PreToolUse/pass",
        "PostToolUse/pass",
    ),
    "generic-read-replay": (
        "PreToolUse/pass",
        "PostToolUse/pass",
        "PreToolUse/pass",
        "PostToolUse/pass",
        "PreToolUse/pass",
        "PostToolUse/context",
        "PreToolUse/deny",
    ),
    "nested-spawn": ("PreToolUse/deny",),
    "concurrent-child-exhaustion": (
        "PreToolUse/pass",
        "PreToolUse/pass",
        "PreToolUse/deny",
    ),
    "total-child-exhaustion": (
        "PreToolUse/pass",
        "SubagentStart/pass",
        "SubagentStop/pass",
        "PreToolUse/pass",
        "SubagentStart/pass",
        "SubagentStop/pass",
        "PreToolUse/pass",
        "SubagentStart/pass",
        "SubagentStop/pass",
        "PreToolUse/deny",
    ),
    "repeated-wait": (
        "PreToolUse/pass",
        "PostToolUse/pass",
        "PreToolUse/pass",
        "PostToolUse/pass",
        "PreToolUse/pass",
        "PostToolUse/context",
        "PreToolUse/deny",
    ),
    "three-no-progress-auto-compactions": (
        "PostCompact/pass",
        "PostCompact/pass",
        "PostCompact/stop:loop_fuse_no_progress_compaction",
    ),
    "healthy-progress-separated-compactions": (
        "PostToolUse/pass",
        "PostCompact/pass",
        "PostCompact/pass",
        "PostToolUse/pass",
        "PostCompact/pass",
    ),
    "terminal-internal-continuation": (
        "PostCompact/pass",
        "PostCompact/pass",
        "PostCompact/stop:loop_fuse_no_progress_compaction",
        "PreCompact/stop:loop_fuse_no_progress_compaction",
    ),
    "non-sol-pass-through": ("PostToolUse/pass", "PreToolUse/pass", "PostCompact/pass"),
}
V2_CONTRACTS = {
    **V1_CONTRACTS,
    "generic-read-replay": (
        "PreToolUse/pass",
        "PostToolUse/pass",
        "PreToolUse/pass",
        "PostToolUse/pass",
        "PreToolUse/pass",
        "PostToolUse/pass",
        "PreToolUse/deny",
    ),
    "repeated-wait": (
        "PreToolUse/pass",
        "PostToolUse/pass",
        "PreToolUse/pass",
        "PostToolUse/pass",
        "PreToolUse/pass",
        "PostToolUse/pass",
        "PreToolUse/deny",
    ),
}
SEALED_MANIFEST_SHA256 = {
    "super-sol-loop-sequences/v1": (
        "d68858f2fb29aa535cecaa5ffb072dcc7e66859dcf0146cbbb2d623a82026273"
    ),
    "super-sol-loop-sequences/v2": (
        "160ef30fde4b49a8bd2b1b8b5cc0240dc319d612207d641499a4c6d0da10a6a5"
    ),
}


def as_dict(value: object) -> dict[str, object] | None:
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def as_list(value: object) -> list[object] | None:
    return cast("list[object]", value) if isinstance(value, list) else None


def canonical(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode()


def _event_signature(event: object) -> tuple[str, str]:
    values = as_dict(event)
    payload = as_dict(values.get("payload")) if values is not None else None
    expected = as_dict(values.get("expected_action")) if values is not None else None
    if (
        values is None
        or set(values) != {"payload", "expected_action"}
        or payload is None
        or expected is None
    ):
        raise ValueError(MANIFEST_ERROR)
    name, kind = payload.get("hook_event_name"), expected.get("kind")
    if not isinstance(name, str) or not isinstance(kind, str):
        raise TypeError
    reason = expected.get("reason")
    action = f"{kind}:{reason}" if isinstance(reason, str) else kind
    return name, f"{name}/{action}"


def _validate_case(case: dict[str, object], contracts: dict[str, tuple[str, ...]]) -> set[str]:
    case_id = case.get("id")
    if not isinstance(case_id, str) or case_id not in contracts:
        raise ValueError(MANIFEST_ERROR)
    events = as_list(case.get("events"))
    setup = (
        {"kind": "corrupt_loop_state", "before_event": 0}
        if case_id == "healthy-progress-separated-compactions"
        else None
    )
    expected_keys = {"id", "events", "setup"} if setup is not None else {"id", "events"}
    if not events or case.get("setup") != setup or set(case) != expected_keys:
        raise ValueError(MANIFEST_ERROR)
    signatures = tuple(_event_signature(event) for event in events)
    if tuple(signature for _name, signature in signatures) != contracts[case_id]:
        raise ValueError(MANIFEST_ERROR)
    return {name for name, _signature in signatures}


def validate_manifest(payload: dict[str, object]) -> list[dict[str, object]]:
    schema = payload.get("schema")
    contracts = (
        V1_CONTRACTS
        if schema == "super-sol-loop-sequences/v1"
        else V2_CONTRACTS
        if schema == "super-sol-loop-sequences/v2"
        else None
    )
    cases = as_list(payload.get("cases"))
    expected_digest = SEALED_MANIFEST_SHA256.get(schema) if isinstance(schema, str) else None
    if contracts is None or expected_digest is None or cases is None:
        raise ValueError(MANIFEST_ERROR)
    typed = [as_dict(case) for case in cases]
    if any(case is None for case in typed):
        raise ValueError(MANIFEST_ERROR)
    valid = cast("list[dict[str, object]]", typed)
    if tuple(case.get("id") for case in valid) != tuple(contracts):
        raise ValueError(MANIFEST_ERROR)
    observed: set[str] = set()
    try:
        for case in valid:
            observed.update(_validate_case(case, contracts))
    except TypeError as error:
        raise ValueError(MANIFEST_ERROR) from error
    sealed = hashlib.sha256(canonical(payload)).hexdigest()
    if observed != set(HOOK_EVENTS) or sealed != expected_digest:
        raise ValueError(MANIFEST_ERROR)
    return valid


def manifest_payload(manifest: Path | dict[str, object]) -> tuple[dict[str, object], bytes]:
    raw = manifest.read_bytes() if isinstance(manifest, Path) else canonical(manifest)
    value = cast("object", json.loads(raw.decode())) if isinstance(manifest, Path) else manifest
    payload = as_dict(value)
    if payload is None:
        raise ValueError(MANIFEST_ERROR)
    return payload, raw
