"""Typed construction and measurement for one live evaluation session."""

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final, final

from agents import ModelResponse, Tool
from anyio import to_thread

from fablized_sol.engine.events import (
    ClassifyEvent,
    EvidenceRejectedEvent,
    GateFireEvent,
    MutationToolEvent,
    ReadToolEvent,
    VerificationToolEvent,
)
from fablized_sol.engine.ledger import Ledger
from fablized_sol.engine.models import HoldoutArm, SessionId, ToolKind, ToolName
from fablized_sol.eval.manifest import TaskSpec
from fablized_sol.harness.registry import ToolRegistry, ToolSpec
from fablized_sol.harness.router import InstructionRequest, build_instructions
from fablized_sol.harness.run import (
    RunCompleted,
    RunExhausted,
    RunRequest,
    SdkAttemptExecutor,
    run_fablized,
)
from fablized_sol.harness.workspace_tools import (
    FablizedContext,
    list_files,
    read_file,
    run_verification,
    write_file,
)
from fablized_sol.measure.shadow import RunFinished, RunStatus

_BASE_INSTRUCTIONS: Final = (
    "Inspect and modify only the provided workspace with the available tools. "
    "Use the configured verification tool to check the result before finishing."
)
_TOOLS: Final[tuple[Tool, ...]] = (list_files, read_file, write_file, run_verification)


@dataclass(frozen=True, slots=True)
class PlannedRun:
    """One immutable task/model/arm assignment."""

    task: TaskSpec
    model: str
    session_id: SessionId
    arm: HoldoutArm


@final
class UsageObserver:
    """Accumulate model-response token usage across bounded attempts."""

    __slots__ = ("input_tokens", "output_tokens")
    input_tokens: int
    output_tokens: int

    def __init__(self) -> None:
        """Start a zeroed response-usage accumulator."""
        self.input_tokens = 0
        self.output_tokens = 0

    def observe(self, response: ModelResponse) -> None:
        """Add one SDK response's tokens to the out-of-band totals."""
        self.input_tokens += response.usage.input_tokens
        self.output_tokens += response.usage.output_tokens


@dataclass(frozen=True, slots=True)
class LiveRun:
    """Filesystem and metric state owned by one started session."""

    planned: PlannedRun
    workspace: Path
    ledger: Ledger
    usage: UsageObserver
    started: float


def create_live_run(planned: PlannedRun, run_root: Path) -> LiveRun:
    """Create session-local paths without touching the fixture input."""
    return LiveRun(
        planned=planned,
        workspace=run_root / "workspaces" / planned.session_id,
        ledger=Ledger(run_root / "ledgers" / f"{planned.session_id}.jsonl"),
        usage=UsageObserver(),
        started=time.monotonic(),
    )


def _tool_registry() -> ToolRegistry:
    registry = ToolRegistry.create(
        (
            ToolSpec(ToolName("list_files"), ToolKind.READ),
            ToolSpec(ToolName("read_file"), ToolKind.READ),
            ToolSpec(ToolName("write_file"), ToolKind.MUTATION),
            ToolSpec(ToolName("run_verification"), ToolKind.VERIFICATION),
        )
    )
    registry.validate_exposed(tuple(ToolName(tool.name) for tool in _TOOLS))
    return registry


async def execute_live(run: LiveRun, max_gate_retries: int) -> RunCompleted | RunExhausted:
    """Copy one fixture, route once, and invoke the bounded runner."""
    _ = await to_thread.run_sync(shutil.copytree, run.planned.task.fixture, run.workspace)
    bundle = build_instructions(
        InstructionRequest(
            prompt=run.planned.task.prompt,
            base=_BASE_INSTRUCTIONS,
            arm=run.planned.arm,
        )
    )
    run.ledger.append(
        ClassifyEvent(
            mode=bundle.classification.mode,
            risk_flags=bundle.classification.risk_flags,
        )
    )
    context = FablizedContext(
        workspace=run.workspace,
        verify_argv=run.planned.task.verify_argv,
        ledger=run.ledger,
        registry=_tool_registry(),
        arm=run.planned.arm,
        retry_limit=max_gate_retries,
    )
    executor = SdkAttemptExecutor(
        context=context,
        model=run.planned.model,
        tools=_TOOLS,
        instructions=bundle.instructions,
        response_observer=run.usage,
    )
    return await run_fablized(
        executor,
        RunRequest(
            original_prompt=run.planned.task.prompt,
            max_gate_retries=max_gate_retries,
        ),
    )


def _ledger_counts(ledger: Ledger) -> tuple[int, int, int]:
    tool_calls = 0
    failed_verifications = 0
    gate_blocks = 0
    for event in ledger.read():
        match event:
            case VerificationToolEvent(success=success):
                tool_calls += 1
                failed_verifications += int(not success)
            case ReadToolEvent() | MutationToolEvent() | EvidenceRejectedEvent():
                tool_calls += 1
            case GateFireEvent():
                gate_blocks += 1
            case ClassifyEvent():
                pass
    return tool_calls, failed_verifications, gate_blocks


def finished_event(run: LiveRun, status: RunStatus, error_type: str | None) -> RunFinished:
    """Build one terminal event from ledger and response usage evidence."""
    tool_calls, failed_verifications, gate_blocks = _ledger_counts(run.ledger)
    return RunFinished(
        session_id=run.planned.session_id,
        arm=run.planned.arm,
        model=run.planned.model,
        status=status,
        wall_time_seconds=time.monotonic() - run.started,
        tool_calls=tool_calls,
        failed_verifications=failed_verifications,
        gate_blocks=gate_blocks,
        input_tokens=run.usage.input_tokens,
        output_tokens=run.usage.output_tokens,
        final_defect_found=None,
        error_type=error_type,
    )


def empty_finished_event(
    planned: PlannedRun,
    status: RunStatus,
    error_type: str,
) -> RunFinished:
    """Retain a terminal outcome when a planned run never starts."""
    return RunFinished(
        session_id=planned.session_id,
        arm=planned.arm,
        model=planned.model,
        status=status,
        wall_time_seconds=0,
        tool_calls=0,
        failed_verifications=0,
        gate_blocks=0,
        input_tokens=0,
        output_tokens=0,
        final_defect_found=None,
        error_type=error_type,
    )
