import pytest
from super_sol_state import next_context_kind


@pytest.mark.parametrize(
    ("state", "events", "verification_success", "expected"),
    [
        (
            {"diagnostic_mode": "adaptive", "primary_contract": "retry_state"},
            ({"kind": "edit", "success": True},),
            True,
            "residual",
        ),
        (
            {"diagnostic_mode": "adaptive", "primary_contract": "retry_state"},
            ({"kind": "edit", "success": True},),
            False,
            "repair",
        ),
        (
            {"diagnostic_mode": "adaptive", "primary_contract": None},
            ({"kind": "edit", "success": True},),
            True,
            None,
        ),
        (
            {"diagnostic_mode": "observe", "primary_contract": "retry_state"},
            ({"kind": "edit", "success": True},),
            True,
            None,
        ),
        (
            {"diagnostic_mode": "adaptive", "primary_contract": "retry_state"},
            (),
            True,
            None,
        ),
        (
            {"diagnostic_mode": "adaptive", "primary_contract": "retry_state"},
            ({"kind": "edit", "success": False},),
            True,
            None,
        ),
    ],
)
def test_each_context_guard_blocks_its_mutation(
    state: dict[str, object],
    events: tuple[dict[str, object], ...],
    verification_success: bool,
    expected: str | None,
) -> None:
    assert next_context_kind(state, events, verification_success) == expected
