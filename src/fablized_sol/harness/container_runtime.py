"""Hardened, secret-free Docker process boundary for verification."""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from secrets import token_hex
from typing import Final, Protocol, final, override

import anyio
from anyio import to_thread
from anyio.abc import ByteReceiveStream

_CONTAINER_WORKSPACE: Final = "/workspace"
_OUTPUT_LIMIT_BYTES: Final = 32 * 1024
_PID_LIMIT: Final = "256"
_TMPFS: Final = "/tmp:rw,noexec,nosuid,size=64m"  # noqa: S108  # nosec B108
_IMAGE_PATTERN: Final = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
_MEMORY_LIMIT: Final = "512m"
_CPU_LIMIT: Final = "1.0"
_CLEANUP_TIMEOUT_SECONDS: Final = 10.0
_PREFLIGHT_TIMEOUT_SECONDS: Final = 30.0


@final
class DockerCleanupTimeoutError(Exception):
    """A forced container removal exceeded its independent deadline."""

    __slots__ = ("container_name",)

    def __init__(self, container_name: str) -> None:
        """Retain the container identity for the evaluation boundary."""
        self.container_name = container_name
        super().__init__(container_name)

    @override
    def __str__(self) -> str:
        return f"docker cleanup timed out for container {self.container_name}"


@final
class DockerCleanupError(Exception):
    """A forced container removal failed with bounded diagnostics."""

    __slots__ = ("container_name", "exit_code", "stderr")

    container_name: str
    exit_code: int
    stderr: str

    def __init__(self, container_name: str, exit_code: int, stderr: str) -> None:
        """Retain typed bounded cleanup diagnostics."""
        self.container_name = container_name
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(container_name, exit_code, stderr)

    @override
    def __str__(self) -> str:
        return (
            f"docker cleanup failed for container {self.container_name} "
            f"with exit code {self.exit_code}: {self.stderr}"
        )


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


def preflight_local_images(images: tuple[str, ...]) -> bool:
    """Confirm every immutable image exists locally before a model run begins."""
    try:
        docker = _resolve_docker_executable()
        environment = {
            key: value
            for key in ("HOME", "DOCKER_CONFIG", "DOCKER_CONTEXT", "DOCKER_HOST")
            if (value := os.environ.get(key)) is not None
        }
        for image in images:
            completed = subprocess.run(  # noqa: S603
                (str(docker), "image", "inspect", image),
                check=False,
                env=environment,
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                timeout=_PREFLIGHT_TIMEOUT_SECONDS,
            )
            if completed.returncode != 0:
                return False
    except (OSError, subprocess.TimeoutExpired):
        return False
    return True


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


def build_grader_invocation(
    workspace: Path,
    image: str,
    grader_argv: tuple[str, ...],
) -> DockerInvocation:
    """Build a read-only grader container with one-way privilege dropping."""
    root = workspace.resolve()
    mount = f"type=bind,src={root},dst={_CONTAINER_WORKSPACE},readonly"
    container_name = f"fablized-grader-{token_hex(12)}"
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
            "--cap-add",
            "SETUID",
            "--cap-add",
            "SETGID",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "0:0",
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
            *grader_argv,
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
    stderr = bytearray()
    exit_code = 127
    try:
        with anyio.fail_after(_CLEANUP_TIMEOUT_SECONDS):
            async with (
                await anyio.open_process(
                    (str(docker), "rm", "-f", invocation.container_name),
                    env=dict(invocation.environment),
                    stdin=None,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                ) as process,
                anyio.create_task_group() as task_group,
            ):
                _ = task_group.start_soon(_drain_tail, process.stderr, stderr)
                exit_code = await process.wait()
    except TimeoutError as error:
        raise DockerCleanupTimeoutError(invocation.container_name) from error
    if exit_code != 0:
        raise DockerCleanupError(
            container_name=invocation.container_name,
            exit_code=exit_code,
            stderr=stderr.decode("utf-8", errors="replace"),
        )
