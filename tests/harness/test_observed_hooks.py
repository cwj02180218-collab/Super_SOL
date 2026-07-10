from dataclasses import fields
from pathlib import Path
from typing import final

import anyio
from agents import Agent, ModelResponse, RunContextWrapper, Usage

from fablized_sol.engine.ledger import Ledger
from fablized_sol.engine.models import HoldoutArm
from fablized_sol.harness.hooks import LedgerHooks, ObservedLedgerHooks
from fablized_sol.harness.registry import ToolRegistry
from fablized_sol.harness.run import SdkAttemptExecutor
from fablized_sol.harness.workspace_tools import FablizedContext


@final
class _UsageObserver:
    input_tokens: int

    def __init__(self) -> None:
        self.input_tokens = 0

    def observe(self, response: ModelResponse) -> None:
        self.input_tokens += response.usage.input_tokens


def _context(tmp_path: Path) -> FablizedContext:
    return FablizedContext(
        workspace=tmp_path,
        verify_argv=("true",),
        ledger=Ledger(tmp_path / "ledger.jsonl"),
        registry=ToolRegistry.create(()),
        arm=HoldoutArm.ON,
        retry_limit=2,
    )


def test_observed_hooks_extend_mandatory_ledger_hooks(tmp_path: Path) -> None:
    # Given an out-of-band model-response observer
    observer = _UsageObserver()
    hooks = ObservedLedgerHooks(observer)
    response = ModelResponse(
        output=[],
        usage=Usage(input_tokens=13, output_tokens=2, total_tokens=15),
        response_id="offline",
    )

    # When the composed SDK hook receives a model response
    anyio.run(
        hooks.on_llm_end,
        RunContextWrapper(context=_context(tmp_path), usage=Usage()),
        Agent[FablizedContext](name="offline"),
        response,
    )

    # Then ledger tool observation remains inherited and usage is observed separately
    assert isinstance(hooks, LedgerHooks)
    assert ObservedLedgerHooks.on_tool_end is LedgerHooks.on_tool_end
    assert observer.input_tokens == 13


def test_sdk_executor_does_not_expose_replaceable_run_hooks() -> None:
    # Given the public SDK executor dataclass
    field_names = {field.name for field in fields(SdkAttemptExecutor)}

    # When its extension points are inspected
    # Then arbitrary SDK hooks cannot replace the executor-owned ledger hook
    assert "hooks" not in field_names
    assert "response_observer" in field_names
