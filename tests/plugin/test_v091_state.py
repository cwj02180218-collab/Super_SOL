from pathlib import Path

from super_sol_state import (
    STATE_NAMESPACE,
    claim_context,
    event_path,
    load_events,
    record_event,
    write_private_json,
)


def test_context_claims_allow_one_prompt_and_one_evidence(tmp_path: Path) -> None:
    root = tmp_path / "turn"

    assert STATE_NAMESPACE == "v4"
    assert claim_context(root, "prompt") is True
    assert claim_context(root, "prompt") is False
    assert claim_context(root, "evidence") is True
    assert claim_context(root, "evidence") is False
    assert claim_context(root, "unknown") is False


def test_duplicate_tool_delivery_records_one_event(tmp_path: Path) -> None:
    root = tmp_path / "turn"

    assert record_event(root, "edit-one", "edit", success=True) is True
    assert record_event(root, "edit-one", "edit", success=True) is False
    assert load_events(root) == ({"kind": "edit", "success": True},)


def test_events_are_loaded_in_observation_order(tmp_path: Path) -> None:
    root = tmp_path / "turn"
    late, _ = event_path(root, "edit-late", 30)
    first, _ = event_path(root, "verify-first", 10)
    middle, _ = event_path(root, "edit-middle", 20)
    write_private_json(late, {"kind": "edit", "success": True})
    write_private_json(first, {"kind": "verification", "success": False})
    write_private_json(middle, {"kind": "edit", "success": True})

    assert load_events(root) == (
        {"kind": "verification", "success": False},
        {"kind": "edit", "success": True},
        {"kind": "edit", "success": True},
    )
