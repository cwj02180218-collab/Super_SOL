from pathlib import Path
from typing import ClassVar

import anyio
import pytest
from pydantic import BaseModel, ConfigDict, TypeAdapter

from fablized_sol.harness import container_runtime
from fablized_sol.harness.container_runtime import (
    AnyioDockerRunner,
    DockerInvocation,
    build_docker_invocation,
)

_IMAGE = "ghcr.io/example/verify@sha256:" + "a" * 64


class _Call(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    executable: str
    argv: tuple[str, ...]
    env: dict[str, str]


_CALL = TypeAdapter[_Call](_Call)


def _write_fake_docker(tmp_path: Path) -> tuple[Path, Path]:
    executable = tmp_path / "docker"
    log = tmp_path / "calls.jsonl"
    script = f"""#!/usr/bin/python3
import json
import os
import sys
import time

with open({str(log)!r}, "a", encoding="utf-8") as stream:
    record = {{"executable": sys.argv[0], "argv": sys.argv[1:], "env": dict(os.environ)}}
    stream.write(json.dumps(record) + "\\n")
if sys.argv[1] == "run" and "--sleep" in sys.argv:
    time.sleep(30)
if sys.argv[1] == "rm" and os.path.exists({str(tmp_path / "hang-cleanup")!r}):
    time.sleep(30)
if sys.argv[1] == "rm" and os.path.exists({str(tmp_path / "fail-cleanup")!r}):
    os.write(2, b"X" * 50000 + b"cleanup failed")
    raise SystemExit(9)
print("captured")
"""
    _ = executable.write_text(script, encoding="utf-8")
    executable.chmod(0o700)
    return executable, log


def _read_calls(path: Path) -> list[_Call]:
    return [_CALL.validate_json(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_docker_invocation_is_named_immutable_and_resource_capped(tmp_path: Path) -> None:
    # Given a trusted workspace, image digest, and manifest argv
    invocation = build_docker_invocation(tmp_path, _IMAGE, ("pytest", "-q"))
    next_invocation = build_docker_invocation(tmp_path, _IMAGE, ("pytest", "-q"))

    # When the hardened argv is inspected, then lifecycle and resource limits are fixed
    assert "--pull=never" in invocation.argv
    assert invocation.argv[invocation.argv.index("--name") + 1] == invocation.container_name
    assert invocation.container_name.startswith("fablized-")
    assert invocation.container_name != next_invocation.container_name
    assert invocation.argv[invocation.argv.index("--memory") + 1] == "512m"
    assert invocation.argv[invocation.argv.index("--cpus") + 1] == "1.0"


def test_production_runner_resolves_parent_path_but_clears_child_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given Docker exists only on the parent PATH alongside a parent API secret
    executable, log = _write_fake_docker(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "parent-secret")
    invocation = build_docker_invocation(tmp_path, _IMAGE, ("pytest", "-q"))

    # When the production process runner launches it
    capture = anyio.run(AnyioDockerRunner().run, invocation)

    # Then the absolute executable is found while no parent environment crosses
    calls = _read_calls(log)
    assert capture.exit_code == 0
    assert calls[0].argv == invocation.argv[1:]
    assert calls[0].executable == str(executable)
    assert "PATH" not in calls[0].env
    assert "OPENAI_API_KEY" not in calls[0].env


async def _cancel_run(invocation: DockerInvocation) -> None:
    with anyio.fail_after(0.1):
        _ = await AnyioDockerRunner().run(invocation)


def test_cancelled_client_force_removes_named_container(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a fake Docker run that outlives the client timeout
    executable, log = _write_fake_docker(tmp_path)
    monkeypatch.setenv("PATH", str(tmp_path))
    invocation = build_docker_invocation(tmp_path, _IMAGE, ("--sleep",))

    # When the client is cancelled
    with pytest.raises(TimeoutError):
        anyio.run(_cancel_run, invocation)

    # Then shielded cleanup uses the same absolute runtime and exact generated name
    calls = _read_calls(log)
    assert calls[-1].argv == ("rm", "-f", invocation.container_name)
    assert calls[-1].executable == str(executable)
    assert "PATH" not in calls[-1].env
    assert "OPENAI_API_KEY" not in calls[-1].env


def test_hanging_cleanup_raises_typed_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given both the run and its forced cleanup outlive their independent deadlines
    _, _ = _write_fake_docker(tmp_path)
    _ = (tmp_path / "hang-cleanup").touch()
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(container_runtime, "_CLEANUP_TIMEOUT_SECONDS", 0.05)
    invocation = build_docker_invocation(tmp_path, _IMAGE, ("--sleep",))

    # When the outer client is cancelled, then cleanup cannot hang indefinitely
    with pytest.raises(container_runtime.DockerCleanupTimeoutError) as captured:
        anyio.run(_cancel_run, invocation)
    assert captured.value.container_name == invocation.container_name


def test_nonzero_cleanup_raises_typed_bounded_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given cleanup emits excessive diagnostics and exits unsuccessfully
    _, _ = _write_fake_docker(tmp_path)
    _ = (tmp_path / "fail-cleanup").touch()
    monkeypatch.setenv("PATH", str(tmp_path))
    invocation = build_docker_invocation(tmp_path, _IMAGE, ("--sleep",))

    # When outer cancellation triggers cleanup, then the failure remains observable
    with pytest.raises(container_runtime.DockerCleanupError) as captured:
        anyio.run(_cancel_run, invocation)
    assert captured.value.container_name == invocation.container_name
    assert captured.value.exit_code == 9
    assert len(captured.value.stderr.encode()) <= 32 * 1024
    assert captured.value.stderr.endswith("cleanup failed")
