"""Opt-in test-mutation guard for controlled benchmark runs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import cast

_ENABLED = "SUPER_SOL_BENCHMARK_GUARD"
_ROOTS = "SUPER_SOL_TEST_ROOTS"
_EDIT_TOOLS = frozenset({"apply_patch", "edit", "write"})
_PATCH_MARKERS = ("*** Add File:", "*** Delete File:", "*** Update File:")
_INVALID_REASON = "benchmark_guard_invalid_target"
_TEST_REASON = "benchmark_guard_test_mutation"


@dataclass(frozen=True)
class GuardDecision:
    """A content-free benchmark edit decision."""

    deny: bool
    reason: str | None = None


def _normalized_path(value: str) -> tuple[str, ...] | None:
    candidate = value.strip().replace("\\", "/")
    if not candidate or candidate.startswith("/"):
        return None
    parts = PurePosixPath(candidate).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    return parts


def _test_roots() -> tuple[tuple[str, ...], ...] | None:
    raw = os.environ.get(_ROOTS)
    if raw is None:
        return None
    values = tuple(_normalized_path(value) for value in raw.split(","))
    if not values or any(value is None for value in values):
        return None
    return cast("tuple[tuple[str, ...], ...]", values)


def _input(payload: dict[str, object]) -> dict[str, object] | None:
    value = payload.get("tool_input")
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def _edited_paths(payload: dict[str, object]) -> tuple[str, ...]:
    tool_input = _input(payload)
    if tool_input is None:
        return ()
    paths = [
        value for key in ("file_path", "path") if isinstance(value := tool_input.get(key), str)
    ]
    patch = tool_input.get("patch")
    if isinstance(patch, str):
        for line in patch.splitlines():
            stripped = line.strip()
            for marker in _PATCH_MARKERS:
                if stripped.startswith(marker):
                    paths.append(stripped.removeprefix(marker).strip())
                    break
    return tuple(dict.fromkeys(paths))


def benchmark_guard_decision(payload: dict[str, object]) -> GuardDecision:
    """Deny only edit-like benchmark requests that are unsafe or target tests."""
    if os.environ.get(_ENABLED, "").strip() != "1":
        return GuardDecision(deny=False)
    tool_name = payload.get("tool_name")
    normalized_tool = tool_name.casefold() if isinstance(tool_name, str) else ""
    if normalized_tool not in _EDIT_TOOLS:
        return GuardDecision(deny=False)
    roots = _test_roots()
    raw_paths = _edited_paths(payload)
    if roots is None or not raw_paths:
        return GuardDecision(deny=True, reason=_INVALID_REASON)
    paths = tuple(_normalized_path(path) for path in raw_paths)
    if any(path is None for path in paths):
        return GuardDecision(deny=True, reason=_INVALID_REASON)
    normalized_paths = cast("tuple[tuple[str, ...], ...]", paths)
    targets_test = any(path[: len(root)] == root for path in normalized_paths for root in roots)
    return (
        GuardDecision(deny=True, reason=_TEST_REASON) if targets_test else GuardDecision(deny=False)
    )
