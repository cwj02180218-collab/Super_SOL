import json
from pathlib import Path

import pytest
from pydantic import JsonValue, TypeAdapter

from fablized_sol.measure.report import build_report
from fablized_sol.measure.report_models import ReportInputError

from .test_day3_report import write_inputs

_ROW_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])


def _add_effort(events: Path, *, mismatched_start: bool = False) -> None:
    rows = [
        _ROW_ADAPTER.validate_json(line) for line in events.read_text(encoding="utf-8").splitlines()
    ]
    for row in rows:
        row["reasoning_effort"] = "medium"
    if mismatched_start:
        start = next(row for row in rows if row["event"] == "run_started")
        start["reasoning_effort"] = "high"
    _ = events.write_text("".join(f"{json.dumps(row)}\n" for row in rows), encoding="utf-8")


def test_report_records_reasoning_effort_for_models_and_cells(tmp_path: Path) -> None:
    events, grades = write_inputs(tmp_path)
    _add_effort(events)

    report = build_report(events, grades, "gpt-5.6-terra", "gpt-5.6-sol")

    assert report.baseline_effort == "medium"
    assert report.reference_effort == "medium"
    assert {cell.reasoning_effort for cell in report.cells} == {"medium"}


def test_report_rejects_plan_start_effort_mismatch(tmp_path: Path) -> None:
    events, grades = write_inputs(tmp_path)
    _add_effort(events, mismatched_start=True)

    with pytest.raises(ReportInputError, match="plan and finish disagree"):
        _ = build_report(events, grades, "gpt-5.6-terra", "gpt-5.6-sol")
