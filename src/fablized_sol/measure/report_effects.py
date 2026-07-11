"""Paired crossover validation and effect estimates."""

from dataclasses import dataclass
from math import log, sqrt
from typing import Final

from fablized_sol.engine.models import HoldoutArm
from fablized_sol.measure.report_models import (
    BenchmarkSample,
    ModelEffect,
    PairedEffect,
    ReportInputError,
    ReportIssue,
)

_T_CRITICAL_95: Final[tuple[float, ...]] = (
    12.706,
    4.303,
    3.182,
    2.776,
    2.571,
    2.447,
    2.365,
    2.306,
    2.262,
    2.228,
    2.201,
    2.179,
    2.160,
    2.145,
    2.131,
    2.120,
    2.110,
    2.101,
    2.093,
    2.086,
    2.080,
    2.074,
    2.069,
    2.064,
    2.060,
    2.056,
    2.052,
    2.048,
    2.045,
    2.042,
)
_MIN_PAIRED_TASKS: Final = 2
_HOEFFDING_LOG_TERM_95: Final = log(40.0)


@dataclass(frozen=True, slots=True)
class _Estimate:
    mean: float
    low: float
    high: float


def _estimate(values: tuple[float, ...]) -> _Estimate:
    mean = sum(values) / len(values)
    degrees_of_freedom = len(values) - 1
    critical = (
        _T_CRITICAL_95[degrees_of_freedom - 1]
        if degrees_of_freedom <= len(_T_CRITICAL_95)
        else 1.96
    )
    variance = sum((value - mean) ** 2 for value in values) / degrees_of_freedom
    margin = critical * sqrt(variance) / sqrt(float(len(values)))
    return _Estimate(mean=mean, low=mean - margin, high=mean + margin)


def _quality_estimate(values: tuple[float, ...]) -> _Estimate:
    """Return a conservative distribution-free interval for paired binary deltas."""
    mean = sum(values) / len(values)
    margin = sqrt(2 * _HOEFFDING_LOG_TERM_95 / len(values))
    return _Estimate(mean=mean, low=max(-1.0, mean - margin), high=min(1.0, mean + margin))


def _find(
    samples: tuple[BenchmarkSample, ...],
    task_id: str,
    model: str,
    arm: HoldoutArm,
) -> BenchmarkSample:
    matches = tuple(
        sample
        for sample in samples
        if (sample.task_id, sample.model, sample.arm) == (task_id, model, arm)
    )
    if len(matches) != 1:
        subject = f"{task_id}/{model}/{arm}"
        raise ReportInputError(ReportIssue.INCOMPLETE_CROSSOVER, subject)
    return matches[0]


def validate_crossover(
    samples: tuple[BenchmarkSample, ...],
    baseline_model: str,
    reference_model: str,
) -> tuple[str, ...]:
    """Require an exact two-model, two-arm task lattice."""
    if baseline_model == reference_model:
        raise ReportInputError(ReportIssue.INVALID_MODEL_ROLES)
    models = {sample.model for sample in samples}
    expected_models = {baseline_model, reference_model}
    if models != expected_models:
        raise ReportInputError(ReportIssue.UNEXPECTED_MODELS, ",".join(sorted(models)))
    arms = {sample.arm for sample in samples}
    if arms != {HoldoutArm.ON, HoldoutArm.OFF}:
        raise ReportInputError(ReportIssue.INCOMPLETE_CROSSOVER, "both ON and OFF are required")
    tasks = tuple(sorted({sample.task_id for sample in samples}))
    if len(tasks) < _MIN_PAIRED_TASKS:
        raise ReportInputError(ReportIssue.INSUFFICIENT_PAIRS)
    for task_id in tasks:
        for model in (baseline_model, reference_model):
            for arm in (HoldoutArm.ON, HoldoutArm.OFF):
                _ = _find(samples, task_id, model, arm)
    if len(samples) != len(tasks) * 4:
        raise ReportInputError(ReportIssue.DUPLICATE_CELL)
    return tasks


def paired_effects(
    samples: tuple[BenchmarkSample, ...],
    tasks: tuple[str, ...],
    models: tuple[str, str],
) -> tuple[PairedEffect, ...]:
    """Estimate task-paired ON-minus-OFF quality and resource effects."""
    effects: list[PairedEffect] = []
    for model in models:
        pairs = tuple(
            (
                _find(samples, task_id, model, HoldoutArm.ON),
                _find(samples, task_id, model, HoldoutArm.OFF),
            )
            for task_id in tasks
        )
        quality = _quality_estimate(
            tuple(float(on.defect_free) - float(off.defect_free) for on, off in pairs)
        )
        tokens = _estimate(tuple(float(on.token_volume - off.token_volume) for on, off in pairs))
        wall_time = _estimate(
            tuple(on.wall_time_seconds - off.wall_time_seconds for on, off in pairs)
        )
        effects.append(
            PairedEffect(
                model=model,
                reasoning_effort=pairs[0][0].reasoning_effort,
                tasks=len(tasks),
                quality_delta=quality.mean,
                quality_ci_low=quality.low,
                quality_ci_high=quality.high,
                mean_token_delta=tokens.mean,
                token_ci_low=tokens.low,
                token_ci_high=tokens.high,
                mean_wall_time_delta=wall_time.mean,
                wall_time_ci_low=wall_time.low,
                wall_time_ci_high=wall_time.high,
            )
        )
    return tuple(effects)


def model_effects(
    samples: tuple[BenchmarkSample, ...],
    tasks: tuple[str, ...],
    baseline_model: str,
    reference_model: str,
) -> tuple[ModelEffect, ...]:
    """Estimate task-paired reference-minus-baseline effects within each arm."""
    effects: list[ModelEffect] = []
    for arm in (HoldoutArm.ON, HoldoutArm.OFF):
        pairs = tuple(
            (
                _find(samples, task_id, reference_model, arm),
                _find(samples, task_id, baseline_model, arm),
            )
            for task_id in tasks
        )
        quality = _quality_estimate(
            tuple(
                float(reference.defect_free) - float(baseline.defect_free)
                for reference, baseline in pairs
            )
        )
        tokens = _estimate(
            tuple(
                float(reference.token_volume - baseline.token_volume)
                for reference, baseline in pairs
            )
        )
        wall_time = _estimate(
            tuple(
                reference.wall_time_seconds - baseline.wall_time_seconds
                for reference, baseline in pairs
            )
        )
        effects.append(
            ModelEffect(
                arm=arm,
                tasks=len(tasks),
                quality_delta=quality.mean,
                quality_ci_low=quality.low,
                quality_ci_high=quality.high,
                mean_token_delta=tokens.mean,
                token_ci_low=tokens.low,
                token_ci_high=tokens.high,
                mean_wall_time_delta=wall_time.mean,
                wall_time_ci_low=wall_time.low,
                wall_time_ci_high=wall_time.high,
            )
        )
    return tuple(effects)
