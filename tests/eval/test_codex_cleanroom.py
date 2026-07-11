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
