from pathlib import Path
from typing import final

import anyio

from fablized_sol.eval.grader import (
    GraderFailed,
    GraderInfrastructureError,
    run_out_of_band_grader,
)
from fablized_sol.harness.container_runtime import DockerInvocation, ProcessCapture

_GRADER_IMAGE = "ghcr.io/example/grader@sha256:" + "b" * 64


@final
class _CaptureRunner:
    def __init__(self, exit_code: int) -> None:
        self.exit_code = exit_code
        self.invocations: list[DockerInvocation] = []

    async def run(self, invocation: DockerInvocation) -> ProcessCapture:
        self.invocations.append(invocation)
        return ProcessCapture(self.exit_code, b"private grader output", b"private failure")


def test_out_of_band_grader_returns_only_status_from_separate_image(tmp_path: Path) -> None:
    # Given a grader process whose diagnostics must never return to the model
    runner = _CaptureRunner(exit_code=1)

    # When grading runs after the model turn
    result = anyio.run(
        run_out_of_band_grader,
        tmp_path,
        _GRADER_IMAGE,
        ("pytest", "-q", "/opt/grader"),
        runner,
    )

    # Then only a boolean crosses the boundary and the grader uses its own image
    assert isinstance(result, GraderFailed)
    invocation = runner.invocations[0]
    assert invocation.environment == ()
    assert _GRADER_IMAGE in invocation.argv
    assert "/opt/grader" in invocation.argv
    mount = invocation.argv[invocation.argv.index("--mount") + 1]
    assert mount.endswith(",readonly")
    assert invocation.argv.count("--cap-add") == 2


def test_out_of_band_grader_separates_infrastructure_exit(tmp_path: Path) -> None:
    # Given a process exit that is not pytest pass or test failure
    runner = _CaptureRunner(exit_code=2)

    # When the grader interprets the terminal status
    result = anyio.run(
        run_out_of_band_grader,
        tmp_path,
        _GRADER_IMAGE,
        ("pytest", "-q", "/opt/grader"),
        runner,
    )

    # Then benchmark infrastructure failure remains a distinct typed outcome
    assert result == GraderInfrastructureError(exit_code=2)
