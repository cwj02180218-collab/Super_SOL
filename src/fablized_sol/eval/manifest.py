"""Strict task-manifest parsing at the evaluation trust boundary."""

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, override

from pydantic import BaseModel, ConfigDict, Field, StrictStr, ValidationError


@dataclass(frozen=True, slots=True)
class ManifestParseError(Exception):
    """A task manifest could not be parsed into runnable task specifications."""

    path: Path
    detail: str

    @override
    def __str__(self) -> str:
        return f"{self.path}: {self.detail}"


class TaskSpec(BaseModel):
    """One immutable evaluation task and its trusted verification argv."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    id: StrictStr = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    prompt: StrictStr = Field(min_length=1)
    fixture: Path
    verify_argv: tuple[StrictStr, ...] = Field(min_length=1)


class TaskManifest(BaseModel):
    """A non-empty immutable collection of evaluation tasks."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    tasks: tuple[TaskSpec, ...] = Field(min_length=1)

    @classmethod
    def load(cls, path: Path) -> "TaskManifest":
        """Read UTF-8 JSON, resolve fixtures, and reject ambiguous manifests."""
        try:
            manifest = cls.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError) as error:
            raise ManifestParseError(path=path, detail=str(error)) from error

        seen: set[str] = set()
        resolved_tasks: list[TaskSpec] = []
        for task in manifest.tasks:
            if task.id in seen:
                raise ManifestParseError(path=path, detail=f"duplicate task id: {task.id}")
            seen.add(task.id)
            fixture = (
                task.fixture.resolve()
                if task.fixture.is_absolute()
                else (path.parent / task.fixture).resolve()
            )
            if not fixture.is_dir():
                raise ManifestParseError(
                    path=path,
                    detail=f"fixture directory does not exist: {fixture}",
                )
            resolved_tasks.append(task.model_copy(update={"fixture": fixture}))
        return cls(tasks=tuple(resolved_tasks))


class EvalOptions(BaseModel):
    """Parsed options owned by the evaluation I/O boundary."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    tasks: Path
    output_dir: Path
    run_id: StrictStr = Field(min_length=1, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    models: tuple[StrictStr, StrictStr]
    max_gate_retries: int = Field(ge=0, le=5)
    dry_run: bool
