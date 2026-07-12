"""Clean-room planner and no-call dry-run tests."""

# Sentinel runners intentionally raise if a forbidden dry-run call occurs.
# ruff: noqa: EM101, TRY003

import json
import shutil
from pathlib import Path
from typing import final

import pytest
from pydantic import JsonValue, TypeAdapter, ValidationError

from fablized_sol.eval.codex_cleanroom import (
    CodexABOptions,
    CodexArm,
    CodexProcessCall,
    CodexProcessCapture,
    plan_slots,
    run_codex_ab,
)
from fablized_sol.eval.codex_cleanroom_home import CleanroomHomes, HomeArm, HomeTreeEvidence
from fablized_sol.eval.manifest import TaskManifest
from fablized_sol.harness.container_runtime import DockerInvocation, ProcessCapture

_OBJECT_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])


def _write_two_task_manifest(tmp_path: Path) -> Path:
    tasks: list[dict[str, object]] = []
    for task_id in ("t1", "t2"):
        fixture = tmp_path / task_id
        fixture.mkdir(exist_ok=True)
        _ = (fixture / "subject.py").write_text("VALUE = 1\n", encoding="utf-8")
        tasks.append(
            {
                "id": task_id,
                "prompt": f"update {task_id}",
                "fixture": task_id,
                "verify_argv": ["python", "-m", "pytest", "-q"],
                "grader_argv": ["python", "-m", "pytest", "-q", "hidden"],
            }
        )
    path = tmp_path / "tasks.json"
    _ = path.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
    return path


def _make_options(tmp_path: Path, **overrides: object) -> CodexABOptions:
    codex_binary = tmp_path / "codex"
    _ = codex_binary.write_text("#!/bin/sh\necho 'codex-cli 0.144.1'\n", encoding="utf-8")
    codex_binary.chmod(0o755)
    plugin = tmp_path / "plugins" / "super-sol"
    plugin.mkdir(parents=True, exist_ok=True)
    _ = (plugin / "plugin.txt").write_text("lean plugin\n", encoding="utf-8")
    values: dict[str, object] = {
        "tasks": _write_two_task_manifest(tmp_path),
        "output_dir": tmp_path / "out",
        "run_id": "run-one",
        "codex_binary": codex_binary,
        "model": "gpt-5.6-sol",
        "effort": "xhigh",
        "repetitions": 2,
        "plugin_source": tmp_path,
        "plugin_ref": "a" * 40,
        "auth_source": None,
        "grader_image": None,
        "timeout_seconds": 300,
        "dry_run": True,
        "confirm_billable": False,
    }
    values.update(overrides)
    return CodexABOptions.model_validate(values)


@final
class _FakeCodexProcessRunner:
    calls: list[CodexProcessCall]

    def __init__(self) -> None:
        self.calls = []

    def run(self, call: CodexProcessCall) -> CodexProcessCapture:
        self.calls.append(call)
        raise AssertionError("dry-run started a Codex model process")


@final
class _FakeHomeFactory:
    plugin_install_calls: int
    cleaned_roots: int

    def __init__(self) -> None:
        self.plugin_install_calls = 0
        self.cleaned_roots = 0

    def build(self, options: CodexABOptions, *, include_auth: bool) -> CleanroomHomes:
        assert include_auth is (not options.dry_run)
        self.plugin_install_calls += 1
        root = options.output_dir.parent / "fake-homes"
        raw = root / "raw"
        lean = root / "lean"
        raw.mkdir(parents=True)
        lean.mkdir()
        return CleanroomHomes(
            root=root,
            raw=raw,
            lean=lean,
            raw_evidence=HomeTreeEvidence(HomeArm.RAW, "1" * 64, (), (), ()),
            lean_evidence=HomeTreeEvidence(
                HomeArm.LEAN,
                "2" * 64,
                ("plugins/cache/super-sol/plugin.json",),
                ("plugins/cache/super-sol/skills/super-sol/SKILL.md",),
                ("super-sol",),
            ),
        )

    def remove(self, homes: CleanroomHomes) -> None:
        self.cleaned_roots += 1
        shutil.rmtree(homes.root)


@final
class _FailingGraderRunner:
    calls: int

    def __init__(self) -> None:
        self.calls = 0

    async def run(self, invocation: DockerInvocation) -> ProcessCapture:
        _ = invocation
        self.calls += 1
        raise AssertionError("dry-run started Docker grading")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _live_options(tmp_path: Path, *, resume: bool = False) -> CodexABOptions:
    auth = tmp_path / "auth.json"
    _ = auth.write_text('{"auth_mode":"chatgpt"}', encoding="utf-8")
    auth.chmod(0o600)
    return _make_options(
        tmp_path,
        auth_source=auth,
        grader_image="grader@sha256:" + "b" * 64,
        dry_run=False,
        confirm_billable=True,
        resume=resume,
    )


def _completed_capture() -> CodexProcessCapture:
    return CodexProcessCapture(
        0,
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 1000,
                    "cached_input_tokens": 800,
                    "output_tokens": 20,
                    "reasoning_output_tokens": 5,
                },
            }
        ),
        "",
    )


@final
class _SequenceCodexRunner:
    calls: list[CodexProcessCall]

    def __init__(self, captures: tuple[CodexProcessCapture, ...]) -> None:
        self._captures = iter(captures)
        self.calls = []

    def run(self, call: CodexProcessCall) -> CodexProcessCapture:
        self.calls.append(call)
        return next(self._captures)


@final
class _PassingGraderRunner:
    calls: int

    def __init__(self) -> None:
        self.calls = 0

    async def run(self, invocation: DockerInvocation) -> ProcessCapture:
        _ = invocation
        self.calls += 1
        return ProcessCapture(exit_code=0, stdout=b"", stderr=b"")


def _normalized_argv(call: CodexProcessCall) -> tuple[str, ...]:
    return tuple("<WORKSPACE>" if value == str(call.cwd) else value for value in call.argv)


def _terminal_events(tmp_path: Path) -> list[dict[str, object]]:
    events = _read_jsonl(tmp_path / "out" / "run-one" / "events.jsonl")
    return [event for event in events if event["type"] in {"slot.completed", "slot.missing"}]


def test_live_options_require_explicit_confirmation(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="confirm-billable"):
        _ = _make_options(tmp_path, dry_run=False, confirm_billable=False)


def test_slot_order_is_balanced_and_deterministic(tmp_path: Path) -> None:
    manifest = TaskManifest.load(_write_two_task_manifest(tmp_path))
    options = _make_options(tmp_path, repetitions=2)

    first = plan_slots(options, manifest)
    second = plan_slots(options, manifest)

    assert first == second
    assert [(slot.task.id, slot.repetition, slot.arm) for slot in first] == [
        ("t1", 1, CodexArm.RAW),
        ("t1", 1, CodexArm.LEAN),
        ("t1", 2, CodexArm.LEAN),
        ("t1", 2, CodexArm.RAW),
        ("t2", 1, CodexArm.LEAN),
        ("t2", 1, CodexArm.RAW),
        ("t2", 2, CodexArm.RAW),
        ("t2", 2, CodexArm.LEAN),
    ]


def test_dry_run_writes_plan_without_starting_codex_or_docker(tmp_path: Path) -> None:
    process = _FakeCodexProcessRunner()
    homes = _FakeHomeFactory()
    grader = _FailingGraderRunner()

    exit_code = run_codex_ab(_make_options(tmp_path), process, homes, grader)

    assert exit_code == 0
    assert process.calls == []
    assert grader.calls == 0
    assert homes.plugin_install_calls == 1
    assert homes.cleaned_roots == 1
    events = _read_jsonl(tmp_path / "out" / "run-one" / "events.jsonl")
    assert {event["type"] for event in events} == {"slot.planned"}
    assert len(events) == 8
    assert not (tmp_path / "out" / "run-one" / "workspaces").exists()
    run_record = _OBJECT_ADAPTER.validate_json(
        (tmp_path / "out" / "run-one" / "run.json").read_text(encoding="utf-8")
    )
    raw_home = run_record["raw_home"]
    lean_home = run_record["lean_home"]
    assert isinstance(raw_home, dict)
    assert isinstance(lean_home, dict)
    assert raw_home["tree_digest"] == "1" * 64
    assert lean_home["tree_digest"] == "2" * 64
    assert "prompt" not in json.dumps(run_record)


def test_existing_run_directory_fails_without_model_process(tmp_path: Path) -> None:
    options = _make_options(tmp_path)
    run_root = options.output_dir / options.run_id
    run_root.mkdir(parents=True)
    process = _FakeCodexProcessRunner()
    homes = _FakeHomeFactory()

    exit_code = run_codex_ab(options, process, homes, _FailingGraderRunner())

    assert exit_code == 2
    assert process.calls == []
    assert homes.plugin_install_calls == 0


def test_live_arms_differ_only_by_normalized_paths_and_plugin_home(tmp_path: Path) -> None:
    process = _SequenceCodexRunner((_completed_capture(),) * 8)
    grader = _PassingGraderRunner()

    exit_code = run_codex_ab(
        _live_options(tmp_path),
        process,
        _FakeHomeFactory(),
        grader,
        image_preflight=lambda _images: True,
    )

    assert exit_code == 0
    assert len(process.calls) == 8
    assert grader.calls == 8
    raw_call, lean_call = process.calls[:2]
    assert _normalized_argv(raw_call) == _normalized_argv(lean_call)
    assert raw_call.stdin == lean_call.stdin
    assert (raw_call.cwd / "subject.py").read_bytes() == (lean_call.cwd / "subject.py").read_bytes()
    assert raw_call.env.keys() == lean_call.env.keys()
    assert raw_call.env["CODEX_HOME"] != lean_call.env["CODEX_HOME"]
    assert "--ignore-user-config" not in raw_call.argv
    assert "--dangerously-bypass-approvals-and-sandbox" not in raw_call.argv
    assert "OPENAI_API_KEY" not in raw_call.env
    terminal = _terminal_events(tmp_path)
    assert len(terminal) == 8
    assert {event["type"] for event in terminal} == {"slot.completed"}


def test_rate_limit_is_missing_and_never_zero_score(tmp_path: Path) -> None:
    failure = CodexProcessCapture(1, "", "429 session limit")
    process = _SequenceCodexRunner((failure,) * 8)
    grader = _PassingGraderRunner()

    exit_code = run_codex_ab(
        _live_options(tmp_path),
        process,
        _FakeHomeFactory(),
        grader,
        image_preflight=lambda _images: True,
    )

    assert exit_code == 1
    assert grader.calls == 0
    terminal = _terminal_events(tmp_path)
    assert len(terminal) == 8
    assert {event["infrastructure_kind"] for event in terminal} == {"rate_limit"}
    assert all("score" not in event for event in terminal)


def test_image_preflight_failure_stops_before_model_and_grader(tmp_path: Path) -> None:
    process = _SequenceCodexRunner((_completed_capture(),) * 8)
    grader = _PassingGraderRunner()

    exit_code = run_codex_ab(
        _live_options(tmp_path),
        process,
        _FakeHomeFactory(),
        grader,
        image_preflight=lambda _images: False,
    )

    assert exit_code == 1
    assert process.calls == []
    assert grader.calls == 0
    terminal = _terminal_events(tmp_path)
    assert len(terminal) == 8
    assert {event["infrastructure_kind"] for event in terminal} == {"image_preflight"}


def test_resume_never_calls_an_already_completed_slot(tmp_path: Path) -> None:
    failure = CodexProcessCapture(1, "", "429 session limit")
    first = _SequenceCodexRunner((_completed_capture(),) + (failure,) * 7)
    grader = _PassingGraderRunner()
    homes = _FakeHomeFactory()

    first_exit = run_codex_ab(
        _live_options(tmp_path),
        first,
        homes,
        grader,
        image_preflight=lambda _images: True,
    )
    second = _SequenceCodexRunner((_completed_capture(),) * 7)
    second_exit = run_codex_ab(
        _live_options(tmp_path, resume=True),
        second,
        homes,
        grader,
        image_preflight=lambda _images: True,
    )

    assert first_exit == 1
    assert second_exit == 0
    assert len(second.calls) == 7
    assert first.calls[0].slot_id not in {call.slot_id for call in second.calls}
    terminal = _terminal_events(tmp_path)
    assert sum(event["type"] == "slot.completed" for event in terminal) == 8
