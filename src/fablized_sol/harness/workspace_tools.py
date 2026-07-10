"""Confined workspace helpers and their OpenAI Agents SDK adapters."""

from dataclasses import dataclass
from pathlib import Path
from typing import Final, override

import anyio
from agents import function_tool
from agents.tool_context import ToolContext

from fablized_sol.engine.ledger import Ledger
from fablized_sol.engine.models import ChangeKind, HoldoutArm
from fablized_sol.harness.registry import ToolRegistry

_DOC_SUFFIXES: Final = frozenset({".md", ".rst", ".txt"})
_OUTPUT_LIMIT_BYTES: Final = 32 * 1024
_VERIFICATION_TIMEOUT_SECONDS: Final = 120


@dataclass(frozen=True, slots=True)
class VerificationToolResult:
    """Typed process outcome whose status is independent of output text."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        """Whether the verification process exited successfully."""
        return self.exit_code == 0


@dataclass(frozen=True, slots=True)
class MutationToolResult:
    """Typed mutation evidence returned by the confined writer."""

    path: str
    change_kind: ChangeKind


@dataclass(frozen=True, slots=True)
class FablizedContext:
    """Manifest-owned state made available to local SDK function tools."""

    workspace: Path
    verify_argv: tuple[str, ...]
    ledger: Ledger
    registry: ToolRegistry
    arm: HoldoutArm
    retry_limit: int


@dataclass(frozen=True, slots=True)
class WorkspaceEscapeError(Exception):
    """A requested path resolves outside the configured workspace."""

    path: str

    @override
    def __str__(self) -> str:
        return f"path escapes workspace: {self.path}"


def _resolve_confined(context: FablizedContext, path: str | Path) -> tuple[Path, Path]:
    relative = Path(path)
    if relative.is_absolute():
        raise WorkspaceEscapeError(path=str(path))
    root = context.workspace.resolve()
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise WorkspaceEscapeError(path=str(path))
    return relative, resolved


def list_file_paths(context: FablizedContext) -> tuple[str, ...]:
    """List confined files as stable workspace-relative POSIX paths."""
    root = context.workspace.resolve()
    return tuple(
        sorted(
            path.relative_to(root).as_posix()
            for candidate in root.rglob("*")
            if candidate.is_file() and (path := candidate.resolve()).is_relative_to(root)
        )
    )


def read_text(context: FablizedContext, path: str | Path) -> str:
    """Read UTF-8 text only after resolving the path inside the workspace."""
    _, resolved = _resolve_confined(context, path)
    return resolved.read_text(encoding="utf-8")


def write_text(context: FablizedContext, path: str | Path, content: str) -> MutationToolResult:
    """Write confined UTF-8 text and classify the changed artifact."""
    relative, resolved = _resolve_confined(context, path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    _ = resolved.write_text(content, encoding="utf-8")
    change_kind = ChangeKind.DOCS if resolved.suffix.lower() in _DOC_SUFFIXES else ChangeKind.CODE
    return MutationToolResult(path=relative.as_posix(), change_kind=change_kind)


def _decode_tail(output: bytes) -> str:
    return output[-_OUTPUT_LIMIT_BYTES:].decode("utf-8", errors="replace")


async def run_verification_process(context: FablizedContext) -> VerificationToolResult:
    """Run only manifest-owned argv and preserve a bounded typed process result."""
    try:
        with anyio.fail_after(_VERIFICATION_TIMEOUT_SECONDS):
            completed = await anyio.run_process(
                context.verify_argv,
                cwd=context.workspace,
                check=False,
            )
    except TimeoutError:
        return VerificationToolResult(exit_code=124, stdout="", stderr="verification timed out")
    except (FileNotFoundError, PermissionError) as error:
        return VerificationToolResult(exit_code=127, stdout="", stderr=str(error))
    return VerificationToolResult(
        exit_code=completed.returncode,
        stdout=_decode_tail(completed.stdout),
        stderr=_decode_tail(completed.stderr),
    )


@function_tool(failure_error_function=None)
def list_files(context: ToolContext[FablizedContext]) -> tuple[str, ...]:
    """List all files under the confined workspace."""
    return list_file_paths(context.context)


@function_tool(failure_error_function=None)
def read_file(context: ToolContext[FablizedContext], path: str) -> str:
    """Read one UTF-8 file from the confined workspace.

    Args:
        context: SDK tool-call context carrying the trusted workspace manifest.
        path: Workspace-relative file path.
    """
    return read_text(context.context, path)


@function_tool(failure_error_function=None)
def write_file(
    context: ToolContext[FablizedContext],
    path: str,
    content: str,
) -> MutationToolResult:
    """Write one UTF-8 file inside the confined workspace.

    Args:
        context: SDK tool-call context carrying the trusted workspace manifest.
        path: Workspace-relative file path.
        content: Complete replacement file content.
    """
    return write_text(context.context, path, content)


@function_tool(failure_error_function=None)
async def run_verification(context: ToolContext[FablizedContext]) -> VerificationToolResult:
    """Run the manifest-owned verification command without model arguments."""
    return await run_verification_process(context.context)
