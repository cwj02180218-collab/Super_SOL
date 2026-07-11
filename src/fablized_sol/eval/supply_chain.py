"""Deterministic verifier-image policy and local Docker Scout audit."""

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Final, override

import typer

BASE_IMAGE: Final = (
    "python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df"
)
_VERIFIER_TAG: Final = "super-sol-verifier:audit"
_GRADER_TAG: Final = "super-sol-grader:audit"
_DEFAULT_REPO_ROOT: Final = Path()
_DEFAULT_SBOM_DIR: Final = Path("security/sbom")
_SHA_PIN = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
_FROM_INSTRUCTION = re.compile(r"^from(?:\s|$)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SupplyChainPolicyError(Exception):
    """A verifier Dockerfile does not use the reviewed immutable base."""

    path: Path
    reason: str

    @override
    def __str__(self) -> str:
        return f"{self.path}: {self.reason}"


def validate_pinned_base(path: Path) -> str:
    """Require one exact reviewed Python Alpine base in a Dockerfile."""
    try:
        from_lines = [
            stripped
            for line in path.read_text().splitlines()
            if _FROM_INSTRUCTION.match(stripped := line.strip())
        ]
    except OSError as error:
        raise SupplyChainPolicyError(path, str(error)) from error
    expected = f"FROM {BASE_IMAGE}"
    if from_lines != [expected] or _SHA_PIN.fullmatch(BASE_IMAGE) is None:
        raise SupplyChainPolicyError(path, "base must match the reviewed Python Alpine digest")
    return BASE_IMAGE


def build_audit_commands(repo_root: Path, sbom_dir: Path) -> tuple[tuple[str, ...], ...]:
    """Build argument-only Docker commands for two images, scans, and SBOMs."""
    verifier_root = repo_root / "eval" / "verifier"
    context = str(verifier_root.relative_to(repo_root))
    verifier_file = str((verifier_root / "Dockerfile").relative_to(repo_root))
    grader_file = str((verifier_root / "Dockerfile.grader").relative_to(repo_root))
    builds = (
        ("docker", "build", "--pull", "--file", verifier_file, "--tag", _VERIFIER_TAG, context),
        ("docker", "build", "--pull", "--file", grader_file, "--tag", _GRADER_TAG, context),
    )
    scans = tuple(
        (
            "docker",
            "scout",
            "cves",
            "--only-severity",
            "critical,high",
            "--exit-code",
            f"local://{tag}",
        )
        for tag in (_VERIFIER_TAG, _GRADER_TAG)
    )
    sboms = tuple(
        (
            "docker",
            "scout",
            "sbom",
            "--format",
            "spdx",
            "--output",
            str(sbom_dir / filename),
            f"local://{tag}",
        )
        for tag, filename in (
            (_VERIFIER_TAG, "verifier.spdx.json"),
            (_GRADER_TAG, "grader.spdx.json"),
        )
    )
    return builds + sboms + scans


def run_audit(repo_root: Path, sbom_dir: Path) -> int:
    """Validate policy, run every audit command, and return the first failure."""
    root = repo_root.resolve()
    _ = validate_pinned_base(root / "eval" / "verifier" / "Dockerfile")
    _ = validate_pinned_base(root / "eval" / "verifier" / "Dockerfile.grader")
    output = sbom_dir if sbom_dir.is_absolute() else root / sbom_dir
    try:
        output.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as error:
        typer.echo(f"container audit could not create SBOM directory: {error}", err=True)
        return 73
    first_failure = 0
    try:
        for command in build_audit_commands(root, output):
            completed = subprocess.run(command, cwd=root, check=False)  # noqa: S603
            if completed.returncode != 0:
                if command[:2] == ("docker", "build"):
                    return completed.returncode
                if first_failure == 0:
                    first_failure = completed.returncode
    except OSError as error:
        typer.echo(f"container audit could not start: {error}", err=True)
        return 127
    return first_failure


def audit_command(
    repo_root: Annotated[Path, typer.Option(exists=True, file_okay=False)] = _DEFAULT_REPO_ROOT,
    sbom_dir: Annotated[Path, typer.Option(file_okay=False)] = _DEFAULT_SBOM_DIR,
) -> None:
    """Build, scan, and emit SPDX evidence for both verifier images."""
    try:
        exit_code = run_audit(repo_root, sbom_dir)
    except SupplyChainPolicyError as error:
        raise typer.BadParameter(str(error), param_hint="verifier Dockerfiles") from error
    if exit_code != 0:
        raise typer.Exit(exit_code)


app = typer.Typer(no_args_is_help=True)
_ = app.command(name="audit")(audit_command)


def main() -> None:
    """Run the installed container supply-chain audit command."""
    app()
