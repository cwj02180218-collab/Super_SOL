"""Independent clean-room aggregate reproduction and public-artifact audit."""

# Audit failures are deliberate boundary diagnostics.
# ruff: noqa: EM101, TRY003

from __future__ import annotations

import re
from math import isclose
from pathlib import Path  # noqa: TC003 - Typer resolves annotations at runtime
from statistics import fmean
from typing import Annotated, ClassVar, Final

import typer
from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError

from fablized_sol.eval.codex_cleanroom import CodexArm
from fablized_sol.measure.codex_ab import finalize_promotion
from fablized_sol.measure.codex_ab_models import (
    CodexABAudit,
    PromotionCandidate,
)

_OBJECT_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])
_CANDIDATE_ADAPTER = TypeAdapter[PromotionCandidate](PromotionCandidate)
_SECRET_PATTERN: Final = re.compile(rb"(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,})")
_FORBIDDEN_CONTENT: Final = (
    b'"access_token"',
    b'"refresh_token"',
    b'"prompt"',
    b"/opt/grader",
    b"grader_argv",
)


class _AuditSample(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="ignore", strict=True)

    task_id: str
    repetition: int = Field(ge=1)
    arm: CodexArm
    score: float
    full_pass: bool
    total_tokens: int = Field(ge=0)
    wall_time_seconds: float = Field(gt=0.0)


def _load_audit_samples(events: Path) -> tuple[_AuditSample, ...]:
    try:
        records = tuple(
            _OBJECT_ADAPTER.validate_json(line)
            for line in events.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    except (OSError, ValidationError) as error:
        raise ValueError("invalid audit event stream") from error
    samples: list[_AuditSample] = []
    for record in records:
        if record.get("type") != "slot.completed":
            continue
        arm = record.get("arm")
        if not isinstance(arm, str):
            raise TypeError("audit sample arm is missing")
        samples.append(_AuditSample.model_validate(record | {"arm": CodexArm(arm)}))
    return tuple(samples)


def _independent_aggregates(samples: tuple[_AuditSample, ...]) -> dict[str, float | int]:
    raw = tuple(sample for sample in samples if sample.arm is CodexArm.RAW)
    lean = tuple(sample for sample in samples if sample.arm is CodexArm.LEAN)
    raw_cells = {(sample.task_id, sample.repetition): sample for sample in raw}
    lean_cells = {(sample.task_id, sample.repetition): sample for sample in lean}
    if not raw or set(raw_cells) != set(lean_cells) or len(raw_cells) * 2 != len(samples):
        raise ValueError("audit requires a complete paired lattice")
    deltas = tuple(lean_cells[key].score - raw_cells[key].score for key in sorted(raw_cells))
    return {
        "pairs": len(deltas),
        "tasks": len({task_id for task_id, _repetition in raw_cells}),
        "mean_score_delta": fmean(deltas),
        "raw_mean_score": fmean(sample.score for sample in raw),
        "lean_mean_score": fmean(sample.score for sample in lean),
        "raw_full_pass_rate": fmean(float(sample.full_pass) for sample in raw),
        "lean_full_pass_rate": fmean(float(sample.full_pass) for sample in lean),
        "raw_mean_tokens": fmean(sample.total_tokens for sample in raw),
        "lean_mean_tokens": fmean(sample.total_tokens for sample in lean),
        "raw_mean_wall_time": fmean(sample.wall_time_seconds for sample in raw),
        "lean_mean_wall_time": fmean(sample.wall_time_seconds for sample in lean),
    }


def _aggregates_match(candidate: PromotionCandidate, observed: dict[str, float | int]) -> bool:
    comparisons: tuple[tuple[float | int, float | int], ...] = (
        (observed["pairs"], candidate.pairs),
        (observed["tasks"], candidate.tasks),
        (observed["mean_score_delta"], candidate.mean_score_delta),
        (observed["raw_mean_score"], candidate.raw_mean_score),
        (observed["lean_mean_score"], candidate.lean_mean_score),
        (observed["raw_full_pass_rate"], candidate.raw_full_pass_rate),
        (observed["lean_full_pass_rate"], candidate.lean_full_pass_rate),
        (observed["raw_mean_tokens"], candidate.raw_mean_tokens),
        (observed["lean_mean_tokens"], candidate.lean_mean_tokens),
        (observed["raw_mean_wall_time"], candidate.raw_mean_wall_time),
        (observed["lean_mean_wall_time"], candidate.lean_mean_wall_time),
    )
    for value, expected in comparisons:
        if isinstance(value, int) and isinstance(expected, int):
            if value != expected:
                return False
        elif not isclose(float(value), float(expected), rel_tol=0.0, abs_tol=1e-9):
            return False
    return True


def _artifact_findings(root: Path, expected: tuple[Path, ...]) -> tuple[int, int]:
    omissions = sum(not path.is_file() for path in expected)
    leakage = 0
    if root.is_symlink() or not root.is_dir():
        return omissions + 1, leakage
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            leakage += 1
            continue
        if not path.is_file():
            continue
        lowered_name = path.name.casefold()
        content = path.read_bytes()
        if "hidden" in lowered_name or _SECRET_PATTERN.search(content) is not None:
            leakage += 1
            continue
        if any(marker in content for marker in _FORBIDDEN_CONTENT):
            leakage += 1
    return omissions, leakage


def audit_codex_ab(events: Path, candidate_path: Path, artifact_root: Path) -> CodexABAudit:
    """Recompute core aggregates independently and scan declared public artifacts."""
    try:
        candidate = _CANDIDATE_ADAPTER.validate_json(candidate_path.read_text(encoding="utf-8"))
        observed = _independent_aggregates(_load_audit_samples(events))
    except (OSError, TypeError, ValidationError, ValueError):
        return CodexABAudit(
            artifact_omissions=1,
            leakage_findings=0,
            aggregate_reproduced=False,
        )
    omissions, leakage = _artifact_findings(
        artifact_root,
        (events, artifact_root / "run.json", candidate_path),
    )
    return CodexABAudit(
        artifact_omissions=omissions,
        leakage_findings=leakage,
        aggregate_reproduced=_aggregates_match(candidate, observed),
    )


def audit(
    events: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    candidate: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    artifact_root: Annotated[Path, typer.Option(exists=True, file_okay=False)],
    audit_output: Annotated[Path, typer.Option()],
    final_output: Annotated[Path, typer.Option()],
) -> None:
    """Write independent audit evidence and the finalized all-gates decision."""
    try:
        candidate_record = _CANDIDATE_ADAPTER.validate_json(candidate.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as error:
        raise typer.BadParameter(str(error), param_hint="candidate") from error
    audit_record = audit_codex_ab(events, candidate, artifact_root)
    decision = finalize_promotion(candidate_record, audit_record)
    audit_output.parent.mkdir(parents=True, exist_ok=True)
    final_output.parent.mkdir(parents=True, exist_ok=True)
    _ = audit_output.write_text(audit_record.model_dump_json(indent=2), encoding="utf-8")
    _ = final_output.write_text(decision.model_dump_json(indent=2), encoding="utf-8")


app = typer.Typer(no_args_is_help=True)
_ = app.command()(audit)


def main() -> None:
    """Run the installed independent Codex A/B audit command."""
    app()
