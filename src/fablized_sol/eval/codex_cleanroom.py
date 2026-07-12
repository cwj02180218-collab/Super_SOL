"""Clean-room raw-versus-Super-SOL stock Codex evaluation CLI."""

# Validation diagnostics are deliberate public boundary messages.
# ruff: noqa: EM101, TRY003

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, ClassVar, Final, Protocol, cast, final

import anyio
import typer
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictStr,
    TypeAdapter,
    ValidationError,
    model_validator,
)
from pydantic_core import PydanticCustomError

from fablized_sol.eval.codex_cleanroom_home import (
    CleanroomHomes,
    HomeTreeEvidence,
    SubprocessHomeCommandRunner,
    build_cleanroom_homes,
    remove_cleanroom_homes,
)
from fablized_sol.eval.codex_telemetry import (
    CodexInfrastructureFailure,
    InfrastructureKind,
    parse_codex_capture,
)
from fablized_sol.eval.grader import (
    GraderInfrastructureError,
    GraderPassed,
    GraderResult,
    run_out_of_band_grader,
)
from fablized_sol.eval.manifest import ReasoningEffort, TaskManifest, TaskSpec, VerificationImage
from fablized_sol.eval.provenance import digest_json, task_digest
from fablized_sol.harness.container_runtime import (
    AnyioDockerRunner,
    VerificationProcessRunner,
    preflight_local_images,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

_RUN_SCHEMA: Final = "super-sol-codex-ab/v1"
_SLOT_SCHEMA: Final = "super-sol-codex-slot/v1"
_IMMUTABLE_REF: Final = r"^(?:v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?|[0-9a-f]{40})$"
_ENVIRONMENT_NAMES: Final = (
    "CODEX_HOME",
    "HOME",
    "LANG",
    "LC_ALL",
    "PATH",
    "PLUGIN_DATA",
    "PYTHONUTF8",
    "SHELL",
    "TMPDIR",
    "TZ",
)
_OBJECT_ADAPTER = TypeAdapter[dict[str, JsonValue]](dict[str, JsonValue])


@final
class CodexABError(Exception):
    """The clean-room planner could not produce valid evidence."""


class CodexArm(StrEnum):
    """Raw or one-plugin Codex arm."""

    RAW = "raw"
    LEAN = "lean"


class CodexABOptions(BaseModel):
    """Strict CLI boundary for one clean-room comparison."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    tasks: Path
    output_dir: Path
    run_id: StrictStr = Field(min_length=1, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    codex_binary: Path
    model: StrictStr = Field(min_length=1)
    effort: ReasoningEffort
    repetitions: int = Field(ge=1, le=5)
    plugin_source: Path
    plugin_ref: StrictStr = Field(pattern=_IMMUTABLE_REF)
    auth_source: Path | None
    grader_image: VerificationImage | None
    timeout_seconds: int = Field(ge=30, le=3600)
    dry_run: bool
    confirm_billable: bool = False
    resume: bool = False

    @model_validator(mode="after")
    def validate_paths_and_live_consent(self) -> CodexABOptions:
        """Fail before output or model work on invalid paths or missing live consent."""
        if not self.codex_binary.is_absolute() or not self.codex_binary.is_file():
            raise PydanticCustomError(
                "invalid_codex_binary", "codex binary must be an absolute file"
            )
        if not os.access(self.codex_binary, os.X_OK):
            raise PydanticCustomError("non_executable_codex", "codex binary must be executable")
        if self.plugin_source.is_symlink() or not self.plugin_source.is_dir():
            raise PydanticCustomError("invalid_plugin_source", "plugin source must be a directory")
        if not self.tasks.is_file():
            raise PydanticCustomError("missing_tasks", "task manifest does not exist")
        if not self.dry_run:
            if not self.confirm_billable:
                raise PydanticCustomError(
                    "billable_confirmation_required",
                    "live clean-room evaluation requires --confirm-billable",
                )
            if self.grader_image is None:
                raise PydanticCustomError(
                    "missing_grader_image",
                    "live clean-room evaluation requires a digest-pinned grader image",
                )
            if (
                self.auth_source is None
                or self.auth_source.is_symlink()
                or not self.auth_source.is_file()
            ):
                raise PydanticCustomError(
                    "missing_auth_source",
                    "live clean-room evaluation requires a regular auth source",
                )
        elif self.resume:
            raise PydanticCustomError(
                "dry_resume_forbidden",
                "--resume is only valid for an explicitly approved live run",
            )
        return self


class CodexRunIdentity(BaseModel):
    """Content-bound inputs shared by every slot in one run."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid", strict=True)

    schema_version: str
    run_id: str
    codex_binary_path: str
    codex_binary_version: str
    codex_binary_digest: str
    model: str
    effort: ReasoningEffort
    repetitions: int
    task_digests: tuple[tuple[str, str], ...]
    plugin_ref: str
    plugin_tree_digest: str
    command_template_digest: str
    environment_names: tuple[str, ...]
    timeout_seconds: int
    grader_image: str


@dataclass(frozen=True, slots=True)
class CodexSlot:
    """One task, repetition, and arm assignment."""

    slot_id: str
    task: TaskSpec
    task_content_digest: str
    repetition: int
    arm: CodexArm
    run_digest: str


@dataclass(frozen=True, slots=True)
class CodexProcessCall:
    """Complete one-shot stock Codex process request."""

    slot_id: str
    argv: tuple[str, ...]
    cwd: Path
    env: Mapping[str, str]
    stdin: str
    timeout_seconds: int


@dataclass(frozen=True, slots=True)
class CodexProcessCapture:
    """Bounded stock Codex process output."""

    returncode: int
    stdout: str
    stderr: str


class CodexProcessRunner(Protocol):
    """Injectable seam that alone may start a quota-consuming Codex turn."""

    def run(self, call: CodexProcessCall) -> CodexProcessCapture:
        """Run one preregistered slot exactly once."""
        ...


class CleanroomHomeFactory(Protocol):
    """Injectable construction and cleanup of symmetric Codex homes."""

    def build(self, options: CodexABOptions, *, include_auth: bool) -> CleanroomHomes:
        """Create and validate a home pair."""
        ...

    def remove(self, homes: CleanroomHomes) -> None:
        """Delete the owned temporary home pair."""
        ...


@final
class StockCodexHomeFactory:
    """Production home factory backed by stock Codex plugin commands."""

    def build(self, options: CodexABOptions, *, include_auth: bool) -> CleanroomHomes:
        """Build homes with authentication only for explicitly approved live work."""
        return build_cleanroom_homes(
            codex_binary=options.codex_binary,
            plugin_source=options.plugin_source,
            plugin_ref=options.plugin_ref,
            auth_source=options.auth_source if include_auth else None,
            runner=SubprocessHomeCommandRunner(),
        )

    def remove(self, homes: CleanroomHomes) -> None:
        """Remove homes through their ownership guard."""
        remove_cleanroom_homes(homes)


@final
class SubprocessCodexProcessRunner:
    """Bounded, shell-free stock Codex process implementation."""

    def run(self, call: CodexProcessCall) -> CodexProcessCapture:
        """Run exactly the supplied Codex call and capture JSONL diagnostics."""
        try:
            completed = subprocess.run(  # noqa: S603
                call.argv,
                cwd=call.cwd,
                env=dict(call.env),
                input=call.stdin,
                text=True,
                capture_output=True,
                check=False,
                timeout=call.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return CodexProcessCapture(124, "", "timeout")
        return CodexProcessCapture(completed.returncode, completed.stdout, completed.stderr)


def _tree_digest(root: Path) -> str:
    entries: list[dict[str, object]] = []
    if root.is_symlink() or not root.is_dir():
        raise CodexABError("plugin tree is missing")
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise CodexABError("plugin tree contains a symlink")
        mode = stat.S_IMODE(path.stat().st_mode)
        if path.is_dir():
            entries.append({"kind": "directory", "mode": mode, "path": relative})
        elif path.is_file():
            entries.append(
                {
                    "content_sha256": sha256(path.read_bytes()).hexdigest(),
                    "kind": "file",
                    "mode": mode,
                    "path": relative,
                }
            )
        else:
            raise CodexABError("plugin tree contains a non-regular entry")
    return digest_json({"entries": entries, "schema": "super-sol-plugin-tree/v1"})


def _codex_version(binary: Path) -> str:
    with tempfile.TemporaryDirectory(prefix="super-sol-codex-version-") as home:
        try:
            completed = subprocess.run(  # noqa: S603
                (str(binary), "--version"),
                check=False,
                capture_output=True,
                env={"CODEX_HOME": home, "HOME": home, "PATH": os.environ.get("PATH", "")},
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise CodexABError("could not inspect Codex version") from error
    version = completed.stdout.strip()
    if completed.returncode != 0 or not version:
        raise CodexABError("could not inspect Codex version")
    return version


def _command_template(options: CodexABOptions) -> tuple[str, ...]:
    return (
        str(options.codex_binary),
        "exec",
        "--json",
        "--ephemeral",
        "--skip-git-repo-check",
        "--dangerously-bypass-hook-trust",
        "--sandbox",
        "workspace-write",
        "--ask-for-approval",
        "never",
        "--model",
        options.model,
        "--config",
        f'model_reasoning_effort="{options.effort}"',
        "-C",
        "<WORKSPACE>",
        "-",
    )


def build_run_identity(options: CodexABOptions, manifest: TaskManifest) -> CodexRunIdentity:
    """Bind all non-secret run inputs before any model process can start."""
    binary = options.codex_binary.resolve()
    return CodexRunIdentity(
        schema_version=_RUN_SCHEMA,
        run_id=options.run_id,
        codex_binary_path=str(binary),
        codex_binary_version=_codex_version(binary),
        codex_binary_digest=sha256(binary.read_bytes()).hexdigest(),
        model=options.model,
        effort=options.effort,
        repetitions=options.repetitions,
        task_digests=tuple((task.id, task_digest(task)) for task in manifest.tasks),
        plugin_ref=options.plugin_ref,
        plugin_tree_digest=_tree_digest(options.plugin_source.resolve() / "plugins" / "super-sol"),
        command_template_digest=digest_json(_command_template(options)),
        environment_names=_ENVIRONMENT_NAMES,
        timeout_seconds=options.timeout_seconds,
        grader_image=options.grader_image or "dry-run",
    )


def _slots_from_identity(
    options: CodexABOptions,
    manifest: TaskManifest,
    identity: CodexRunIdentity,
) -> tuple[CodexSlot, ...]:
    run_digest = digest_json(identity.model_dump(mode="json"))
    digests = dict(identity.task_digests)
    planned: list[CodexSlot] = []
    for task_index, task in enumerate(manifest.tasks):
        first = (CodexArm.RAW, CodexArm.LEAN)
        if task_index % 2:
            first = tuple(reversed(first))
        for repetition in range(1, options.repetitions + 1):
            arms = first if repetition % 2 else tuple(reversed(first))
            for arm in arms:
                slot_id = digest_json(
                    {
                        "arm": arm,
                        "repetition": repetition,
                        "run_digest": run_digest,
                        "schema": _SLOT_SCHEMA,
                        "task_digest": digests[task.id],
                    }
                )
                planned.append(
                    CodexSlot(
                        slot_id=slot_id,
                        task=task,
                        task_content_digest=digests[task.id],
                        repetition=repetition,
                        arm=arm,
                        run_digest=run_digest,
                    )
                )
    return tuple(planned)


def plan_slots(options: CodexABOptions, manifest: TaskManifest) -> tuple[CodexSlot, ...]:
    """Return deterministic balanced task/repetition/arm assignments."""
    return _slots_from_identity(options, manifest, build_run_identity(options, manifest))


def _home_payload(evidence: HomeTreeEvidence) -> dict[str, object]:
    return asdict(evidence)


def _write_private(path: Path, content: str) -> None:
    _ = path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def _write_plan(
    run_root: Path,
    identity: CodexRunIdentity,
    slots: tuple[CodexSlot, ...],
    homes: CleanroomHomes,
) -> None:
    run_payload = {
        "schema": _RUN_SCHEMA,
        "identity": identity.model_dump(mode="json"),
        "run_digest": digest_json(identity.model_dump(mode="json")),
        "raw_home": _home_payload(homes.raw_evidence),
        "lean_home": _home_payload(homes.lean_evidence),
    }
    _write_private(
        run_root / "run.json",
        json.dumps(run_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
    )
    events = "\n".join(
        json.dumps(
            {
                "arm": slot.arm,
                "repetition": slot.repetition,
                "run_digest": slot.run_digest,
                "slot_id": slot.slot_id,
                "task_digest": slot.task_content_digest,
                "task_id": slot.task.id,
                "type": "slot.planned",
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        for slot in slots
    )
    _write_private(run_root / "events.jsonl", f"{events}\n")


def _append_event(path: Path, payload: Mapping[str, object]) -> None:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    with path.open("a", encoding="utf-8") as stream:
        _ = stream.write(f"{encoded}\n")
        stream.flush()
        os.fsync(stream.fileno())


def _read_objects(path: Path) -> tuple[dict[str, JsonValue], ...]:
    try:
        return tuple(
            _OBJECT_ADAPTER.validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    except (OSError, ValidationError) as error:
        raise CodexABError("invalid existing clean-room evidence") from error


def _validate_resume(  # noqa: C901, PLR0912 - fail-closed event-state parser
    run_root: Path,
    identity: CodexRunIdentity,
    slots: tuple[CodexSlot, ...],
    homes: CleanroomHomes,
) -> tuple[CodexSlot, ...]:
    records = _read_objects(run_root / "run.json")
    if len(records) != 1:
        raise CodexABError("resume run identity is missing")
    record = records[0]
    if digest_json(record.get("identity")) != digest_json(identity.model_dump(mode="json")):
        raise CodexABError("resume run identity does not match")
    if digest_json(record.get("raw_home")) != digest_json(_home_payload(homes.raw_evidence)):
        raise CodexABError("resume raw home digest does not match")
    if digest_json(record.get("lean_home")) != digest_json(_home_payload(homes.lean_evidence)):
        raise CodexABError("resume lean home digest does not match")

    expected = {slot.slot_id for slot in slots}
    planned: set[str] = set()
    missing: set[str] = set()
    completed: set[str] = set()
    events = _read_objects(run_root / "events.jsonl")
    for event in events:
        event_type = event.get("type")
        slot_id = event.get("slot_id")
        if (
            not isinstance(event_type, str)
            or not isinstance(slot_id, str)
            or slot_id not in expected
        ):
            raise CodexABError("resume event is outside the preregistered slot lattice")
        if event_type == "slot.planned":
            if slot_id in planned:
                raise CodexABError("resume evidence contains a duplicate planned slot")
            planned.add(slot_id)
        elif event_type == "slot.missing":
            missing.add(slot_id)
        elif event_type == "slot.completed":
            completed.add(slot_id)
        elif event_type not in {"slot.started", "slot.resumed"}:
            raise CodexABError("resume evidence contains an unknown event")
    if planned != expected:
        raise CodexABError("resume evidence has an incomplete planned lattice")
    if missing & completed:
        resumed_ids: set[str] = set()
        for event in events:
            resumed_slot = event.get("slot_id")
            if event.get("type") == "slot.resumed" and isinstance(resumed_slot, str):
                resumed_ids.add(resumed_slot)
        if not (missing & completed) <= resumed_ids:
            raise CodexABError("completed slot lacks a valid resume transition")
    unresolved = missing - completed
    if not unresolved:
        raise CodexABError("resume has no infrastructure-missing slots")
    if expected - completed - missing:
        raise CodexABError("resume accepts only explicitly missing slots")
    return tuple(slot for slot in slots if slot.slot_id in unresolved)


def _snapshot(root: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise CodexABError("model workspace contains a symlink")
        if path.is_file():
            entries[relative] = digest_json(
                {
                    "content_sha256": sha256(path.read_bytes()).hexdigest(),
                    "mode": stat.S_IMODE(path.stat().st_mode),
                }
            )
    return entries


def _changed_files(before: Mapping[str, str], after: Mapping[str, str]) -> tuple[str, ...]:
    return tuple(
        path for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)
    )


def _slot_environment(slot_runtime: Path, home: Path) -> dict[str, str]:
    home_directory = slot_runtime / "home"
    plugin_data = slot_runtime / "plugin-data"
    temporary = slot_runtime / "tmp"
    for directory in (home_directory, plugin_data, temporary):
        directory.mkdir(parents=True)
    return {
        "CODEX_HOME": str(home),
        "HOME": str(home_directory),
        "LANG": "C",
        "LC_ALL": "C",
        "PATH": os.environ.get("PATH", ""),
        "PLUGIN_DATA": str(plugin_data),
        "PYTHONUTF8": "1",
        "SHELL": "/bin/sh",
        "TMPDIR": str(temporary),
        "TZ": "UTC",
    }


async def _grade(
    workspace: Path,
    image: str,
    argv: tuple[str, ...],
    runner: VerificationProcessRunner,
) -> GraderResult:
    return await run_out_of_band_grader(workspace, image, argv, runner)


def _missing_event(slot: CodexSlot, kind: InfrastructureKind | str) -> dict[str, object]:
    return {
        "arm": slot.arm,
        "infrastructure_kind": str(kind),
        "repetition": slot.repetition,
        "run_digest": slot.run_digest,
        "slot_id": slot.slot_id,
        "task_digest": slot.task_content_digest,
        "task_id": slot.task.id,
        "type": "slot.missing",
    }


def _execute_slots(  # noqa: PLR0913 - sequential trust boundary
    options: CodexABOptions,
    slots: tuple[CodexSlot, ...],
    run_root: Path,
    homes: CleanroomHomes,
    process_runner: CodexProcessRunner,
    grader_runner: VerificationProcessRunner,
    *,
    resumed: bool,
) -> int:
    events_path = run_root / "events.jsonl"
    workspaces = run_root / "workspaces"
    workspaces.mkdir(exist_ok=True)
    failed = False
    grader_image = cast("str", options.grader_image)
    template = _command_template(options)
    for slot in slots:
        workspace = workspaces / slot.slot_id
        if workspace.exists():
            shutil.rmtree(workspace)
        _ = shutil.copytree(slot.task.fixture, workspace)
        before = _snapshot(workspace)
        runtime = homes.root / "runtime" / slot.slot_id
        if runtime.exists():
            shutil.rmtree(runtime)
        selected_home = homes.raw if slot.arm is CodexArm.RAW else homes.lean
        environment = _slot_environment(runtime, selected_home)
        argv = tuple(str(workspace) if value == "<WORKSPACE>" else value for value in template)
        _append_event(
            events_path,
            {
                "arm": slot.arm,
                "repetition": slot.repetition,
                "slot_id": slot.slot_id,
                "task_id": slot.task.id,
                "type": "slot.resumed" if resumed else "slot.started",
            },
        )
        started = time.monotonic()
        try:
            capture = process_runner.run(
                CodexProcessCall(
                    slot_id=slot.slot_id,
                    argv=argv,
                    cwd=workspace,
                    env=environment,
                    stdin=slot.task.prompt,
                    timeout_seconds=options.timeout_seconds,
                )
            )
        except Exception:  # noqa: BLE001 - process seam becomes missing infrastructure
            _append_event(events_path, _missing_event(slot, InfrastructureKind.NONZERO_EXIT))
            failed = True
            continue
        telemetry = parse_codex_capture(capture.stdout, capture.stderr, capture.returncode)
        if isinstance(telemetry, CodexInfrastructureFailure):
            _append_event(events_path, _missing_event(slot, telemetry.kind))
            failed = True
            continue
        grader_result = anyio.run(
            _grade,
            workspace,
            grader_image,
            slot.task.grader_argv,
            grader_runner,
        )
        if isinstance(grader_result, GraderInfrastructureError):
            _append_event(events_path, _missing_event(slot, "grader_infrastructure"))
            failed = True
            continue
        grader_passed = isinstance(grader_result, GraderPassed)
        try:
            changed = _changed_files(before, _snapshot(workspace))
        except CodexABError:
            _append_event(events_path, _missing_event(slot, "artifact_violation"))
            failed = True
            continue
        usage = telemetry.usage
        _append_event(
            events_path,
            {
                "arm": slot.arm,
                "cached_input_tokens": usage.cached_input_tokens,
                "changed_files": changed,
                "changed_files_digest": digest_json(changed),
                "full_pass": grader_passed,
                "grader_passed": grader_passed,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "public_verification": "unobserved",
                "reasoning_output_tokens": usage.reasoning_output_tokens,
                "repetition": slot.repetition,
                "run_digest": slot.run_digest,
                "score": 100.0 if grader_passed else 0.0,
                "slot_id": slot.slot_id,
                "task_digest": slot.task_content_digest,
                "task_id": slot.task.id,
                "total_tokens": usage.total_tokens,
                "type": "slot.completed",
                "wall_time_seconds": max(0.0, time.monotonic() - started),
            },
        )
        failed = failed or not grader_passed
    return int(failed)


def run_codex_ab(
    options: CodexABOptions,
    process_runner: CodexProcessRunner,
    home_factory: CleanroomHomeFactory,
    grader_runner: VerificationProcessRunner,
    *,
    image_preflight: Callable[[tuple[str, ...]], bool] = preflight_local_images,
) -> int:
    """Validate, preflight, and execute only preregistered clean-room slots."""
    run_root = options.output_dir / options.run_id
    if run_root.exists() and not options.resume:
        return 2
    if options.resume and not run_root.is_dir():
        return 2
    manifest = TaskManifest.load(options.tasks)
    identity = build_run_identity(options, manifest)
    slots = _slots_from_identity(options, manifest, identity)
    homes = home_factory.build(options, include_auth=not options.dry_run)
    try:
        selected = slots
        if options.resume:
            selected = _validate_resume(run_root, identity, slots, homes)
        else:
            run_root.mkdir(parents=True)
            _write_plan(run_root, identity, slots, homes)
        if options.dry_run:
            return 0
        grader_image = cast("str", options.grader_image)
        if not image_preflight((grader_image,)):
            for slot in selected:
                _append_event(run_root / "events.jsonl", _missing_event(slot, "image_preflight"))
            return 1
        return _execute_slots(
            options,
            selected,
            run_root,
            homes,
            process_runner,
            grader_runner,
            resumed=options.resume,
        )
    finally:
        home_factory.remove(homes)


def evaluate(  # noqa: PLR0913 - Typer option signature is the CLI contract
    tasks: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    output_dir: Annotated[Path, typer.Option()],
    run_id: Annotated[str, typer.Option()],
    plugin_ref: Annotated[str, typer.Option()],
    codex_binary: Annotated[Path | None, typer.Option()] = None,
    model: Annotated[str, typer.Option()] = "gpt-5.6-sol",
    effort: Annotated[str, typer.Option()] = "xhigh",
    repetitions: Annotated[int, typer.Option(min=1, max=5)] = 2,
    plugin_source: Annotated[Path | None, typer.Option()] = None,
    auth_source: Annotated[Path | None, typer.Option()] = None,
    grader_image: Annotated[str | None, typer.Option()] = None,
    timeout_seconds: Annotated[int, typer.Option(min=30, max=3600)] = 900,
    dry_run: Annotated[bool, typer.Option()] = False,
    confirm_billable: Annotated[bool, typer.Option()] = False,
    resume: Annotated[bool, typer.Option()] = False,
) -> None:
    """Plan or run a symmetric stock Codex raw-versus-Super-SOL comparison."""
    binary_value = codex_binary or Path(shutil.which("codex") or "codex")
    try:
        options = CodexABOptions(
            tasks=tasks,
            output_dir=output_dir,
            run_id=run_id,
            codex_binary=binary_value.resolve(),
            model=model,
            effort=cast("ReasoningEffort", effort),
            repetitions=repetitions,
            plugin_source=(plugin_source or Path.cwd()).resolve(),
            plugin_ref=plugin_ref,
            auth_source=auth_source,
            grader_image=grader_image,
            timeout_seconds=timeout_seconds,
            dry_run=dry_run,
            confirm_billable=confirm_billable,
            resume=resume,
        )
    except ValidationError as error:
        raise typer.BadParameter(str(error), param_hint="clean-room options") from error
    exit_code = run_codex_ab(
        options,
        SubprocessCodexProcessRunner(),
        StockCodexHomeFactory(),
        AnyioDockerRunner(),
    )
    if exit_code != 0:
        raise typer.Exit(exit_code)


app = typer.Typer(no_args_is_help=True)
_ = app.command()(evaluate)


def main() -> None:
    """Run the installed clean-room Codex A/B console script."""
    app()
