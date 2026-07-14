"""Prompt-time routing, privacy, and billing state for Super SOL hooks."""

from __future__ import annotations

import os
import re
import time

from super_sol_routes import Route, context_for, route_prompt
from super_sol_state import claim_once, turn_root, write_private_json

_SCHEMA_VERSION = 4
_DIAGNOSTIC_MODE = "SUPER_SOL_DIAGNOSTIC_MODE"
_FORCED_ROUTE = "SUPER_SOL_FORCED_ROUTE"
_SECRET = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
_NEGATIVE_BILLING = (
    "과금 없이",
    "과금하지",
    "api 호출하지",
    "api를 호출하지",
    "no api call",
    "no billing",
    "don't call api",
    "do not call api",
)
_BILLABLE_CONFIRMATIONS = ("super sol 유료 실행 승인", "super sol billable run approved")


def _context(event: str, text: str) -> dict[str, object]:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def _warning(message: str) -> dict[str, object]:
    return {"continue": True, "systemMessage": f"Super SOL: {message}"}


def _billable_authorized(prompt: str) -> bool:
    lowered = prompt.casefold()
    if any(signal in lowered for signal in _NEGATIVE_BILLING):
        return False
    lines = {line.strip().casefold() for line in prompt.splitlines()}
    return any(confirmation in lines for confirmation in _BILLABLE_CONFIRMATIONS)


def _diagnostic_control() -> tuple[str, Route | None, str | None]:
    mode = os.environ.get(_DIAGNOSTIC_MODE, "").strip().casefold()
    if not mode:
        return "adaptive", None, None
    if mode == "observe":
        return "observe", None, None
    if mode != "forced":
        return "adaptive", None, "invalid_diagnostic_mode"
    forced = os.environ.get(_FORCED_ROUTE, "").strip().casefold()
    try:
        route = Route(forced)
    except ValueError:
        return "adaptive", None, "invalid_forced_route"
    if route is Route.PASS_THROUGH:
        return "adaptive", None, "invalid_forced_route"
    return "forced", route, None


def model_profile(payload: dict[str, object]) -> str:
    """Return the model eligibility profile without persisting model text."""
    model = payload.get("model")
    return (
        "sol" if isinstance(model, str) and model.strip().casefold() == "gpt-5.6-sol" else "observe"
    )


def reset_for_prompt(payload: dict[str, object]) -> None:
    """Reset an existing canonical Sol loop ledger after one user prompt."""
    root = turn_root(payload)
    if model_profile(payload) != "sol" or root is None or not (root / "loop.json").is_file():
        return
    from super_sol_loop_state import LoopLedger, mutate_loop_ledger  # noqa: PLC0415

    _ = mutate_loop_ledger(root, lambda _state: LoopLedger.fresh(time.time_ns()))


def process_prompt(payload: dict[str, object]) -> dict[str, object] | None:  # noqa: C901
    """Process a prompt event with the v0.8 route, privacy, and billing behavior."""
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        return _warning("요청 내용을 읽지 못해 자동 절차 없이 계속합니다.")
    if _SECRET.search(prompt):
        return {
            "decision": "block",
            "reason": "API 키로 보이는 값이 있습니다. 키를 폐기하고 채팅에서 제거하세요.",
        }
    decision = route_prompt(prompt)
    diagnostic_mode, forced_route, diagnostic_warning = _diagnostic_control()
    profile = model_profile(payload)
    effective_route = Route.PASS_THROUGH
    if profile == "sol":
        if diagnostic_mode == "observe":
            effective_route = Route.PASS_THROUGH
        elif diagnostic_mode == "forced" and forced_route is not None:
            effective_route = forced_route
        elif decision.forced:
            effective_route = decision.route
    root = turn_root(payload)
    billable_authorized = _billable_authorized(prompt)
    should_persist = (
        billable_authorized
        or decision.contract is not None
        or decision.forced
        or diagnostic_mode != "adaptive"
        or diagnostic_warning is not None
    )
    if root is not None and should_persist:
        private_state: dict[str, object] = {
            "billable_authorized": billable_authorized,
            "confidence": decision.confidence,
            "diagnostic_mode": diagnostic_mode,
            "effective_route": effective_route.value,
            "forced": decision.forced or diagnostic_mode == "forced",
            "natural_route": decision.route.value,
            "primary_contract": decision.contract.value if decision.contract is not None else None,
            "schema_version": _SCHEMA_VERSION,
            "signal_ids": list(decision.signal_ids),
        }
        if diagnostic_warning is not None:
            private_state["diagnostic_warning"] = diagnostic_warning
        if diagnostic_mode != "observe":
            private_state["model_profile"] = profile
        write_private_json(root / "request.json", private_state)
    if decision.warning is not None:
        return _warning(decision.warning)
    context = context_for(effective_route)
    if context is not None and root is not None:
        _ = claim_once(root, "model-visible-context")
    return _context("UserPromptSubmit", context) if context is not None else None
