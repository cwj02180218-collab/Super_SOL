"""Typed OpenAI Agents SDK hook adapter for evidence ledger events."""

from typing import assert_never, override

from agents import Agent, RunContextWrapper, RunHooks, Tool

from fablized_sol.engine.events import (
    EvidenceRejectedEvent,
    MutationToolEvent,
    ReadToolEvent,
    VerificationToolEvent,
)
from fablized_sol.engine.models import ToolKind, ToolName
from fablized_sol.harness.workspace_tools import (
    FablizedContext,
    MutationToolResult,
    VerificationToolResult,
)


def _mutation_event(name: ToolName, result: MutationToolResult) -> MutationToolEvent:
    return MutationToolEvent(
        tool=name,
        path=result.path,
        change_kind=result.change_kind,
    )


def _verification_event(
    name: ToolName,
    result: VerificationToolResult,
) -> VerificationToolEvent:
    return VerificationToolEvent(tool=name, success=result.success)


def _rejected_result(name: ToolName, kind: ToolKind) -> EvidenceRejectedEvent:
    return EvidenceRejectedEvent(tool=name, claimed_kind=kind, reason="malformed_result")


class LedgerHooks(RunHooks[FablizedContext]):
    """Append evidence only for registered tools with exact typed outcomes."""

    @override
    async def on_tool_end(
        self,
        context: RunContextWrapper[FablizedContext],
        agent: Agent[FablizedContext],
        tool: Tool,
        result: object,  # noqa: OBJECT_OK
    ) -> None:
        """Adapt the SDK's raw runtime result without string inference."""
        del agent
        name = ToolName(tool.name)
        kind = context.context.registry.kind_for(name)
        match kind:
            case ToolKind.READ:
                event = ReadToolEvent(tool=name)
            case ToolKind.MUTATION:
                event = (
                    _mutation_event(name, result)
                    if isinstance(result, MutationToolResult)
                    else _rejected_result(name, ToolKind.MUTATION)
                )
            case ToolKind.VERIFICATION:
                event = (
                    _verification_event(name, result)
                    if isinstance(result, VerificationToolResult)
                    else _rejected_result(name, ToolKind.VERIFICATION)
                )
            case ToolKind.UNKNOWN:
                event = EvidenceRejectedEvent(
                    tool=name,
                    claimed_kind=ToolKind.UNKNOWN,
                    reason="unknown_tool",
                )
            case _:
                assert_never(kind)
        context.context.ledger.append(event)
