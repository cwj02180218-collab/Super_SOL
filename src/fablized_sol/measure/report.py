"""Fail-closed Day 3 benchmark analysis over out-of-band evidence."""

from pathlib import Path
from typing import Final

from pydantic import ValidationError

from fablized_sol.engine.models import HoldoutArm, SessionId
from fablized_sol.measure.report_effects import model_effects, paired_effects, validate_crossover
from fablized_sol.measure.report_events import load_events
from fablized_sol.measure.report_models import (
    BenchmarkCell,
    BenchmarkReport,
    BenchmarkSample,
    GradeFile,
    LazyCascade,
    ReportInputError,
    ReportIssue,
)
from fablized_sol.measure.super_sol import SUPER_SOL_PROFILE

_MAX_EVIDENCE_BYTES: Final = 16 * 1024 * 1024


def _load_grades(path: Path) -> dict[SessionId, bool]:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise ReportInputError(ReportIssue.INVALID_GRADES, str(error)) from error
    if size > _MAX_EVIDENCE_BYTES:
        raise ReportInputError(ReportIssue.EVIDENCE_TOO_LARGE, str(path))
    try:
        payload = GradeFile.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise ReportInputError(ReportIssue.INVALID_GRADES, str(error)) from error
    grades: dict[SessionId, bool] = {}
    for grade in payload.grades:
        if grade.session_id in grades:
            raise ReportInputError(ReportIssue.DUPLICATE_GRADE, grade.session_id)
        grades[grade.session_id] = grade.final_defect_found
    return grades


def _samples(events: Path, grades: Path) -> tuple[BenchmarkSample, ...]:
    event_index = load_events(events)
    plans = event_index.plans
    starts = event_index.starts
    finishes = event_index.finishes
    grade_map = _load_grades(grades)
    if set(finishes) != set(plans):
        raise ReportInputError(ReportIssue.INCOMPLETE_TERMINAL_EVENTS)
    if set(grade_map) != set(plans):
        missing = sorted(set(plans) - set(grade_map))
        if missing:
            raise ReportInputError(ReportIssue.MISSING_GRADE, missing[0])
        raise ReportInputError(ReportIssue.UNKNOWN_GRADE)
    if set(starts) != set(plans):
        raise ReportInputError(ReportIssue.INCOMPLETE_LIFECYCLE)
    samples: list[BenchmarkSample] = []
    for session_id, plan in plans.items():
        finish = finishes[session_id]
        start = starts[session_id]
        if (plan.model, plan.arm) != (start.model, start.arm) or (
            plan.model,
            plan.arm,
        ) != (finish.model, finish.arm):
            raise ReportInputError(ReportIssue.PLAN_FINISH_MISMATCH, session_id)
        if (
            plan.profile,
            plan.profile_version,
        ) != (SUPER_SOL_PROFILE.name, SUPER_SOL_PROFILE.version):
            raise ReportInputError(ReportIssue.PROFILE_MISMATCH, session_id)
        if finish.grader_passed is None:
            raise ReportInputError(ReportIssue.MISSING_GRADER_RESULT, session_id)
        samples.append(
            BenchmarkSample(
                task_id=plan.task_id,
                session_id=session_id,
                arm=plan.arm,
                model=plan.model,
                status=finish.status,
                wall_time_seconds=finish.wall_time_seconds,
                tool_calls=finish.tool_calls,
                failed_verifications=finish.failed_verifications,
                gate_blocks=finish.gate_blocks,
                token_volume=finish.input_tokens + finish.output_tokens,
                grader_passed=finish.grader_passed,
                final_defect_found=grade_map[session_id],
            )
        )
    return tuple(samples)


def _cell(model: str, arm: HoldoutArm, samples: tuple[BenchmarkSample, ...]) -> BenchmarkCell:
    runs = len(samples)
    defect_free = sum(sample.defect_free for sample in samples)
    tokens = sum(sample.token_volume for sample in samples)
    return BenchmarkCell(
        model=model,
        arm=arm,
        runs=runs,
        completed_runs=sum(sample.status == "completed" for sample in samples),
        grader_passed_runs=sum(sample.grader_passed for sample in samples),
        defect_free_runs=defect_free,
        quality_rate=defect_free / runs,
        token_volume=tokens,
        tokens_per_defect_free_run=tokens / defect_free if defect_free else None,
        mean_wall_time_seconds=sum(sample.wall_time_seconds for sample in samples) / runs,
        tool_calls=sum(sample.tool_calls for sample in samples),
        failed_verifications=sum(sample.failed_verifications for sample in samples),
        gate_blocks=sum(sample.gate_blocks for sample in samples),
    )


def _cascade(
    arm: HoldoutArm,
    samples: tuple[BenchmarkSample, ...],
    baseline_model: str,
    reference_model: str,
) -> LazyCascade:
    by_task: dict[str, dict[str, BenchmarkSample]] = {}
    for sample in samples:
        models = by_task.setdefault(sample.task_id, {})
        if sample.model in models:
            raise ReportInputError(ReportIssue.DUPLICATE_CELL, sample.task_id)
        models[sample.model] = sample
    pairs = tuple((models[baseline_model], models[reference_model]) for models in by_task.values())
    escalations = sum(not baseline.operational_success for baseline, _reference in pairs)
    successes = sum(
        baseline.defect_free or (not baseline.operational_success and reference.defect_free)
        for baseline, reference in pairs
    )
    token_volume = sum(
        baseline.token_volume + (reference.token_volume if not baseline.operational_success else 0)
        for baseline, reference in pairs
    )
    reference_tokens = sum(reference.token_volume for _baseline, reference in pairs)
    savings = 1 - (token_volume / reference_tokens) if reference_tokens else None
    return LazyCascade(
        arm=arm,
        tasks=len(pairs),
        escalations=escalations,
        escalation_rate=escalations / len(pairs),
        defect_free_tasks=successes,
        quality_rate=successes / len(pairs),
        token_volume=token_volume,
        always_reference_token_volume=reference_tokens,
        token_savings_rate=savings,
    )


def build_report(
    events: Path,
    grades: Path,
    baseline_model: str,
    reference_model: str,
) -> BenchmarkReport:
    """Build a fail-closed crossover report and deployable lazy cascade."""
    samples = _samples(events, grades)
    tasks = validate_crossover(samples, baseline_model, reference_model)
    grouped: dict[tuple[str, HoldoutArm], list[BenchmarkSample]] = {}
    for sample in samples:
        grouped.setdefault((sample.model, sample.arm), []).append(sample)
    cells = tuple(
        _cell(model, arm, tuple(cell_samples))
        for (model, arm), cell_samples in sorted(grouped.items())
    )
    cascades = tuple(
        _cascade(
            arm,
            tuple(sample for sample in samples if sample.arm == arm),
            baseline_model,
            reference_model,
        )
        for arm in (HoldoutArm.ON, HoldoutArm.OFF)
    )
    return BenchmarkReport(
        baseline_model=baseline_model,
        reference_model=reference_model,
        cells=cells,
        paired_effects=paired_effects(samples, tasks, (baseline_model, reference_model)),
        model_effects=model_effects(samples, tasks, baseline_model, reference_model),
        lazy_cascades=cascades,
    )
