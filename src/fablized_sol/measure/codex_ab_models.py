"""Typed public records for clean-room Codex A/B decisions."""

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from fablized_sol.eval.codex_cleanroom import CodexArm


class CodexABSample(BaseModel):
    """One completed raw or lean arm result with bound provenance."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    task_id: StrictStr = Field(min_length=1)
    repetition: int = Field(ge=1)
    arm: CodexArm
    score: float = Field(ge=0.0, le=100.0)
    full_pass: bool
    total_tokens: int = Field(ge=0)
    wall_time_seconds: float = Field(gt=0.0)
    run_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    task_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    codex_binary_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    plugin_ref: StrictStr = Field(pattern=r"^(?:v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?|[0-9a-f]{40})$")
    raw_home_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    lean_home_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")


class PromotionGate(BaseModel):
    """One preregistered pass/fail condition and its observed value."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    name: StrictStr
    passed: bool
    observed: float | int | bool
    threshold: float | int | bool


class PromotionCandidate(BaseModel):
    """Statistical/resource result that still requires independent audit."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: Literal["super-sol-codex-ab-candidate/v1"]
    seed: int
    pairs: int
    tasks: int
    mean_score_delta: float
    bootstrap_ci_low: float
    bootstrap_ci_high: float
    raw_mean_score: float
    lean_mean_score: float
    raw_full_pass_rate: float
    lean_full_pass_rate: float
    raw_mean_tokens: float
    lean_mean_tokens: float
    token_ratio: float
    raw_mean_wall_time: float
    lean_mean_wall_time: float
    wall_time_ratio: float
    repeated_regressions: int
    positive_pairs: int
    negative_pairs: int
    tied_pairs: int
    rank_biserial: float
    statistical_candidate: bool
    awaiting_independent_audit: Literal[True]
    gates: tuple[PromotionGate, ...]


class CodexABAudit(BaseModel):
    """Independent artifact, leakage, and aggregate reproduction evidence."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    artifact_omissions: int = Field(ge=0)
    leakage_findings: int = Field(ge=0)
    aggregate_reproduced: bool


class PromotionDecision(BaseModel):
    """Final all-gates decision after independent audit."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: Literal["super-sol-codex-ab-decision/v1"]
    promote: bool
    gates: tuple[PromotionGate, ...]
    candidate: PromotionCandidate
    audit: CodexABAudit
