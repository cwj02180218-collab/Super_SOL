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


class Contract(str, Enum):
    """One bounded semantic obligation detected in a request."""

    OWNERSHIP_ALIASING = "ownership_aliasing"
    INPUT_ERROR_SEMANTICS = "input_error_semantics"
    RETRY_STATE = "retry_state"
    CONCURRENCY_CANCELLATION = "concurrency_cancellation"
    FAILURE_ATOMICITY = "failure_atomicity"
    MIGRATION_COMPATIBILITY = "migration_compatibility"
    SECURITY_PATH_BOUNDARY = "security_path_boundary"


@dataclass(frozen=True)
class RouteDecision:
    """Privacy-safe route metadata for one prompt."""

    route: Route
    score: int
    signal_ids: tuple[str, ...]
    forced: bool = False
    warning: Optional[str] = None
    contract: Optional[Contract] = None
    confidence: int = 0


@dataclass(frozen=True)
class _Signal:
    identifier: str
    weight: int
    phrases: tuple[str, ...]


_ACTION_PHRASES = (
    "add",
    "allow",
    "change",
    "fix",
    "implement",
    "make",
    "migrate",
    "must",
    "reject",
    "repair",
    "return",
    "update",
    "clean up",
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
_CONFIDENCE_MARGIN = 1

_CONTRACT_SIGNALS: dict[Contract, tuple[_Signal, ...]] = {
    Contract.OWNERSHIP_ALIASING: (
        _Signal(
            "ownership.copy",
            2,
            ("deep copy", "shallow copy", "copy without sharing", "깊은 복사", "얕은 복사"),
        ),
        _Signal(
            "ownership.alias",
            2,
            ("nested alias", "shared alias", "sharing nested", "aliasing", "별칭 공유"),
        ),
        _Signal(
            "ownership.immutable",
            1,
            ("without mutating", "input immutability", "do not mutate input", "입력 불변"),
        ),
    ),
    Contract.INPUT_ERROR_SEMANTICS: (
        _Signal(
            "input.unknown",
            2,
            ("unknown command", "unknown input", "알 수 없는 명령", "알 수 없는 입력"),
        ),
        _Signal("input.arity", 2, ("wrong arity", "invalid arity", "잘못된 인자 수")),
        _Signal("input.usage", 1, ("usage message", "usage text", "사용법 문구")),
        _Signal("input.return_code", 1, ("return code", "exit code", "반환 코드", "종료 코드")),
        _Signal("input.malformed", 1, ("malformed input", "invalid input", "잘못된 입력")),
    ),
    Contract.RETRY_STATE: (
        _Signal(
            "retry.after_failure",
            2,
            ("retry after failure", "retry after a failure", "실패 후 재시도"),
        ),
        _Signal(
            "retry.identity",
            2,
            ("same id", "same identifier", "동일 id", "같은 id"),
        ),
        _Signal(
            "retry.duplicate",
            2,
            ("duplicate state", "중복 상태"),
        ),
        _Signal("retry.idempotent", 2, ("idempotent retry", "idempotent retries", "멱등 재시도")),
    ),
    Contract.CONCURRENCY_CANCELLATION: (
        _Signal(
            "concurrency.race", 2, ("race condition", "race conditions", "data race", "경쟁 상태")
        ),
        _Signal(
            "concurrency.concurrent", 2, ("concurrent", "concurrently", "동시 요청", "동시 호출")
        ),
        _Signal(
            "concurrency.cancellation",
            1,
            ("cancellation", "cancelled", "canceled", "취소 전파", "취소"),
        ),
        _Signal(
            "concurrency.coalescing", 1, ("share one", "single flight", "coalesc", "공유 작업")
        ),
    ),
    Contract.FAILURE_ATOMICITY: (
        _Signal(
            "failure.atomic",
            2,
            ("atomic commit", "atomic batch", "atomically", "transactional", "원자적"),
        ),
        _Signal(
            "failure.all_or_nothing",
            2,
            (
                "all or nothing",
                "all-or-nothing",
                "none persist",
                "persists nothing unless every",
                "persist nothing unless every",
                "every write succeeds or none",
                "모두 성공",
            ),
        ),
        _Signal(
            "failure.staged_commit",
            2,
            (
                "staged writes",
                "commit only after all validations",
                "all validations succeed",
                "모든 검증이 성공한 뒤에만",
            ),
        ),
        _Signal(
            "failure.replace_after_success",
            2,
            ("temporary file", "replace the destination", "replace destination", "성공 후 교체"),
        ),
        _Signal(
            "failure.cleanup_after_failure",
            2,
            (
                "clean up previously written",
                "remove previously written",
                "앞서 저장한 결과도 정리",
            ),
        ),
        _Signal(
            "failure.duplicate_side_effect",
            2,
            ("duplicate side effects", "duplicate side effect", "중복 부작용"),
        ),
        _Signal("failure.rollback", 2, ("roll back", "rollback", "롤백", "되돌려")),
        _Signal(
            "failure.validation",
            1,
            ("validate before mutation", "before an atomic", "변경 전 검증"),
        ),
        _Signal("failure.partial", 2, ("partial failure", "partial-failure", "부분 실패")),
    ),
    Contract.MIGRATION_COMPATIBILITY: (
        _Signal(
            "migration.core",
            2,
            ("schema migration", "migrate", "migration", "마이그레이션", "이전해"),
        ),
        _Signal(
            "migration.compatibility",
            2,
            ("backward-compatible", "backward compatible", "하위 호환", "이전 버전 호환"),
        ),
        _Signal("migration.future", 1, ("future version", "future versions", "향후 버전")),
        _Signal("migration.idempotent", 1, ("idempotently", "idempotent migration", "멱등 이전")),
    ),
    Contract.SECURITY_PATH_BOUNDARY: (
        _Signal(
            "security.traversal",
            2,
            ("path traversal", "directory traversal", "경로 순회", "경로 탈출"),
        ),
        _Signal("security.symlink", 2, ("symlink", "symbolic link", "심볼릭 링크")),
        _Signal(
            "security.boundary",
            1,
            ("secure upload", "upload boundary", "trust boundary", "신뢰 경계"),
        ),
        _Signal("security.secret", 1, ("secret filename", "secret exposure", "비밀 파일")),
    ),
}

_CONTRACT_ROUTE = {
    Contract.CONCURRENCY_CANCELLATION: Route.CONCURRENCY_STATE,
    Contract.FAILURE_ATOMICITY: Route.FAILURE_ATOMICITY,
    Contract.MIGRATION_COMPATIBILITY: Route.MIGRATION_COMPATIBILITY,
    Contract.SECURITY_PATH_BOUNDARY: Route.SECURITY_BOUNDARY,
}

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
            "failure.all_or_nothing",
            2,
            (
                "persists nothing unless every",
                "persist nothing unless every",
                "all destinations succeed",
                "every write succeeds or none persist",
                "all or nothing",
                "all-or-nothing",
                "모두 성공하지 않으면 저장하지",
                "전부 성공하지 않으면 저장하지",
            ),
        ),
        _Signal(
            "failure.staged_commit",
            2,
            (
                "staged writes",
                "staged update",
                "commit only after",
                "apply only after all validations",
                "all validations succeed",
                "모든 검증이 성공한 뒤에만",
                "검증이 성공한 뒤에만 변경을 반영",
            ),
        ),
        _Signal(
            "failure.temporary_write",
            1,
            ("temporary file", "temporary output", "임시 파일", "임시 결과"),
        ),
        _Signal(
            "failure.replace_after_success",
            1,
            (
                "replace the destination",
                "replace destination",
                "swap after success",
                "성공 후 교체",
                "성공한 뒤 교체",
            ),
        ),
        _Signal(
            "failure.cleanup_after_failure",
            2,
            (
                "clean up previously written",
                "remove previously written",
                "cleanup after failure",
                "clean up after failure",
                "실패하면 앞서 저장한 결과도 정리",
                "실패 시 이미 쓴 결과를 정리",
            ),
        ),
        _Signal(
            "failure.duplicate_side_effect",
            2,
            (
                "duplicate side effects",
                "duplicate side effect",
                "repeated attempts avoid duplicate",
                "중복 부작용",
                "반복 시 중복 실행",
            ),
        ),
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

    scored: list[tuple[int, Contract, tuple[_Signal, ...]]] = []
    for contract, signals in _CONTRACT_SIGNALS.items():
        matched = tuple(
            signal for signal in signals if any(phrase in lowered for phrase in signal.phrases)
        )
        scored.append((sum(signal.weight for signal in matched), contract, matched))
    scored.sort(key=lambda item: (-item[0], item[1].value))
    best_score, contract, matched = scored[0]
    runner_up = scored[1][0]
    if best_score < _ACTIVATION_SCORE or best_score - runner_up < _CONFIDENCE_MARGIN:
        return RouteDecision(Route.PASS_THROUGH, 0, ())
    identifiers = tuple(
        signal.identifier
        for signal in sorted(matched, key=lambda signal: (-signal.weight, signal.identifier))[:2]
    )
    route = _CONTRACT_ROUTE.get(contract, Route.PASS_THROUGH)
    return RouteDecision(
        route,
        best_score,
        identifiers,
        contract=contract,
        confidence=best_score,
    )


def context_for(route: Route) -> Optional[str]:
    """Return the frozen model context for one specialist route."""
    return _PACKS.get(route)


def residual_context(contract: Contract) -> str:
    """Return one bounded post-verification semantic check."""
    label = contract.value.replace("_", " ")
    return (
        f"Final semantic check only: compare the patch once with the requested {label} behavior. "
        "If one explicit edge is missing, make one focused correction; otherwise stop. "
        "Do not rerun passed tests."
    )
