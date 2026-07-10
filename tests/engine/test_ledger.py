import json
from pathlib import Path

import pytest

from fablized_sol.engine.events import (
    ClassifyEvent,
    EvidenceRejectedEvent,
    GateFireEvent,
    MutationToolEvent,
    ReadToolEvent,
    VerificationToolEvent,
)
from fablized_sol.engine.ledger import Ledger, LedgerParseError, LedgerStateError
from fablized_sol.engine.models import ChangeKind, TaskMode, ToolKind, ToolName


def test_append_preserves_event_order_and_writes_one_json_line_per_event(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "ledger.jsonl"
    ledger = Ledger(path)
    events = (
        ClassifyEvent(mode=TaskMode.DEEP, risk_flags=("database",)),
        ReadToolEvent(tool=ToolName("read_file")),
        MutationToolEvent(
            tool=ToolName("write_file"),
            path="src/x.py",
            change_kind=ChangeKind.CODE,
        ),
    )

    # When
    for event in events:
        ledger.append(event)

    # Then
    assert ledger.read() == events
    assert len(path.read_text(encoding="utf-8").splitlines()) == len(events)


def test_malformed_json_reports_line_number(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "ledger.jsonl"
    _ = path.write_text('{"event":"classify"}\nnot-json\n', encoding="utf-8")

    # When / Then
    with pytest.raises(LedgerParseError, match="line 2"):
        _ = Ledger(path).read()


def test_invalid_event_reports_line_number(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "ledger.jsonl"
    invalid = json.dumps({"event": "classify", "mode": "impossible", "risk_flags": []})
    _ = path.write_text(f"{invalid}\n", encoding="utf-8")

    # When / Then
    with pytest.raises(LedgerParseError, match="line 1"):
        _ = Ledger(path).read()


@pytest.mark.parametrize("coercive_success", ["true", 1], ids=["string", "integer"])
def test_coercive_verification_success_reports_line_number(
    tmp_path: Path,
    coercive_success: str | int,
) -> None:
    # Given
    path = tmp_path / "ledger.jsonl"
    classify = json.dumps({"event": "classify", "mode": "deep", "risk_flags": []})
    verification = json.dumps(
        {
            "event": "tool_call",
            "tool": "test",
            "kind": "verification",
            "success": coercive_success,
        }
    )
    _ = path.write_text(f"{classify}\n{verification}\n", encoding="utf-8")

    # When / Then
    with pytest.raises(LedgerParseError, match="line 2"):
        _ = Ledger(path).read()


def test_event_with_extra_field_reports_line_number(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "ledger.jsonl"
    classify = json.dumps(
        {"event": "classify", "mode": "deep", "risk_flags": [], "unexpected": "value"}
    )
    _ = path.write_text(f"{classify}\n", encoding="utf-8")

    # When / Then
    with pytest.raises(LedgerParseError, match="line 1"):
        _ = Ledger(path).read()


def test_state_rejects_missing_classification(tmp_path: Path) -> None:
    # Given
    ledger = Ledger(tmp_path / "ledger.jsonl")

    # When / Then
    with pytest.raises(LedgerStateError, match="classification"):
        _ = ledger.state()


def test_state_rejects_multiple_classifications(tmp_path: Path) -> None:
    # Given
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(ClassifyEvent(mode=TaskMode.QUICK, risk_flags=()))
    ledger.append(ClassifyEvent(mode=TaskMode.DEEP, risk_flags=()))

    # When / Then
    with pytest.raises(LedgerStateError, match="classification"):
        _ = ledger.state()


def test_state_tracks_latest_mutation_and_successful_verification(tmp_path: Path) -> None:
    # Given
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(ClassifyEvent(mode=TaskMode.DEEP, risk_flags=()))
    ledger.append(
        MutationToolEvent(
            tool=ToolName("write_file"),
            path="README.md",
            change_kind=ChangeKind.DOCS,
        )
    )
    ledger.append(VerificationToolEvent(tool=ToolName("test"), success=False))
    ledger.append(VerificationToolEvent(tool=ToolName("test"), success=True))
    ledger.append(
        MutationToolEvent(
            tool=ToolName("write_file"),
            path="src/x.py",
            change_kind=ChangeKind.CODE,
        )
    )
    ledger.append(GateFireEvent(reason="verification required"))

    # When
    state = ledger.state()

    # Then
    assert state.task_mode is TaskMode.DEEP
    assert state.changed_files_seen is True
    assert state.change_kinds == frozenset({ChangeKind.CODE, ChangeKind.DOCS})
    assert state.latest_mutation_index == 4
    assert state.latest_successful_verification_index == 3
    assert state.has_fresh_verification is False
    assert state.stop_blocks == 1


def test_rejected_evidence_is_observable_but_has_zero_state_credit(tmp_path: Path) -> None:
    # Given
    ledger = Ledger(tmp_path / "ledger.jsonl")
    classify = ClassifyEvent(mode=TaskMode.DEEP, risk_flags=())
    rejected_mutation = EvidenceRejectedEvent(
        tool=ToolName("mystery_write"),
        claimed_kind=ToolKind.MUTATION,
        reason="unknown_tool",
    )
    rejected_verification = EvidenceRejectedEvent(
        tool=ToolName("mystery_test"),
        claimed_kind=ToolKind.VERIFICATION,
        reason="malformed_result",
    )
    ledger.append(classify)
    ledger.append(rejected_mutation)
    ledger.append(rejected_verification)

    # When
    events = ledger.read()
    state = ledger.state()

    # Then
    assert events == (classify, rejected_mutation, rejected_verification)
    assert state.changed_files_seen is False
    assert state.change_kinds == frozenset()
    assert state.latest_mutation_index is None
    assert state.latest_successful_verification_index is None
