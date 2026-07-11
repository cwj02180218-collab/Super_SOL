"""Sequential paired Day 0 evaluation CLI."""

import os
from hashlib import sha256
from pathlib import Path
from typing import Annotated, assert_never, cast

import anyio
import typer
from anyio import to_thread
from pydantic import ValidationError

from fablized_sol.engine.models import HoldoutArm, SessionId
from fablized_sol.eval.grader import (
    GraderFailed,
    GraderInfrastructureError,
    GraderPassed,
    run_out_of_band_grader,
)
from fablized_sol.eval.live import (
    PlannedRun,
    create_live_run,
    empty_finished_event,
    execute_live,
    finished_event,
)
from fablized_sol.eval.manifest import ArmDesign, EvalOptions, ReasoningEffort, TaskManifest
from fablized_sol.eval.provenance import build_run_provenance, session_digest
from fablized_sol.harness.container_runtime import AnyioDockerRunner, preflight_local_images
from fablized_sol.harness.run import RunCompleted, RunExhausted
from fablized_sol.measure.holdout import assign_arm
from fablized_sol.measure.shadow import RunPlanned, RunStarted, ShadowWriter
from fablized_sol.measure.super_sol import SUPER_SOL_PROFILE


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _planned_runs(options: EvalOptions, manifest: TaskManifest) -> tuple[PlannedRun, ...]:
    planned: list[PlannedRun] = []
    provenance = build_run_provenance(options, manifest)
    for task in manifest.tasks:
        assignment_key = SessionId(_digest(f"{options.run_id}:{task.id}"))
        arms_by_design = {
            ArmDesign.HOLDOUT: (assign_arm(assignment_key),),
            ArmDesign.CROSSOVER: (HoldoutArm.ON, HoldoutArm.OFF),
        }
        arms = arms_by_design[options.arm_design]
        model_efforts = tuple(zip(options.models, options.efforts, strict=True))
        if options.arm_design is ArmDesign.CROSSOVER:
            if int(assignment_key[-1], 16) % 2:
                arms = tuple(reversed(arms))
            if int(_digest(f"{assignment_key}:model-order")[-1], 16) % 2:
                model_efforts = tuple(reversed(model_efforts))
        planned.extend(
            PlannedRun(
                task=task,
                model=model,
                reasoning_effort=effort,
                session_id=SessionId(session_digest(provenance, task.id, model, effort, arm)),
                arm=arm,
                run_digest=provenance.run_digest,
                task_digest=provenance.digest_for_task(task.id),
                preregistration_digest=provenance.preregistration_digest,
                harness_version=provenance.harness_version,
                agents_sdk_version=provenance.agents_sdk_version,
                openai_sdk_version=provenance.openai_sdk_version,
                verification_image=provenance.verification_image,
                grader_image=provenance.grader_image,
            )
            for arm in arms
            for model, effort in model_efforts
        )
    return tuple(planned)


def _grader_passed(
    result: GraderPassed | GraderFailed | GraderInfrastructureError,
) -> bool | None:
    match result:
        case GraderPassed():
            return True
        case GraderFailed():
            return False
        case GraderInfrastructureError():
            return None
        case _:
            assert_never(result)


async def _preflight_images(
    planned: tuple[PlannedRun, ...],
    writer: ShadowWriter,
    images: tuple[str, str],
) -> bool:
    if await to_thread.run_sync(preflight_local_images, images):
        return True
    for item in planned:
        writer.append(
            RunStarted(
                session_id=item.session_id,
                arm=item.arm,
                model=item.model,
                reasoning_effort=item.reasoning_effort,
            )
        )
        writer.append(empty_finished_event(item, "error", "ImagePreflightError"))
    return False


async def run_evaluation(options: EvalOptions) -> int:  # noqa: C901, PLR0912
    """Own evaluation filesystem I/O and sequential live execution."""
    manifest = TaskManifest.load(options.tasks)
    options.output_dir.mkdir(parents=True, exist_ok=True)
    run_root = options.output_dir / options.run_id
    try:
        run_root.mkdir()
    except FileExistsError:
        return 2

    writer = ShadowWriter(run_root / "events.jsonl")
    planned = _planned_runs(options, manifest)
    for item in planned:
        writer.append(
            RunPlanned(
                session_id=item.session_id,
                task_id=item.task.id,
                arm=item.arm,
                model=item.model,
                reasoning_effort=item.reasoning_effort,
                profile=SUPER_SOL_PROFILE.name,
                profile_version=SUPER_SOL_PROFILE.version,
                run_digest=item.run_digest,
                task_digest=item.task_digest,
                preregistration_digest=item.preregistration_digest,
                harness_version=item.harness_version,
                agents_sdk_version=item.agents_sdk_version,
                openai_sdk_version=item.openai_sdk_version,
                verification_image=item.verification_image,
                grader_image=item.grader_image,
            )
        )
    if options.dry_run:
        return 0
    if not os.environ.get("OPENAI_API_KEY"):
        for item in planned:
            writer.append(empty_finished_event(item, "error", "MissingApiKeyError"))
        return 1

    verification_image = cast("str", options.verification_image)
    grader_image = cast("str", options.grader_image)
    if not await _preflight_images(planned, writer, (verification_image, grader_image)):
        return 1

    (run_root / "workspaces").mkdir()
    (run_root / "ledgers").mkdir()
    failed = False
    for index, item in enumerate(planned):
        writer.append(
            RunStarted(
                session_id=item.session_id,
                arm=item.arm,
                model=item.model,
                reasoning_effort=item.reasoning_effort,
            )
        )
        run = create_live_run(item, run_root)
        try:
            outcome = await execute_live(run, options.max_gate_retries, verification_image)
            grader_result = await run_out_of_band_grader(
                run.workspace,
                grader_image,
                item.task.grader_argv,
                AnyioDockerRunner(),
            )
        except Exception as error:  # noqa: BLE001 - CLI boundary; # noqa: BROAD_EXCEPT_OK
            writer.append(finished_event(run, "error", type(error).__name__, grader_passed=False))
            failed = True
            continue
        except BaseException as error:  # noqa: BLE001 - CLI boundary; # noqa: BROAD_EXCEPT_OK
            error_type = type(error).__name__
            writer.append(finished_event(run, "abandoned", error_type, grader_passed=False))
            for remaining in planned[index + 1 :]:
                writer.append(empty_finished_event(remaining, "abandoned", error_type))
            return 1

        grader_passed = _grader_passed(grader_result)
        if grader_passed is None:
            writer.append(
                finished_event(
                    run,
                    "error",
                    "GraderInfrastructureError",
                    grader_passed=None,
                )
            )
            failed = True
            continue

        match outcome:
            case RunCompleted():
                writer.append(finished_event(run, "completed", None, grader_passed=grader_passed))
                failed = failed or not grader_passed
            case RunExhausted():
                writer.append(finished_event(run, "exhausted", None, grader_passed=grader_passed))
                failed = True
            case _:
                assert_never(outcome)
    return int(failed)


def evaluate(  # noqa: PLR0913
    tasks: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    output_dir: Annotated[Path, typer.Option()],
    run_id: Annotated[str, typer.Option()],
    product_model: Annotated[str, typer.Option()] = "gpt-5.6-terra",
    reference_model: Annotated[str, typer.Option()] = "gpt-5.6-sol",
    product_effort: Annotated[str, typer.Option()] = "medium",
    reference_effort: Annotated[str, typer.Option()] = "medium",
    max_gate_retries: Annotated[int, typer.Option(min=0, max=5)] = 2,
    arm_design: Annotated[ArmDesign, typer.Option()] = ArmDesign.HOLDOUT,
    dry_run: Annotated[bool, typer.Option()] = False,
    confirm_billable: Annotated[bool, typer.Option()] = False,
    verification_image: Annotated[str | None, typer.Option()] = None,
    grader_image: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Run a paired model evaluation; the CLI signature is the option contract."""
    try:
        options = EvalOptions(
            tasks=tasks,
            output_dir=output_dir,
            run_id=run_id,
            models=(product_model, reference_model),
            efforts=(
                cast("ReasoningEffort", product_effort),
                cast("ReasoningEffort", reference_effort),
            ),
            max_gate_retries=max_gate_retries,
            dry_run=dry_run,
            confirm_billable=confirm_billable,
            arm_design=arm_design,
            verification_image=verification_image,
            grader_image=grader_image,
        )
    except ValidationError as error:
        raise typer.BadParameter(str(error), param_hint="evaluation options") from error
    exit_code = anyio.run(run_evaluation, options)
    if exit_code != 0:
        raise typer.Exit(exit_code)


app = typer.Typer(no_args_is_help=True)
_ = app.command()(evaluate)


def main() -> None:
    """Run the installed evaluation console script."""
    app()
