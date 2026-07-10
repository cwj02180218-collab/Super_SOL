import json
from pathlib import Path

import pytest
from agents import Agent, ModelResponse, RunContextWrapper, Usage
from pydantic import JsonValue, TypeAdapter
from typer.testing import CliRunner

from fablized_sol.engine.models import GateAction
from fablized_sol.eval.day0_ab import app
from fablized_sol.harness.run import (
    AttemptBlocked,
    AttemptCompleted,
    AttemptRequest,
    SdkAttemptExecutor,
)
from fablized_sol.harness.workspace_tools import FablizedContext

_RUNNER = CliRunner()
_ROW_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])
_STRING_ADAPTER = TypeAdapter[str](str)


def _example_manifest(tmp_path: Path) -> Path:
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
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _read_jsonl(path: Path) -> list[dict[str, JsonValue]]:
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
    result = _RUNNER.invoke(
        app,
        [
            "--tasks",
            str(_example_manifest(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "day0-test",
            "--dry-run",
        ],
    )

    # Then both configured models are planned without accessing the network
    assert result.exit_code == 0
    rows = _read_jsonl(output_dir / "day0-test" / "events.jsonl")
    assert {_text(row, "model") for row in rows if row["event"] == "run_planned"} == {
        "gpt-5.6-sol",
        "gpt-5.5",
    }


def test_dry_run_pairs_arms_and_separates_sessions(tmp_path: Path) -> None:
    # Given one task evaluated against two models
    output_dir = tmp_path / "out"

    # When planning the paired evaluation
    result = _RUNNER.invoke(
        app,
        [
            "--tasks",
            str(_example_manifest(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "paired",
            "--dry-run",
        ],
    )

    # Then models share one arm but have distinct deterministic session IDs
    assert result.exit_code == 0
    rows = _read_jsonl(output_dir / "paired" / "events.jsonl")
    planned = [row for row in rows if row["event"] == "run_planned"]
    assert len({_text(row, "arm") for row in planned}) == 1
    assert len({_text(row, "session_id") for row in planned}) == 2


def test_existing_run_root_fails_without_appending(tmp_path: Path) -> None:
    # Given an already populated run root
    output_dir = tmp_path / "out"
    run_root = output_dir / "existing"
    run_root.mkdir(parents=True)
    marker = run_root / "events.jsonl"
    _ = marker.write_text("original\n", encoding="utf-8")

    # When a repeated invocation targets the same run identifier
    result = _RUNNER.invoke(
        app,
        [
            "--tasks",
            str(_example_manifest(tmp_path)),
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


def test_live_run_is_sequential_isolated_and_records_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given an offline attempt seam that mutates its first isolated workspace
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    observed: list[tuple[str, Path]] = []

    async def execute(
        self: SdkAttemptExecutor,
        request: AttemptRequest,
    ) -> AttemptCompleted:
        del request
        assert self.hooks is not None
        observed.append((str(self.model), self.context.workspace))
        assert not (self.context.workspace / "other-session.txt").exists()
        _ = (self.context.workspace / "other-session.txt").write_text("private", encoding="utf-8")
        await self.hooks.on_llm_end(
            RunContextWrapper(context=self.context, usage=Usage()),
            Agent[FablizedContext](name="offline"),
            ModelResponse(
                output=[],
                usage=Usage(input_tokens=11, output_tokens=7, total_tokens=18),
                response_id="offline",
            ),
        )
        return AttemptCompleted(output="offline completion")

    monkeypatch.setattr(SdkAttemptExecutor, "execute", execute)
    output_dir = tmp_path / "out"

    # When the live CLI executes both models
    result = _RUNNER.invoke(
        app,
        [
            "--tasks",
            str(_example_manifest(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "live-offline",
        ],
    )

    # Then runs are sequential, isolated, classified once, and retain token costs
    assert result.exit_code == 0
    assert [model for model, _workspace in observed] == ["gpt-5.6-sol", "gpt-5.5"]
    assert observed[0][1] != observed[1][1]
    rows = _read_jsonl(output_dir / "live-offline" / "events.jsonl")
    finished = [row for row in rows if row["event"] == "run_finished"]
    assert [row["status"] for row in finished] == ["completed", "completed"]
    assert [row["input_tokens"] for row in finished] == [11, 11]
    assert [row["output_tokens"] for row in finished] == [7, 7]
    for row in finished:
        ledger = output_dir / "live-offline" / "ledgers" / f"{row['session_id']}.jsonl"
        ledger_rows = _read_jsonl(ledger)
        assert [event["event"] for event in ledger_rows].count("classify") == 1


def test_live_run_retains_error_and_continues_pair(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given the first offline model fails outside the bounded runner
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    async def execute(
        self: SdkAttemptExecutor,
        request: AttemptRequest,
    ) -> AttemptCompleted:
        del request
        if str(self.model) == "gpt-5.6-sol":
            message = "offline failure"
            raise RuntimeError(message)
        return AttemptCompleted(output="baseline completion")

    monkeypatch.setattr(SdkAttemptExecutor, "execute", execute)
    output_dir = tmp_path / "out"

    # When the live evaluation runs the pair
    result = _RUNNER.invoke(
        app,
        [
            "--tasks",
            str(_example_manifest(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "error-pair",
        ],
    )

    # Then the error is terminally recorded and the baseline still completes
    assert result.exit_code != 0
    rows = _read_jsonl(output_dir / "error-pair" / "events.jsonl")
    finished = [row for row in rows if row["event"] == "run_finished"]
    assert [row["status"] for row in finished] == ["error", "completed"]
    assert finished[0]["error_type"] == "RuntimeError"


def test_live_run_retains_exhaustion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given every offline attempt reports an exhausted verification gate
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    async def execute(
        self: SdkAttemptExecutor,
        request: AttemptRequest,
    ) -> AttemptBlocked:
        del self, request
        return AttemptBlocked(
            action=GateAction.EXHAUSTED,
            reason="verification retry limit exhausted",
            blocked_output="unverified",
        )

    monkeypatch.setattr(SdkAttemptExecutor, "execute", execute)
    output_dir = tmp_path / "out"

    # When the live evaluation runs the pair
    result = _RUNNER.invoke(
        app,
        [
            "--tasks",
            str(_example_manifest(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "exhausted-pair",
        ],
    )

    # Then exhaustion is retained rather than converted to completion or error
    assert result.exit_code == 0
    rows = _read_jsonl(output_dir / "exhausted-pair" / "events.jsonl")
    finished = [row for row in rows if row["event"] == "run_finished"]
    assert [row["status"] for row in finished] == ["exhausted", "exhausted"]
