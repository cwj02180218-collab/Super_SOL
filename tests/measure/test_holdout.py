from fablized_sol.engine.models import HoldoutArm, SessionId
from fablized_sol.measure.holdout import assign_arm


def test_holdout_assignment_is_stable_and_has_both_arms() -> None:
    first = [assign_arm(SessionId(f"session-{index}")) for index in range(100)]
    second = [assign_arm(SessionId(f"session-{index}")) for index in range(100)]
    assert first == second
    assert set(first) == {HoldoutArm.ON, HoldoutArm.OFF}
    assert assign_arm(SessionId("session-0")) is HoldoutArm.ON
    assert assign_arm(SessionId("session-1")) is HoldoutArm.OFF
