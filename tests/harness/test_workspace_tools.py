import sys
from collections.abc import Awaitable
from pathlib import Path
from typing import Protocol

import anyio
import pytest
from agents import Usage
from agents.tool_context import ToolContext
from openai.types.responses.response_usage import InputTokensDetails, OutputTokensDetails

from fablized_sol.engine.ledger import Ledger
from fablized_sol.engine.models import ChangeKind, HoldoutArm, ToolKind, ToolName
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
        _ = write_text(context, "../outside.py", "unsafe")


def test_read_file_rejects_absolute_path(context: FablizedContext) -> None:
    # Given an absolute path
    # When it is read, then confinement rejects it
    with pytest.raises(WorkspaceEscapeError):
        _ = read_text(context, context.workspace / "outside.py")


def test_write_file_rejects_symlink_escape(context: FablizedContext, tmp_path: Path) -> None:
    # Given a workspace symlink targeting a sibling directory
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (context.workspace / "escape").symlink_to(outside, target_is_directory=True)

    # When a descendant is written, then resolved-path confinement rejects it
    with pytest.raises(WorkspaceEscapeError):
        _ = write_text(context, "escape/outside.py", "unsafe")


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
    result = write_text(context, path, "content")

    # Then the typed result retains its path and artifact kind
    assert result == MutationToolResult(path=path, change_kind=expected_kind)


def test_list_files_returns_sorted_relative_files(context: FablizedContext) -> None:
    # Given nested workspace files
    _ = write_text(context, "z.py", "z")
    _ = write_text(context, "src/a.py", "a")

    # When files are listed
    paths = list_file_paths(context)

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


def test_sdk_verification_tool_preserves_typed_result(context: FablizedContext) -> None:
    # Given a real SDK ToolContext for the no-argument verification function tool
    sdk_context = ToolContext(
        context=context,
        usage=Usage(
            input_tokens_details=InputTokensDetails(cache_write_tokens=0, cached_tokens=0),
            output_tokens_details=OutputTokensDetails(reasoning_tokens=0),
        ),
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
