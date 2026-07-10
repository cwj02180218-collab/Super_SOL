"""Typed OpenAI Agents SDK hook adapters for mandatory ledger evidence."""

from typing import Protocol, assert_never, final, override

from agents import Agent, ModelResponse, RunContextWrapper, RunHooks, Tool

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


class ModelResponseObserver(Protocol):
    """Narrow extension point for out-of-band response measurement."""

    def observe(self, response: ModelResponse) -> None:
        """Observe one completed model response without controlling SDK hooks."""
        ...


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
        result: object,
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


@final
class ObservedLedgerHooks(LedgerHooks):
    """Retain ledger behavior while forwarding only model responses."""

    __slots__ = ("_observer",)

    def __init__(self, observer: ModelResponseObserver) -> None:
        """Compose an observer under the mandatory ledger hook."""
        self._observer = observer

    @override
    async def on_llm_end(
        self,
        context: RunContextWrapper[FablizedContext],
        agent: Agent[FablizedContext],
        response: ModelResponse,
    ) -> None:
        del context, agent
        self._observer.observe(response)
