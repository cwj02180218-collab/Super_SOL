import json
from pathlib import Path

from pydantic import JsonValue, TypeAdapter
from typer.testing import CliRunner

from fablized_sol.eval.day0_ab import app

_RUNNER = CliRunner()
_ROW_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])
_STRING_ADAPTER = TypeAdapter[str](str)


def _manifest(tmp_path: Path) -> Path:
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    path = tmp_path / "tasks.json"
    _ = path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "paired-task",
                        "prompt": "Fix and verify the fixture.",
                        "fixture": "fixture",
                        "verify_argv": ["pytest", "-q"],
                        "grader_argv": ["pytest", "-q"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_crossover_plans_each_task_in_both_arms_for_both_models(tmp_path: Path) -> None:
    # Given one task and the crossover experiment design
    output_dir = tmp_path / "out"

    # When the evaluator plans a dry run
    result = _RUNNER.invoke(
        app,
        [
            "--tasks",
            str(_manifest(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "day1-crossover",
            "--arm-design",
            "crossover",
            "--dry-run",
        ],
    )

    # Then every model receives directly comparable ON and OFF runs
    assert result.exit_code == 0
    rows = [
        _ROW_ADAPTER.validate_json(line)
        for line in (output_dir / "day1-crossover" / "events.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    planned = [row for row in rows if row["event"] == "run_planned"]
    assert len(planned) == 4
    assert {
        (
            _STRING_ADAPTER.validate_python(row["model"]),
            _STRING_ADAPTER.validate_python(row["arm"]),
        )
        for row in planned
    } == {
        ("gpt-5.6-terra", "on"),
        ("gpt-5.6-terra", "off"),
        ("gpt-5.6-sol", "on"),
        ("gpt-5.6-sol", "off"),
    }
    assert len({_STRING_ADAPTER.validate_python(row["session_id"]) for row in planned}) == 4
