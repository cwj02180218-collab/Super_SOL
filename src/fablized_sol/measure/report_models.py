"""Typed inputs and outputs for Day 3 benchmark analysis."""

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import ClassVar, override

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from fablized_sol.engine.models import HoldoutArm, SessionId
from fablized_sol.eval.manifest import ReasoningEffort


@unique
class ReportIssue(StrEnum):
    """Closed set of benchmark evidence failures."""

    INVALID_GRADES = "invalid grades"
    DUPLICATE_GRADE = "duplicate grade"
    INVALID_EVENTS = "invalid events"
    EVIDENCE_TOO_LARGE = "evidence file exceeds size limit"
    DUPLICATE_PLAN = "duplicate plan"
    DUPLICATE_START = "duplicate start"
    DUPLICATE_FINISH = "duplicate finish"
    INCOMPLETE_LIFECYCLE = "every planned session must have exactly one start"
    INVALID_LIFECYCLE_ORDER = "lifecycle events are out of order"
    INCOMPLETE_TERMINAL_EVENTS = "every planned session must have exactly one terminal event"
    MISSING_GRADE = "missing grade"
    UNKNOWN_GRADE = "grades contain unknown sessions"
    PLAN_FINISH_MISMATCH = "plan and finish disagree"
    PROFILE_MISMATCH = "benchmark profile does not match Super Sol"
    MISSING_GRADER_RESULT = "missing out-of-band grader result"
    DUPLICATE_CELL = "duplicate task/model/arm sample"
    INCOMPLETE_CROSSOVER = "incomplete crossover evidence"
    INSUFFICIENT_PAIRS = "at least two paired tasks are required"
    INVALID_MODEL_ROLES = "baseline and reference models must be distinct"
    UNEXPECTED_MODELS = "evidence models do not match report roles"
    INCONSISTENT_EFFORT = "each model must use exactly one reasoning effort"


@dataclass(frozen=True, slots=True)
class ReportInputError(Exception):
    """The supplied benchmark evidence cannot support a report."""

    issue: ReportIssue
    subject: str | None = None

    @override
    def __str__(self) -> str:
        return f"{self.issue}: {self.subject}" if self.subject is not None else self.issue


class Grade(BaseModel):
    """One out-of-band terminal quality judgment."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    session_id: SessionId
    final_defect_found: StrictBool


class GradeFile(BaseModel):
    """Complete grade set for one benchmark report."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    grades: tuple[Grade, ...] = Field(min_length=1)


class BenchmarkCell(BaseModel):
    """Quality and resource metrics for one model and arm."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    model: str
    reasoning_effort: ReasoningEffort
    arm: HoldoutArm
    runs: int
    completed_runs: int
    grader_passed_runs: int
    defect_free_runs: int
    quality_rate: float
    token_volume: int
    tokens_per_defect_free_run: float | None
    mean_wall_time_seconds: float
    tool_calls: int
    failed_verifications: int
    gate_blocks: int


class LazyCascade(BaseModel):
    """Deployable baseline-first escalation metrics for one arm."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    arm: HoldoutArm
    tasks: int
    escalations: int
    escalation_rate: float
    defect_free_tasks: int
    quality_rate: float
    token_volume: int
    always_reference_token_volume: int
    token_savings_rate: float | None


class PairedEffect(BaseModel):
    """Task-paired ON-minus-OFF effect with normal 95 percent intervals."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    model: str
    reasoning_effort: ReasoningEffort
    tasks: int
    quality_delta: float
    quality_ci_low: float
    quality_ci_high: float
    mean_token_delta: float
    token_ci_low: float
    token_ci_high: float
    mean_wall_time_delta: float
    wall_time_ci_low: float
    wall_time_ci_high: float


class ModelEffect(BaseModel):
    """Task-paired reference-minus-baseline effect within one arm."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    arm: HoldoutArm
    tasks: int
    quality_delta: float
    quality_ci_low: float
    quality_ci_high: float
    mean_token_delta: float
    token_ci_low: float
    token_ci_high: float
    mean_wall_time_delta: float
    wall_time_ci_low: float
    wall_time_ci_high: float


class BenchmarkReport(BaseModel):
    """Machine-readable Super Sol Day 3 report."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    baseline_model: str
    baseline_effort: ReasoningEffort
    reference_model: str
    reference_effort: ReasoningEffort
    cells: tuple[BenchmarkCell, ...]
    paired_effects: tuple[PairedEffect, ...]
    model_effects: tuple[ModelEffect, ...]
    lazy_cascades: tuple[LazyCascade, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkSample:
    """One fully joined plan, terminal event, grader result, and external grade."""

    task_id: str
    session_id: SessionId
    arm: HoldoutArm
    model: str
    reasoning_effort: ReasoningEffort
    status: str
    wall_time_seconds: float
    tool_calls: int
    failed_verifications: int
    gate_blocks: int
    token_volume: int
    grader_passed: bool
    final_defect_found: bool

    @property
    def operational_success(self) -> bool:
        """Whether baseline-first routing can accept this run without oracle knowledge."""
        return self.status == "completed" and self.grader_passed

    @property
    def defect_free(self) -> bool:
        """Whether all observed and external quality checks passed."""
        return self.operational_success and not self.final_defect_found
