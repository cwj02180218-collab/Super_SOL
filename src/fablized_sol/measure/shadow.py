"""Out-of-band evaluation events that never enter model context."""

from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Annotated, ClassVar, Literal, final

from pydantic import BaseModel, ConfigDict, Field

from fablized_sol.engine.models import HoldoutArm, SessionId
from fablized_sol.measure.super_sol import SUPER_SOL_PROFILE

type RunStatus = Literal["completed", "exhausted", "error", "abandoned"]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class _ShadowBase(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    ts: datetime = Field(default_factory=_utc_now)
    session_id: SessionId
    arm: HoldoutArm
    model: str = Field(min_length=1)


class RunPlanned(_ShadowBase):
    """A deterministic task/model pair scheduled for one run."""

    event: Literal["run_planned"] = "run_planned"
    task_id: str = Field(min_length=1)
    profile: str = SUPER_SOL_PROFILE.name
    profile_version: str = SUPER_SOL_PROFILE.version


class RunStarted(_ShadowBase):
    """A planned run that has entered live execution."""

    event: Literal["run_started"] = "run_started"


class RunFinished(_ShadowBase):
    """Terminal experimental outcomes and pre-registered cost guardrails."""

    event: Literal["run_finished"] = "run_finished"
    status: RunStatus
    wall_time_seconds: float = Field(ge=0)
    tool_calls: int = Field(ge=0)
    failed_verifications: int = Field(ge=0)
    gate_blocks: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    final_defect_found: bool | None
    error_type: str | None


type ShadowEvent = Annotated[RunPlanned | RunStarted | RunFinished, Field(discriminator="event")]


@final
class ShadowWriter:
    """Append one validated shadow event per JSON line under a local lock."""

    __slots__ = ("_lock", "path")

    def __init__(self, path: Path) -> None:
        """Bind the writer to one append-only JSONL path."""
        self.path = path
        self._lock = Lock()

    def append(self, event: ShadowEvent) -> None:
        """Serialize one event without introducing model-visible fields."""
        line = event.model_dump_json()
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            _ = stream.write(f"{line}\n")
