from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, override

import anyio
import pytest
from agents import (
    AgentOutputSchemaBase,
    Handoff,
    Model,
    ModelBehaviorError,
    ModelResponse,
    ModelSettings,
    ModelTracing,
    Tool,
    Usage,
)
from agents.items import TResponseInputItem, TResponseStreamEvent
from openai.types.responses import ResponseOutputMessage, ResponseOutputText
from openai.types.responses.response_prompt_param import ResponsePromptParam

from fablized_sol.engine.events import ClassifyEvent, MutationToolEvent
from fablized_sol.engine.ledger import Ledger
from fablized_sol.engine.models import (
    ChangeKind,
    GateAction,
    HoldoutArm,
    TaskMode,
    ToolKind,
    ToolName,
)
from fablized_sol.harness.registry import ToolRegistry, ToolSpec
from fablized_sol.harness.run import (
    AttemptBlocked,
    AttemptCompleted,
    AttemptRequest,
    RunCompleted,
    RunExhausted,
    RunRequest,
    SdkAttemptExecutor,
    run_fablized,
)
from fablized_sol.harness.workspace_tools import FablizedContext


class _FakeExecutor:
    __slots__: ClassVar[tuple[str, ...]] = ("inputs", "outcomes")

    outcomes: tuple[AttemptCompleted | AttemptBlocked, ...]
    inputs: list[str]

    def __init__(self, outcomes: tuple[AttemptCompleted | AttemptBlocked, ...]) -> None:
        self.outcomes = outcomes
        self.inputs = []

    async def execute(self, request: AttemptRequest) -> AttemptCompleted | AttemptBlocked:
        self.inputs.append(request.input_text)
        return self.outcomes[len(self.inputs) - 1]


def _request(max_gate_retries: int = 2) -> RunRequest:
    return RunRequest(
        original_prompt="Fix the calculation bug.",
        max_gate_retries=max_gate_retries,
    )


def test_runner_retries_with_original_prompt_reason_and_verification_instruction() -> None:
    # Given one blocked attempt followed by a completed correction
    executor = _FakeExecutor(
        outcomes=(
            AttemptBlocked(
                action=GateAction.BLOCK,
                reason="verification missing",
                blocked_output="done",
            ),
            AttemptCompleted(output="verified"),
        )
    )

    # When bounded orchestration runs the task
    result = anyio.run(run_fablized, executor, _request())

    # Then the correction retains all context needed to repair evidence narrowly
    assert result == RunCompleted(output="verified", attempts=2)
    assert executor.inputs[0] == "Fix the calculation bug."
    correction = executor.inputs[1]
    assert correction.startswith("ORIGINAL TASK")
    assert "Fix the calculation bug." in correction
    assert "workspace may already be modified" in correction
    assert "verification missing" in correction
    assert "narrowest configured verification" in correction


def test_runner_returns_sdk_exhausted_without_faking_success() -> None:
    # Given the ledger-driven adapter reports EXHAUSTED on the last attempt
    executor = _FakeExecutor(
        outcomes=(
            AttemptBlocked(GateAction.BLOCK, "verification missing", "first"),
            AttemptBlocked(GateAction.BLOCK, "verification missing", "second"),
            AttemptBlocked(GateAction.EXHAUSTED, "retry limit reached", "last blocked"),
        )
    )

    # When all configured correction attempts are consumed
    result = anyio.run(run_fablized, executor, _request())

    # Then terminal output remains exhausted with the final blocked output and reason
    assert result == RunExhausted(
        last_output="last blocked",
        attempts=3,
        reason="retry limit reached",
    )


def test_runner_budget_exhaustion_cannot_turn_block_into_success() -> None:
    # Given a zero-retry request whose first and only attempt is blocked
    executor = _FakeExecutor(
        outcomes=(AttemptBlocked(GateAction.BLOCK, "verification missing", "unverified"),)
    )

    # When orchestration reaches its local retry budget
    result = anyio.run(run_fablized, executor, _request(max_gate_retries=0))

    # Then it returns exhaustion from the blocked result rather than synthetic completion
    assert result == RunExhausted(
        last_output="unverified",
        attempts=1,
        reason="verification missing",
    )


@dataclass(frozen=True, slots=True)
class _OfflineModel(Model):
    error: ModelBehaviorError | None = None

    @override
    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: ResponsePromptParam | None,
    ) -> ModelResponse:
        del (
            system_instructions,
            input,
            model_settings,
            tools,
            output_schema,
            handoffs,
            tracing,
            previous_response_id,
            conversation_id,
            prompt,
        )
        if self.error is not None:
            raise self.error
        return ModelResponse(
            output=[
                ResponseOutputMessage(
                    id="message-1",
                    content=[
                        ResponseOutputText(
                            annotations=[],
                            logprobs=[],
                            text="claimed complete",
                            type="output_text",
                        )
                    ],
                    role="assistant",
                    status="completed",
                    type="message",
                )
            ],
            usage=Usage(),
            response_id="response-1",
        )

    @override
    def stream_response(
        self,
        system_instructions: str | None,
        input: str | list[TResponseInputItem],
        model_settings: ModelSettings,
        tools: list[Tool],
        output_schema: AgentOutputSchemaBase | None,
        handoffs: list[Handoff],
        tracing: ModelTracing,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: ResponsePromptParam | None,
    ) -> AsyncIterator[TResponseStreamEvent]:
        del (
            system_instructions,
            input,
            model_settings,
            tools,
            output_schema,
            handoffs,
            tracing,
            previous_response_id,
            conversation_id,
            prompt,
        )
        message = "streaming is not used"
        raise AssertionError(message)


def _context(tmp_path: Path, arm: HoldoutArm) -> FablizedContext:
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
        retry_limit=2,
    )


def test_sdk_executor_translates_real_output_tripwire_shape_offline(tmp_path: Path) -> None:
    # Given the real SDK runner, an offline model, and gate-worthy ledger state
    executor = SdkAttemptExecutor(
        context=_context(tmp_path, HoldoutArm.ON),
        model=_OfflineModel(),
        tools=(),
        instructions="Test instructions",
    )

    # When the actual 0.17.4 SDK guardrail raises its tripwire exception
    result = anyio.run(executor.execute, AttemptRequest("finish"))

    # Then the adapter parses the nested output info without an API request
    assert result == AttemptBlocked(
        action=GateAction.BLOCK,
        reason="deep code changes require fresh successful verification",
        blocked_output="claimed complete",
    )


def test_sdk_executor_does_not_translate_other_live_run_errors(tmp_path: Path) -> None:
    # Given an SDK model that raises a non-guardrail typed failure
    error = ModelBehaviorError("live failure")
    executor = SdkAttemptExecutor(
        context=_context(tmp_path, HoldoutArm.ON),
        model=_OfflineModel(error=error),
        tools=(),
        instructions="Test instructions",
    )

    # When the SDK attempt fails before an output guardrail tripwire
    with pytest.raises(ModelBehaviorError, match="live failure"):
        _ = anyio.run(executor.execute, AttemptRequest("finish"))


def test_sdk_executor_off_arm_has_no_output_guardrails(tmp_path: Path) -> None:
    # Given an OFF-arm run whose ledger would otherwise block
    executor = SdkAttemptExecutor(
        context=_context(tmp_path, HoldoutArm.OFF),
        model=_OfflineModel(),
        tools=(),
        instructions="Base instructions",
    )

    # When the real SDK executor completes offline
    result = anyio.run(executor.execute, AttemptRequest("finish"))

    # Then no gate is installed and normal completion is returned
    assert result == AttemptCompleted(output="claimed complete")
