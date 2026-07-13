"""Low-startup dispatcher for clearly generic prompt hook events."""

from __future__ import annotations

import json
import os
import sys
import unicodedata
from typing import Protocol, cast

_MAX_INPUT_BYTES = 1_048_576
_SECRET_MATCH_LENGTH = 23
_DIAGNOSTIC_KEYS = ("SUPER_SOL_DIAGNOSTIC_MODE", "SUPER_SOL_FORCED_ROUTE")
_BILLING_AND_CONTROL_PHRASES = (
    "super sol",
    "과금 없이",
    "과금하지",
    "api 호출하지",
    "api를 호출하지",
    "no api call",
    "no billing",
    "don't call api",
    "do not call api",
)
_SIGNAL_PHRASES = (
    "copy",
    "복사",
    "alias",
    "sharing nested",
    "별칭",
    "mutat",
    "불변",
    "unknown",
    "알 수 없는",
    "arity",
    "인자 수",
    "usage",
    "사용법",
    "return code",
    "exit code",
    "코드",
    "input",
    "입력",
    "retry",
    "재시도",
    "same id",
    "same identifier",
    "동일 id",
    "같은 id",
    "duplicate",
    "중복",
    "idempot",
    "멱등",
    "race",
    "경쟁",
    "concurrent",
    "동시",
    "cancel",
    "취소",
    "share one",
    "single flight",
    "coalesc",
    "공유",
    "atomic",
    "transaction",
    "원자",
    "all or nothing",
    "all-or-nothing",
    "persist",
    "every write succeeds or none",
    "성공",
    "저장하지",
    "staged",
    "commit only after",
    "validation",
    "검증",
    "temporary",
    "임시",
    "replace",
    "swap",
    "교체",
    "previously written",
    "앞서 저장한",
    "이미 쓴",
    "side effect",
    "부작용",
    "roll",
    "rollback",
    "롤백",
    "되돌",
    "partial",
    "부분 실패",
    "migrate",
    "migration",
    "마이그레이션",
    "이전",
    "compatible",
    "호환",
    "version",
    "v1 and v2",
    "버전",
    "path",
    "traversal",
    "경로",
    "symlink",
    "link",
    "링크",
    "upload",
    "boundary",
    "경계",
    "secret",
    "비밀",
    "작업",
    "lock",
    "mutex",
    "잠금",
    "extraction",
    "authorization",
    "permission",
    "권한",
    "인가",
    "untrusted",
    "schema",
    "스키마",
    "field",
    "필드",
    "destination",
    "cleanup",
    "clean up",
    "remove",
    "실패",
    "정리",
    "트랜잭션",
    "checkpoint",
    "after success",
    "체크포인트",
    "기록",
    "permanent error",
    "영구 오류",
)


class _FullProcessor(Protocol):
    def __call__(self, raw: bytes) -> dict[str, object] | None: ...


class _Environment(Protocol):
    def __contains__(self, key: object, /) -> bool: ...


class _FullHookModule(Protocol):
    def process_raw(self, raw: bytes) -> dict[str, object] | None: ...


def _secret_shaped(prompt: str) -> bool:
    allowed = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    start = 0
    while True:
        start = prompt.find("sk-", start)
        if start < 0:
            return False
        end = start + 3
        while end < len(prompt) and prompt[end] in allowed:
            end += 1
        if end - start >= _SECRET_MATCH_LENGTH:
            return True
        start += 3


def _clearly_generic(payload: object, environment: _Environment) -> bool:
    if not isinstance(payload, dict):
        return False
    payload = cast("dict[object, object]", payload)
    if payload.get("hook_event_name") != "UserPromptSubmit":
        return False
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or any(key in environment for key in _DIAGNOSTIC_KEYS):
        return False
    if _secret_shaped(prompt):
        return False
    normalized = unicodedata.normalize("NFKC", prompt).casefold()
    guarded = _BILLING_AND_CONTROL_PHRASES + _SIGNAL_PHRASES
    return not any(phrase in normalized for phrase in guarded)


def _full_process(raw: bytes) -> dict[str, object] | None:
    module = cast("_FullHookModule", __import__("super_sol_hook"))
    return module.process_raw(raw)


def dispatch(
    raw: bytes,
    environment: _Environment,
    full_processor: _FullProcessor = _full_process,
) -> dict[str, object] | None:
    """Return early only for bounded, valid, clearly generic prompt input."""
    if len(raw) <= _MAX_INPUT_BYTES:
        try:
            payload = cast("object", json.loads(raw.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        else:
            if _clearly_generic(payload, environment):
                return None
    return full_processor(raw)


def main() -> int:
    """Read one prompt hook event and emit the full hook response when needed."""
    raw = sys.stdin.buffer.read(_MAX_INPUT_BYTES + 1)
    output = dispatch(raw, os.environ)
    if output is not None:
        json.dump(output, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
