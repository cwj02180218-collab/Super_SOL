"""Typed domain models for the procedure engine."""

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import NewType

SessionId = NewType("SessionId", str)
ToolName = NewType("ToolName", str)


@unique
class TaskMode(StrEnum):
    """Execution depth selected for a prompt."""

    QUICK = "quick"
    NORMAL = "normal"
    DEEP = "deep"


@unique
class HoldoutArm(StrEnum):
    """Experiment arm assigned to a session."""

    ON = "on"
    OFF = "off"


@unique
class ToolKind(StrEnum):
    """Behavioral category of a tool."""

    READ = "read"
    MUTATION = "mutation"
    VERIFICATION = "verification"
    UNKNOWN = "unknown"


@unique
class ChangeKind(StrEnum):
    """Kind of artifact being changed."""

    CODE = "code"
    DOCS = "docs"


@unique
class GateAction(StrEnum):
    """Decision emitted by an evidence gate."""

    ALLOW = "allow"
    BLOCK = "block"
    EXHAUSTED = "exhausted"


@dataclass(frozen=True, slots=True)
class Classification:
    """Prompt classification with stable risk labels."""

    mode: TaskMode
    risk_flags: tuple[str, ...] = ()
