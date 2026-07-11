from pathlib import Path

import anyio
import pytest

from fablized_sol.engine.ledger import Ledger
from fablized_sol.engine.models import ChangeKind, HoldoutArm, ToolKind, ToolName
from fablized_sol.harness.registry import ToolRegistry, ToolSpec
from fablized_sol.harness.workspace_tools import (
    FablizedContext,
    MutationToolResult,
    WorkspaceEscapeError,
    list_file_paths,
    read_text,
    write_text,
)


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
        verify_argv=("uv", "run", "pytest", "-q"),
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
    # Given a confined artifact path, when text is written
    result = anyio.run(write_text, context, path, "content")

    # Then the typed result retains its path and artifact kind
    assert result == MutationToolResult(path=path, change_kind=expected_kind)


def test_list_files_returns_sorted_relative_files(context: FablizedContext) -> None:
    # Given nested workspace files
    _ = anyio.run(write_text, context, "z.py", "z")
    _ = anyio.run(write_text, context, "src/a.py", "a")

    # When files are listed, then only stable workspace-relative paths are returned
    assert anyio.run(list_file_paths, context) == ("src/a.py", "z.py")
