"""Out-of-band grader boundary kept outside model-callable tools."""

from dataclasses import dataclass
from pathlib import Path
from typing import Final

import anyio

from fablized_sol.harness.container_runtime import (
    VerificationProcessRunner,
    build_grader_invocation,
)

_GRADER_TIMEOUT_SECONDS: Final = 120


@dataclass(frozen=True, slots=True)
class GraderPassed:
    """The grader completed and all checks passed."""


@dataclass(frozen=True, slots=True)
class GraderFailed:
    """The grader completed and found a task defect."""


@dataclass(frozen=True, slots=True)
class GraderInfrastructureError:
    """The grader could not produce a valid quality judgment."""

    exit_code: int


type GraderResult = GraderPassed | GraderFailed | GraderInfrastructureError


async def run_out_of_band_grader(
    workspace: Path,
    image: str,
    argv: tuple[str, ...],
    runner: VerificationProcessRunner,
) -> GraderResult:
    """Return typed grader status without exposing diagnostics."""
    invocation = build_grader_invocation(workspace, image, argv)
    try:
        with anyio.fail_after(_GRADER_TIMEOUT_SECONDS):
            capture = await runner.run(invocation)
    except TimeoutError:
        return GraderInfrastructureError(exit_code=124)
    if capture.exit_code == 0:
        return GraderPassed()
    if capture.exit_code == 1:
        return GraderFailed()
    return GraderInfrastructureError(exit_code=capture.exit_code)
