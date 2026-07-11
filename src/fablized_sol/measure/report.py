"""Fail-closed Day 3 benchmark analysis over out-of-band evidence."""

from pathlib import Path
from typing import Final, cast

from pydantic import ValidationError

from fablized_sol.engine.models import HoldoutArm, SessionId
from fablized_sol.eval.manifest import ReasoningEffort
from fablized_sol.eval.provenance import digest_json, session_identity_digest
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
from fablized_sol.measure.shadow import RunPlanned
from fablized_sol.measure.super_sol import SUPER_SOL_PROFILE

_MAX_EVIDENCE_BYTES: Final = 16 * 1024 * 1024


def _load_grades(path: Path) -> tuple[GradeFile, dict[SessionId, bool]]:
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
    return payload, grades


def _validate_provenance(
    plans: dict[SessionId, RunPlanned],
    grade_file: GradeFile,
) -> RunPlanned:
    provenance = {
        (
            plan.run_digest,
            plan.preregistration_digest,
            plan.harness_version,
            plan.agents_sdk_version,
            plan.openai_sdk_version,
            plan.verification_image,
            plan.grader_image,
            plan.profile,
            plan.profile_version,
        )
        for plan in plans.values()
    }
    if len(provenance) != 1:
        raise ReportInputError(ReportIssue.INCONSISTENT_PROVENANCE)
    representative = next(iter(plans.values()))
    identities = {plan.run_identity.model_dump_json() for plan in plans.values()}
    if len(identities) != 1:
        raise ReportInputError(ReportIssue.INCONSISTENT_PROVENANCE)
    identity = representative.run_identity
    recomputed_run_digest = digest_json(identity.model_dump(mode="json"))
    if recomputed_run_digest != representative.run_digest:
        raise ReportInputError(ReportIssue.IDENTITY_MISMATCH, "run digest")
    if grade_file.run_digest != representative.run_digest:
        raise ReportInputError(ReportIssue.RUN_DIGEST_MISMATCH)
    task_digests: dict[str, str] = {}
    for plan in plans.values():
        previous_digest = task_digests.setdefault(plan.task_id, plan.task_digest)
        if previous_digest != plan.task_digest:
            raise ReportInputError(ReportIssue.INCONSISTENT_PROVENANCE, plan.task_id)
        expected_session = session_identity_digest(
            representative.run_digest,
            plan.task_digest,
            plan.model,
            plan.reasoning_effort,
            plan.arm,
        )
        if plan.session_id != expected_session:
            raise ReportInputError(ReportIssue.IDENTITY_MISMATCH, plan.session_id)
    if tuple(task_digests.items()) != identity.task_digests:
        raise ReportInputError(ReportIssue.IDENTITY_MISMATCH, "task digests")
    duplicated_identity = (
        representative.preregistration_digest,
        representative.harness_version,
        representative.agents_sdk_version,
        representative.openai_sdk_version,
        representative.verification_image,
        representative.grader_image,
        representative.profile,
        representative.profile_version,
    )
    canonical_identity = (
        identity.preregistration_digest,
        identity.harness_version,
        identity.agents_sdk_version,
        identity.openai_sdk_version,
        identity.verification_image,
        identity.grader_image,
        identity.profile,
        identity.profile_version,
    )
    if duplicated_identity != canonical_identity:
        raise ReportInputError(ReportIssue.IDENTITY_MISMATCH, "duplicated provenance")
    return representative


def _samples(events: Path, grades: Path) -> tuple[tuple[BenchmarkSample, ...], RunPlanned]:
    event_index = load_events(events)
    plans = event_index.plans
    starts = event_index.starts
    finishes = event_index.finishes
    grade_file, grade_map = _load_grades(grades)
    if set(finishes) != set(plans):
        raise ReportInputError(ReportIssue.INCOMPLETE_TERMINAL_EVENTS)
    if set(grade_map) != set(plans):
        missing = sorted(set(plans) - set(grade_map))
        if missing:
            raise ReportInputError(ReportIssue.MISSING_GRADE, missing[0])
        raise ReportInputError(ReportIssue.UNKNOWN_GRADE)
    if set(starts) != set(plans):
        raise ReportInputError(ReportIssue.INCOMPLETE_LIFECYCLE)
    representative = _validate_provenance(plans, grade_file)
    samples: list[BenchmarkSample] = []
    for session_id, plan in plans.items():
        finish = finishes[session_id]
        start = starts[session_id]
        if (plan.model, plan.arm, plan.reasoning_effort) != (
            start.model,
            start.arm,
            start.reasoning_effort,
        ) or (
            plan.model,
            plan.arm,
            plan.reasoning_effort,
        ) != (finish.model, finish.arm, finish.reasoning_effort):
            raise ReportInputError(ReportIssue.PLAN_FINISH_MISMATCH, session_id)
        if (
            plan.profile,
            plan.profile_version,
        ) != (SUPER_SOL_PROFILE.name, SUPER_SOL_PROFILE.version):
            raise ReportInputError(ReportIssue.PROFILE_MISMATCH, session_id)
        if finish.grader_passed is None:
            raise ReportInputError(ReportIssue.MISSING_GRADER_RESULT, session_id)
        if finish.final_defect_found is not None:
            raise ReportInputError(ReportIssue.EMBEDDED_FINAL_DEFECT, session_id)
        samples.append(
            BenchmarkSample(
                task_id=plan.task_id,
                session_id=session_id,
                arm=plan.arm,
                model=plan.model,
                reasoning_effort=plan.reasoning_effort,
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
    return tuple(samples), representative


def _cell(
    model: str,
    effort: ReasoningEffort,
    arm: HoldoutArm,
    samples: tuple[BenchmarkSample, ...],
) -> BenchmarkCell:
    runs = len(samples)
    defect_free = sum(sample.defect_free for sample in samples)
    tokens = sum(sample.token_volume for sample in samples)
    return BenchmarkCell(
        model=model,
        reasoning_effort=effort,
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
    samples, provenance = _samples(events, grades)
    tasks = validate_crossover(samples, baseline_model, reference_model)
    efforts: dict[str, ReasoningEffort] = {}
    for model in (baseline_model, reference_model):
        observed = {sample.reasoning_effort for sample in samples if sample.model == model}
        if len(observed) != 1:
            raise ReportInputError(ReportIssue.INCONSISTENT_EFFORT, model)
        efforts[model] = cast("ReasoningEffort", observed.pop())
    grouped: dict[tuple[str, ReasoningEffort, HoldoutArm], list[BenchmarkSample]] = {}
    for sample in samples:
        grouped.setdefault((sample.model, sample.reasoning_effort, sample.arm), []).append(sample)
    cells = tuple(
        _cell(model, effort, arm, tuple(cell_samples))
        for (model, effort, arm), cell_samples in sorted(grouped.items())
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
        run_digest=provenance.run_digest,
        preregistration_digest=provenance.preregistration_digest,
        harness_version=provenance.harness_version,
        agents_sdk_version=provenance.agents_sdk_version,
        openai_sdk_version=provenance.openai_sdk_version,
        verification_image=provenance.verification_image,
        grader_image=provenance.grader_image,
        run_identity=provenance.run_identity,
        baseline_model=baseline_model,
        baseline_effort=efforts[baseline_model],
        reference_model=reference_model,
        reference_effort=efforts[reference_model],
        cells=cells,
        paired_effects=paired_effects(samples, tasks, (baseline_model, reference_model)),
        model_effects=model_effects(samples, tasks, baseline_model, reference_model),
        lazy_cascades=cascades,
    )
