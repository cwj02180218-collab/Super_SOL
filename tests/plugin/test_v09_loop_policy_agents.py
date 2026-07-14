from super_sol_loop_policy import (
    FuseAction,
    after_tool,
    before_tool,
    on_subagent_start,
    on_subagent_stop,
)
from super_sol_loop_state import LoopLedger


def test_nested_spawn_is_denied_without_reserving_a_slot() -> None:
    state, decision = before_tool(
        LoopLedger.fresh(), "spawn-nested", "spawn", is_child=True, now_ns=1
    )

    assert decision.action is FuseAction.BLOCK_ACTION
    assert decision.reason == "loop_fuse_nested_agent"
    assert state.pending_spawns == 0
    assert state.total_agents == 0


def test_spawn_reserves_two_concurrent_slots_and_three_total_slots() -> None:
    state = LoopLedger.fresh()
    state, first = before_tool(state, "spawn-a", "spawn", is_child=False, now_ns=1)
    state, second = before_tool(state, "spawn-b", "spawn", is_child=False, now_ns=2)
    _, concurrent = before_tool(state, "spawn-c", "spawn", is_child=False, now_ns=3)

    assert first.action is FuseAction.PASS
    assert second.action is FuseAction.PASS
    assert state.pending_spawns == 2
    assert state.total_agents == 2
    assert concurrent.reason == "loop_fuse_concurrent_agent_budget"

    state, _ = on_subagent_start(state, "agent-a", now_ns=4)
    state, _ = on_subagent_start(state, "agent-b", now_ns=5)
    state, _ = on_subagent_stop(state, "agent-a", now_ns=6)
    state, third = before_tool(state, "spawn-c", "spawn", is_child=False, now_ns=7)
    state, _ = on_subagent_stop(state, "agent-b", now_ns=8)
    _, total = before_tool(state, "spawn-d", "spawn", is_child=False, now_ns=9)

    assert third.action is FuseAction.PASS
    assert state.pending_spawns == 1
    assert state.total_agents == 3
    assert total.reason == "loop_fuse_total_agent_budget"


def test_unknown_or_duplicate_subagent_stop_does_not_release_pending_spawn() -> None:
    state = LoopLedger.fresh()
    state, _ = before_tool(state, "spawn-a", "spawn", is_child=False, now_ns=1)
    state, _ = on_subagent_start(state, "agent-a", now_ns=2)
    state, _ = before_tool(state, "spawn-b", "spawn", is_child=False, now_ns=3)
    state, _ = on_subagent_stop(state, "agent-a", now_ns=4)
    state, _ = on_subagent_stop(state, "agent-a", now_ns=5)
    state, _ = on_subagent_stop(state, "unknown-agent", now_ns=6)

    assert state.active_agents == ()
    assert state.pending_spawns == 1
    assert state.total_agents == 2


def test_failed_spawns_release_concurrency_but_consume_total_budget() -> None:
    state = LoopLedger.fresh()
    for moment in range(1, 4):
        fingerprint = f"spawn-{moment}"
        state, allowed = before_tool(
            state, fingerprint, "spawn", is_child=False, now_ns=moment * 2 - 1
        )
        state, _ = after_tool(state, fingerprint, "spawn", "fail", now_ns=moment * 2)
        assert allowed.action is FuseAction.PASS
        assert state.pending_spawns == 0

    _, denied = before_tool(state, "spawn-4", "spawn", is_child=False, now_ns=7)

    assert state.total_agents == 3
    assert denied.action is FuseAction.BLOCK_ACTION
    assert denied.reason == "loop_fuse_total_agent_budget"
