from pathlib import Path

import pytest
from agents import ModelResponse, Usage
from typer.testing import Result

from fablized_sol.engine.models import GateAction
from fablized_sol.eval.day0_ab import app
from fablized_sol.eval.grader import GraderPassed, GraderResult
from fablized_sol.harness.container_runtime import VerificationProcessRunner
from fablized_sol.harness.run import (
    AttemptBlocked,
    AttemptCompleted,
    AttemptRequest,
    SdkAttemptExecutor,
)

from .test_day0_ab import (
    RUNNER,
    example_manifest,
    read_jsonl,
)

_IMAGE = "ghcr.io/example/verify@sha256:" + "a" * 64
_GRADER_IMAGE = "ghcr.io/example/grader@sha256:" + "b" * 64


def _images_ready(_images: tuple[str, ...]) -> bool:
    return True


def _images_missing(_images: tuple[str, ...]) -> bool:
    return False


@pytest.fixture(autouse=True)
def local_image_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "fablized_sol.eval.day0_ab.preflight_local_images",
        _images_ready,
    )


async def _pass_grader(
    workspace: Path,
    image: str,
    argv: tuple[str, ...],
    runner: VerificationProcessRunner,
) -> GraderResult:
    del workspace, image, argv, runner
    return GraderPassed()


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
        assert self.response_observer is not None
        observed.append((str(self.model), self.context.workspace))
        assert not (self.context.workspace / "other-session.txt").exists()
        _ = (self.context.workspace / "other-session.txt").write_text("private", encoding="utf-8")
        self.response_observer.observe(
            ModelResponse(
                output=[],
                usage=Usage(input_tokens=11, output_tokens=7, total_tokens=18),
                response_id="offline",
            )
        )
        return AttemptCompleted(output="offline completion")

    monkeypatch.setattr(SdkAttemptExecutor, "execute", execute)
    monkeypatch.setattr("fablized_sol.eval.day0_ab.run_out_of_band_grader", _pass_grader)
    output_dir = tmp_path / "out"

    result = RUNNER.invoke(
        app,
        [
            "--tasks",
            str(example_manifest(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--run-id",
            "live-offline",
            "--verification-image",
            _IMAGE,
            "--grader-image",
            _GRADER_IMAGE,
            "--confirm-billable",
        ],
    )

    assert result.exit_code == 0
    assert [model for model, _workspace in observed] == ["gpt-5.6-terra", "gpt-5.6-sol"]
    assert observed[0][1] != observed[1][1]
    rows = read_jsonl(output_dir / "live-offline" / "events.jsonl")
    finished = [row for row in rows if row["event"] == "run_finished"]
    assert [row["status"] for row in finished] == ["completed", "completed"]
    assert [row["input_tokens"] for row in finished] == [11, 11]
    assert [row["output_tokens"] for row in finished] == [7, 7]
    assert [row["grader_passed"] for row in finished] == [True, True]
    for row in finished:
        ledger = output_dir / "live-offline" / "ledgers" / f"{row['session_id']}.jsonl"
        assert [event["event"] for event in read_jsonl(ledger)].count("classify") == 1


def test_live_run_checks_both_images_before_first_model_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "fablized_sol.eval.day0_ab.preflight_local_images",
        _images_missing,
    )
    model_called = False

    async def execute(
        self: SdkAttemptExecutor,
        request: AttemptRequest,
    ) -> AttemptCompleted:
        del self, request
        nonlocal model_called
        model_called = True
        return AttemptCompleted(output="must not run")

    monkeypatch.setattr(SdkAttemptExecutor, "execute", execute)
    output_dir = tmp_path / "out"

    result = _invoke_live(tmp_path, output_dir, "missing-local-image")

    assert result.exit_code != 0
    assert model_called is False
    rows = read_jsonl(output_dir / "missing-local-image" / "events.jsonl")
    finished = [row for row in rows if row["event"] == "run_finished"]
    assert all(row["error_type"] == "ImagePreflightError" for row in finished)
    assert not (output_dir / "missing-local-image" / "workspaces").exists()


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
    monkeypatch.setattr("fablized_sol.eval.day0_ab.run_out_of_band_grader", _pass_grader)
    output_dir = tmp_path / "out"
    result = _invoke_live(tmp_path, output_dir, "error-pair")

    assert result.exit_code != 0
    finished = [
        row
        for row in read_jsonl(output_dir / "error-pair" / "events.jsonl")
        if row["event"] == "run_finished"
    ]
    assert [row["status"] for row in finished] == ["completed", "error"]
    assert finished[1]["error_type"] == "RuntimeError"


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
    monkeypatch.setattr("fablized_sol.eval.day0_ab.run_out_of_band_grader", _pass_grader)
    output_dir = tmp_path / "out"
    result = _invoke_live(tmp_path, output_dir, "exhausted-pair")

    assert result.exit_code != 0
    finished = [
        row
        for row in read_jsonl(output_dir / "exhausted-pair" / "events.jsonl")
        if row["event"] == "run_finished"
    ]
    assert [row["status"] for row in finished] == ["exhausted", "exhausted"]


def _invoke_live(tmp_path: Path, output_dir: Path, run_id: str) -> Result:
    return RUNNER.invoke(
        app,
        [
            "--tasks",
            str(example_manifest(tmp_path)),
            "--output-dir",
            str(output_dir),
            "--run-id",
            run_id,
            "--verification-image",
            _IMAGE,
            "--grader-image",
            _GRADER_IMAGE,
            "--confirm-billable",
        ],
    )
