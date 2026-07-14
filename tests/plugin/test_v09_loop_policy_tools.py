from super_sol_loop_policy import FuseAction, after_tool, before_tool
from super_sol_loop_state import LoopLedger


def test_passed_verifier_blocks_identical_rerun_until_edit() -> None:
    state = LoopLedger.fresh()
    state, _ = after_tool(state, "verify-a", "verifier", "pass", now_ns=1)
    state, decision = before_tool(state, "verify-a", "verifier", is_child=False, now_ns=2)

    assert decision.action is FuseAction.BLOCK_ACTION
    assert decision.reason == "loop_fuse_verifier_replay"

    state, _ = after_tool(state, "edit-a", "edit", "pass", now_ns=3)
    _, decision = before_tool(state, "verify-a", "verifier", is_child=False, now_ns=4)

    assert decision.action is FuseAction.PASS


def test_failed_verifier_blocks_identical_rerun_until_edit() -> None:
    state = LoopLedger.fresh()
    state, _ = after_tool(state, "verify-a", "verifier", "fail", now_ns=1)
    _, decision = before_tool(state, "verify-a", "verifier", is_child=False, now_ns=2)

    assert decision.action is FuseAction.BLOCK_ACTION


def test_generic_replay_warns_third_and_blocks_fourth() -> None:
    state = LoopLedger.fresh()
    decisions: list[FuseAction] = []
    reasons: list[str | None] = []
    for moment in range(1, 4):
        state, _ = before_tool(state, "read-a", "read", is_child=False, now_ns=moment)
        state, decision = after_tool(state, "read-a", "read", "same", now_ns=moment)
        decisions.append(decision.action)
        reasons.append(decision.reason)

    assert decisions == [FuseAction.PASS, FuseAction.PASS, FuseAction.WARN_ONCE]
    assert reasons[-1] == "loop_fuse_tool_replay"

    _, blocked = before_tool(state, "read-a", "read", is_child=False, now_ns=4)

    assert blocked.action is FuseAction.BLOCK_ACTION
    assert blocked.reason == "loop_fuse_tool_replay"


def test_failed_edit_does_not_reset_verifier_replay() -> None:
    state = LoopLedger.fresh()
    state, _ = after_tool(state, "verify-a", "verifier", "pass", now_ns=1)
    state, _ = after_tool(state, "edit-a", "edit", "fail", now_ns=2)
    _, decision = before_tool(state, "verify-a", "verifier", is_child=False, now_ns=3)

    assert decision.action is FuseAction.BLOCK_ACTION


def test_ninth_distinct_verifier_preserves_block_for_first_result() -> None:
    state = LoopLedger.fresh()
    for moment in range(9):
        state, _ = after_tool(state, f"verify-{moment}", "verifier", "pass", now_ns=moment + 1)

    _, decision = before_tool(state, "verify-0", "verifier", is_child=False, now_ns=10)

    assert len(state.verifier_results) <= 8
    assert decision.action is FuseAction.BLOCK_ACTION
    assert decision.reason == "loop_fuse_verifier_replay"


def test_verifier_overflow_fails_closed_for_new_requests() -> None:
    state = LoopLedger.fresh()
    for moment in range(9):
        state, _ = after_tool(state, f"verify-{moment}", "verifier", "pass", now_ns=moment + 1)

    _, decision = before_tool(state, "verify-new", "verifier", is_child=False, now_ns=10)

    assert decision.action is FuseAction.BLOCK_ACTION
    assert decision.reason == "loop_fuse_verifier_replay"


def test_successful_edit_clears_verifier_overflow() -> None:
    state = LoopLedger.fresh()
    for moment in range(9):
        state, _ = after_tool(state, f"verify-{moment}", "verifier", "pass", now_ns=moment + 1)
    state, _ = after_tool(state, "edit-a", "edit", "pass", now_ns=10)
    _, decision = before_tool(state, "verify-new", "verifier", is_child=False, now_ns=11)

    assert state.verifier_results == ()
    assert decision.action is FuseAction.PASS
