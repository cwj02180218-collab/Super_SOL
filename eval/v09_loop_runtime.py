from __future__ import annotations

import hashlib
import json
import os
import subprocess
from typing import TYPE_CHECKING, cast

from v09_loop_audit import (  # pyright: ignore[reportImplicitRelativeImport]
    selected_commands,
)
from v09_loop_contract import (  # pyright: ignore[reportImplicitRelativeImport]
    MANIFEST_ERROR,
    as_dict,
    as_list,
)
from v09_loop_isolation import (  # pyright: ignore[reportImplicitRelativeImport]
    KernelIsolation,
    isolated_run,
    launcher_environment,
)

if TYPE_CHECKING:
    from pathlib import Path


def _action(output: object, event: str) -> dict[str, object] | None:
    if output is None:
        return {"kind": "pass"}
    values = as_dict(output)
    if values is None:
        return None
    if set(values) == {"continue", "stopReason"} and values.get("continue") is False:
        reason = values.get("stopReason")
        return {"kind": "stop", "reason": reason} if isinstance(reason, str) else None
    hook = as_dict(values.get("hookSpecificOutput"))
    if set(values) != {"hookSpecificOutput"} or hook is None:
        return None
    if set(hook) == {"hookEventName", "permissionDecision", "permissionDecisionReason"}:
        valid = (
            hook.get("hookEventName") == "PreToolUse"
            and hook.get("permissionDecision") == "deny"
            and isinstance(hook.get("permissionDecisionReason"), str)
        )
        return {"kind": "deny"} if valid else None
    context = hook.get("additionalContext")
    valid = (
        set(hook) == {"hookEventName", "additionalContext"}
        and hook.get("hookEventName") == event
        and isinstance(context, str)
        and len(context) <= 180
    )
    return {"kind": "context"} if valid else None


def _event_command(
    event: object, plugin_root: Path
) -> tuple[dict[str, object], dict[str, object], str, str, int]:
    values = as_dict(event)
    payload = as_dict(values.get("payload")) if values is not None else None
    expected = as_dict(values.get("expected_action")) if values is not None else None
    name = payload.get("hook_event_name") if payload is not None else None
    if payload is None or expected is None or not isinstance(name, str):
        raise TypeError
    selected = selected_commands(plugin_root).get(name)
    if selected is None:
        raise ValueError(MANIFEST_ERROR)
    command, timeout = selected
    return payload, expected, name, command, timeout


def _run_event(
    event: object,
    plugin_root: Path,
    plugin_data: Path,
    isolation: KernelIsolation,
) -> tuple[bool, bool, str | None]:
    try:
        payload, expected, name, command, timeout = _event_command(event, plugin_root)
        completed = isolated_run(
            isolation,
            ("/bin/sh", "-c", command),
            env=launcher_environment(plugin_root, plugin_data),
            input_text=json.dumps(payload, separators=(",", ":")),
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, False, "timeout"
    except (OSError, TypeError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
        return False, False, "runner_error"
    if completed.returncode != 0:
        return False, False, "nonzero_exit"
    try:
        output = cast("object", json.loads(completed.stdout)) if completed.stdout.strip() else None
    except json.JSONDecodeError:
        return False, False, "malformed_json"
    actual = _action(output, name)
    output_values = as_dict(output)
    hook = as_dict(output_values.get("hookSpecificOutput")) if output_values is not None else None
    unexpected = (isinstance(output, dict) and "systemMessage" in output) or (
        hook is not None and "additionalContext" in hook and expected.get("kind") != "context"
    )
    failure = (
        None
        if actual == expected
        else ("malformed_action" if actual is None else "action_mismatch")
    )
    return actual == expected, unexpected, failure


def _turn_root(plugin_data: Path, event: object) -> Path:
    values = as_dict(event)
    payload = as_dict(values.get("payload")) if values is not None else None
    if payload is None:
        raise ValueError(MANIFEST_ERROR)

    def identifier(value: object) -> str:
        text = value if isinstance(value, str) else "missing"
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    return (
        plugin_data
        / "super-sol"
        / "v3"
        / identifier(payload.get("session_id"))
        / identifier(payload.get("turn_id"))
    )


def _prepare_corrupt_state(plugin_data: Path, events: list[object]) -> Path:
    root = _turn_root(plugin_data, events[0])
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(root / "loop.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        _ = stream.write(b"{")
    return root


def _corrupt_recovered(root: Path) -> bool:
    try:
        ledger = cast("object", json.loads((root / "loop.json").read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(ledger, dict) and len(list(root.glob("loop.corrupt.*"))) == 1


def run_case_isolated(
    case: dict[str, object],
    plugin_root: Path,
    data_root: Path,
    isolation: KernelIsolation,
) -> dict[str, object]:
    case_id, events = case.get("id"), as_list(case.get("events"))
    if not isinstance(case_id, str) or not events:
        return {
            "id": "invalid",
            "passed": False,
            "events": 0,
            "failures": ["manifest"],
            "unexpected_contexts": 0,
        }
    plugin_data = data_root / hashlib.sha256(case_id.encode()).hexdigest()[:16]
    setup_root = _prepare_corrupt_state(plugin_data, events) if case.get("setup") else None
    failures: list[str] = []
    unexpected_contexts = 0
    setup_evidenced = False
    for index, event in enumerate(events):
        passed, unexpected, failure = _run_event(event, plugin_root, plugin_data, isolation)
        unexpected_contexts += int(unexpected)
        if not passed:
            failures.append(f"event-{index}:{failure}")
        if index == 0 and setup_root is not None:
            setup_evidenced = _corrupt_recovered(setup_root)
            if not setup_evidenced:
                failures.append("setup:corrupt_recovery")
    result: dict[str, object] = {
        "id": case_id,
        "passed": not failures,
        "events": len(events),
        "failures": failures,
        "unexpected_contexts": unexpected_contexts,
    }
    if setup_root is not None:
        result["setup"] = {"kind": "corrupt_loop_state", "evidenced": setup_evidenced}
    return result
