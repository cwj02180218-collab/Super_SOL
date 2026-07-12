"""Deterministic task routing and frozen Super SOL procedure packs."""

# This hook is parsed by macOS /usr/bin/python3 (3.9), so modernized annotation and StrEnum
# suggestions are deliberately disabled here.
# ruff: noqa: UP042, UP045
# pyright: reportDeprecated=false

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Route(str, Enum):
    """One public v0.5 routing outcome."""

    PASS_THROUGH = "pass_through"  # noqa: S105 - routing label, not a credential
    CONCURRENCY_STATE = "concurrency_state"
    SECURITY_BOUNDARY = "security_boundary"
    MIGRATION_COMPATIBILITY = "migration_compatibility"
    FAILURE_ATOMICITY = "failure_atomicity"


@dataclass(frozen=True)
class RouteDecision:
    """Privacy-safe route metadata for one prompt."""

    route: Route
    score: int
    signal_ids: tuple[str, ...]
    forced: bool = False
    warning: Optional[str] = None


@dataclass(frozen=True)
class _Signal:
    identifier: str
    weight: int
    phrases: tuple[str, ...]


_ACTION_PHRASES = (
    "add",
    "change",
    "fix",
    "implement",
    "migrate",
    "must",
    "reject",
    "repair",
    "update",
    "validate",
    "고쳐",
    "구현",
    "막아",
    "마이그레이션",
    "수정",
    "차단",
    "추가",
)
_EXPLANATION_PHRASES = (
    "explain",
    "what is",
    "what are",
    "설명만",
    "무엇인지",
    "뭐야",
)
_ACTIVATION_SCORE = 2

_SIGNALS: dict[Route, tuple[_Signal, ...]] = {
    Route.CONCURRENCY_STATE: (
        _Signal(
            "concurrency.race",
            2,
            ("race condition", "race conditions", "data race", "경쟁 상태"),
        ),
        _Signal(
            "concurrency.concurrent",
            2,
            ("concurrent", "concurrently", "동시 요청", "동시 호출"),
        ),
        _Signal(
            "concurrency.coalescing",
            1,
            ("share one", "single flight", "coalesc", "하나의 작업", "공유 작업"),
        ),
        _Signal(
            "concurrency.cancellation",
            1,
            ("cancellation", "cancelled", "canceled", "취소 전파", "취소"),
        ),
        _Signal(
            "concurrency.lock",
            1,
            ("lock ordering", "per-key lock", "mutex", "잠금 순서", "키별 잠금"),
        ),
    ),
    Route.SECURITY_BOUNDARY: (
        _Signal(
            "security.traversal",
            2,
            ("path traversal", "directory traversal", "경로 순회", "경로 탈출"),
        ),
        _Signal(
            "security.extraction",
            2,
            ("safe extraction", "archive extraction", "secure upload", "upload boundary"),
        ),
        _Signal(
            "security.symlink",
            1,
            ("symlink", "symbolic link", "hardlink", "심볼릭 링크", "하드 링크"),
        ),
        _Signal(
            "security.authorization",
            1,
            ("authorization", "permission boundary", "권한 경계", "인가"),
        ),
        _Signal(
            "security.untrusted",
            1,
            ("untrusted input", "secret exposure", "secret filename", "신뢰 경계"),
        ),
    ),
    Route.MIGRATION_COMPATIBILITY: (
        _Signal(
            "migration.schema",
            2,
            ("schema migration", "backward-compatible", "backward compatible", "스키마 이전"),
        ),
        _Signal(
            "migration.migrate",
            1,
            ("migrate", "migration", "마이그레이션", "이전해"),
        ),
        _Signal(
            "migration.versions",
            1,
            ("schema v", "v1 and v2", "future version", "지원 버전", "향후 버전"),
        ),
        _Signal(
            "migration.idempotence",
            1,
            ("idempotent", "idempotently", "repeated migration", "멱등"),
        ),
        _Signal(
            "migration.unknown_fields",
            1,
            ("unknown fields", "unknown field", "알 수 없는 필드", "미지 필드"),
        ),
    ),
    Route.FAILURE_ATOMICITY: (
        _Signal(
            "failure.atomic",
            2,
            ("atomic batch", "atomically", "transactional", "원자적", "트랜잭션"),
        ),
        _Signal(
            "failure.rollback",
            2,
            ("roll back", "rollback", "롤백", "되돌려"),
        ),
        _Signal(
            "failure.partial",
            2,
            ("partial failure", "partial-failure", "부분 실패"),
        ),
        _Signal(
            "failure.validation",
            1,
            ("validate before mutation", "validation before mutation", "변경 전 검증"),
        ),
        _Signal(
            "failure.checkpoint",
            1,
            ("checkpoint", "after success", "성공 후 기록", "체크포인트"),
        ),
        _Signal(
            "failure.retry",
            1,
            ("retry transient", "permanent error", "재시도", "영구 오류"),
        ),
    ),
}

_PACKS = {
    Route.CONCURRENCY_STATE: (
        "Before editing, list the shared state, owner, and per-key synchronization "
        "invariant. Check same-key coalescing, different-key independence, cancellation, "
        "failure cleanup, and retry after failure. Preserve the public API. Add or run a "
        "deterministic concurrency test. "
        "Repair only an observed failure; avoid unrelated refactoring."
    ),
    Route.SECURITY_BOUNDARY: (
        "Before editing, identify the trust boundary and each input or path normalization step. "
        "Validate before mutation; reject traversal, aliases, symlinks, partial writes, and secret "
        "exposure when applicable. Preserve the public API. Run focused boundary tests. "
        "Repair only "
        "an observed failure; avoid unrelated refactoring."
    ),
    Route.MIGRATION_COMPATIBILITY: (
        "Before editing, write source and target invariants for every supported version. Preserve "
        "unknown and nested fields, input immutability, idempotence, normalization order, and "
        "future-version rejection. Preserve the public API. Run a focused version matrix. Repair "
        "only an observed failure; avoid unrelated refactoring."
    ),
    Route.FAILURE_ATOMICITY: (
        "Before editing, state atomicity, ordering, and idempotency invariants. Separate "
        "validation, mutation, and commit; distinguish transient, permanent, and cancellation "
        "failures; and "
        "checkpoint only after success. Preserve the public API. Run focused failure-injection "
        "tests. Repair only an observed failure; avoid unrelated refactoring."
    ),
}

REPAIR_CONTEXT = (
    "Verification failed. Use only the observed failure to revisit the active route invariants, "
    "make the smallest correction, and rerun the same focused verification once."
)

_ROUTE_CONTROL = re.compile(r"^SUPER SOL ROUTE ([a-z_]+)$", re.ASCII)


def _normalized(prompt: str) -> str:
    return unicodedata.normalize("NFKC", prompt).casefold()


def _control(prompt: str) -> tuple[Optional[RouteDecision], str]:
    lines = prompt.splitlines()
    first_index = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first_index is None:
        return None, ""
    control = unicodedata.normalize("NFKC", lines[first_index]).strip()
    remainder = "\n".join(lines[:first_index] + lines[first_index + 1 :]).strip()
    if control == "SUPER SOL OFF":
        return RouteDecision(Route.PASS_THROUGH, 0, (), forced=True), remainder
    matched = _ROUTE_CONTROL.fullmatch(control)
    if matched is None:
        return None, prompt
    try:
        route = Route(matched.group(1))
    except ValueError:
        return (
            RouteDecision(
                Route.PASS_THROUGH,
                0,
                (),
                forced=True,
                warning="알 수 없는 route라 pass-through로 계속합니다.",
            ),
            remainder,
        )
    if route is Route.PASS_THROUGH:
        return RouteDecision(route, 0, (), forced=True), remainder
    return RouteDecision(route, _ACTIVATION_SCORE, ("control.explicit",), forced=True), remainder


def route_prompt(prompt: str) -> RouteDecision:
    """Classify one prompt without retaining or returning its content."""
    controlled, remainder = _control(prompt)
    if controlled is not None:
        return controlled
    lowered = _normalized(remainder)
    if any(phrase in lowered for phrase in _EXPLANATION_PHRASES):
        return RouteDecision(Route.PASS_THROUGH, 0, ())
    if not any(phrase in lowered for phrase in _ACTION_PHRASES):
        return RouteDecision(Route.PASS_THROUGH, 0, ())

    scored: dict[Route, tuple[int, tuple[str, ...]]] = {}
    for route, signals in _SIGNALS.items():
        matched = tuple(
            signal
            for signal in signals
            if any(phrase in lowered for phrase in signal.phrases)
        )
        scored[route] = (
            sum(signal.weight for signal in matched),
            tuple(signal.identifier for signal in matched),
        )
    active = tuple(
        route for route, (score, _) in scored.items() if score >= _ACTIVATION_SCORE
    )
    if len(active) != 1:
        return RouteDecision(Route.PASS_THROUGH, 0, ())
    route = active[0]
    score, identifiers = scored[route]
    return RouteDecision(route, score, identifiers)


def context_for(route: Route) -> Optional[str]:
    """Return the frozen model context for one specialist route."""
    return _PACKS.get(route)
