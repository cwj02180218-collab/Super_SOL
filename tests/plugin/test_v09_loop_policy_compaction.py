from super_sol_loop_policy import FuseAction, after_tool, on_compact
from super_sol_loop_state import LoopLedger

_THIRTY_MINUTES_NS = 30 * 60 * 1_000_000_000


def test_no_progress_for_thirty_minutes_emits_one_warning() -> None:
    state, decision = on_compact(LoopLedger.fresh(), "pre", "auto", now_ns=_THIRTY_MINUTES_NS)

    assert decision.action is FuseAction.WARN_ONCE
    assert decision.reason == "loop_fuse_tool_replay"
    assert state.warned is True


def test_third_no_progress_auto_compaction_stops_and_persists_through_precompact() -> None:
    state = LoopLedger.fresh()
    for moment in range(1, 3):
        state, decision = on_compact(state, "post", "auto", now_ns=moment)
        assert decision.action is FuseAction.PASS

    state, stopped = on_compact(state, "post", "auto", now_ns=3)
    persisted, repeated = on_compact(state, "pre", "auto", now_ns=4)

    assert stopped.action is FuseAction.STOP_TURN
    assert stopped.reason == "loop_fuse_no_progress_compaction"
    assert state.terminal_reason == "loop_fuse_no_progress_compaction"
    assert persisted == state
    assert repeated.action is FuseAction.STOP_TURN
    assert repeated.reason == "loop_fuse_no_progress_compaction"


def test_manual_compaction_neither_counts_nor_clears_auto_streak() -> None:
    state = LoopLedger.fresh()
    state, _ = on_compact(state, "post", "auto", now_ns=1)
    state, _ = on_compact(state, "post", "manual", now_ns=2)
    state, _ = on_compact(state, "post", "manual", now_ns=3)

    assert state.compact_streak == 1


def test_successful_edit_resets_auto_compaction_streak() -> None:
    state = LoopLedger.fresh()
    state, _ = on_compact(state, "post", "auto", now_ns=1)
    state, _ = on_compact(state, "post", "auto", now_ns=2)
    state, _ = after_tool(state, "edit-a", "edit", "pass", now_ns=3)
    state, decision = on_compact(state, "post", "auto", now_ns=4)

    assert state.compact_streak == 1
    assert decision.action is FuseAction.PASS
