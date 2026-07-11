"""Hardened, secret-free Docker process boundary for verification."""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from secrets import token_hex
from typing import Final, Protocol

import anyio
from anyio import to_thread
from anyio.abc import ByteReceiveStream

_CONTAINER_WORKSPACE: Final = "/workspace"
_OUTPUT_LIMIT_BYTES: Final = 32 * 1024
_PID_LIMIT: Final = "256"
_TMPFS: Final = "/tmp:rw,noexec,nosuid,size=64m"  # noqa: S108 - isolated container path
_IMAGE_PATTERN: Final = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
_MEMORY_LIMIT: Final = "512m"
_CPU_LIMIT: Final = "1.0"


@dataclass(frozen=True, slots=True)
class ProcessCapture:
    """Bounded exit data returned by the verification process seam."""

    exit_code: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True, slots=True)
class DockerInvocation:
    """A complete secret-free Docker invocation."""

    argv: tuple[str, ...]
    container_name: str
    environment: tuple[tuple[str, str], ...] = ()


class VerificationProcessRunner(Protocol):
    """Narrow async seam for running one hardened Docker command."""

    async def run(self, invocation: DockerInvocation) -> ProcessCapture:
        """Run one invocation and return bounded diagnostics."""
        ...


def is_digest_pinned_image(image: str) -> bool:
    """Whether an image reference is immutable and syntactically complete."""
    return _IMAGE_PATTERN.fullmatch(image) is not None


def build_docker_invocation(
    workspace: Path,
    image: str,
    verify_argv: tuple[str, ...],
) -> DockerInvocation:
    """Build fixed Docker policy flags around manifest-owned verification argv."""
    root = workspace.resolve()
    mount = f"type=bind,src={root},dst={_CONTAINER_WORKSPACE}"
    container_name = f"fablized-{token_hex(12)}"
    return DockerInvocation(
        argv=(
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--name",
            container_name,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            _PID_LIMIT,
            "--memory",
            _MEMORY_LIMIT,
            "--cpus",
            _CPU_LIMIT,
            "--tmpfs",
            _TMPFS,
            "--mount",
            mount,
            "--workdir",
            _CONTAINER_WORKSPACE,
            image,
            *verify_argv,
        ),
        container_name=container_name,
    )


def _append_tail(output: bytearray, chunk: bytes) -> None:
    if len(chunk) >= _OUTPUT_LIMIT_BYTES:
        output[:] = chunk[-_OUTPUT_LIMIT_BYTES:]
        return
    overflow = len(output) + len(chunk) - _OUTPUT_LIMIT_BYTES
    if overflow > 0:
        del output[:overflow]
    output.extend(chunk)


async def _drain_tail(stream: ByteReceiveStream | None, output: bytearray) -> None:
    if stream is None:
        return
    async for chunk in stream:
        _append_tail(output, chunk)


class AnyioDockerRunner:
    """Production runner that launches Docker without parent environment data."""

    async def run(self, invocation: DockerInvocation) -> ProcessCapture:
        """Resolve Docker from the parent PATH, then launch without inheriting it."""
        docker = await to_thread.run_sync(_resolve_docker_executable)
        argv = (str(docker), *invocation.argv[1:])
        stdout = bytearray()
        stderr = bytearray()
        exit_code = 127
        completed = False
        try:
            async with (
                await anyio.open_process(
                    argv,
                    stdin=None,
                    env=dict(invocation.environment),
                ) as process,
                anyio.create_task_group() as task_group,
            ):
                _ = task_group.start_soon(_drain_tail, process.stdout, stdout)
                _ = task_group.start_soon(_drain_tail, process.stderr, stderr)
                exit_code = await process.wait()
                completed = True
        finally:
            if not completed:
                with anyio.CancelScope(shield=True):
                    await _force_remove(docker, invocation)
        return ProcessCapture(exit_code, bytes(stdout), bytes(stderr))


def _resolve_docker_executable() -> Path:
    executable = shutil.which("docker")
    if executable is None:
        message = "docker executable was not found on parent PATH"
        raise FileNotFoundError(message)
    resolved = Path(executable).resolve(strict=True)
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        message = f"docker executable is not executable: {resolved}"
        raise PermissionError(message)
    return resolved


async def _force_remove(docker: Path, invocation: DockerInvocation) -> None:
    _ = await anyio.run_process(
        (str(docker), "rm", "-f", invocation.container_name),
        env=dict(invocation.environment),
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
