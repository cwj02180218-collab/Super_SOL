"""Append-only event persistence and chronological state aggregation."""

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Final, assert_never, final, override

from pydantic import JsonValue, TypeAdapter, ValidationError

from fablized_sol.engine.events import (
    ClassifyEvent,
    EvidenceRejectedEvent,
    GateFireEvent,
    LedgerEvent,
    MutationToolEvent,
    ReadToolEvent,
    VerificationToolEvent,
)
from fablized_sol.engine.models import ChangeKind, TaskMode

_EVENT_ADAPTER: Final = TypeAdapter[LedgerEvent](LedgerEvent)
_JSON_ADAPTER: Final = TypeAdapter[JsonValue](JsonValue)


@dataclass(frozen=True, slots=True)
class LedgerParseError(Exception):
    """A ledger line that is not a valid event."""

    path: Path
    line_number: int
    detail: str

    @override
    def __str__(self) -> str:
        """Render the failing path, line, and validation detail."""
        return f"{self.path}: line {self.line_number}: {self.detail}"


@dataclass(frozen=True, slots=True)
class LedgerStateError(Exception):
    """A ledger whose events cannot form one session state."""

    path: Path
    classification_count: int

    @override
    def __str__(self) -> str:
        """Render the invalid classification count."""
        return (
            f"{self.path}: expected exactly one classification, found {self.classification_count}"
        )


@dataclass(frozen=True, slots=True)
class SessionState:
    """Evidence-relevant state aggregated in ledger order."""

    task_mode: TaskMode
    changed_files_seen: bool
    change_kinds: frozenset[ChangeKind]
    latest_mutation_index: int | None
    latest_successful_verification_index: int | None
    stop_blocks: int

    @property
    def has_fresh_verification(self) -> bool:
        """Whether successful verification follows the latest mutation."""
        if self.latest_mutation_index is None:
            return False
        if self.latest_successful_verification_index is None:
            return False
        return self.latest_successful_verification_index > self.latest_mutation_index


@final
class Ledger:  # noqa: MUTABLE_OK
    """Mutable file owner that serializes appends with a process-local lock."""

    __slots__ = ("_lock", "_path")

    def __init__(self, path: Path) -> None:
        """Bind the ledger to a JSONL path and process-local lock."""
        self._path = path
        self._lock = Lock()

    def append(self, event: LedgerEvent) -> None:
        """Append one event as one UTF-8 JSON line."""
        line = event.model_dump_json()
        with self._lock, self._path.open("a", encoding="utf-8") as stream:
            _ = stream.write(f"{line}\n")

    def read(self) -> tuple[LedgerEvent, ...]:
        """Parse all ledger events in file order."""
        with self._lock:
            if not self._path.exists():
                return ()
            with self._path.open(encoding="utf-8") as stream:
                lines = tuple(stream)
            for line_number, line in enumerate(lines, start=1):
                self._ensure_json(line=line, line_number=line_number)
            return tuple(
                self._parse_event(line=line, line_number=line_number)
                for line_number, line in enumerate(lines, start=1)
            )

    def state(self) -> SessionState:
        """Aggregate the ledger into evidence-relevant session state."""
        task_modes: list[TaskMode] = []
        change_kinds: set[ChangeKind] = set()
        latest_mutation_index: int | None = None
        latest_verification_index: int | None = None
        stop_blocks = 0

        for index, event in enumerate(self.read()):
            match event:
                case ClassifyEvent(mode=mode):
                    task_modes.append(mode)
                case MutationToolEvent(change_kind=change_kind):
                    change_kinds.add(change_kind)
                    latest_mutation_index = index
                case VerificationToolEvent(success=success):
                    if success:
                        latest_verification_index = index
                case GateFireEvent():
                    stop_blocks += 1
                case ReadToolEvent() | EvidenceRejectedEvent():
                    pass
                case _:
                    assert_never(event)

        if len(task_modes) != 1:
            raise LedgerStateError(
                path=self._path,
                classification_count=len(task_modes),
            )
        return SessionState(
            task_mode=task_modes[0],
            changed_files_seen=latest_mutation_index is not None,
            change_kinds=frozenset(change_kinds),
            latest_mutation_index=latest_mutation_index,
            latest_successful_verification_index=latest_verification_index,
            stop_blocks=stop_blocks,
        )

    def _ensure_json(self, *, line: str, line_number: int) -> None:
        try:
            _ = _JSON_ADAPTER.validate_json(line)
        except (json.JSONDecodeError, ValidationError) as error:
            raise LedgerParseError(
                path=self._path,
                line_number=line_number,
                detail=str(error),
            ) from error

    def _parse_event(self, *, line: str, line_number: int) -> LedgerEvent:
        try:
            return _EVENT_ADAPTER.validate_json(line)
        except ValidationError as error:
            raise LedgerParseError(
                path=self._path,
                line_number=line_number,
                detail=str(error),
            ) from error
