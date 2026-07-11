from pathlib import Path
from typing import Protocol

import anyio
import pytest
from agents import Agent, GuardrailFunctionOutput, RunContextWrapper, Usage

from fablized_sol.engine.events import ClassifyEvent, GateFireEvent, MutationToolEvent
from fablized_sol.engine.ledger import Ledger
from fablized_sol.engine.models import (
    ChangeKind,
    GateAction,
    HoldoutArm,
    TaskMode,
    ToolKind,
    ToolName,
)
from fablized_sol.harness.guardrails import GuardrailInfo, verification_gate
from fablized_sol.harness.registry import ToolRegistry, ToolSpec
from fablized_sol.harness.workspace_tools import FablizedContext


class _OutputWithInfo(Protocol):
    @property
    def output_info(self) -> GuardrailInfo: ...


def _parse_info(output: _OutputWithInfo) -> GuardrailInfo:
    return GuardrailInfo.model_validate(output.output_info)


def _context(tmp_path: Path, *, arm: HoldoutArm, retry_limit: int = 2) -> FablizedContext:
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
    registry = ToolRegistry.create(
        (
            ToolSpec(ToolName("list_files"), ToolKind.READ),
            ToolSpec(ToolName("read_file"), ToolKind.READ),
            ToolSpec(ToolName("write_file"), ToolKind.MUTATION),
            ToolSpec(ToolName("run_verification"), ToolKind.VERIFICATION),
        )
    )
    return FablizedContext(
        workspace=tmp_path,
        verify_argv=("uv", "run", "pytest", "-q"),
        ledger=ledger,
        registry=registry,
        arm=arm,
        retry_limit=retry_limit,
    )


async def _call_gate(
    context: FablizedContext,
    output: str,
) -> GuardrailFunctionOutput:
    wrapped = RunContextWrapper(context=context, usage=Usage())
    agent = Agent[FablizedContext](name="guardrail-test")
    result = await verification_gate.run(wrapped, agent, output)
    return result.output


def test_guardrail_blocks_deep_changed_unverified(tmp_path: Path) -> None:
    # Given a deep code mutation without fresh verification
    context = _context(tmp_path, arm=HoldoutArm.ON)

    # When the SDK output guardrail evaluates a completion claim
    result = anyio.run(_call_gate, context, "claimed done")

    # Then it blocks while preserving the rejected output and exact reason
    info = _parse_info(result)
    assert result.tripwire_triggered is True
    assert info.decision is GateAction.BLOCK
    assert info.blocked_output == "claimed done"
    event = context.ledger.read()[-1]
    assert isinstance(event, GateFireEvent)
    assert event.reason == info.reason


def test_guardrail_preserves_exhausted_output_and_reason(tmp_path: Path) -> None:
    # Given a deep mutation whose retry ledger is already exhausted
    context = _context(tmp_path, arm=HoldoutArm.ON, retry_limit=0)

    # When the guardrail evaluates the blocked output
    result = anyio.run(_call_gate, context, "still unverified")

    # Then exhausted is a tripwire with auditable output and reason
    info = _parse_info(result)
    assert result.tripwire_triggered is True
    assert info.decision is GateAction.EXHAUSTED
    assert info.reason == "verification retry limit exhausted"
    assert info.blocked_output == "still unverified"
    event = context.ledger.read()[-1]
    assert isinstance(event, GateFireEvent)
    assert event.reason == info.reason


@pytest.mark.parametrize("arm", [HoldoutArm.OFF])
def test_guardrail_never_records_gate_event_for_off_arm(
    tmp_path: Path,
    arm: HoldoutArm,
) -> None:
    # Given a holdout run with otherwise gate-worthy ledger state
    context = _context(tmp_path, arm=arm)
    event_count = len(context.ledger.read())

    # When the guardrail is called directly
    result = anyio.run(_call_gate, context, "holdout output")

    # Then OFF allows completion and never appends a gate event
    info = _parse_info(result)
    assert result.tripwire_triggered is False
    assert info.decision is GateAction.ALLOW
    assert info.blocked_output == "holdout output"
    assert len(context.ledger.read()) == event_count
