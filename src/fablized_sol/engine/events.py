"""Validated event schemas stored in the session ledger."""

from datetime import UTC, datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from fablized_sol.engine.models import ChangeKind, TaskMode, ToolKind, ToolName


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ReadToolEvent(BaseModel):
    """A tool call that only observes state."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    event: Literal["tool_call"] = "tool_call"
    ts: datetime = Field(default_factory=_utc_now)
    tool: ToolName
    kind: Literal[ToolKind.READ] = ToolKind.READ


class MutationToolEvent(BaseModel):
    """A tool call that changes a classified artifact."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    event: Literal["tool_call"] = "tool_call"
    ts: datetime = Field(default_factory=_utc_now)
    tool: ToolName
    kind: Literal[ToolKind.MUTATION] = ToolKind.MUTATION
    path: str
    change_kind: ChangeKind


class VerificationToolEvent(BaseModel):
    """A tool call that provides explicit verification evidence."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    event: Literal["tool_call"] = "tool_call"
    ts: datetime = Field(default_factory=_utc_now)
    tool: ToolName
    kind: Literal[ToolKind.VERIFICATION] = ToolKind.VERIFICATION
    success: bool


class EvidenceRejectedEvent(BaseModel):
    """An observable tool claim that receives no evidence credit."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    event: Literal["evidence_rejected"] = "evidence_rejected"
    ts: datetime = Field(default_factory=_utc_now)
    tool: ToolName
    claimed_kind: ToolKind
    reason: Literal["unknown_tool", "malformed_result"]


class ClassifyEvent(BaseModel):
    """The task classification fixed for a session."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    event: Literal["classify"] = "classify"
    ts: datetime = Field(default_factory=_utc_now)
    mode: TaskMode
    risk_flags: tuple[str, ...]


class GateFireEvent(BaseModel):
    """A recorded stop attempt blocked by the evidence gate."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True, extra="forbid")

    event: Literal["gate_fire"] = "gate_fire"
    ts: datetime = Field(default_factory=_utc_now)
    reason: str


type LedgerEvent = (
    ReadToolEvent
    | MutationToolEvent
    | VerificationToolEvent
    | EvidenceRejectedEvent
    | ClassifyEvent
    | GateFireEvent
)
