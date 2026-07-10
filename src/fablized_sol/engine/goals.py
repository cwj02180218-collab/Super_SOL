"""Immutable evidence-aware goal transitions."""

from dataclasses import dataclass, replace
from enum import StrEnum, unique
from typing import NewType, assert_never, override

GoalId = NewType("GoalId", str)
Evidence = NewType("Evidence", str)
VerifyCommand = NewType("VerifyCommand", str)


@unique
class GoalStatus(StrEnum):
    """Lifecycle state for a goal."""

    PENDING = "pending"
    COMPLETE = "complete"


@dataclass(frozen=True, slots=True)
class DuplicateGoalIdError(Exception):
    """A goal identifier that appears more than once in a book."""

    goal_id: GoalId

    @override
    def __str__(self) -> str:
        """Render the duplicated identifier."""
        return f"duplicate goal id: {self.goal_id}"


@dataclass(frozen=True, slots=True)
class MissingEvidenceError(Exception):
    """A completion attempt that lacks non-blank evidence."""

    goal_id: GoalId

    @override
    def __str__(self) -> str:
        """Render the goal missing completion evidence."""
        return f"goal {self.goal_id} requires non-blank evidence"


@dataclass(frozen=True, slots=True)
class VerificationGoalError(Exception):
    """A final-goal completion that lacks a verification command."""

    goal_id: GoalId

    @override
    def __str__(self) -> str:
        """Render the final goal missing verification data."""
        return f"final goal {self.goal_id} requires a non-blank verification command"


@dataclass(frozen=True, slots=True)
class InvalidGoalTransitionError(Exception):
    """A completion attempt for an unknown or terminal goal."""

    goal_id: GoalId
    status: GoalStatus | None

    @override
    def __str__(self) -> str:
        """Render the unavailable transition and current state."""
        if self.status is None:
            return f"goal {self.goal_id} does not exist"
        return f"goal {self.goal_id} cannot transition from {self.status} to complete"


@dataclass(frozen=True, slots=True)
class Goal:
    """One stable story outcome and its completion evidence."""

    id: GoalId
    title: str
    objective: str
    status: GoalStatus = GoalStatus.PENDING
    evidence: Evidence | None = None
    verify_cmd: VerifyCommand | None = None


@dataclass(frozen=True, slots=True)
class GoalBook:
    """An immutable ordered collection of story goals."""

    brief: str
    goals: tuple[Goal, ...]

    @classmethod
    def create(cls, brief: str, goals: tuple[Goal, ...]) -> "GoalBook":
        """Create a book after enforcing unique stable goal identifiers."""
        seen: set[GoalId] = set()
        for goal in goals:
            if goal.id in seen:
                raise DuplicateGoalIdError(goal.id)
            seen.add(goal.id)
        return cls(brief=brief, goals=goals)

    def complete(
        self,
        goal_id: GoalId,
        evidence: Evidence,
        verify_cmd: VerifyCommand | None = None,
    ) -> "GoalBook":
        """Return a new book with exactly one pending goal completed."""
        match = next(
            ((index, goal) for index, goal in enumerate(self.goals) if goal.id == goal_id),
            None,
        )
        if match is None:
            raise InvalidGoalTransitionError(goal_id=goal_id, status=None)
        index, goal = match

        match goal.status:
            case GoalStatus.PENDING:
                pass
            case GoalStatus.COMPLETE:
                raise InvalidGoalTransitionError(goal_id=goal_id, status=goal.status)
            case _:
                assert_never(goal.status)

        if not evidence.strip():
            raise MissingEvidenceError(goal_id)
        if index == len(self.goals) - 1 and (verify_cmd is None or not verify_cmd.strip()):
            raise VerificationGoalError(goal_id)

        completed = replace(
            goal,
            status=GoalStatus.COMPLETE,
            evidence=evidence,
            verify_cmd=verify_cmd,
        )
        return replace(
            self,
            goals=tuple(
                completed if current_index == index else current
                for current_index, current in enumerate(self.goals)
            ),
        )
