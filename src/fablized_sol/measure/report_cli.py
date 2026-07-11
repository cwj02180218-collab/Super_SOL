"""CLI for Super Sol Day 3 benchmark reports."""

from pathlib import Path
from typing import Annotated

import typer

from fablized_sol.measure.report import build_report
from fablized_sol.measure.report_models import BenchmarkReport, ReportInputError


def _markdown(report: BenchmarkReport) -> str:
    baseline = report.baseline_model.replace("|", "\\|").replace("\n", " ")
    reference = report.reference_model.replace("|", "\\|").replace("\n", " ")
    wall_time_header = "Wall-time delta (95% CI)"
    paired_header = (
        f"| Model | Effort | Quality delta (95% CI) | Token delta (95% CI) | {wall_time_header} |"
    )
    lines = [
        "# Super Sol Day 3 Report",
        "",
        f"Baseline: `{baseline}` (`{report.baseline_effort}`)  ",
        f"Reference: `{reference}` (`{report.reference_effort}`)",
        f"Run digest: `{report.run_digest}`  ",
        f"Quality interval: `{report.quality_interval_method}`",
        f"Resource interval: `{report.resource_interval_method}`",
        "",
        "| Model | Effort | Arm | Quality | Tokens | Tokens / good run | Mean seconds |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for cell in report.cells:
        model = cell.model.replace("|", "\\|").replace("\n", " ")
        efficiency = (
            f"{cell.tokens_per_defect_free_run:.1f}"
            if cell.tokens_per_defect_free_run is not None
            else "n/a"
        )
        row = (
            f"| {model} | {cell.reasoning_effort} | {cell.arm} | {cell.quality_rate:.1%} | "
            f"{cell.token_volume} | {efficiency} | {cell.mean_wall_time_seconds:.2f} |"
        )
        lines.append(row)
    lines.extend(
        [
            "",
            "## Paired ON-minus-OFF effects",
            "",
            paired_header,
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for effect in report.paired_effects:
        model = effect.model.replace("|", "\\|").replace("\n", " ")
        row = (
            f"| {model} | {effect.reasoning_effort} | {effect.quality_delta:.1%} "
            f"[{effect.quality_ci_low:.1%}, {effect.quality_ci_high:.1%}] | "
            f"{effect.mean_token_delta:.1f} "
            f"[{effect.token_ci_low:.1f}, {effect.token_ci_high:.1f}] | "
            f"{effect.mean_wall_time_delta:.2f} "
            f"[{effect.wall_time_ci_low:.2f}, {effect.wall_time_ci_high:.2f}] |"
        )
        lines.append(row)
    lines.extend(
        [
            "",
            "## Paired reference-minus-baseline effects",
            "",
            "| Arm | Quality delta (95% CI) | Token delta (95% CI) | Wall-time delta (95% CI) |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for effect in report.model_effects:
        row = (
            f"| {effect.arm} | {effect.quality_delta:.1%} "
            f"[{effect.quality_ci_low:.1%}, {effect.quality_ci_high:.1%}] | "
            f"{effect.mean_token_delta:.1f} "
            f"[{effect.token_ci_low:.1f}, {effect.token_ci_high:.1f}] | "
            f"{effect.mean_wall_time_delta:.2f} "
            f"[{effect.wall_time_ci_low:.2f}, {effect.wall_time_ci_high:.2f}] |"
        )
        lines.append(row)
    lines.extend(
        [
            "",
            "## Lazy baseline-first cascade",
            "",
            "| Arm | Quality | Escalation | Token savings vs always-reference |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for cascade in report.lazy_cascades:
        savings = (
            f"{cascade.token_savings_rate:.1%}" if cascade.token_savings_rate is not None else "n/a"
        )
        row = (
            f"| {cascade.arm} | {cascade.quality_rate:.1%} | "
            f"{cascade.escalation_rate:.1%} | {savings} |"
        )
        lines.append(row)
    return "\n".join(lines) + "\n"


def report_command(
    events: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    grades: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    output: Annotated[Path, typer.Option(dir_okay=False)],
    baseline_model: Annotated[str, typer.Option()] = "gpt-5.6-terra",
    reference_model: Annotated[str, typer.Option()] = "gpt-5.6-sol",
) -> None:
    """Analyze complete shadow events and external quality grades."""
    if output.suffix != ".json":
        message = "output must use a .json suffix"
        raise typer.BadParameter(message, param_hint="output")
    markdown_output = output.with_suffix(".md")
    candidates = (output, markdown_output)
    if any(path.exists() or path.is_symlink() for path in candidates):
        message = "report output paths must not already exist"
        raise typer.BadParameter(message, param_hint="output")
    if any(parent.is_symlink() for parent in output.parents if parent.exists()):
        message = "report output parent must not be a symlink"
        raise typer.BadParameter(message, param_hint="output")
    try:
        report = build_report(events, grades, baseline_model, reference_model)
    except ReportInputError as error:
        raise typer.BadParameter(str(error), param_hint="benchmark evidence") from error
    output.parent.mkdir(parents=True, exist_ok=True)
    json_created = False
    markdown_created = False
    try:
        with output.open("x", encoding="utf-8") as stream:
            json_created = True
            _ = stream.write(report.model_dump_json(indent=2) + "\n")
        with markdown_output.open("x", encoding="utf-8") as stream:
            markdown_created = True
            _ = stream.write(_markdown(report))
    except OSError:
        if json_created:
            output.unlink(missing_ok=True)
        if markdown_created:
            markdown_output.unlink(missing_ok=True)
        raise


app = typer.Typer(no_args_is_help=True)
_ = app.command(name="report")(report_command)


def main() -> None:
    """Run the installed report console script."""
    app()
