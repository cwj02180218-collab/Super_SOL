import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier, Lock
from typing import cast

import pytest
from super_sol_loop_state import (
    ActionRecord,
    LoopLedger,
    keyed_fingerprint,
    load_loop_ledger,
    mutate_loop_ledger,
)


def test_keyed_fingerprint_is_stable_without_storing_input(tmp_path: Path) -> None:
    root = tmp_path / "super-sol" / "v3" / "session" / "turn"
    raw = "pytest tests/private_case.py -q"
    first = keyed_fingerprint(root, raw)
    second = keyed_fingerprint(root, raw)
    _ = mutate_loop_ledger(
        root,
        lambda state: replace(
            state,
            actions=(ActionRecord(first, "ok", 1, state.edit_epoch),),
        ),
    )

    assert first == second
    assert len(first) == 24
    key_path = root.parents[1] / ".loop-key"
    assert key_path.exists()
    assert key_path.parent == root.parents[1]
    textual = "".join(
        path.read_text(encoding="utf-8")
        for path in key_path.parent.rglob("*")
        if path.is_file() and path != key_path
    )
    assert raw not in textual
    assert all(part not in textual for part in ("pytest", "tests", "private_case.py", "-q"))


def test_ledger_keeps_only_eight_actions(tmp_path: Path) -> None:
    root = tmp_path / "turn"
    for index in range(20):
        fingerprint = keyed_fingerprint(root, f"action-{index}")
        _ = mutate_loop_ledger(
            root,
            lambda state, fingerprint=fingerprint: replace(
                state,
                actions=(*state.actions, ActionRecord(fingerprint, "ok", 1, state.edit_epoch))[-8:],
            ),
        )

    ledger = load_loop_ledger(root)
    assert len(ledger.actions) == 8
    assert tuple(action.fingerprint for action in ledger.actions) == tuple(
        keyed_fingerprint(root, f"action-{value}") for value in range(12, 20)
    )
    assert (root / "loop.json").stat().st_size <= 4096


def test_corrupt_ledger_is_quarantined_and_reset(tmp_path: Path) -> None:
    root = tmp_path / "turn"
    root.mkdir(parents=True)
    _ = (root / "loop.json").write_text("not-json", encoding="utf-8")

    assert load_loop_ledger(root) == LoopLedger.fresh()
    assert list(root.glob("loop.corrupt.*"))


def test_invalid_utf8_ledger_is_quarantined_and_reset(tmp_path: Path) -> None:
    root = tmp_path / "turn"
    root.mkdir(parents=True)
    _ = (root / "loop.json").write_bytes(b"\xff\xfe")

    assert load_loop_ledger(root) == LoopLedger.fresh()
    assert list(root.glob("loop.corrupt.*"))


@pytest.mark.parametrize(
    ("field", "invalid"),
    [("fingerprint", "private_case.py"), ("outcome", "private outcome")],
)
def test_invalid_persisted_action_is_quarantined(tmp_path: Path, field: str, invalid: str) -> None:
    root = tmp_path / "turn"
    fingerprint = keyed_fingerprint(root, "pytest tests/private_case.py -q")
    _ = mutate_loop_ledger(
        root,
        lambda state: replace(
            state,
            actions=(ActionRecord(fingerprint, "pass", 1, state.edit_epoch),),
        ),
    )
    payload = cast(
        "dict[str, object]", json.loads((root / "loop.json").read_text(encoding="utf-8"))
    )
    actions = cast("list[dict[str, object]]", payload["actions"])
    actions[0][field] = invalid
    _ = (root / "loop.json").write_text(json.dumps(payload), encoding="utf-8")

    assert load_loop_ledger(root) == LoopLedger.fresh()
    assert list(root.glob("loop.corrupt.*"))


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("verifier_results", ["private verifier"]),
        ("verifier_results", ["a" * 24] * 9),
        ("active_agents", ["private agent"]),
        ("active_agents", ["a" * 24] * 3),
        ("terminal_reason", "private terminal reason"),
    ],
)
def test_invalid_persisted_ledger_fields_are_quarantined(
    tmp_path: Path, field: str, invalid: object
) -> None:
    root = tmp_path / "turn"
    _ = mutate_loop_ledger(root, lambda state: state)
    payload = cast(
        "dict[str, object]", json.loads((root / "loop.json").read_text(encoding="utf-8"))
    )
    payload[field] = invalid
    _ = (root / "loop.json").write_text(json.dumps(payload), encoding="utf-8")

    assert load_loop_ledger(root) == LoopLedger.fresh()
    assert list(root.glob("loop.corrupt.*"))


def test_invalid_outgoing_action_is_rejected_before_write(tmp_path: Path) -> None:
    root = tmp_path / "turn"
    fingerprint = keyed_fingerprint(root, "pytest tests/private_case.py -q")
    invalid_actions = (
        ActionRecord("private_case.py", "ok", 1, 0),
        ActionRecord(fingerprint, "private outcome", 1, 0),
    )

    for action in invalid_actions:
        with pytest.raises(ValueError, match=r"^$"):
            _ = mutate_loop_ledger(
                root,
                lambda state, action=action: replace(state, actions=(action,)),
            )

    assert not (root / "loop.json").exists()


def test_invalid_outgoing_ledger_fields_are_rejected_before_write(tmp_path: Path) -> None:
    root = tmp_path / "turn"
    invalid = (
        replace(LoopLedger.fresh(), verifier_results=("private verifier",)),
        replace(LoopLedger.fresh(), active_agents=("private agent",)),
        replace(LoopLedger.fresh(), terminal_reason="private terminal reason"),
    )

    for ledger in invalid:
        with pytest.raises(ValueError, match=r"^$"):
            _ = mutate_loop_ledger(root, lambda _state, ledger=ledger: ledger)

    assert not (root / "loop.json").exists()


def test_existing_group_readable_key_is_repaired_to_owner_only(tmp_path: Path) -> None:
    root = tmp_path / "super-sol" / "v3" / "session" / "turn"
    key_path = root.parents[1] / ".loop-key"
    key_path.parent.mkdir(parents=True)
    _ = key_path.write_bytes(b"x" * 32)
    key_path.chmod(0o644)

    _ = keyed_fingerprint(root, "pytest tests/private_case.py -q")

    assert key_path.stat().st_mode & 0o777 == 0o600


def test_simultaneous_first_key_use_waits_for_one_complete_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "super-sol" / "v3" / "session" / "turn"

    def delayed_create(path: Path) -> bytes:
        path.parent.mkdir(parents=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        key = b"x" * 32
        with os.fdopen(descriptor, "wb") as stream:
            _ = stream.write(key[:1])
            stream.flush()
            time.sleep(0.05)
            _ = stream.write(key[1:])
        return key

    monkeypatch.setattr("super_sol_loop_state._create_key", delayed_create)
    barrier = Barrier(16)

    def fingerprint(_index: int) -> str:
        _ = barrier.wait()
        return keyed_fingerprint(root, "pytest tests/private_case.py -q")

    with ThreadPoolExecutor(max_workers=16) as executor:
        fingerprints = list(executor.map(fingerprint, range(16)))

    assert len(set(fingerprints)) == 1
    assert (root.parents[1] / ".loop-key").read_bytes() == b"x" * 32


def test_stale_lock_is_recovered_before_mutation(tmp_path: Path) -> None:
    root = tmp_path / "turn"
    root.mkdir(parents=True)
    lock = root / "loop.lock"
    _ = lock.write_text("", encoding="utf-8")
    stale = time.time() - 6
    _ = lock.touch()
    lock.chmod(0o600)
    os.utime(lock, (stale, stale))

    updated = mutate_loop_ledger(root, lambda state: replace(state, edit_epoch=1))

    assert updated.edit_epoch == 1
    assert not lock.exists()


def test_stale_marker_contenders_keep_one_critical_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "turn"
    root.mkdir(parents=True)
    marker = root / "loop.lock"
    _ = marker.write_text("", encoding="utf-8")
    stale = time.time() - 6
    os.utime(marker, (stale, stale))
    monkeypatch.setattr("super_sol_loop_state.time.time", lambda: stale + 16)
    barrier = Barrier(4)
    counter_lock = Lock()
    active = 0
    maximum = 0

    def increment(_index: int) -> int:
        nonlocal active, maximum
        _ = barrier.wait()

        def transition(state: LoopLedger) -> LoopLedger:
            nonlocal active, maximum
            with counter_lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.03)
            with counter_lock:
                active -= 1
            return replace(state, edit_epoch=state.edit_epoch + 1)

        return mutate_loop_ledger(root, transition).edit_epoch

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(increment, range(4)))

    assert sorted(results) == [1, 2, 3, 4]
    assert maximum == 1
    assert json.loads((root / "loop.json").read_text(encoding="utf-8"))["edit_epoch"] == 4


def test_locked_ledger_times_out_within_bounded_wait(tmp_path: Path) -> None:
    root = tmp_path / "turn"
    root.mkdir(parents=True)
    lock = root / "loop.lock"
    _ = lock.write_text("", encoding="utf-8")

    started = time.monotonic()
    with pytest.raises(TimeoutError):
        _ = mutate_loop_ledger(root, lambda state: state)

    assert time.monotonic() - started < 0.5


def test_mutations_are_deterministic_across_sixteen_threads(tmp_path: Path) -> None:
    root = tmp_path / "turn"

    def increment() -> int:
        return mutate_loop_ledger(
            root, lambda state: replace(state, edit_epoch=state.edit_epoch + 1)
        ).edit_epoch

    def run_increment(_index: int) -> int:
        return increment()

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(executor.map(run_increment, range(16)))

    assert sorted(results) == list(range(1, 17))
    assert load_loop_ledger(root).edit_epoch == 16
    assert json.loads((root / "loop.json").read_text(encoding="utf-8"))["edit_epoch"] == 16


def test_oversized_transition_is_rejected_without_replacing_ledger(tmp_path: Path) -> None:
    root = tmp_path / "turn"
    original = mutate_loop_ledger(root, lambda state: replace(state, edit_epoch=3))
    fingerprint = keyed_fingerprint(root, "pytest tests/private_case.py -q")
    oversized_actions = tuple(ActionRecord(fingerprint, "ok", 10**1000, 0) for _ in range(8))

    with pytest.raises(ValueError, match="4096"):
        _ = mutate_loop_ledger(root, lambda state: replace(state, actions=oversized_actions))

    assert load_loop_ledger(root) == original
