"""Bounded parsing for append-only benchmark lifecycle events."""

from pathlib import Path
from typing import Final, final

from pydantic import TypeAdapter, ValidationError

from fablized_sol.engine.models import SessionId
from fablized_sol.measure.report_models import ReportInputError, ReportIssue
from fablized_sol.measure.shadow import RunFinished, RunPlanned, RunStarted, ShadowEvent

_EVENT_ADAPTER = TypeAdapter[ShadowEvent](ShadowEvent)
_MAX_EVIDENCE_BYTES: Final = 16 * 1024 * 1024
_MAX_EVENT_LINE_BYTES: Final = 64 * 1024


@final
class EventIndex:
    """Mutable lifecycle accumulator used only while parsing one event stream."""

    __slots__ = ("finishes", "plans", "starts")

    plans: dict[SessionId, RunPlanned]
    starts: dict[SessionId, RunStarted]
    finishes: dict[SessionId, RunFinished]

    def __init__(self) -> None:
        """Start with no observed lifecycle events."""
        self.plans = {}
        self.starts = {}
        self.finishes = {}

    def add_plan(self, event: RunPlanned) -> None:
        """Add a plan only before any later event for that session."""
        if event.session_id in self.starts or event.session_id in self.finishes:
            raise ReportInputError(ReportIssue.INVALID_LIFECYCLE_ORDER, event.session_id)
        if event.session_id in self.plans:
            raise ReportInputError(ReportIssue.DUPLICATE_PLAN, event.session_id)
        self.plans[event.session_id] = event

    def add_start(self, event: RunStarted) -> None:
        """Add a start only after its plan and before its finish."""
        if event.session_id not in self.plans or event.session_id in self.finishes:
            raise ReportInputError(ReportIssue.INVALID_LIFECYCLE_ORDER, event.session_id)
        if event.session_id in self.starts:
            raise ReportInputError(ReportIssue.DUPLICATE_START, event.session_id)
        self.starts[event.session_id] = event

    def add_finish(self, event: RunFinished) -> None:
        """Add a finish only after its start."""
        if event.session_id not in self.starts:
            raise ReportInputError(ReportIssue.INVALID_LIFECYCLE_ORDER, event.session_id)
        if event.session_id in self.finishes:
            raise ReportInputError(ReportIssue.DUPLICATE_FINISH, event.session_id)
        self.finishes[event.session_id] = event


def _read_lines(path: Path) -> tuple[str, ...]:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise ReportInputError(ReportIssue.INVALID_EVENTS, str(error)) from error
    if size > _MAX_EVIDENCE_BYTES:
        raise ReportInputError(ReportIssue.EVIDENCE_TOO_LARGE, str(path))
    try:
        lines = tuple(path.read_text(encoding="utf-8").splitlines())
    except OSError as error:
        raise ReportInputError(ReportIssue.INVALID_EVENTS, str(error)) from error
    if any(len(line.encode()) > _MAX_EVENT_LINE_BYTES for line in lines):
        raise ReportInputError(ReportIssue.EVIDENCE_TOO_LARGE, str(path))
    return lines


def load_events(path: Path) -> EventIndex:
    """Parse a bounded stream while enforcing plan, start, finish order."""
    index = EventIndex()
    for line in _read_lines(path):
        try:
            event = _EVENT_ADAPTER.validate_json(line)
        except ValidationError as error:
            raise ReportInputError(ReportIssue.INVALID_EVENTS, str(error)) from error
        match event:
            case RunPlanned():
                index.add_plan(event)
            case RunStarted():
                index.add_start(event)
            case RunFinished():
                index.add_finish(event)
    return index
