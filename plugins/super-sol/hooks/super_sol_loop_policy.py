"""Pure, deterministic loop-fuse policy transitions.

The shipped hook interpreter is macOS Python 3.9, so frozen dataclasses here
intentionally omit ``slots=True``. This matches the immutable ledger schema
while preserving the runtime compatibility required by shipped hooks.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from super_sol_loop_state import ActionRecord, LoopLedger

_AUTO_TRIGGER = "auto"
_COMPACTION_STOP = "loop_fuse_no_progress_compaction"
_CONCURRENT_AGENT_BUDGET = "loop_fuse_concurrent_agent_budget"
_ELAPSED_WARNING_NS = 30 * 60 * 1_000_000_000
_MAX_CONCURRENT_AGENTS = 2
_MAX_REPLAY_STREAK = 3
_MAX_TOTAL_AGENTS = 3
_MAX_VERIFIER_RESULTS = 8
_NESTED_AGENT = "loop_fuse_nested_agent"
_SUCCESSFUL_OUTCOMES = frozenset({"ok", "pass"})
_TOOL_REPLAY = "loop_fuse_tool_replay"
_VERIFIER_REPLAY = "loop_fuse_verifier_replay"
# Valid persisted fingerprint reserved to fail closed after verifier-memory overflow.
_VERIFIER_OVERFLOW = "ffffffffffffffffffffffff"


class FuseAction(Enum):
    """The bounded actions that a loop-fuse adapter may take."""

    PASS = "pass"  # noqa: S105
    WARN_ONCE = "warn_once"
    BLOCK_ACTION = "block_action"
    STOP_TURN = "stop_turn"


@dataclass(frozen=True)
class FuseDecision:
    """One deterministic policy result without model-visible text."""

    action: FuseAction
    reason: str | None = None


_PASS = FuseDecision(FuseAction.PASS)
_WARN = FuseDecision(FuseAction.WARN_ONCE, _TOOL_REPLAY)


def _touched(state: LoopLedger, now_ns: int) -> LoopLedger:
    return replace(state, last_event_ns=now_ns)


def _current_action(state: LoopLedger, fingerprint: str) -> ActionRecord | None:
    for action in reversed(state.actions):
        if action.fingerprint == fingerprint and action.edit_epoch == state.edit_epoch:
            return action
    return None


def _record_action(state: LoopLedger, fingerprint: str, outcome: str, streak: int) -> LoopLedger:
    actions = tuple(action for action in state.actions if action.fingerprint != fingerprint)
    record = ActionRecord(fingerprint, outcome, streak, state.edit_epoch)
    return replace(state, actions=(*actions, record)[-8:])


def _remember_verifier(state: LoopLedger, fingerprint: str) -> tuple[str, ...]:
    results = state.verifier_results
    if _VERIFIER_OVERFLOW in results or fingerprint in results:
        return results
    if len(results) < _MAX_VERIFIER_RESULTS:
        return (*results, fingerprint)
    return (*results[: _MAX_VERIFIER_RESULTS - 1], _VERIFIER_OVERFLOW)


def _stop(state: LoopLedger) -> FuseDecision:
    return FuseDecision(FuseAction.STOP_TURN, state.terminal_reason)


def _elapsed_warning(state: LoopLedger, now_ns: int) -> tuple[LoopLedger, FuseDecision]:
    if state.warned or now_ns - state.last_progress_ns < _ELAPSED_WARNING_NS:
        return state, _PASS
    return replace(state, warned=True), _WARN


def _kind_is(kind: str, expected: str) -> bool:
    return kind == expected


def _before_spawn(state: LoopLedger, is_child: bool) -> tuple[LoopLedger, FuseDecision]:
    if is_child:
        return state, FuseDecision(FuseAction.BLOCK_ACTION, _NESTED_AGENT)
    if state.total_agents >= _MAX_TOTAL_AGENTS:
        return state, FuseDecision(FuseAction.BLOCK_ACTION, "loop_fuse_total_agent_budget")
    if len(state.active_agents) + state.pending_spawns >= _MAX_CONCURRENT_AGENTS:
        return state, FuseDecision(FuseAction.BLOCK_ACTION, _CONCURRENT_AGENT_BUDGET)
    return replace(
        state,
        pending_spawns=state.pending_spawns + 1,
        total_agents=state.total_agents + 1,
    ), _PASS


def before_tool(
    state: LoopLedger, fingerprint: str, kind: str, *, is_child: bool, now_ns: int
) -> tuple[LoopLedger, FuseDecision]:
    """Decide whether a normalized tool action may start."""
    if state.terminal_reason is not None:
        return state, _stop(state)
    state = _touched(state, now_ns)
    if _kind_is(kind, "spawn"):
        return _before_spawn(state, is_child)
    if _kind_is(kind, "verifier") and (
        _VERIFIER_OVERFLOW in state.verifier_results or fingerprint in state.verifier_results
    ):
        return state, FuseDecision(FuseAction.BLOCK_ACTION, _VERIFIER_REPLAY)
    action = _current_action(state, fingerprint)
    if action is not None and action.streak >= _MAX_REPLAY_STREAK:
        return state, FuseDecision(FuseAction.BLOCK_ACTION, _TOOL_REPLAY)
    return _elapsed_warning(state, now_ns)


def after_tool(
    state: LoopLedger, fingerprint: str, kind: str, outcome: str, *, now_ns: int
) -> tuple[LoopLedger, FuseDecision]:
    """Record a completed normalized tool action and its policy result."""
    if state.terminal_reason is not None:
        return state, _stop(state)
    state = _touched(state, now_ns)
    if _kind_is(kind, "edit") and outcome in _SUCCESSFUL_OUTCOMES:
        return replace(
            state,
            edit_epoch=state.edit_epoch + 1,
            actions=(),
            verifier_results=(),
            compact_streak=0,
            last_progress_ns=now_ns,
        ), _PASS
    if _kind_is(kind, "spawn") and outcome == "fail" and state.pending_spawns > 0:
        state = replace(state, pending_spawns=state.pending_spawns - 1)
    previous = _current_action(state, fingerprint)
    streak = previous.streak + 1 if previous is not None and previous.outcome == outcome else 1
    state = _record_action(state, fingerprint, outcome, streak)
    if _kind_is(kind, "verifier"):
        progressed = previous is None or previous.outcome != outcome
        state = replace(
            state,
            verifier_results=_remember_verifier(state, fingerprint),
            compact_streak=0 if progressed else state.compact_streak,
            last_progress_ns=now_ns if progressed else state.last_progress_ns,
        )
        return _elapsed_warning(state, now_ns)
    if streak == _MAX_REPLAY_STREAK and not state.warned:
        return replace(state, warned=True), _WARN
    return _elapsed_warning(state, now_ns)


def on_subagent_start(
    state: LoopLedger, agent_id: str, *, now_ns: int
) -> tuple[LoopLedger, FuseDecision]:
    """Reconcile a reserved child slot with its observed start event."""
    if state.terminal_reason is not None:
        return state, _stop(state)
    state = _touched(state, now_ns)
    if agent_id in state.active_agents:
        return _elapsed_warning(state, now_ns)
    reserved = state.pending_spawns > 0
    return _elapsed_warning(
        replace(
            state,
            active_agents=(*state.active_agents, agent_id),
            pending_spawns=max(state.pending_spawns - 1, 0),
            total_agents=state.total_agents if reserved else state.total_agents + 1,
        ),
        now_ns,
    )


def on_subagent_stop(
    state: LoopLedger, agent_id: str, *, now_ns: int
) -> tuple[LoopLedger, FuseDecision]:
    """Remove an observed active child without changing spawn reservations."""
    if state.terminal_reason is not None:
        return state, _stop(state)
    state = _touched(state, now_ns)
    if agent_id in state.active_agents:
        state = replace(
            state,
            active_agents=tuple(active for active in state.active_agents if active != agent_id),
        )
    return _elapsed_warning(state, now_ns)


def on_compact(
    state: LoopLedger, phase: str, trigger: str, *, now_ns: int
) -> tuple[LoopLedger, FuseDecision]:
    """Apply the automatic no-progress compaction circuit breaker."""
    if state.terminal_reason is not None:
        return state, _stop(state)
    state = _touched(state, now_ns)
    if trigger == _AUTO_TRIGGER and phase.casefold() in {"post", "postcompact"}:
        state = replace(state, compact_streak=state.compact_streak + 1)
        if state.compact_streak >= _MAX_REPLAY_STREAK:
            state = replace(state, terminal_reason=_COMPACTION_STOP)
            return state, _stop(state)
    return _elapsed_warning(state, now_ns)
