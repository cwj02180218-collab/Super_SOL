"""Ledger-backed output guardrail for completion claims."""

from typing import ClassVar, assert_never

from agents import Agent, GuardrailFunctionOutput, RunContextWrapper, output_guardrail
from pydantic import BaseModel, ConfigDict

from fablized_sol.engine.events import GateFireEvent
from fablized_sol.engine.models import GateAction
from fablized_sol.engine.verify_state import decide_stop
from fablized_sol.harness.workspace_tools import FablizedContext


class GuardrailInfo(BaseModel):
    """Typed output retained when the SDK stops a completion claim."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    decision: GateAction
    reason: str
    blocked_output: str


@output_guardrail
async def verification_gate(
    ctx: RunContextWrapper[FablizedContext],
    agent: Agent[FablizedContext],
    output: str,
) -> GuardrailFunctionOutput:
    """Decide completion from ledger evidence without another model call."""
    del agent
    decision = decide_stop(ctx.context.ledger.state(), ctx.context.arm, ctx.context.retry_limit)
    match decision.action:
        case GateAction.ALLOW:
            tripwire_triggered = False
        case GateAction.BLOCK | GateAction.EXHAUSTED:
            ctx.context.ledger.append(GateFireEvent(reason=decision.reason))
            tripwire_triggered = True
        case _:
            assert_never(decision.action)
    return GuardrailFunctionOutput(
        output_info=GuardrailInfo(
            decision=decision.action,
            reason=decision.reason,
            blocked_output=output,
        ),
        tripwire_triggered=tripwire_triggered,
    )
