import json

import pytest

from fablized_sol.eval.codex_telemetry import (
    CodexCompleted,
    CodexInfrastructureFailure,
    InfrastructureKind,
    parse_codex_capture,
)


def _completed_event(input_tokens: int = 1) -> str:
    return json.dumps(
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": input_tokens,
                "cached_input_tokens": 0,
                "output_tokens": 1,
                "reasoning_output_tokens": 0,
            },
        }
    )


def test_completed_turn_extracts_provider_usage() -> None:
    started = json.dumps({"type": "turn.started"})
    completed = json.dumps(
        {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 176161,
                "cached_input_tokens": 150656,
                "output_tokens": 2314,
                "reasoning_output_tokens": 544,
            },
        }
    )
    stdout = f"{started}\n{completed}"

    result = parse_codex_capture(stdout=stdout, stderr="", returncode=0)

    assert isinstance(result, CodexCompleted)
    assert result.usage.total_tokens == 178475
    assert result.usage.cached_input_tokens == 150656
    assert result.usage.reasoning_output_tokens == 544


@pytest.mark.parametrize(
    ("stdout", "stderr", "returncode", "kind"),
    [
        ("", "429 session limit", 1, InfrastructureKind.RATE_LIMIT),
        ('{"type":"turn.started"}', "", 0, InfrastructureKind.MISSING_TERMINAL_EVENT),
        ("not-json", "", 0, InfrastructureKind.INVALID_JSONL),
        (
            f"{_completed_event()}\n{_completed_event()}",
            "",
            0,
            InfrastructureKind.DUPLICATE_TERMINAL_EVENT,
        ),
        (
            _completed_event(input_tokens=-1),
            "",
            0,
            InfrastructureKind.INVALID_USAGE,
        ),
        (
            '{"type":"turn.failed","error":{"message":"provider unavailable"}}',
            "",
            0,
            InfrastructureKind.PROVIDER_ERROR,
        ),
    ],
)
def test_invalid_or_provider_outcomes_are_infrastructure_missing(
    stdout: str,
    stderr: str,
    returncode: int,
    kind: InfrastructureKind,
) -> None:
    result = parse_codex_capture(stdout=stdout, stderr=stderr, returncode=returncode)

    assert result == CodexInfrastructureFailure(kind=kind)


@pytest.mark.parametrize("phrase", ["rate limit", "too many requests", "quota", "session limit"])
def test_rate_limit_phrases_win_over_generic_nonzero_exit(phrase: str) -> None:
    result = parse_codex_capture(stdout="", stderr=phrase, returncode=1)

    assert result == CodexInfrastructureFailure(kind=InfrastructureKind.RATE_LIMIT)


def test_non_object_event_and_nonzero_exit_are_missing() -> None:
    non_object = parse_codex_capture(stdout="[]", stderr="", returncode=0)
    nonzero = parse_codex_capture(stdout="", stderr="unexpected failure", returncode=7)

    assert non_object == CodexInfrastructureFailure(kind=InfrastructureKind.INVALID_EVENT)
    assert nonzero == CodexInfrastructureFailure(kind=InfrastructureKind.NONZERO_EXIT)
