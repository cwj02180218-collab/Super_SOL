import sys
from collections.abc import Awaitable
from pathlib import Path
from typing import Protocol

import anyio
import pytest
from agents import Usage
from agents.tool_context import ToolContext
from anyio.lowlevel import checkpoint

from fablized_sol.engine.ledger import Ledger
from fablized_sol.engine.models import ChangeKind, HoldoutArm, ToolKind, ToolName
from fablized_sol.harness import workspace_tools
from fablized_sol.harness.registry import ToolRegistry, ToolSpec
from fablized_sol.harness.workspace_tools import (
    FablizedContext,
    MutationToolResult,
    VerificationToolResult,
    WorkspaceEscapeError,
    list_file_paths,
    read_text,
    run_verification,
    run_verification_process,
    write_text,
)


class _TypedToolInvoker(Protocol):
    def __call__(
        self,
        context: ToolContext[FablizedContext],
        arguments: str,
        /,
    ) -> Awaitable[VerificationToolResult]:
        """Invoke the SDK verification tool through its expected typed boundary."""
        ...


async def _invoke_sdk_tool(
    invoke: _TypedToolInvoker,
    context: ToolContext[FablizedContext],
) -> VerificationToolResult:
    return await invoke(context, "{}")


def _registry() -> ToolRegistry:
    return ToolRegistry.create(
        (
            ToolSpec(ToolName("list_files"), ToolKind.READ),
            ToolSpec(ToolName("read_file"), ToolKind.READ),
            ToolSpec(ToolName("write_file"), ToolKind.MUTATION),
            ToolSpec(ToolName("run_verification"), ToolKind.VERIFICATION),
        )
    )


@pytest.fixture
def context(tmp_path: Path) -> FablizedContext:
    return FablizedContext(
        workspace=tmp_path,
        verify_argv=(sys.executable, "-c", "print('verified')"),
        ledger=Ledger(tmp_path / "ledger.jsonl"),
        registry=_registry(),
        arm=HoldoutArm.ON,
        retry_limit=2,
    )


def test_write_file_rejects_parent_escape(context: FablizedContext) -> None:
    # Given a relative path that escapes the workspace
    # When it is written, then confinement rejects it
    with pytest.raises(WorkspaceEscapeError):
        _ = anyio.run(write_text, context, "../outside.py", "unsafe")


def test_read_file_rejects_absolute_path(context: FablizedContext) -> None:
    # Given an absolute path
    # When it is read, then confinement rejects it
    with pytest.raises(WorkspaceEscapeError):
        _ = anyio.run(read_text, context, context.workspace / "outside.py")


def test_write_file_rejects_symlink_escape(context: FablizedContext, tmp_path: Path) -> None:
    # Given a workspace symlink targeting a sibling directory
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (context.workspace / "escape").symlink_to(outside, target_is_directory=True)

    # When a descendant is written, then resolved-path confinement rejects it
    with pytest.raises(WorkspaceEscapeError):
        _ = anyio.run(write_text, context, "escape/outside.py", "unsafe")


@pytest.mark.parametrize(
    ("path", "expected_kind"),
    [
        pytest.param("docs/guide.md", ChangeKind.DOCS),
        pytest.param("docs/guide.rst", ChangeKind.DOCS),
        pytest.param("notes.txt", ChangeKind.DOCS),
        pytest.param("src/main.py", ChangeKind.CODE),
    ],
)
def test_write_file_classifies_changes(
    context: FablizedContext,
    path: str,
    expected_kind: ChangeKind,
) -> None:
    # Given a confined artifact path
    # When text is written
    result = anyio.run(write_text, context, path, "content")

    # Then the typed result retains its path and artifact kind
    assert result == MutationToolResult(path=path, change_kind=expected_kind)


def test_list_files_returns_sorted_relative_files(context: FablizedContext) -> None:
    # Given nested workspace files
    _ = anyio.run(write_text, context, "z.py", "z")
    _ = anyio.run(write_text, context, "src/a.py", "a")

    # When files are listed
    paths = anyio.run(list_file_paths, context)

    # Then only stable workspace-relative paths are returned
    assert paths == ("src/a.py", "z.py")


def test_verification_returns_exit_code_without_output_parsing(
    context: FablizedContext,
) -> None:
    # Given manifest-owned verification argv that prints a success marker
    # When verification runs
    result = anyio.run(run_verification_process, context)

    # Then process status alone determines success
    assert result.exit_code == 0
    assert result.success is True
    assert result.stdout == "verified\n"


def test_verification_failure_is_typed(context: FablizedContext) -> None:
    # Given manifest-owned argv that exits unsuccessfully
    failed_context = FablizedContext(
        workspace=context.workspace,
        verify_argv=(sys.executable, "-c", "raise SystemExit(1)"),
        ledger=context.ledger,
        registry=context.registry,
        arm=context.arm,
        retry_limit=context.retry_limit,
    )

    # When verification runs
    result = anyio.run(run_verification_process, failed_context)

    # Then the typed result derives failure solely from the exit code
    assert result == VerificationToolResult(exit_code=1, stdout="", stderr="")
    assert result.success is False


def test_missing_verification_executable_returns_typed_failure(
    context: FablizedContext,
) -> None:
    # Given a missing manifest-owned executable
    missing_context = FablizedContext(
        workspace=context.workspace,
        verify_argv=("definitely-not-a-real-fablized-sol-executable",),
        ledger=context.ledger,
        registry=context.registry,
        arm=context.arm,
        retry_limit=context.retry_limit,
    )

    # When verification runs
    result = anyio.run(run_verification_process, missing_context)

    # Then infrastructure failure remains a typed verification result
    assert result.exit_code == 127
    assert result.success is False


def test_verification_keeps_only_final_32_kib_of_each_stream(
    context: FablizedContext,
) -> None:
    # Given a process that fills both pipes well beyond their bounded diagnostic tails
    output_size = 2 * 1024 * 1024
    tail_size = 32 * 1024
    noisy_context = FablizedContext(
        workspace=context.workspace,
        verify_argv=(
            sys.executable,
            "-c",
            (
                "import os;"
                f"os.write(1, b'A' * {output_size} + b'B' * {tail_size});"
                f"os.write(2, b'C' * {output_size} + b'D' * {tail_size})"
            ),
        ),
        ledger=context.ledger,
        registry=context.registry,
        arm=context.arm,
        retry_limit=context.retry_limit,
    )

    # When verification concurrently drains stdout and stderr
    result = anyio.run(run_verification_process, noisy_context)

    # Then each retained diagnostic is exactly its final 32 KiB
    assert result.exit_code == 0
    assert result.stdout == "B" * tail_size
    assert result.stderr == "D" * tail_size


def test_verification_timeout_returns_exit_code_124(
    context: FablizedContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a verification process exceeding a short configured test timeout
    monkeypatch.setattr(
        "fablized_sol.harness.workspace_tools._VERIFICATION_TIMEOUT_SECONDS",
        0.01,
    )
    slow_context = FablizedContext(
        workspace=context.workspace,
        verify_argv=(sys.executable, "-c", "import time; time.sleep(60)"),
        ledger=context.ledger,
        registry=context.registry,
        arm=context.arm,
        retry_limit=context.retry_limit,
    )

    # When verification reaches the deadline
    result = anyio.run(run_verification_process, slow_context)

    # Then timeout remains a typed infrastructure failure
    assert result == VerificationToolResult(
        exit_code=124,
        stdout="",
        stderr="verification timed out",
    )


def test_non_executable_verification_returns_exit_code_127(context: FablizedContext) -> None:
    # Given a manifest-owned file without execute permission
    executable = context.workspace / "not-executable"
    _ = executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o600)
    denied_context = FablizedContext(
        workspace=context.workspace,
        verify_argv=(str(executable),),
        ledger=context.ledger,
        registry=context.registry,
        arm=context.arm,
        retry_limit=context.retry_limit,
    )

    # When verification attempts to spawn it
    result = anyio.run(run_verification_process, denied_context)

    # Then permission failure remains a typed infrastructure failure
    assert result.exit_code == 127
    assert result.success is False


async def _observe_workspace_serialization(
    context: FablizedContext,
    monkeypatch: pytest.MonkeyPatch,
) -> list[str]:
    started = anyio.Event()
    release = anyio.Event()
    observed: list[str] = []

    async def capture(_context: FablizedContext) -> tuple[int, bytearray, bytearray]:
        started.set()
        await release.wait()
        return 0, bytearray(), bytearray()

    monkeypatch.setattr(workspace_tools, "_capture_process", capture)

    async def verify() -> None:
        _ = await run_verification_process(context)
        observed.append("verification")

    async def read() -> None:
        _ = await read_text(context, "data.txt")
        observed.append("read")

    async with anyio.create_task_group() as task_group:
        _ = task_group.start_soon(verify)
        await started.wait()
        _ = task_group.start_soon(read)
        await checkpoint()
        assert observed == []
        release.set()

    return observed


def test_verification_serializes_workspace_operations(
    context: FablizedContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given verification that holds the workspace lock until released
    _ = (context.workspace / "data.txt").write_text("data", encoding="utf-8")

    # When a harness read starts while verification owns the workspace
    observed = anyio.run(_observe_workspace_serialization, context, monkeypatch)

    # Then the read completes only after verification releases the process-local lock
    assert observed == ["verification", "read"]


def test_sdk_verification_tool_preserves_typed_result(context: FablizedContext) -> None:
    # Given a real SDK ToolContext for the no-argument verification function tool
    sdk_context = ToolContext(
        context=context,
        usage=Usage(),
        tool_name="run_verification",
        tool_call_id="call-1",
        tool_arguments="{}",
    )

    # When the SDK invokes the decorated tool
    invoke: _TypedToolInvoker = run_verification.on_invoke_tool
    result = anyio.run(_invoke_sdk_tool, invoke, sdk_context)

    # Then the raw hook-facing output remains typed rather than becoming a string
    assert isinstance(result, VerificationToolResult)
    assert result.success is True
