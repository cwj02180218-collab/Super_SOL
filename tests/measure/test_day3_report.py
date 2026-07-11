import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fablized_sol.engine.models import HoldoutArm
from fablized_sol.measure.report import build_report
from fablized_sol.measure.report_cli import app
from fablized_sol.measure.report_models import BenchmarkReport, GradeFile

_RUNNER = CliRunner()


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    events = tmp_path / "events.jsonl"
    grades = tmp_path / "grades.json"
    rows: list[dict[str, str | int | float | bool | None]] = []
    grade_rows: list[dict[str, str | bool]] = []
    samples = (
        ("task-a", "gpt-5.5", "on", "a-base", "completed", 100, False),
        ("task-a", "gpt-5.6-sol", "on", "a-ref", "completed", 200, False),
        ("task-b", "gpt-5.5", "on", "b-base", "completed", 100, True),
        ("task-b", "gpt-5.6-sol", "on", "b-ref", "completed", 200, False),
        ("task-a", "gpt-5.5", "off", "a-base-off", "completed", 120, False),
        ("task-a", "gpt-5.6-sol", "off", "a-ref-off", "completed", 220, False),
        ("task-b", "gpt-5.5", "off", "b-base-off", "completed", 120, False),
        ("task-b", "gpt-5.6-sol", "off", "b-ref-off", "completed", 220, True),
    )
    for task_id, model, arm, session_id, status, tokens, defect in samples:
        grader_passed = session_id != "b-base"
        rows.append(
            {
                "event": "run_planned",
                "ts": "2026-07-11T00:00:00Z",
                "session_id": session_id,
                "task_id": task_id,
                "arm": arm,
                "model": model,
                "profile": "super-sol",
                "profile_version": "2026-07-11",
            }
        )
        rows.append(
            {
                "event": "run_started",
                "ts": "2026-07-11T00:00:00Z",
                "session_id": session_id,
                "arm": arm,
                "model": model,
            }
        )
        rows.append(
            {
                "event": "run_finished",
                "ts": "2026-07-11T00:00:01Z",
                "session_id": session_id,
                "arm": arm,
                "model": model,
                "status": status,
                "wall_time_seconds": 1.0,
                "tool_calls": 2,
                "failed_verifications": 0,
                "gate_blocks": 0,
                "input_tokens": tokens - 10,
                "output_tokens": 10,
                "grader_passed": grader_passed,
                "final_defect_found": None,
                "error_type": None,
            }
        )
        grade_rows.append({"session_id": session_id, "final_defect_found": defect})
    _ = events.write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows),
        encoding="utf-8",
    )
    _ = grades.write_text(json.dumps({"grades": grade_rows}), encoding="utf-8")
    return events, grades


def test_report_quantifies_quality_efficiency_and_lazy_escalation(tmp_path: Path) -> None:
    # Given complete out-of-band grades for paired baseline and reference runs
    events, grades = _write_inputs(tmp_path)
    output = tmp_path / "report.json"

    # When the Day 3 analyzer builds a machine-readable report
    result = _RUNNER.invoke(
        app,
        [
            "--events",
            str(events),
            "--grades",
            str(grades),
            "--output",
            str(output),
            "--baseline-model",
            "gpt-5.5",
            "--reference-model",
            "gpt-5.6-sol",
        ],
    )

    # Then it separates model cells and prices the lazy fallback in token volume
    assert result.exit_code == 0
    report = BenchmarkReport.model_validate_json(output.read_text(encoding="utf-8"))
    cells = {(cell.model, cell.arm): cell for cell in report.cells}
    assert cells[("gpt-5.5", HoldoutArm.ON)].quality_rate == 0.5
    assert cells[("gpt-5.6-sol", HoldoutArm.ON)].quality_rate == 1.0
    cascades = {cascade.arm: cascade for cascade in report.lazy_cascades}
    cascade = cascades[HoldoutArm.ON]
    assert cascade.arm == "on"
    assert cascade.escalation_rate == 0.5
    assert cascade.quality_rate == 1.0
    assert cascade.token_volume == 400
    assert cascade.always_reference_token_volume == 400
    assert cascade.token_savings_rate == 0.0
    effects = {effect.model: effect for effect in report.paired_effects}
    assert effects["gpt-5.5"].quality_delta == -0.5
    assert effects["gpt-5.5"].mean_token_delta == -20.0
    assert effects["gpt-5.6-sol"].quality_delta == 0.5


def test_report_fails_closed_when_an_out_of_band_grade_is_missing(tmp_path: Path) -> None:
    # Given one omitted human grade
    events, grades = _write_inputs(tmp_path)
    payload = GradeFile.model_validate_json(grades.read_text(encoding="utf-8"))
    incomplete = payload.model_copy(update={"grades": payload.grades[:-1]})
    _ = grades.write_text(incomplete.model_dump_json(), encoding="utf-8")

    # When the analyzer is invoked
    result = _RUNNER.invoke(
        app,
        [
            "--events",
            str(events),
            "--grades",
            str(grades),
            "--output",
            str(tmp_path / "report.json"),
        ],
    )

    # Then incomplete quality evidence cannot become a benchmark claim
    assert result.exit_code != 0
    assert "missing grade" in result.output


def test_report_rejects_identical_model_roles_and_markdown_output_path(tmp_path: Path) -> None:
    # Given complete crossover evidence but invalid report options
    events, grades = _write_inputs(tmp_path)

    # When model roles collide or the JSON output uses a Markdown suffix
    duplicate = _RUNNER.invoke(
        app,
        [
            "--events",
            str(events),
            "--grades",
            str(grades),
            "--output",
            str(tmp_path / "duplicate.json"),
            "--baseline-model",
            "gpt-5.5",
            "--reference-model",
            "gpt-5.5",
        ],
    )
    collision = _RUNNER.invoke(
        app,
        [
            "--events",
            str(events),
            "--grades",
            str(grades),
            "--output",
            str(tmp_path / "report.md"),
        ],
    )
    target = tmp_path / "target.txt"
    _ = target.write_text("keep", encoding="utf-8")
    symlink = tmp_path / "linked.json"
    symlink.symlink_to(target)
    linked = _RUNNER.invoke(
        app,
        [
            "--events",
            str(events),
            "--grades",
            str(grades),
            "--output",
            str(symlink),
        ],
    )

    # Then neither invalid request can produce a report
    assert duplicate.exit_code != 0
    assert collision.exit_code != 0
    assert linked.exit_code != 0
    assert not (tmp_path / "duplicate.json").exists()
    assert not (tmp_path / "report.md").exists()
    assert target.read_text(encoding="utf-8") == "keep"


def test_report_rejects_out_of_order_lifecycle_events(tmp_path: Path) -> None:
    # Given complete crossover records with one finish placed before its start
    events, grades = _write_inputs(tmp_path)
    lines = events.read_text(encoding="utf-8").splitlines()
    lines[:3] = (lines[2], lines[1], lines[0])
    _ = events.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # When the report reads the append-only stream
    result = _RUNNER.invoke(
        app,
        [
            "--events",
            str(events),
            "--grades",
            str(grades),
            "--output",
            str(tmp_path / "report.json"),
        ],
    )

    # Then lifecycle reordering cannot become benchmark evidence
    assert result.exit_code != 0
    assert "out of order" in result.output


def test_report_rolls_back_json_if_markdown_creation_races(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given valid evidence and a competing Markdown creator after initial validation
    events, grades = _write_inputs(tmp_path)
    markdown = tmp_path / "race.md"

    def racing_build(
        events_path: Path,
        grades_path: Path,
        baseline_model: str,
        reference_model: str,
    ) -> BenchmarkReport:
        report = build_report(events_path, grades_path, baseline_model, reference_model)
        _ = markdown.write_text("other process\n", encoding="utf-8")
        return report

    monkeypatch.setattr("fablized_sol.measure.report_cli.build_report", racing_build)
    output = tmp_path / "race.json"

    # When JSON succeeds but exclusive Markdown creation loses the race
    result = _RUNNER.invoke(
        app,
        ["--events", str(events), "--grades", str(grades), "--output", str(output)],
    )

    # Then the command leaves no partial JSON and preserves the competing file
    assert result.exit_code != 0
    assert not output.exists()
    assert markdown.read_text(encoding="utf-8") == "other process\n"
