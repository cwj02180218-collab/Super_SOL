import json
from pathlib import Path

import pytest
from pydantic import JsonValue, TypeAdapter
from typer.testing import CliRunner

from fablized_sol.eval.day0_ab import app
from fablized_sol.measure.super_sol import SUPER_SOL_PROFILE

RUNNER = CliRunner()
_ROW_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])
_STRING_ADAPTER = TypeAdapter[str](str)


def example_manifest(tmp_path: Path) -> Path:
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    _ = (fixture / "calc.py").write_text("def add(a: int, b: int) -> int:\n    return a - b\n")
    path = tmp_path / "tasks.json"
    _ = path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "python-logic",
                        "prompt": "Diagnose and fix the failing test.",
                        "fixture": "fixture",
                        "verify_argv": ["uv", "run", "pytest", "-q"],
                        "grader_argv": ["uv", "run", "pytest", "-q"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def read_jsonl(path: Path) -> list[dict[str, JsonValue]]:
    return [
        _ROW_ADAPTER.validate_json(line) for line in path.read_text(encoding="utf-8").splitlines()
    ]


def _text(row: dict[str, JsonValue], key: str) -> str:
    return _STRING_ADAPTER.validate_python(row[key])


def test_dry_run_emits_two_models_without_api_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given a valid task manifest and no live API credential
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    output_dir = tmp_path / "out"

    # When the default CLI command performs a dry run
    result = RUNNER.invoke(
        app,
        [
            "--tasks",
            str(example_manifest(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "day0-test",
            "--dry-run",
        ],
    )

    # Then both configured models are planned without accessing the network
    assert result.exit_code == 0
    rows = read_jsonl(output_dir / "day0-test" / "events.jsonl")
    planned = [row for row in rows if row["event"] == "run_planned"]
    assert {(_text(row, "model"), _text(row, "reasoning_effort")) for row in planned} == {
        ("gpt-5.6-terra", "medium"),
        ("gpt-5.6-sol", "medium"),
    }
    assert {_text(row, "profile") for row in planned} == {SUPER_SOL_PROFILE.name}
    assert {_text(row, "profile_version") for row in planned} == {SUPER_SOL_PROFILE.version}
    assert len({_text(row, "run_digest") for row in planned}) == 1
    assert all(len(_text(row, "run_digest")) == 64 for row in planned)
    assert all(len(_text(row, "task_digest")) == 64 for row in planned)
    assert {_text(row, "verification_image") for row in planned} == {"dry-run"}
    assert {_text(row, "grader_image") for row in planned} == {"dry-run"}
    assert all(_text(row, "preregistration_digest") for row in planned)
    assert all(_text(row, "harness_version") == "0.3.0" for row in planned)
    assert all(_text(row, "agents_sdk_version") for row in planned)
    assert all(_text(row, "openai_sdk_version") for row in planned)


def test_dry_run_pairs_arms_and_separates_sessions(tmp_path: Path) -> None:
    # Given one task evaluated against two models
    output_dir = tmp_path / "out"

    # When planning the paired evaluation
    result = RUNNER.invoke(
        app,
        [
            "--tasks",
            str(example_manifest(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "paired",
            "--dry-run",
        ],
    )

    # Then models share one arm but have distinct deterministic session IDs
    assert result.exit_code == 0
    rows = read_jsonl(output_dir / "paired" / "events.jsonl")
    planned = [row for row in rows if row["event"] == "run_planned"]
    assert len({_text(row, "arm") for row in planned}) == 1
    assert len({_text(row, "session_id") for row in planned}) == 2


def test_session_identity_changes_with_task_and_fixture_content(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first_manifest = example_manifest(first_root)
    second_manifest = example_manifest(second_root)
    second_text = second_manifest.read_text(encoding="utf-8").replace(
        "Diagnose and fix the failing test.",
        "A materially different task.",
    )
    _ = second_manifest.write_text(second_text, encoding="utf-8")
    _ = (second_root / "fixture" / "calc.py").write_text("def add(a, b):\n    return a + b\n")

    for manifest, output in (
        (first_manifest, tmp_path / "out-first"),
        (second_manifest, tmp_path / "out-second"),
    ):
        result = RUNNER.invoke(
            app,
            [
                "--tasks",
                str(manifest),
                "--output-dir",
                str(output),
                "--run-id",
                "same-label",
                "--dry-run",
            ],
        )
        assert result.exit_code == 0

    first = read_jsonl(tmp_path / "out-first" / "same-label" / "events.jsonl")
    second = read_jsonl(tmp_path / "out-second" / "same-label" / "events.jsonl")
    assert {_text(row, "run_digest") for row in first} != {
        _text(row, "run_digest") for row in second
    }
    assert {_text(row, "session_id") for row in first} != {
        _text(row, "session_id") for row in second
    }


def test_live_cli_rejects_missing_billable_confirmation_before_creating_run(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "out"
    result = RUNNER.invoke(
        app,
        [
            "--tasks",
            str(example_manifest(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "unconfirmed",
            "--verification-image",
            "ghcr.io/example/verify@sha256:" + "a" * 64,
            "--grader-image",
            "ghcr.io/example/grader@sha256:" + "b" * 64,
        ],
    )

    assert result.exit_code != 0
    assert "confirm-billable" in result.output
    assert not output_dir.exists()


def test_dry_run_rejects_identical_comparison_models_before_writing(tmp_path: Path) -> None:
    # Given both CLI comparison roles name the same model
    output_dir = tmp_path / "out"

    # When the evaluation is planned
    result = RUNNER.invoke(
        app,
        [
            "--tasks",
            str(example_manifest(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "duplicate-models",
            "--product-model",
            "gpt-5.5",
            "--reference-model",
            "gpt-5.5",
            "--dry-run",
        ],
    )

    # Then no colliding sessions or ledgers are created
    assert result.exit_code != 0
    assert "comparison models must be distinct" in result.output
    assert "Traceback" not in result.output
    assert not output_dir.exists()


def test_existing_run_root_fails_without_appending(tmp_path: Path) -> None:
    # Given an already populated run root
    output_dir = tmp_path / "out"
    run_root = output_dir / "existing"
    run_root.mkdir(parents=True)
    marker = run_root / "events.jsonl"
    _ = marker.write_text("original\n", encoding="utf-8")

    # When a repeated invocation targets the same run identifier
    result = RUNNER.invoke(
        app,
        [
            "--tasks",
            str(example_manifest(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "existing",
            "--dry-run",
        ],
    )

    # Then it fails before changing prior sample data
    assert result.exit_code != 0
    assert marker.read_text(encoding="utf-8") == "original\n"
