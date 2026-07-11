"""Preregistered paired estimates and promotion gates for clean-room Codex A/B."""

# Boundary errors are intentionally concise CLI diagnostics.
# ruff: noqa: EM101, EM102, TRY003

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path  # noqa: TC003 - Typer resolves annotations at runtime
from statistics import fmean
from typing import Annotated, Final, final, override

import typer
from pydantic import JsonValue, TypeAdapter, ValidationError

from fablized_sol.eval.codex_cleanroom import CodexArm
from fablized_sol.measure.codex_ab_models import (
    CodexABAudit,
    CodexABSample,
    PromotionCandidate,
    PromotionDecision,
    PromotionGate,
)

_BOOTSTRAP_RESAMPLES: Final = 10_000
_REPEATED_REGRESSION_DELTA: Final = -10.0
_BOOTSTRAP_FLOOR: Final = -2.0
_TOKEN_RATIO_LIMIT: Final = 1.05
_WALL_TIME_RATIO_LIMIT: Final = 1.10
_OBJECT_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])
_CANDIDATE_ADAPTER = TypeAdapter[PromotionCandidate](PromotionCandidate)


@final
class CodexABReportError(Exception):
    """Completed samples cannot support the preregistered report."""

    detail: str

    def __init__(self, detail: str) -> None:
        """Retain one bounded report-validation diagnostic."""
        self.detail = detail
        super().__init__()

    @override
    def __str__(self) -> str:
        return self.detail


@dataclass(frozen=True, slots=True)
class _Pair:
    task_id: str
    repetition: int
    raw: CodexABSample
    lean: CodexABSample

    @property
    def score_delta(self) -> float:
        return self.lean.score - self.raw.score


def _validated_pairs(samples: tuple[CodexABSample, ...]) -> tuple[_Pair, ...]:
    if not samples:
        raise CodexABReportError("complete lattice requires samples")
    common = {
        (
            sample.run_digest,
            sample.codex_binary_digest,
            sample.plugin_ref,
            sample.raw_home_digest,
            sample.lean_home_digest,
        )
        for sample in samples
    }
    if len(common) != 1:
        raise CodexABReportError("complete lattice requires common provenance")
    tasks = {sample.task_id for sample in samples}
    cells: dict[tuple[str, int, CodexArm], CodexABSample] = {}
    for sample in samples:
        key = (sample.task_id, sample.repetition, sample.arm)
        if key in cells:
            raise CodexABReportError("complete lattice contains a duplicate cell")
        cells[key] = sample
    expected = {
        (task_id, repetition, arm)
        for task_id in tasks
        for repetition in (1, 2)
        for arm in (CodexArm.RAW, CodexArm.LEAN)
    }
    if set(cells) != expected:
        raise CodexABReportError("complete lattice requires two arms and two repetitions")
    pairs: list[_Pair] = []
    for task_id in sorted(tasks):
        task_digests = {sample.task_digest for sample in samples if sample.task_id == task_id}
        if len(task_digests) != 1:
            raise CodexABReportError("complete lattice requires one task digest per task")
        pairs.extend(
            _Pair(
                task_id,
                repetition,
                cells[(task_id, repetition, CodexArm.RAW)],
                cells[(task_id, repetition, CodexArm.LEAN)],
            )
            for repetition in (1, 2)
        )
    return tuple(pairs)


def _bootstrap_interval(deltas: tuple[float, ...], seed: int) -> tuple[float, float]:
    generator = random.Random(seed)  # noqa: S311 - deterministic statistical resampling
    size = len(deltas)
    estimates = sorted(
        fmean(generator.choice(deltas) for _ in range(size)) for _ in range(_BOOTSTRAP_RESAMPLES)
    )
    low_index = int(0.025 * (_BOOTSTRAP_RESAMPLES - 1))
    high_index = int(0.975 * (_BOOTSTRAP_RESAMPLES - 1))
    return estimates[low_index], estimates[high_index]


def _ratio(numerator: float, denominator: float, label: str) -> float:
    if denominator <= 0:
        raise CodexABReportError(f"{label} baseline must be positive")
    return numerator / denominator


def build_candidate_report(
    samples: tuple[CodexABSample, ...],
    seed: int,
) -> PromotionCandidate:
    """Compute deterministic paired estimates and the six candidate gates."""
    pairs = _validated_pairs(samples)
    raw = tuple(pair.raw for pair in pairs)
    lean = tuple(pair.lean for pair in pairs)
    deltas = tuple(pair.score_delta for pair in pairs)
    mean_delta = fmean(deltas)
    ci_low, ci_high = _bootstrap_interval(deltas, seed)
    raw_score = fmean(sample.score for sample in raw)
    lean_score = fmean(sample.score for sample in lean)
    raw_pass = fmean(float(sample.full_pass) for sample in raw)
    lean_pass = fmean(float(sample.full_pass) for sample in lean)
    raw_tokens = fmean(sample.total_tokens for sample in raw)
    lean_tokens = fmean(sample.total_tokens for sample in lean)
    raw_time = fmean(sample.wall_time_seconds for sample in raw)
    lean_time = fmean(sample.wall_time_seconds for sample in lean)
    token_ratio = _ratio(lean_tokens, raw_tokens, "token")
    wall_ratio = _ratio(lean_time, raw_time, "wall-time")
    repeated = sum(
        all(
            pair.score_delta <= _REPEATED_REGRESSION_DELTA
            for pair in pairs
            if pair.task_id == task_id
        )
        for task_id in {pair.task_id for pair in pairs}
    )
    positive = sum(delta > 0 for delta in deltas)
    negative = sum(delta < 0 for delta in deltas)
    ties = len(deltas) - positive - negative
    non_ties = positive + negative
    rank_biserial = 0.0 if non_ties == 0 else (positive - negative) / non_ties
    gates = (
        PromotionGate(
            name="mean_score_uplift", passed=mean_delta >= 0.0, observed=mean_delta, threshold=0.0
        ),
        PromotionGate(
            name="bootstrap_lower_bound",
            passed=ci_low >= _BOOTSTRAP_FLOOR,
            observed=ci_low,
            threshold=_BOOTSTRAP_FLOOR,
        ),
        PromotionGate(
            name="full_pass_rate",
            passed=lean_pass >= raw_pass,
            observed=lean_pass,
            threshold=raw_pass,
        ),
        PromotionGate(
            name="token_budget",
            passed=token_ratio <= _TOKEN_RATIO_LIMIT,
            observed=token_ratio,
            threshold=_TOKEN_RATIO_LIMIT,
        ),
        PromotionGate(
            name="wall_time_budget",
            passed=wall_ratio <= _WALL_TIME_RATIO_LIMIT,
            observed=wall_ratio,
            threshold=_WALL_TIME_RATIO_LIMIT,
        ),
        PromotionGate(
            name="repeated_task_regression", passed=repeated == 0, observed=repeated, threshold=0
        ),
    )
    return PromotionCandidate(
        schema_version="super-sol-codex-ab-candidate/v1",
        seed=seed,
        pairs=len(pairs),
        tasks=len({pair.task_id for pair in pairs}),
        mean_score_delta=mean_delta,
        bootstrap_ci_low=ci_low,
        bootstrap_ci_high=ci_high,
        raw_mean_score=raw_score,
        lean_mean_score=lean_score,
        raw_full_pass_rate=raw_pass,
        lean_full_pass_rate=lean_pass,
        raw_mean_tokens=raw_tokens,
        lean_mean_tokens=lean_tokens,
        token_ratio=token_ratio,
        raw_mean_wall_time=raw_time,
        lean_mean_wall_time=lean_time,
        wall_time_ratio=wall_ratio,
        repeated_regressions=repeated,
        positive_pairs=positive,
        negative_pairs=negative,
        tied_pairs=ties,
        rank_biserial=rank_biserial,
        statistical_candidate=all(gate.passed for gate in gates),
        awaiting_independent_audit=True,
        gates=gates,
    )


def finalize_promotion(
    candidate: PromotionCandidate,
    audit: CodexABAudit,
) -> PromotionDecision:
    """Add the three independent-audit gates and make the final decision."""
    audit_gates = (
        PromotionGate(
            name="artifact_completeness",
            passed=audit.artifact_omissions == 0,
            observed=audit.artifact_omissions,
            threshold=0,
        ),
        PromotionGate(
            name="hidden_test_leakage",
            passed=audit.leakage_findings == 0,
            observed=audit.leakage_findings,
            threshold=0,
        ),
        PromotionGate(
            name="independent_audit",
            passed=audit.aggregate_reproduced,
            observed=audit.aggregate_reproduced,
            threshold=True,
        ),
    )
    gates = candidate.gates + audit_gates
    return PromotionDecision(
        schema_version="super-sol-codex-ab-decision/v1",
        promote=all(gate.passed for gate in gates),
        gates=gates,
        candidate=candidate,
        audit=audit,
    )


def _object(value: JsonValue | None, label: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise CodexABReportError(f"{label} must be an object")
    return value


def load_completed_samples(events: Path) -> tuple[CodexABSample, ...]:
    """Load completed event records and bind run-level provenance."""
    try:
        run = _OBJECT_ADAPTER.validate_json(
            (events.parent / "run.json").read_text(encoding="utf-8")
        )
        identity = _object(run.get("identity"), "run identity")
        raw_home = _object(run.get("raw_home"), "raw home")
        lean_home = _object(run.get("lean_home"), "lean home")
        records = tuple(
            _OBJECT_ADAPTER.validate_json(line)
            for line in events.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    except (OSError, ValidationError) as error:
        raise CodexABReportError("could not load clean-room events") from error
    samples: list[CodexABSample] = []
    seen_slots: set[str] = set()
    for event in records:
        if event.get("type") != "slot.completed":
            continue
        slot_id = event.get("slot_id")
        if not isinstance(slot_id, str) or slot_id in seen_slots:
            raise CodexABReportError("complete lattice contains duplicate completed slots")
        seen_slots.add(slot_id)
        arm = event.get("arm")
        if not isinstance(arm, str):
            raise CodexABReportError("completed sample arm is missing")
        try:
            parsed_arm = CodexArm(arm)
        except ValueError as error:
            raise CodexABReportError("completed sample arm is invalid") from error
        sample = CodexABSample.model_validate(
            {
                "task_id": event.get("task_id"),
                "repetition": event.get("repetition"),
                "arm": parsed_arm,
                "score": event.get("score"),
                "full_pass": event.get("full_pass"),
                "total_tokens": event.get("total_tokens"),
                "wall_time_seconds": event.get("wall_time_seconds"),
                "run_digest": event.get("run_digest"),
                "task_digest": event.get("task_digest"),
                "codex_binary_digest": identity.get("codex_binary_digest"),
                "plugin_ref": identity.get("plugin_ref"),
                "raw_home_digest": raw_home.get("tree_digest"),
                "lean_home_digest": lean_home.get("tree_digest"),
            }
        )
        samples.append(sample)
    return tuple(samples)


def report(
    events: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option()],
    seed: Annotated[int, typer.Option()] = 20260711,
) -> None:
    """Write a candidate report that remains non-promoted until independent audit."""
    try:
        candidate = build_candidate_report(load_completed_samples(events), seed)
    except (CodexABReportError, ValidationError) as error:
        raise typer.BadParameter(str(error), param_hint="Codex A/B evidence") from error
    output.parent.mkdir(parents=True, exist_ok=True)
    _ = output.write_text(candidate.model_dump_json(indent=2), encoding="utf-8")
    interval = (
        f"- Bootstrap 95% CI: [{candidate.bootstrap_ci_low:.3f}, {candidate.bootstrap_ci_high:.3f}]"
    )
    markdown = "\n".join(
        (
            "# Super SOL Codex A/B candidate",
            "",
            f"- Mean score delta: {candidate.mean_score_delta:.3f}",
            interval,
            f"- Statistical candidate: {candidate.statistical_candidate}",
            "- Final promotion: false (awaiting independent audit)",
            "",
        )
    )
    _ = output.with_suffix(".md").write_text(markdown, encoding="utf-8")


app = typer.Typer(no_args_is_help=True)
_ = app.command()(report)


def main() -> None:
    """Run the installed clean-room report command."""
    app()
