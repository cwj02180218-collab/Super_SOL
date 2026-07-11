"""Sequential paired Day 0 evaluation CLI."""

import os
from hashlib import sha256
from pathlib import Path
from typing import Annotated, assert_never

import anyio
import typer
from pydantic import ValidationError

from fablized_sol.engine.models import SessionId
from fablized_sol.eval.live import (
    PlannedRun,
    create_live_run,
    empty_finished_event,
    execute_live,
    finished_event,
)
from fablized_sol.eval.manifest import EvalOptions, TaskManifest
from fablized_sol.harness.run import RunCompleted, RunExhausted
from fablized_sol.measure.holdout import assign_arm
from fablized_sol.measure.shadow import RunPlanned, RunStarted, ShadowWriter


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _planned_runs(options: EvalOptions, manifest: TaskManifest) -> tuple[PlannedRun, ...]:
    planned: list[PlannedRun] = []
    for task in manifest.tasks:
        assignment_key = SessionId(_digest(f"{options.run_id}:{task.id}"))
        arm = assign_arm(assignment_key)
        planned.extend(
            PlannedRun(
                task=task,
                model=model,
                session_id=SessionId(_digest(f"{options.run_id}:{task.id}:{model}")),
                arm=arm,
            )
            for model in options.models
        )
    return tuple(planned)


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
            if image is None:
                writer.append(finished_event(run, "error", "MissingVerificationImageError"))
                failed = True
                continue
            outcome = await execute_live(run, options.max_gate_retries, image)
        except Exception as error:  # noqa: BLE001 - CLI boundary; # noqa: BROAD_EXCEPT_OK
            writer.append(finished_event(run, "error", type(error).__name__))
            failed = True
            continue
        except BaseException as error:  # noqa: BLE001 - CLI boundary; # noqa: BROAD_EXCEPT_OK
            error_type = type(error).__name__
            writer.append(finished_event(run, "abandoned", error_type))
            for remaining in planned[index + 1 :]:
                writer.append(empty_finished_event(remaining, "abandoned", error_type))
            return 1

        match outcome:
            case RunCompleted():
                writer.append(finished_event(run, "completed", None))
            case RunExhausted():
                writer.append(finished_event(run, "exhausted", None))
                failed = True
            case _:
                assert_never(outcome)
    return int(failed)


def evaluate(  # noqa: PLR0913
    tasks: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    output_dir: Annotated[Path, typer.Option()],
    run_id: Annotated[str, typer.Option()],
    sol_model: Annotated[str, typer.Option()] = "gpt-5.6-sol",
    baseline_model: Annotated[str, typer.Option()] = "gpt-5.5",
    max_gate_retries: Annotated[int, typer.Option(min=0, max=5)] = 2,
    dry_run: Annotated[bool, typer.Option()] = False,
    verification_image: Annotated[str | None, typer.Option()] = None,
) -> None:
    """Run a paired model evaluation; the CLI signature is the option contract."""
    try:
        options = EvalOptions(
            tasks=tasks,
            output_dir=output_dir,
            run_id=run_id,
            models=(sol_model, baseline_model),
            max_gate_retries=max_gate_retries,
            dry_run=dry_run,
            verification_image=verification_image,
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
