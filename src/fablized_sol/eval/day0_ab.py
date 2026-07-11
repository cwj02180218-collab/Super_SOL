"""Sequential paired Day 0 evaluation CLI."""

import os
from hashlib import sha256
from pathlib import Path
from typing import Annotated, assert_never

import anyio
import typer
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
from fablized_sol.eval.manifest import ArmDesign, EvalOptions, TaskManifest
from fablized_sol.harness.container_runtime import AnyioDockerRunner
from fablized_sol.harness.run import RunCompleted, RunExhausted
from fablized_sol.measure.holdout import assign_arm
from fablized_sol.measure.shadow import RunPlanned, RunStarted, ShadowWriter
from fablized_sol.measure.super_sol import SUPER_SOL_PROFILE


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _planned_runs(options: EvalOptions, manifest: TaskManifest) -> tuple[PlannedRun, ...]:
    planned: list[PlannedRun] = []
    for task in manifest.tasks:
        assignment_key = SessionId(_digest(f"{options.run_id}:{task.id}"))
        arms_by_design = {
            ArmDesign.HOLDOUT: (assign_arm(assignment_key),),
            ArmDesign.CROSSOVER: (HoldoutArm.ON, HoldoutArm.OFF),
        }
        arms = arms_by_design[options.arm_design]
        models = options.models
        if options.arm_design is ArmDesign.CROSSOVER:
            if int(assignment_key[-1], 16) % 2:
                arms = tuple(reversed(arms))
            if int(_digest(f"{assignment_key}:model-order")[-1], 16) % 2:
                models = tuple(reversed(models))
        planned.extend(
            PlannedRun(
                task=task,
                model=model,
                session_id=SessionId(_digest(f"{options.run_id}:{task.id}:{model}:{arm}")),
                arm=arm,
            )
            for arm in arms
            for model in models
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
                profile=SUPER_SOL_PROFILE.name,
                profile_version=SUPER_SOL_PROFILE.version,
            )
        )
    if options.dry_run:
        return 0
    if not os.environ.get("OPENAI_API_KEY"):
        for item in planned:
            writer.append(empty_finished_event(item, "error", "MissingApiKeyError"))
        return 1

    (run_root / "workspaces").mkdir()
    (run_root / "ledgers").mkdir()
    failed = False
    for index, item in enumerate(planned):
        writer.append(RunStarted(session_id=item.session_id, arm=item.arm, model=item.model))
        run = create_live_run(item, run_root)
        try:
            image = options.verification_image
            grader_image = options.grader_image
            if image is None or grader_image is None:
                writer.append(
                    finished_event(run, "error", "MissingImageError", grader_passed=False)
                )
                failed = True
                continue
            outcome = await execute_live(run, options.max_gate_retries, image)
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
    product_model: Annotated[str, typer.Option()] = "gpt-5.5",
    reference_model: Annotated[str, typer.Option()] = "gpt-5.6-sol",
    max_gate_retries: Annotated[int, typer.Option(min=0, max=5)] = 2,
    arm_design: Annotated[ArmDesign, typer.Option()] = ArmDesign.HOLDOUT,
    dry_run: Annotated[bool, typer.Option()] = False,
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
            max_gate_retries=max_gate_retries,
            dry_run=dry_run,
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
