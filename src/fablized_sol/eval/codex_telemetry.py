"""Strict, diagnostic-free parsing of stock Codex JSONL telemetry."""

from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError

_OBJECT_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])
_JSON_ADAPTER = TypeAdapter[JsonValue](JsonValue)
_RATE_LIMIT_PHRASES: Final = (
    "429",
    "quota",
    "rate limit",
    "session limit",
    "too many requests",
)
_PROVIDER_ERROR_EVENTS: Final = {"error", "turn.failed"}


class InfrastructureKind(StrEnum):
    """Why one Codex process cannot produce a benchmark sample."""

    RATE_LIMIT = "rate_limit"
    NONZERO_EXIT = "nonzero_exit"
    INVALID_JSONL = "invalid_jsonl"
    INVALID_EVENT = "invalid_event"
    MISSING_TERMINAL_EVENT = "missing_terminal_event"
    DUPLICATE_TERMINAL_EVENT = "duplicate_terminal_event"
    INVALID_USAGE = "invalid_usage"
    PROVIDER_ERROR = "provider_error"


class _UsageModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    reasoning_output_tokens: int = Field(ge=0)


@dataclass(frozen=True, slots=True)
class CodexUsage:
    """Provider-reported usage for exactly one completed Codex turn."""

    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int

    @property
    def total_tokens(self) -> int:
        """Return input plus output tokens without double-counting cached input."""
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class CodexCompleted:
    """One valid terminal event and its strict usage record."""

    usage: CodexUsage


@dataclass(frozen=True, slots=True)
class CodexInfrastructureFailure:
    """A missing benchmark outcome that must never become a zero score."""

    kind: InfrastructureKind


type CodexTelemetryResult = CodexCompleted | CodexInfrastructureFailure


def _failure(kind: InfrastructureKind) -> CodexInfrastructureFailure:
    return CodexInfrastructureFailure(kind=kind)


def parse_codex_capture(  # noqa: C901, PLR0911 - explicit fail-closed state machine
    stdout: str, stderr: str, returncode: int
) -> CodexTelemetryResult:
    """Parse exactly one terminal turn or return a typed infrastructure-missing result."""
    diagnostics = f"{stdout}\n{stderr}".casefold()
    if returncode != 0:
        if any(phrase in diagnostics for phrase in _RATE_LIMIT_PHRASES):
            return _failure(InfrastructureKind.RATE_LIMIT)
        return _failure(InfrastructureKind.NONZERO_EXIT)

    completed: list[dict[str, JsonValue]] = []
    for line in (candidate for candidate in stdout.splitlines() if candidate.strip()):
        try:
            raw = _JSON_ADAPTER.validate_json(line)
        except ValidationError:
            return _failure(InfrastructureKind.INVALID_JSONL)
        if not isinstance(raw, dict):
            return _failure(InfrastructureKind.INVALID_EVENT)
        try:
            event = _OBJECT_ADAPTER.validate_python(raw)
        except ValidationError:
            return _failure(InfrastructureKind.INVALID_EVENT)
        event_type = event.get("type")
        if not isinstance(event_type, str):
            return _failure(InfrastructureKind.INVALID_EVENT)
        if event_type in _PROVIDER_ERROR_EVENTS:
            return _failure(InfrastructureKind.PROVIDER_ERROR)
        if event_type == "turn.completed":
            completed.append(event)
    if not completed:
        return _failure(InfrastructureKind.MISSING_TERMINAL_EVENT)
    if len(completed) != 1:
        return _failure(InfrastructureKind.DUPLICATE_TERMINAL_EVENT)
    try:
        usage = _UsageModel.model_validate(completed[0].get("usage"))
    except ValidationError:
        return _failure(InfrastructureKind.INVALID_USAGE)
    return CodexCompleted(
        usage=CodexUsage(
            input_tokens=usage.input_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            output_tokens=usage.output_tokens,
            reasoning_output_tokens=usage.reasoning_output_tokens,
        )
    )
