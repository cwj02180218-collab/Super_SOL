"""Content-bound identities for reproducible Super SOL evaluation runs."""

import json
import platform
import stat
import sys
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict

from fablized_sol import __version__
from fablized_sol.eval.manifest import EvalOptions, TaskManifest, TaskSpec
from fablized_sol.measure.super_sol import SUPER_SOL_PROFILE

_RUN_SCHEMA: Final = "super-sol-run/v3"
_SESSION_SCHEMA: Final = "super-sol-session/v3"
_DRY_RUN_IMAGE: Final = "dry-run"
_RUNTIME_DISTRIBUTIONS: Final = ("anyio", "openai", "openai-agents", "pydantic", "typer")


def digest_json(value: object) -> str:
    """Hash one canonical JSON value without delimiter ambiguity."""
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return sha256(encoded).hexdigest()


def _fixture_digest(root: Path) -> str:
    entries: list[dict[str, object]] = []
    for path in sorted(
        root.rglob("*"), key=lambda candidate: candidate.relative_to(root).as_posix()
    ):
        relative = path.relative_to(root).as_posix()
        mode = stat.S_IMODE(path.stat().st_mode)
        if path.is_dir():
            entries.append({"kind": "directory", "mode": mode, "path": relative})
        else:
            entries.append(
                {
                    "content_sha256": sha256(path.read_bytes()).hexdigest(),
                    "kind": "file",
                    "mode": mode,
                    "path": relative,
                }
            )
    return digest_json({"entries": entries, "schema": "super-sol-fixture/v1"})


def task_digest(task: TaskSpec) -> str:
    """Bind task text, commands, and complete fixture contents."""
    return digest_json(
        {
            "fixture_digest": _fixture_digest(task.fixture),
            "grader_argv": task.grader_argv,
            "id": task.id,
            "prompt": task.prompt,
            "schema": "super-sol-task/v1",
            "verify_argv": task.verify_argv,
        }
    )


def _preregistration_digest() -> str:
    resource = files("fablized_sol.eval").joinpath("PREREGISTRATION.md")
    return sha256(resource.read_bytes()).hexdigest()


def _harness_content_digest() -> str:
    root = files("fablized_sol")
    entries: list[dict[str, str]] = []

    def visit(node: Traversable, relative: str) -> None:
        for child in sorted(node.iterdir(), key=lambda item: item.name):
            child_relative = f"{relative}/{child.name}" if relative else child.name
            if child.name == "__pycache__" or child_relative.endswith((".pyc", ".pyo")):
                continue
            if child.is_dir():
                visit(child, child_relative)
            elif child.is_file():
                entries.append(
                    {"path": child_relative, "sha256": sha256(child.read_bytes()).hexdigest()}
                )

    visit(root, "")
    return digest_json({"entries": entries, "schema": "super-sol-harness-content/v1"})


class RunIdentity(BaseModel):
    """Canonical run-level inputs that independently reproduce the run digest."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: str
    run_id: str
    arm_design: str
    models: tuple[str, str]
    efforts: tuple[str, str]
    max_gate_retries: int
    task_digests: tuple[tuple[str, str], ...]
    preregistration_digest: str
    harness_version: str
    harness_content_digest: str
    dependency_lock_digest: str
    resolved_dependencies: tuple[tuple[str, str], ...]
    python_runtime: str
    runtime_platform: str
    agents_sdk_version: str
    openai_sdk_version: str
    verification_image: str
    grader_image: str
    profile: str
    profile_version: str


@dataclass(frozen=True, slots=True)
class RunProvenance:
    """Frozen versions, images, and content identities for one CLI run."""

    run_digest: str
    task_digests: tuple[tuple[str, str], ...]
    preregistration_digest: str
    harness_version: str
    agents_sdk_version: str
    openai_sdk_version: str
    verification_image: str
    grader_image: str
    identity: RunIdentity

    def digest_for_task(self, task_id: str) -> str:
        """Return the unique content digest for one validated task id."""
        return dict(self.task_digests)[task_id]


def build_run_provenance(options: EvalOptions, manifest: TaskManifest) -> RunProvenance:
    """Construct the common provenance and canonical identity for a run."""
    task_digests = tuple((task.id, task_digest(task)) for task in manifest.tasks)
    preregistration_digest = _preregistration_digest()
    verification_image = options.verification_image or _DRY_RUN_IMAGE
    grader_image = options.grader_image or _DRY_RUN_IMAGE
    agents_sdk_version = version("openai-agents")
    openai_sdk_version = version("openai")
    lock_digest = files("fablized_sol.eval").joinpath("DEPENDENCY_LOCK.sha256").read_text().strip()
    identity = RunIdentity(
        schema_version=_RUN_SCHEMA,
        run_id=options.run_id,
        arm_design=options.arm_design,
        models=options.models,
        efforts=options.efforts,
        max_gate_retries=options.max_gate_retries,
        task_digests=task_digests,
        preregistration_digest=preregistration_digest,
        harness_version=__version__,
        harness_content_digest=_harness_content_digest(),
        dependency_lock_digest=lock_digest,
        resolved_dependencies=tuple((name, version(name)) for name in _RUNTIME_DISTRIBUTIONS),
        python_runtime=platform.python_version(),
        runtime_platform=f"{sys.platform}-{platform.machine()}",
        agents_sdk_version=agents_sdk_version,
        openai_sdk_version=openai_sdk_version,
        verification_image=verification_image,
        grader_image=grader_image,
        profile=SUPER_SOL_PROFILE.name,
        profile_version=SUPER_SOL_PROFILE.version,
    )
    return RunProvenance(
        run_digest=digest_json(identity.model_dump(mode="json")),
        task_digests=task_digests,
        preregistration_digest=preregistration_digest,
        harness_version=__version__,
        agents_sdk_version=agents_sdk_version,
        openai_sdk_version=openai_sdk_version,
        verification_image=verification_image,
        grader_image=grader_image,
        identity=identity,
    )


def session_digest(
    provenance: RunProvenance,
    task_id: str,
    model: str,
    effort: str,
    arm: str,
) -> str:
    """Build one typed versioned session identity from its complete run identity."""
    return session_identity_digest(
        provenance.run_digest,
        provenance.digest_for_task(task_id),
        model,
        effort,
        arm,
    )


def session_identity_digest(
    run_digest: str,
    task_content_digest: str,
    model: str,
    effort: str,
    arm: str,
) -> str:
    """Recompute a session identity from report-visible canonical inputs."""
    return digest_json(
        {
            "arm": arm,
            "effort": effort,
            "model": model,
            "run_digest": run_digest,
            "schema": _SESSION_SCHEMA,
            "task_digest": task_content_digest,
        }
    )
