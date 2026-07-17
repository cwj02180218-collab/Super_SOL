"""Post-tool evidence routing preserved from the v0.8 hook dispatcher."""

from __future__ import annotations

from typing import cast

from super_sol_commands import CommandKind, classify_command, command_text
from super_sol_prompt_hook import model_profile
from super_sol_routes import REPAIR_CONTEXT, Contract, residual_context
from super_sol_state import (
    claim_once,
    load_events,
    load_state,
    next_context_kind,
    record_event,
    turn_root,
)

_EDIT_TOOLS = {"apply_patch", "edit", "write"}


def _context(text: str) -> dict[str, object]:
    return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}


def _succeeded(payload: dict[str, object]) -> bool | None:
    response = payload.get("tool_response")
    if not isinstance(response, dict):
        return None
    values = cast("dict[object, object]", response)
    code = values.get("exit_code")
    explicit_success = values.get("success")
    is_error = values.get("is_error")
    return (
        code == 0
        if type(code) is int
        else (explicit_success if isinstance(explicit_success, bool) else is_error is not True)
    )


def process_evidence(payload: dict[str, object]) -> dict[str, object] | None:  # noqa: PLR0911
    """Record v0.8 edit and verifier evidence, returning one residual when eligible."""
    root = turn_root(payload)
    state = load_state(payload)
    if root is None or state is None:
        return None
    success = _succeeded(payload)
    if success is None:
        return None
    tool_name = payload.get("tool_name")
    normalized_tool = tool_name.casefold() if isinstance(tool_name, str) else ""
    if normalized_tool in _EDIT_TOOLS:
        _ = record_event(root, payload.get("tool_use_id"), "edit", success)
        return None
    if normalized_tool != "bash":
        return None
    command = command_text(payload) or ""
    if classify_command(command).kind is not CommandKind.VERIFIER:
        return None
    _ = record_event(root, payload.get("tool_use_id"), "verification", success)
    if (
        model_profile(payload) != "sol"
        or state.get("model_profile") != "sol"
        or state.get("diagnostic_mode") == "observe"
    ):
        return None
    context_kind = next_context_kind(state, load_events(root), success)
    primary = state.get("primary_contract")
    if context_kind is None or not isinstance(primary, str):
        return None
    if not claim_once(root, "model-visible-context"):
        return None
    try:
        contract = Contract(primary)
    except ValueError:
        return None
    return _context(residual_context(contract) if context_kind == "residual" else REPAIR_CONTEXT)
