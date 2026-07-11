"""Strict task-manifest parsing at the evaluation trust boundary."""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, ClassVar, Self, override

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    model_validator,
)
from pydantic_core import PydanticCustomError


@dataclass(frozen=True, slots=True)
class ManifestParseError(Exception):
    """A task manifest could not be parsed into runnable task specifications."""

    path: Path
    detail: str

    @override
    def __str__(self) -> str:
        return f"{self.path}: {self.detail}"


def _require_distinct_models(
    models: tuple[StrictStr, StrictStr],
) -> tuple[StrictStr, StrictStr]:
    if models[0] == models[1]:
        error_code = "duplicate_comparison_models"
        message = "comparison models must be distinct"
        raise PydanticCustomError(
            error_code,
            message,
        )
    return models


type ComparisonModels = Annotated[
    tuple[StrictStr, StrictStr],
    AfterValidator(_require_distinct_models),
]
type VerificationImage = Annotated[
    StrictStr,
    Field(pattern=r"^[^@\s]+@sha256:[0-9a-f]{64}$"),
]


def _contains_symlink(path: Path) -> bool:
    return path.is_symlink() or any(candidate.is_symlink() for candidate in path.rglob("*"))


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
            fixture_input = (
                task.fixture if task.fixture.is_absolute() else path.parent / task.fixture
            )
            if _contains_symlink(fixture_input):
                raise ManifestParseError(
                    path=path,
                    detail=f"fixture must not contain symlinks: {fixture_input}",
                )
            fixture = fixture_input.resolve()
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
    models: ComparisonModels
    max_gate_retries: int = Field(ge=0, le=5)
    dry_run: bool
    verification_image: VerificationImage | None = None

    @model_validator(mode="after")
    def require_live_verification_image(self) -> Self:
        """Require a digest-pinned sandbox image for billable live runs."""
        if not self.dry_run and self.verification_image is None:
            error_code = "missing_verification_image"
            message = "verification image is required for live evaluation"
            raise PydanticCustomError(
                error_code,
                message,
            )
        return self
