"""Low-startup dispatcher for clearly generic prompt hook events."""

from __future__ import annotations

import json
import os
import sys
import unicodedata
from collections.abc import Callable  # noqa: TC003

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


def _decode_object(raw: bytes) -> dict[str, object] | None:
    """Return only an actual top-level JSON object without typing imports."""
    value = json.loads(raw.decode("utf-8"))  # pyright: ignore[reportAny]
    return value if isinstance(value, dict) else None  # pyright: ignore[reportUnknownVariableType]


def _has_key(environment: object, key: str) -> bool:
    if isinstance(environment, dict):
        return key in environment
    return environment is os.environ and key in os.environ


def _environment_value(environment: object, key: str) -> str | None:
    return os.environ.get(key) if environment is os.environ else None


def _generic_profile(payload: dict[str, object], environment: object) -> str | None:
    if payload.get("hook_event_name") != "UserPromptSubmit":
        return None
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or any(_has_key(environment, key) for key in _DIAGNOSTIC_KEYS):
        return None
    if _secret_shaped(prompt):
        return None
    normalized = unicodedata.normalize("NFKC", prompt).casefold()
    guarded = _BILLING_AND_CONTROL_PHRASES + _SIGNAL_PHRASES
    if any(phrase in normalized for phrase in guarded):
        return None
    model = payload.get("model")
    exact_sol = isinstance(model, str) and model.strip().casefold() == "gpt-5.6-sol"
    return "sol" if exact_sol else "observe"


def _reset_existing_loop(payload: dict[str, object], environment: object) -> None:
    """Reset only a pre-existing canonical Sol ledger without loading prompt routing."""
    plugin_data = _environment_value(environment, "PLUGIN_DATA")
    if not plugin_data:
        return
    state_tree = os.path.join(plugin_data, "super-sol", "v4")  # noqa: PTH118
    if not os.path.isdir(state_tree):  # noqa: PTH112
        return
    import hashlib  # noqa: PLC0415

    def identifier(value: object) -> str:
        text = value if isinstance(value, str) else "missing"
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    root = os.path.join(  # noqa: PTH118
        state_tree,
        identifier(payload.get("session_id")),
        identifier(payload.get("turn_id")),
    )
    if not os.path.isfile(os.path.join(root, "loop.json")):  # noqa: PTH113, PTH118
        return
    from pathlib import Path  # noqa: PLC0415
    from time import time_ns  # noqa: PLC0415

    from super_sol_loop_state import LoopLedger, mutate_loop_ledger  # noqa: PLC0415

    _ = mutate_loop_ledger(Path(root), lambda _state: LoopLedger.fresh(time_ns()))


def _full_process(raw: bytes) -> dict[str, object] | None:
    from super_sol_hook import process_raw  # noqa: PLC0415

    return process_raw(raw)


def dispatch(
    raw: bytes,
    environment: object,
    full_processor: Callable[[bytes], dict[str, object] | None] = _full_process,
) -> dict[str, object] | None:
    """Return early only for bounded, valid, clearly generic prompt input."""
    if len(raw) <= _MAX_INPUT_BYTES:
        try:
            payload = _decode_object(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        else:
            if payload is not None:
                profile = _generic_profile(payload, environment)
                if profile == "observe":
                    return None
                if profile == "sol":
                    try:
                        _reset_existing_loop(payload, environment)
                    except (OSError, TimeoutError, TypeError, ValueError):
                        pass
                    else:
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
