from pathlib import Path

import pytest

from fablized_sol.engine.events import (
    ClassifyEvent,
    GateFireEvent,
    MutationToolEvent,
    VerificationToolEvent,
)
from fablized_sol.engine.ledger import Ledger
from fablized_sol.engine.models import (
    ChangeKind,
    GateAction,
    HoldoutArm,
    TaskMode,
    ToolName,
)
from fablized_sol.engine.verify_state import decide_stop


def deep_changed_ledger(tmp_path: Path) -> Ledger:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(ClassifyEvent(mode=TaskMode.DEEP, risk_flags=()))
    ledger.append(
        MutationToolEvent(
            tool=ToolName("write_file"),
            path="src/x.py",
            change_kind=ChangeKind.CODE,
            sequence=1,
        )
    )
    return ledger


def test_verification_before_mutation_does_not_satisfy_gate(tmp_path: Path) -> None:
    # Given
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(ClassifyEvent(mode=TaskMode.DEEP, risk_flags=()))
    ledger.append(
        VerificationToolEvent(tool=ToolName("run_verification"), success=True, sequence=1)
    )
    ledger.append(
        MutationToolEvent(
            tool=ToolName("write_file"),
            path="src/x.py",
            change_kind=ChangeKind.CODE,
            sequence=2,
        )
    )

    # When
    decision = decide_stop(ledger.state(), HoldoutArm.ON, retry_limit=2)

    # Then
    assert decision.action is GateAction.BLOCK


def test_successful_verification_after_mutation_allows_stop(tmp_path: Path) -> None:
    # Given
    ledger = deep_changed_ledger(tmp_path)
    ledger.append(
        VerificationToolEvent(tool=ToolName("run_verification"), success=True, sequence=2)
    )

    # When
    decision = decide_stop(ledger.state(), HoldoutArm.ON, retry_limit=2)

    # Then
    assert decision.action is GateAction.ALLOW


@pytest.mark.parametrize(
    ("mode", "change_kind", "arm", "expected"),
    [
        pytest.param(TaskMode.QUICK, ChangeKind.CODE, HoldoutArm.ON, GateAction.ALLOW),
        pytest.param(TaskMode.NORMAL, ChangeKind.CODE, HoldoutArm.ON, GateAction.ALLOW),
        pytest.param(TaskMode.DEEP, None, HoldoutArm.ON, GateAction.ALLOW),
        pytest.param(TaskMode.DEEP, ChangeKind.DOCS, HoldoutArm.ON, GateAction.ALLOW),
        pytest.param(TaskMode.DEEP, ChangeKind.CODE, HoldoutArm.OFF, GateAction.ALLOW),
    ],
)
def test_gate_table(
    tmp_path: Path,
    mode: TaskMode,
    change_kind: ChangeKind | None,
    arm: HoldoutArm,
    expected: GateAction,
) -> None:
    # Given
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(ClassifyEvent(mode=mode, risk_flags=()))
    if change_kind is not None:
        ledger.append(
            MutationToolEvent(
                tool=ToolName("write_file"),
                path="changed-artifact",
                change_kind=change_kind,
                sequence=1,
            )
        )

    # When
    decision = decide_stop(ledger.state(), arm, retry_limit=2)

    # Then
    assert decision.action is expected


def test_failed_verification_does_not_satisfy_deep_code_gate(tmp_path: Path) -> None:
    # Given
    ledger = deep_changed_ledger(tmp_path)
    ledger.append(
        VerificationToolEvent(tool=ToolName("run_verification"), success=False, sequence=2)
    )

    # When
    decision = decide_stop(ledger.state(), HoldoutArm.ON, retry_limit=2)

    # Then
    assert decision.action is GateAction.BLOCK


@pytest.mark.parametrize(
    ("existing_blocks", "expected"),
    [
        pytest.param(0, GateAction.BLOCK, id="first-block"),
        pytest.param(1, GateAction.BLOCK, id="second-block"),
        pytest.param(2, GateAction.EXHAUSTED, id="retry-count-exhausted"),
    ],
)
def test_deep_code_gate_honors_retry_limit(
    tmp_path: Path,
    existing_blocks: int,
    expected: GateAction,
) -> None:
    # Given
    ledger = deep_changed_ledger(tmp_path)
    for _ in range(existing_blocks):
        ledger.append(GateFireEvent(reason="verification required"))

    # When
    decision = decide_stop(ledger.state(), HoldoutArm.ON, retry_limit=2)

    # Then
    assert decision.action is expected
