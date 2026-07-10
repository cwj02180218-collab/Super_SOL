from pathlib import Path

import anyio
from agents import Agent, FunctionTool, RunContextWrapper, Usage, function_tool

from fablized_sol.engine.events import (
    ClassifyEvent,
    EvidenceRejectedEvent,
    MutationToolEvent,
    VerificationToolEvent,
)
from fablized_sol.engine.ledger import Ledger
from fablized_sol.engine.models import (
    ChangeKind,
    HoldoutArm,
    TaskMode,
    ToolKind,
    ToolName,
)
from fablized_sol.harness.hooks import LedgerHooks
from fablized_sol.harness.registry import ToolRegistry, ToolSpec
from fablized_sol.harness.workspace_tools import (
    FablizedContext,
    MutationToolResult,
    VerificationToolResult,
    run_verification,
    write_file,
)


@function_tool(name_override="unregistered_tool")
def _unregistered_tool() -> str:
    return "unused"


def _context(tmp_path: Path) -> FablizedContext:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(ClassifyEvent(mode=TaskMode.DEEP, risk_flags=()))
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
        verify_argv=("unused",),
        ledger=ledger,
        registry=registry,
        arm=HoldoutArm.ON,
        retry_limit=2,
    )


type HookResult = MutationToolResult | VerificationToolResult | str


def _invoke_hook(
    context: FablizedContext,
    tool: FunctionTool,
    result: HookResult,
) -> None:
    hooks = LedgerHooks()
    wrapped = RunContextWrapper(
        context=context,
        usage=Usage(),
    )
    agent = Agent[FablizedContext](name="test")
    anyio.run(hooks.on_tool_end, wrapped, agent, tool, result)


def test_hook_records_typed_mutation_result(tmp_path: Path) -> None:
    # Given a registered mutation tool returning its typed result
    context = _context(tmp_path)
    result = MutationToolResult(path="src/x.py", change_kind=ChangeKind.CODE)

    # When the real SDK hook adapter observes the tool ending
    _invoke_hook(context, write_file, result)

    # Then one mutation event is appended
    event = context.ledger.read()[-1]
    assert isinstance(event, MutationToolEvent)
    assert event.tool == ToolName("write_file")
    assert event.path == "src/x.py"
    assert event.change_kind is ChangeKind.CODE


def test_hook_records_failed_verification_result(tmp_path: Path) -> None:
    # Given a registered verification tool returning exit code one
    context = _context(tmp_path)
    result = VerificationToolResult(exit_code=1, stdout="", stderr="failed")

    # When the hook observes the tool ending
    _invoke_hook(context, run_verification, result)

    # Then verification evidence records failure without parsing output
    event = context.ledger.read()[-1]
    assert isinstance(event, VerificationToolEvent)
    assert event.tool == ToolName("run_verification")
    assert event.success is False


def test_hook_rejects_unregistered_tool_without_evidence_credit(tmp_path: Path) -> None:
    # Given an unregistered runtime tool claiming a mutation-shaped result
    context = _context(tmp_path)
    result = MutationToolResult(path="src/x.py", change_kind=ChangeKind.CODE)

    # When the hook observes the tool ending
    _invoke_hook(context, _unregistered_tool, result)

    # Then rejection is observable and mutation/verification indices stay unchanged
    event = context.ledger.read()[-1]
    assert isinstance(event, EvidenceRejectedEvent)
    assert event.tool == ToolName("unregistered_tool")
    assert event.claimed_kind is ToolKind.UNKNOWN
    assert event.reason == "unknown_tool"
    assert context.ledger.state().latest_mutation_index is None
    assert context.ledger.state().latest_successful_verification_index is None


def test_hook_rejects_malformed_mutation_without_evidence_credit(tmp_path: Path) -> None:
    # Given a registered mutation tool returning the wrong result type
    context = _context(tmp_path)

    # When the hook observes the malformed result
    _invoke_hook(context, write_file, "MutationToolResult(path='src/x.py')")

    # Then rejection is observable and no mutation evidence is credited
    event = context.ledger.read()[-1]
    assert isinstance(event, EvidenceRejectedEvent)
    assert event.tool == ToolName("write_file")
    assert event.claimed_kind is ToolKind.MUTATION
    assert event.reason == "malformed_result"
    assert context.ledger.state().latest_mutation_index is None


def test_hook_rejects_malformed_verification_without_evidence_credit(tmp_path: Path) -> None:
    # Given a registered verification tool returning a string that resembles success
    context = _context(tmp_path)

    # When the hook observes the malformed result
    _invoke_hook(context, run_verification, "VerificationToolResult(exit_code=0)")

    # Then rejection is observable and no successful verification is credited
    event = context.ledger.read()[-1]
    assert isinstance(event, EvidenceRejectedEvent)
    assert event.tool == ToolName("run_verification")
    assert event.claimed_kind is ToolKind.VERIFICATION
    assert event.reason == "malformed_result"
    assert context.ledger.state().latest_successful_verification_index is None
