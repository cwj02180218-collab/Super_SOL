"""Stop-gate decisions derived from chronological session evidence."""

from dataclasses import dataclass
from typing import assert_never

from fablized_sol.engine.ledger import SessionState
from fablized_sol.engine.models import ChangeKind, GateAction, HoldoutArm, TaskMode


@dataclass(frozen=True, slots=True)
class GateDecision:
    """The stop action and its audit-friendly reason."""

    action: GateAction
    reason: str


def decide_stop(state: SessionState, arm: HoldoutArm, retry_limit: int) -> GateDecision:
    """Apply the exhaustive v0.1 evidence-gate policy."""
    gate_enabled = _gate_enabled(arm)
    if not gate_enabled:
        decision = GateDecision(GateAction.ALLOW, "holdout arm disabled")
    elif not state.changed_files_seen:
        decision = GateDecision(GateAction.ALLOW, "no file mutations observed")
    elif state.has_fresh_verification:
        decision = GateDecision(
            GateAction.ALLOW,
            "successful verification is newer than latest mutation",
        )
    else:
        match state.task_mode:
            case TaskMode.QUICK:
                decision = GateDecision(
                    GateAction.ALLOW,
                    "quick tasks do not require verification",
                )
            case TaskMode.NORMAL:
                decision = GateDecision(GateAction.ALLOW, "normal tasks are allowed in v0.1")
            case TaskMode.DEEP:
                if state.change_kinds == frozenset({ChangeKind.DOCS}):
                    decision = GateDecision(
                        GateAction.ALLOW,
                        "docs-only changes do not require verification",
                    )
                elif state.stop_blocks >= retry_limit:
                    decision = GateDecision(
                        GateAction.EXHAUSTED,
                        "verification retry limit exhausted",
                    )
                else:
                    decision = GateDecision(
                        GateAction.BLOCK,
                        "deep code changes require fresh successful verification",
                    )
            case _:
                assert_never(state.task_mode)
    return decision


def _gate_enabled(arm: HoldoutArm) -> bool:
    match arm:
        case HoldoutArm.ON:
            return True
        case HoldoutArm.OFF:
            return False
        case _:
            assert_never(arm)
