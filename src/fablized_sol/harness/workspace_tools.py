"""Confined workspace helpers and their OpenAI Agents SDK adapters."""

from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Final, final, override

import anyio
from agents import function_tool
from agents.tool_context import ToolContext
from anyio import to_thread

from fablized_sol.engine.ledger import Ledger
from fablized_sol.engine.models import ChangeKind, HoldoutArm
from fablized_sol.harness.container_runtime import (
    AnyioDockerRunner,
    VerificationProcessRunner,
    build_docker_invocation,
    is_digest_pinned_image,
)
from fablized_sol.harness.registry import ToolRegistry

_DOC_SUFFIXES: Final = frozenset({".md", ".rst", ".txt"})
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


type EvidenceToolResult = MutationToolResult | VerificationToolResult


@final
class CompletionSequencer:
    """Mutable identity map that keeps ordering out of model-visible results."""

    __slots__ = ("_lock", "_next", "_sequences")

    def __init__(self) -> None:
        """Start an empty monotonic completion map."""
        self._lock = Lock()
        self._next = 1
        self._sequences: dict[int, int] = {}

    def record(self, result: EvidenceToolResult) -> None:
        """Assign the next completion sequence to one raw result identity."""
        with self._lock:
            self._sequences[id(result)] = self._next
            self._next += 1

    def consume(self, result: EvidenceToolResult) -> int | None:
        """Consume one sequence exactly once when the mandatory hook runs."""
        with self._lock:
            return self._sequences.pop(id(result), None)


@dataclass(frozen=True, slots=True)
class FablizedContext:
    """Manifest-owned state made available to local SDK function tools."""

    workspace: Path
    verify_argv: tuple[str, ...]
    ledger: Ledger
    registry: ToolRegistry
    arm: HoldoutArm
    retry_limit: int
    verification_image: str | None = None
    process_runner: VerificationProcessRunner = field(
        default_factory=AnyioDockerRunner,
        compare=False,
        repr=False,
    )
    completions: CompletionSequencer = field(
        default_factory=CompletionSequencer,
        compare=False,
        repr=False,
    )
    workspace_lock: anyio.Lock = field(default_factory=anyio.Lock, compare=False, repr=False)


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


def _list_file_paths(context: FablizedContext) -> tuple[str, ...]:
    root = context.workspace.resolve()
    return tuple(
        sorted(
            path.relative_to(root).as_posix()
            for candidate in root.rglob("*")
            if candidate.is_file() and (path := candidate.resolve()).is_relative_to(root)
        )
    )


async def list_file_paths(context: FablizedContext) -> tuple[str, ...]:
    """List confined files while holding the process-local workspace lock."""
    async with context.workspace_lock:
        return await to_thread.run_sync(_list_file_paths, context)


def _read_text(context: FablizedContext, path: str | Path) -> str:
    _, resolved = _resolve_confined(context, path)
    return resolved.read_text(encoding="utf-8")


async def read_text(context: FablizedContext, path: str | Path) -> str:
    """Resolve and read UTF-8 text under the process-local workspace lock."""
    async with context.workspace_lock:
        return await to_thread.run_sync(_read_text, context, path)


def _write_text(
    context: FablizedContext,
    path: str | Path,
    content: str,
) -> MutationToolResult:
    relative, resolved = _resolve_confined(context, path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    _ = resolved.write_text(content, encoding="utf-8")
    change_kind = ChangeKind.DOCS if resolved.suffix.lower() in _DOC_SUFFIXES else ChangeKind.CODE
    return MutationToolResult(path=relative.as_posix(), change_kind=change_kind)


async def write_text(
    context: FablizedContext,
    path: str | Path,
    content: str,
) -> MutationToolResult:
    """Resolve and write UTF-8 text under the process-local workspace lock."""
    async with context.workspace_lock:
        result = await to_thread.run_sync(_write_text, context, path, content)
        context.completions.record(result)
        return result


def _decode(output: bytes) -> str:
    return output.decode("utf-8", errors="replace")


async def run_verification_process(context: FablizedContext) -> VerificationToolResult:
    """Run manifest argv in a hardened container and retain typed evidence."""
    async with context.workspace_lock:
        image = context.verification_image
        if image is None or not is_digest_pinned_image(image):
            result = VerificationToolResult(
                exit_code=127,
                stdout="",
                stderr="digest-pinned verification image is required",
            )
            context.completions.record(result)
            return result
        invocation = build_docker_invocation(context.workspace, image, context.verify_argv)
        try:
            with anyio.fail_after(_VERIFICATION_TIMEOUT_SECONDS):
                capture = await context.process_runner.run(invocation)
        except TimeoutError:
            result = VerificationToolResult(
                exit_code=124,
                stdout="",
                stderr="verification timed out",
            )
            context.completions.record(result)
            return result
        except (FileNotFoundError, PermissionError) as error:
            result = VerificationToolResult(exit_code=127, stdout="", stderr=str(error))
            context.completions.record(result)
            return result
        result = VerificationToolResult(
            exit_code=capture.exit_code,
            stdout=_decode(capture.stdout),
            stderr=_decode(capture.stderr),
        )
        context.completions.record(result)
        return result


@function_tool(failure_error_function=None)
async def list_files(context: ToolContext[FablizedContext]) -> tuple[str, ...]:
    """List all files under the confined workspace."""
    return await list_file_paths(context.context)


@function_tool(failure_error_function=None)
async def read_file(context: ToolContext[FablizedContext], path: str) -> str:
    """Read one UTF-8 file from the confined workspace.

    Args:
        context: SDK tool-call context carrying the trusted workspace manifest.
        path: Workspace-relative file path.
    """
    return await read_text(context.context, path)


@function_tool(failure_error_function=None)
async def write_file(
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
    return await write_text(context.context, path, content)


@function_tool(failure_error_function=None)
async def run_verification(context: ToolContext[FablizedContext]) -> VerificationToolResult:
    """Run the manifest-owned verification command without model arguments."""
    return await run_verification_process(context.context)
