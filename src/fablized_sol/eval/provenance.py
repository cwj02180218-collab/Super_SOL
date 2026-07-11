"""Content-bound identities for reproducible Super SOL evaluation runs."""

import json
import stat
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path
from typing import Final

from fablized_sol import __version__
from fablized_sol.eval.manifest import EvalOptions, TaskManifest, TaskSpec
from fablized_sol.measure.super_sol import SUPER_SOL_PROFILE

_RUN_SCHEMA: Final = "super-sol-run/v3"
_SESSION_SCHEMA: Final = "super-sol-session/v3"
_DRY_RUN_IMAGE: Final = "dry-run"


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
    payload = {
        "agents_sdk_version": agents_sdk_version,
        "arm_design": options.arm_design,
        "efforts": options.efforts,
        "grader_image": grader_image,
        "harness_version": __version__,
        "max_gate_retries": options.max_gate_retries,
        "models": options.models,
        "openai_sdk_version": openai_sdk_version,
        "preregistration_digest": preregistration_digest,
        "profile": SUPER_SOL_PROFILE.name,
        "profile_version": SUPER_SOL_PROFILE.version,
        "run_id": options.run_id,
        "schema": _RUN_SCHEMA,
        "task_digests": task_digests,
        "verification_image": verification_image,
    }
    return RunProvenance(
        run_digest=digest_json(payload),
        task_digests=task_digests,
        preregistration_digest=preregistration_digest,
        harness_version=__version__,
        agents_sdk_version=agents_sdk_version,
        openai_sdk_version=openai_sdk_version,
        verification_image=verification_image,
        grader_image=grader_image,
    )


def session_digest(
    provenance: RunProvenance,
    task_id: str,
    model: str,
    effort: str,
    arm: str,
) -> str:
    """Build one typed versioned session identity from its complete run identity."""
    return digest_json(
        {
            "arm": arm,
            "effort": effort,
            "model": model,
            "run_digest": provenance.run_digest,
            "schema": _SESSION_SCHEMA,
            "task_digest": provenance.digest_for_task(task_id),
        }
    )
