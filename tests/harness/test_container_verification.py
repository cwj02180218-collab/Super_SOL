from collections.abc import Awaitable
from pathlib import Path
from typing import Protocol, final

import anyio
import pytest
from agents import Agent, RunContextWrapper, Usage
from agents.tool_context import ToolContext
from anyio.lowlevel import checkpoint

from fablized_sol.engine.events import VerificationToolEvent
from fablized_sol.engine.ledger import Ledger
from fablized_sol.engine.models import HoldoutArm, ToolKind, ToolName
from fablized_sol.harness.container_runtime import DockerInvocation, ProcessCapture
from fablized_sol.harness.hooks import LedgerHooks
from fablized_sol.harness.registry import ToolRegistry, ToolSpec
from fablized_sol.harness.workspace_tools import (
    FablizedContext,
    VerificationToolResult,
    read_text,
    run_verification,
    run_verification_process,
)

_IMAGE = "ghcr.io/example/verify@sha256:" + "a" * 64


@final
class _FakeRunner:
    """Mutable process fake that captures the security boundary invocation."""

    __slots__ = ("capture", "invocations")

    def __init__(self, capture: ProcessCapture | None = None) -> None:
        self.capture = capture or ProcessCapture(0, b"verified\n", b"")
        self.invocations: list[DockerInvocation] = []

    async def run(self, invocation: DockerInvocation) -> ProcessCapture:
        self.invocations.append(invocation)
        return self.capture


@final
class _ErrorRunner:
    __slots__ = ("denied",)

    def __init__(self, *, denied: bool) -> None:
        self.denied = denied

    async def run(self, invocation: DockerInvocation) -> ProcessCapture:
        del invocation
        message = "docker"
        if self.denied:
            raise PermissionError(message)
        raise FileNotFoundError(message)


@final
class _BlockingRunner:
    def __init__(self, started: anyio.Event, release: anyio.Event) -> None:
        self._started = started
        self._release = release

    async def run(self, invocation: DockerInvocation) -> ProcessCapture:
        del invocation
        self._started.set()
        await self._release.wait()
        return ProcessCapture(0, b"", b"")


@final
class _SlowRunner:
    async def run(self, invocation: DockerInvocation) -> ProcessCapture:
        del invocation
        await anyio.sleep_forever()
        raise AssertionError


class _TypedToolInvoker(Protocol):
    def __call__(
        self,
        context: ToolContext[FablizedContext],
        arguments: str,
        /,
    ) -> Awaitable[VerificationToolResult]: ...


async def _invoke_sdk_tool(
    invoke: _TypedToolInvoker,
    context: ToolContext[FablizedContext],
) -> VerificationToolResult:
    return await invoke(context, "{}")


def _context(tmp_path: Path, runner: _FakeRunner | _ErrorRunner | _SlowRunner) -> FablizedContext:
    return FablizedContext(
        workspace=tmp_path,
        verify_argv=("uv", "run", "pytest", "-q"),
        ledger=Ledger(tmp_path / "ledger.jsonl"),
        registry=ToolRegistry.create(
            (ToolSpec(ToolName("run_verification"), ToolKind.VERIFICATION),)
        ),
        arm=HoldoutArm.ON,
        retry_limit=2,
        verification_image=_IMAGE,
        process_runner=runner,
    )


def test_verification_uses_exit_code_without_output_parsing(tmp_path: Path) -> None:
    context = _context(tmp_path, _FakeRunner(ProcessCapture(1, b"PASS", b"")))

    result = anyio.run(run_verification_process, context)

    assert result == VerificationToolResult(exit_code=1, stdout="PASS", stderr="")
    assert result.success is False


@pytest.mark.parametrize("denied", [False, True])
def test_missing_or_denied_docker_fails_closed(tmp_path: Path, *, denied: bool) -> None:
    context = _context(tmp_path, _ErrorRunner(denied=denied))

    result = anyio.run(run_verification_process, context)

    assert result.exit_code == 127
    assert result.success is False


def test_verification_timeout_is_typed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("fablized_sol.harness.workspace_tools._VERIFICATION_TIMEOUT_SECONDS", 0.01)

    result = anyio.run(run_verification_process, _context(tmp_path, _SlowRunner()))

    assert result == VerificationToolResult(124, "", "verification timed out")


def test_verification_uses_hardened_docker_without_parent_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-cross-boundary")
    runner = _FakeRunner()
    context = _context(tmp_path, runner)

    _ = anyio.run(run_verification_process, context)

    invocation = runner.invocations[0]
    assert invocation.environment == ()
    assert invocation.argv[:5] == ("docker", "run", "--rm", "--network", "none")
    assert invocation.argv[6:8] == ("--cap-drop", "ALL")
    assert invocation.argv[8:10] == ("--security-opt", "no-new-privileges")
    mounts = [
        invocation.argv[index + 1]
        for index, value in enumerate(invocation.argv)
        if value == "--mount"
    ]
    assert mounts == [f"type=bind,src={tmp_path.resolve()},dst=/workspace"]
    assert "OPENAI_API_KEY" not in str(invocation)


@pytest.mark.parametrize("image", [None, "python:3.12"])
def test_missing_or_mutable_verification_image_fails_closed(
    tmp_path: Path,
    image: str | None,
) -> None:
    context = FablizedContext(
        workspace=tmp_path,
        verify_argv=("uv", "run", "pytest"),
        ledger=Ledger(tmp_path / "ledger.jsonl"),
        registry=ToolRegistry.create(()),
        arm=HoldoutArm.ON,
        retry_limit=2,
        verification_image=image,
    )

    result = anyio.run(run_verification_process, context)

    assert result == VerificationToolResult(127, "", "digest-pinned verification image is required")


async def _observe_workspace_serialization(tmp_path: Path) -> list[str]:
    started = anyio.Event()
    release = anyio.Event()
    context = _context(tmp_path, _FakeRunner())
    blocking = FablizedContext(
        workspace=tmp_path,
        verify_argv=context.verify_argv,
        ledger=context.ledger,
        registry=context.registry,
        arm=context.arm,
        retry_limit=2,
        verification_image=_IMAGE,
        process_runner=_BlockingRunner(started, release),
        completions=context.completions,
        workspace_lock=context.workspace_lock,
    )
    observed: list[str] = []

    async def verify() -> None:
        _ = await run_verification_process(blocking)
        observed.append("verification")

    async def read() -> None:
        _ = await read_text(context, "data.txt")
        observed.append("read")

    _ = (tmp_path / "data.txt").write_text("data", encoding="utf-8")
    async with anyio.create_task_group() as task_group:
        _ = task_group.start_soon(verify)
        await started.wait()
        _ = task_group.start_soon(read)
        await checkpoint()
        assert observed == []
        release.set()
    return observed


def test_verification_serializes_workspace_operations(tmp_path: Path) -> None:
    assert anyio.run(_observe_workspace_serialization, tmp_path) == ["verification", "read"]


def test_sdk_verification_tool_preserves_typed_result(tmp_path: Path) -> None:
    context = _context(tmp_path, _FakeRunner())
    sdk_context = ToolContext(
        context=context,
        usage=Usage(),
        tool_name="run_verification",
        tool_call_id="call-1",
        tool_arguments="{}",
    )

    invoke: _TypedToolInvoker = run_verification.on_invoke_tool
    result = anyio.run(_invoke_sdk_tool, invoke, sdk_context)
    anyio.run(
        LedgerHooks().on_tool_end,
        RunContextWrapper(context=context, usage=Usage()),
        Agent[FablizedContext](name="test"),
        run_verification,
        result,
    )

    assert isinstance(result, VerificationToolResult)
    assert result.success is True
    event = context.ledger.read()[-1]
    assert isinstance(event, VerificationToolEvent)
    assert event.sequence == 1
