"""Pure bounded correction orchestration and its Agents SDK adapter."""

from dataclasses import dataclass
from typing import Literal, Protocol, assert_never

from agents import (
    Agent,
    GuardrailFunctionOutput,
    Model,
    OutputGuardrailTripwireTriggered,
    RunHooks,
    Runner,
    Tool,
)

from fablized_sol.engine.models import GateAction, HoldoutArm
from fablized_sol.harness.guardrails import GuardrailInfo, verification_gate
from fablized_sol.harness.hooks import LedgerHooks
from fablized_sol.harness.workspace_tools import FablizedContext


@dataclass(frozen=True, slots=True)
class RunRequest:
    """Original task and number of allowed correction attempts."""

    original_prompt: str
    max_gate_retries: int


@dataclass(frozen=True, slots=True)
class AttemptRequest:
    """Input text for one independent SDK run."""

    input_text: str


@dataclass(frozen=True, slots=True)
class AttemptCompleted:
    """One attempt accepted by its configured output guardrails."""

    output: str


@dataclass(frozen=True, slots=True)
class AttemptBlocked:
    """One rejected output with the gate's exact audit information."""

    action: Literal[GateAction.BLOCK, GateAction.EXHAUSTED]
    reason: str
    blocked_output: str


class AttemptExecutor(Protocol):
    """Execution boundary consumed by pure retry orchestration."""

    async def execute(self, request: AttemptRequest) -> AttemptCompleted | AttemptBlocked:
        """Execute one independent attempt."""
        ...


@dataclass(frozen=True, slots=True)
class RunCompleted:
    """Accepted final output and total attempt count."""

    output: str
    attempts: int


@dataclass(frozen=True, slots=True)
class RunExhausted:
    """Last rejected output and reason when no correction can continue."""

    last_output: str
    attempts: int
    reason: str


type RunOutcome = RunCompleted | RunExhausted


def _correction_input(original_prompt: str, reason: str) -> str:
    return f"""ORIGINAL TASK
{original_prompt}

CORRECTION RUN
The workspace may already be modified by a previous attempt. Continue from its current state.
The previous completion was blocked for this exact reason: {reason}
Address that reason and run the narrowest configured verification that proves the task complete.
"""


async def run_fablized(executor: AttemptExecutor, request: RunRequest) -> RunOutcome:
    """Run the original task plus at most the configured correction attempts."""
    input_text = request.original_prompt
    maximum_attempts = request.max_gate_retries + 1
    for attempts in range(1, maximum_attempts + 1):
        outcome = await executor.execute(AttemptRequest(input_text=input_text))
        match outcome:
            case AttemptCompleted(output=output):
                return RunCompleted(output=output, attempts=attempts)
            case AttemptBlocked(action=action, reason=reason, blocked_output=blocked_output):
                match action:
                    case GateAction.EXHAUSTED:
                        return RunExhausted(blocked_output, attempts, reason)
                    case GateAction.BLOCK if attempts == maximum_attempts:
                        return RunExhausted(blocked_output, attempts, reason)
                    case GateAction.BLOCK:
                        input_text = _correction_input(request.original_prompt, reason)
                    case _:
                        assert_never(action)
            case _:
                assert_never(outcome)
    message = "retry loop must return from every configured attempt"
    raise AssertionError(message)


class _GuardrailOutput(Protocol):
    @property
    def output_info(self) -> GuardrailInfo: ...


def _parse_guardrail_info(output: _GuardrailOutput) -> GuardrailInfo:
    return GuardrailInfo.model_validate(output.output_info)


@dataclass(frozen=True, slots=True)
class SdkAttemptExecutor:
    """Translate only SDK output tripwires into pure attempt outcomes."""

    context: FablizedContext
    model: str | Model
    tools: tuple[Tool, ...]
    instructions: str
    hooks: RunHooks[FablizedContext] | None = None

    async def execute(self, request: AttemptRequest) -> AttemptCompleted | AttemptBlocked:
        """Run one agent and retain the SDK guardrail's nested blocked output."""
        match self.context.arm:
            case HoldoutArm.ON:
                output_guardrails = [verification_gate]
            case HoldoutArm.OFF:
                output_guardrails = []
            case _:
                assert_never(self.context.arm)
        agent = Agent[FablizedContext](
            name="fablized-sol",
            model=self.model,
            tools=list(self.tools),
            instructions=self.instructions,
            output_guardrails=output_guardrails,
        )
        try:
            hooks = self.hooks if self.hooks is not None else LedgerHooks()
            result = await Runner.run(
                agent,
                request.input_text,
                context=self.context,
                hooks=hooks,
            )
        except OutputGuardrailTripwireTriggered as error:
            output: GuardrailFunctionOutput = error.guardrail_result.output
            info = _parse_guardrail_info(output)
            match info.decision:
                case GateAction.BLOCK:
                    action: Literal[GateAction.BLOCK, GateAction.EXHAUSTED] = GateAction.BLOCK
                case GateAction.EXHAUSTED:
                    action = GateAction.EXHAUSTED
                case GateAction.ALLOW:
                    raise
                case _:
                    assert_never(info.decision)
            return AttemptBlocked(
                action=action,
                reason=info.reason,
                blocked_output=info.blocked_output,
            )
        return AttemptCompleted(
            output=result.final_output_as(str, raise_if_incorrect_type=True),
        )
