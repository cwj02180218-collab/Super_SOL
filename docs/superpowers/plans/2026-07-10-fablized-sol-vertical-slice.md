# Fablized SOL Minimum Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a publishable Python package that routes procedural packs, records observed tool evidence, blocks unverified deep-task completion, assigns an out-of-band 80/20 holdout, and dry-runs a GPT-5.6 Sol versus GPT-5.5 evaluation.

**Architecture:** Keep classification, event parsing, ledger aggregation, gate policy, and goals invariants independent of the OpenAI Agents SDK. Put all SDK imports behind a typed adapter that uses an explicit tool-kind registry and converts guardrail exceptions into domain outcomes; measurement and holdout labels stay in a separate shadow stream that is never included in instructions.

**Tech Stack:** Python 3.12, `uv`, OpenAI Agents SDK 0.17.4, Pydantic 2, AnyIO 4, Typer, pytest, Ruff, basedpyright, GitHub Actions.

## Global Constraints

- Use Python `>=3.12`; the current host Python 3.9.6 is not supported by the project.
- Use `uv` for environment and dependency management; do not add `requirements.txt`.
- Pin `openai-agents==0.17.4` for the first measured harness release.
- Use `typeCheckingMode = "all"`, Ruff `select = ["ALL"]`, and pytest strict mode.
- Keep each Python module below 250 non-blank, non-comment lines.
- Use frozen, slotted dataclasses for internal values and frozen Pydantic models at file/CLI boundaries.
- Never infer mutation or verification from free-form tool output text.
- Never expose holdout assignment, shadow labels, or evaluator outcomes to the model.
- Default live models are `gpt-5.6-sol` and `gpt-5.5`; both remain CLI-configurable.
- Live API tests are opt-in; the default quality gate must run without `OPENAI_API_KEY`.
- Every behavior change follows red, green, refactor and ends in an atomic commit.

## File Map

- `pyproject.toml`: package metadata, dependencies, console script, strict tool configuration.
- `.python-version`: Python 3.12 selection for `uv`.
- `.gitignore`: Python, test, build, and local evaluation artifacts.
- `src/fablized_sol/engine/models.py`: enums, branded IDs, and immutable domain outcomes.
- `src/fablized_sol/engine/events.py`: Pydantic ledger event schemas and discriminated parsing.
- `src/fablized_sol/engine/classify_task.py`: Korean/English quick-normal-deep classifier.
- `src/fablized_sol/engine/ledger.py`: append-only JSONL store and chronological aggregation.
- `src/fablized_sol/engine/verify_state.py`: deterministic stop-gate decision table.
- `src/fablized_sol/engine/goals.py`: evidence-aware goal transitions.
- `src/fablized_sol/harness/router.py`: signal routing and pack assembly.
- `src/fablized_sol/harness/registry.py`: immutable tool-name to tool-kind registry.
- `src/fablized_sol/harness/workspace_tools.py`: confined read/write/verification tools.
- `src/fablized_sol/harness/hooks.py`: Agents SDK tool-end observation adapter.
- `src/fablized_sol/harness/guardrails.py`: output guardrail backed only by ledger state.
- `src/fablized_sol/harness/run.py`: bounded retry orchestration and SDK executor.
- `src/fablized_sol/measure/holdout.py`: deterministic 80/20 assignment.
- `src/fablized_sol/measure/shadow.py`: out-of-band JSONL result stream.
- `src/fablized_sol/eval/manifest.py`: trusted task-manifest boundary schema.
- `src/fablized_sol/eval/day0_ab.py`: dry-run/live A/B CLI.
- `src/fablized_sol/packs/*.txt`: three minimal experimental procedure packs.
- `tests/`: mirrors package responsibilities with unit, adapter, and CLI tests.
- `.github/workflows/ci.yml`: default non-live quality gate.
- `README.md`: setup, dry-run, live-run, output schema, and limitations.

---

### Task 1: Project Foundation, Classification, And Holdout

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore`
- Create: `src/fablized_sol/__init__.py`
- Create: `src/fablized_sol/engine/__init__.py`
- Create: `src/fablized_sol/engine/models.py`
- Create: `src/fablized_sol/engine/classify_task.py`
- Create: `src/fablized_sol/measure/__init__.py`
- Create: `src/fablized_sol/measure/holdout.py`
- Test: `tests/engine/test_classify_task.py`
- Test: `tests/measure/test_holdout.py`

**Interfaces:**
- Produces: `classify_prompt(prompt: str) -> Classification`.
- Produces: `assign_arm(session_id: SessionId) -> HoldoutArm`.
- Produces: `TaskMode`, `ToolKind`, `ChangeKind`, `GateAction`, `HoldoutArm`, `SessionId`, `ToolName`, and `Classification`.

- [ ] **Step 1: Install the required local toolchain**

Run:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
```

Expected: `uv --version` exits 0 and `uv run python --version` starts with `Python 3.12` after project metadata exists.

- [ ] **Step 2: Add strict package configuration**

Create `pyproject.toml` with these effective settings:

```toml
[project]
name = "fablized-sol"
version = "0.1.0"
description = "Evidence-gated procedure harness for GPT-5.6 Sol"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "anyio>=4.11,<5",
  "openai-agents==0.17.4",
  "pydantic>=2.12,<3",
  "typer>=0.19,<1",
]

[project.scripts]
fablized-sol-eval = "fablized_sol.eval.day0_ab:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
  "basedpyright>=1.31,<2",
  "pytest>=8.4,<9",
  "pytest-cov>=7,<8",
  "ruff>=0.12,<1",
]

[tool.basedpyright]
typeCheckingMode = "all"
pythonVersion = "3.12"
pythonPlatform = "All"
include = ["src", "tests"]
exclude = ["**/__pycache__", "**/.venv", "**/build", "**/dist"]
reportUnusedCallResult = "warning"
reportUnnecessaryTypeIgnoreComment = "error"
reportUnusedVariable = "error"
reportMissingParameterType = "error"
reportPrivateUsage = "error"

[tool.ruff]
target-version = "py312"
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
# typeCheckingMode = "all" and Ruff ANN rules enforce return annotations.
select = ["ALL"]
ignore = ["COM812", "ISC001", "D203", "D213", "CPY001", "FBT001", "FBT002"]

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101", "ARG", "PLR2004", "SLF001", "D"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
docstring-code-format = true

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = ["-ra", "--strict-config", "--strict-markers"]
filterwarnings = ["error"]
```

Set `.python-version` to `3.12`, ignore `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.fablized/`, `dist/`, and `*.egg-info/`, then run `uv sync --dev`.

Expected: dependency resolution succeeds and creates `uv.lock`.

- [ ] **Step 3: Write failing classification and holdout tests**

```python
from fablized_sol.engine.classify_task import classify_prompt
from fablized_sol.engine.models import HoldoutArm, SessionId, TaskMode
from fablized_sol.measure.holdout import assign_arm


def test_classifies_database_migration_as_deep() -> None:
    result = classify_prompt("프로덕션 DB 마이그레이션을 구현하고 검증해줘")
    assert result.mode is TaskMode.DEEP
    assert result.risk_flags == ("database",)


def test_classifies_explanation_as_quick() -> None:
    assert classify_prompt("이 함수가 뭐야?").mode is TaskMode.QUICK


def test_holdout_assignment_is_stable_and_has_both_arms() -> None:
    first = [assign_arm(SessionId(f"session-{index}")) for index in range(100)]
    second = [assign_arm(SessionId(f"session-{index}")) for index in range(100)]
    assert first == second
    assert set(first) == {HoldoutArm.ON, HoldoutArm.OFF}
    assert assign_arm(SessionId("session-0")) is HoldoutArm.ON
    assert assign_arm(SessionId("session-1")) is HoldoutArm.OFF
```

- [ ] **Step 4: Run the focused tests and confirm red**

Run: `uv run pytest tests/engine/test_classify_task.py tests/measure/test_holdout.py -v`

Expected: collection fails because `fablized_sol.engine.models` and the target functions do not exist.

- [ ] **Step 5: Implement the minimal typed domain and pure functions**

Use `StrEnum`, `NewType`, and a frozen dataclass:

```python
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import NewType

SessionId = NewType("SessionId", str)
ToolName = NewType("ToolName", str)

@unique
class TaskMode(StrEnum):
    QUICK = "quick"
    NORMAL = "normal"
    DEEP = "deep"

@unique
class HoldoutArm(StrEnum):
    ON = "on"
    OFF = "off"

@unique
class ToolKind(StrEnum):
    READ = "read"
    MUTATION = "mutation"
    VERIFICATION = "verification"
    UNKNOWN = "unknown"

@unique
class ChangeKind(StrEnum):
    CODE = "code"
    DOCS = "docs"

@unique
class GateAction(StrEnum):
    ALLOW = "allow"
    BLOCK = "block"
    EXHAUSTED = "exhausted"

@dataclass(frozen=True, slots=True)
class Classification:
    mode: TaskMode
    risk_flags: tuple[str, ...] = ()
```

Implement ordered deep/normal/quick regex tables with Korean and English signals. Use the first matching risk table to add stable flags. Implement holdout using the first eight bytes of SHA-256 as an unsigned integer and `value % 5 == 0` for OFF. Do not special-case test IDs.

- [ ] **Step 6: Verify green and commit**

Run: `uv run pytest tests/engine/test_classify_task.py tests/measure/test_holdout.py -v`

Expected: all focused tests pass.

Run: `uv run ruff check src/fablized_sol/engine src/fablized_sol/measure tests/engine tests/measure && uv run basedpyright`

Expected: both commands exit 0.

```bash
git add pyproject.toml uv.lock .python-version .gitignore src/fablized_sol tests/engine tests/measure
git commit -m "Build typed classification and holdout core"
```

---

### Task 2: Append-only Ledger And Stop Gate

**Files:**
- Create: `src/fablized_sol/engine/events.py`
- Create: `src/fablized_sol/engine/ledger.py`
- Create: `src/fablized_sol/engine/verify_state.py`
- Test: `tests/engine/test_ledger.py`
- Test: `tests/engine/test_verify_state.py`

**Interfaces:**
- Consumes: enums and branded names from `engine.models`.
- Produces: `Ledger.append(event: LedgerEvent) -> None`, `Ledger.read() -> tuple[LedgerEvent, ...]`, and `Ledger.state() -> SessionState`.
- Produces: `decide_stop(state: SessionState, arm: HoldoutArm, retry_limit: int) -> GateDecision`.

- [ ] **Step 1: Write failing chronological-evidence tests**

```python
def test_verification_before_mutation_does_not_satisfy_gate(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append(ClassifyEvent(mode=TaskMode.DEEP, risk_flags=()))
    ledger.append(VerificationToolEvent(tool=ToolName("run_verification"), success=True))
    ledger.append(MutationToolEvent(
        tool=ToolName("write_file"),
        path="src/x.py",
        change_kind=ChangeKind.CODE,
    ))
    decision = decide_stop(ledger.state(), HoldoutArm.ON, retry_limit=2)
    assert decision.action is GateAction.BLOCK


def test_successful_verification_after_mutation_allows_stop(tmp_path: Path) -> None:
    ledger = deep_changed_ledger(tmp_path)
    ledger.append(VerificationToolEvent(tool=ToolName("run_verification"), success=True))
    assert decide_stop(ledger.state(), HoldoutArm.ON, retry_limit=2).action is GateAction.ALLOW


def test_malformed_event_reports_line_number(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"event":"classify"}\nnot-json\n', encoding="utf-8")
    with pytest.raises(LedgerParseError, match="line 2"):
        Ledger(path).read()
```

Add table cases for quick, normal, no mutation, docs-only mutation, failed verification, holdout OFF, first block, second block, and exhausted retry count.

- [ ] **Step 2: Run the focused tests and confirm red**

Run: `uv run pytest tests/engine/test_ledger.py tests/engine/test_verify_state.py -v`

Expected: imports fail because event, ledger, and gate modules do not exist.

- [ ] **Step 3: Implement discriminated event schemas**

Create separate frozen Pydantic variants so mutation events cannot omit a
change kind and verification events cannot omit success:

```python
class ReadToolEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event: Literal["tool_call"] = "tool_call"
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tool: ToolName
    kind: Literal[ToolKind.READ] = ToolKind.READ

class MutationToolEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event: Literal["tool_call"] = "tool_call"
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tool: ToolName
    kind: Literal[ToolKind.MUTATION] = ToolKind.MUTATION
    path: str
    change_kind: ChangeKind

class VerificationToolEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event: Literal["tool_call"] = "tool_call"
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tool: ToolName
    kind: Literal[ToolKind.VERIFICATION] = ToolKind.VERIFICATION
    success: bool

class EvidenceRejectedEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event: Literal["evidence_rejected"] = "evidence_rejected"
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tool: ToolName
    claimed_kind: ToolKind
    reason: Literal["unknown_tool", "malformed_result"]

class ClassifyEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event: Literal["classify"] = "classify"
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    mode: TaskMode
    risk_flags: tuple[str, ...]

class GateFireEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    event: Literal["gate_fire"] = "gate_fire"
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reason: str

type LedgerEvent = (
    ReadToolEvent
    | MutationToolEvent
    | VerificationToolEvent
    | EvidenceRejectedEvent
    | ClassifyEvent
    | GateFireEvent
)
```

Parse each line through `TypeAdapter(LedgerEvent)`. Literal `kind` fields
disambiguate tool-call variants while preserving `"event":"tool_call"`. Wrap
`json.JSONDecodeError` and `ValidationError` in a frozen
`LedgerParseError(path: Path, line_number: int, detail: str)` with `__str__`.
Raise `LedgerStateError` when aggregation sees no classification or more than
one classification for the session.

- [ ] **Step 4: Implement append and aggregation**

`Ledger` is intentionally mutable because it owns a process-local `threading.Lock`; document that exception and use `# noqa: MUTABLE_OK`. Append exactly one UTF-8 JSON line inside the lock. Aggregate events in file order, retaining the sequence number of the latest code mutation and latest successful verification.

```python
@dataclass(frozen=True, slots=True)
class SessionState:
    task_mode: TaskMode
    changed_files_seen: bool
    change_kinds: frozenset[ChangeKind]
    latest_mutation_index: int | None
    latest_successful_verification_index: int | None
    stop_blocks: int

    @property
    def has_fresh_verification(self) -> bool:
        if self.latest_mutation_index is None:
            return False
        if self.latest_successful_verification_index is None:
            return False
        return self.latest_successful_verification_index > self.latest_mutation_index
```

- [ ] **Step 5: Implement the exhaustive gate table**

Return frozen `GateDecision(action: GateAction, reason: str)`. Use boolean guards for arm/no-mutation/fresh-verification, then exhaustive `match` for `TaskMode`. NORMAL is allowed in v0.1; DEEP code changes without fresh verification block until `stop_blocks >= retry_limit`, then return EXHAUSTED. Docs-only means `change_kinds == {ChangeKind.DOCS}`.

- [ ] **Step 6: Verify green and commit**

Run: `uv run pytest tests/engine/test_ledger.py tests/engine/test_verify_state.py -v`

Expected: all ledger and gate cases pass.

```bash
git add src/fablized_sol/engine tests/engine
git commit -m "Enforce chronological verification evidence"
```

---

### Task 3: Evidence-aware Goal Ledger

**Files:**
- Create: `src/fablized_sol/engine/goals.py`
- Test: `tests/engine/test_goals.py`

**Interfaces:**
- Produces: `GoalBook.create(brief: str, goals: tuple[Goal, ...]) -> GoalBook`.
- Produces: `GoalBook.complete(goal_id: GoalId, evidence: Evidence, verify_cmd: VerifyCommand | None = None) -> GoalBook`.
- Produces typed `DuplicateGoalIdError`, `MissingEvidenceError`, `VerificationGoalError`, and `InvalidGoalTransitionError`.

- [ ] **Step 1: Write failing invariant tests**

```python
def test_completion_requires_non_empty_evidence() -> None:
    book = one_goal_book()
    with pytest.raises(MissingEvidenceError):
        book.complete(GoalId("G001"), Evidence(""))


def test_final_goal_requires_command_and_verification_evidence() -> None:
    book = verification_goal_book()
    with pytest.raises(VerificationGoalError):
        book.complete(GoalId("G002"), Evidence("pytest passed"))


def test_completion_returns_new_book_without_mutating_original() -> None:
    book = one_goal_book()
    updated = book.complete(GoalId("G001"), Evidence("test_x passed"))
    assert book.goals[0].status is GoalStatus.PENDING
    assert updated.goals[0].status is GoalStatus.COMPLETE
```

- [ ] **Step 2: Run the focused test and confirm red**

Run: `uv run pytest tests/engine/test_goals.py -v`

Expected: import failure for `fablized_sol.engine.goals`.

- [ ] **Step 3: Implement immutable transitions and typed errors**

Use branded `GoalId`, `Evidence`, and `VerifyCommand`; `GoalStatus` as `StrEnum`; frozen `Goal` and `GoalBook` dataclasses. `GoalBook.create` rejects duplicate IDs. `complete` locates exactly one goal, rejects terminal goals, rejects blank evidence, and requires both non-blank `verify_cmd` and evidence for the final goal. Replace only the matching tuple element with `dataclasses.replace`.

```python
@dataclass(frozen=True, slots=True)
class Goal:
    id: GoalId
    title: str
    objective: str
    status: GoalStatus = GoalStatus.PENDING
    evidence: Evidence | None = None
    verify_cmd: VerifyCommand | None = None

@dataclass(frozen=True, slots=True)
class GoalBook:
    brief: str
    goals: tuple[Goal, ...]
```

Every typed exception is a frozen dataclass with `__str__`; do not call `sys.exit` inside the engine.

- [ ] **Step 4: Verify green and commit**

Run: `uv run pytest tests/engine/test_goals.py -v`

Expected: all goal-invariant tests pass.

```bash
git add src/fablized_sol/engine/goals.py tests/engine/test_goals.py
git commit -m "Require evidence for goal completion"
```

---

### Task 4: Experimental Pack Router

**Files:**
- Create: `src/fablized_sol/harness/__init__.py`
- Create: `src/fablized_sol/harness/router.py`
- Create: `src/fablized_sol/packs/investigation.txt`
- Create: `src/fablized_sol/packs/grounding.txt`
- Create: `src/fablized_sol/packs/multi_story.txt`
- Test: `tests/harness/test_router.py`

**Interfaces:**
- Consumes: `Classification` and `HoldoutArm`.
- Produces: `build_instructions(request: InstructionRequest) -> InstructionBundle`.
- Produces: bundle fields `instructions: str`, `classification: Classification`, and `pack_names: tuple[PackName, ...]`; only `instructions` is model-visible.

- [ ] **Step 1: Write failing routing-isolation tests**

```python
def test_debug_prompt_routes_only_investigation_pack(pack_dir: Path) -> None:
    bundle = build_instructions(InstructionRequest(
        prompt="재현되지 않는 race condition을 디버그해줘",
        base="BASE",
        arm=HoldoutArm.ON,
        pack_dir=pack_dir,
    ))
    assert bundle.pack_names == (PackName.INVESTIGATION,)
    assert "reproduce" in bundle.instructions.lower()
    assert "render" not in bundle.instructions


def test_holdout_receives_base_only_and_no_arm_label(pack_dir: Path) -> None:
    bundle = build_instructions(InstructionRequest(
        prompt="debug this failure",
        base="BASE",
        arm=HoldoutArm.OFF,
        pack_dir=pack_dir,
    ))
    assert bundle.instructions == "BASE"
    assert bundle.pack_names == ()
    assert "holdout" not in bundle.instructions.lower()
```

Add cases for artifact/render signals and explicit multi-outcome prompts.

- [ ] **Step 2: Run the focused test and confirm red**

Run: `uv run pytest tests/harness/test_router.py -v`

Expected: import failure for `harness.router`.

- [ ] **Step 3: Implement exact pack texts and deterministic routing**

Use these immutable boundary types:

```python
@unique
class PackName(StrEnum):
    INVESTIGATION = "investigation"
    GROUNDING = "grounding"
    MULTI_STORY = "multi_story"

@dataclass(frozen=True, slots=True)
class InstructionRequest:
    prompt: str
    base: str
    arm: HoldoutArm
    pack_dir: Path | None = None

@dataclass(frozen=True, slots=True)
class InstructionBundle:
    instructions: str
    classification: Classification
    pack_names: tuple[PackName, ...]
```

Use these initial pack contents:

```text
# investigation.txt
Reproduce the observed failure first. Isolate one falsifiable hypothesis, test it, then make the smallest change and rerun the narrow verification.
```

```text
# grounding.txt
Inspect the actual artifact before judging it. Render, execute, or parse it with an appropriate tool and base conclusions on that observed result.
```

```text
# multi_story.txt
Split independent outcomes into explicit stories. Close each story only with concrete evidence, and reserve the final story for end-to-end verification.
```

Load packs with `importlib.resources.files("fablized_sol.packs")` in production and accept an optional test pack directory through `InstructionRequest`. For ON runs append a concise mode/risk block and only matched packs. For OFF runs return base text byte-for-byte and do not emit mode, risk, arm, or pack labels.

- [ ] **Step 4: Verify green and commit**

Run: `uv run pytest tests/harness/test_router.py -v`

Expected: all routing and holdout-isolation tests pass.

```bash
git add src/fablized_sol/harness src/fablized_sol/packs tests/harness/test_router.py
git commit -m "Route experimental procedure packs"
```

---

### Task 5: Confined Workspace Tools, Registry, And Hooks

**Files:**
- Create: `src/fablized_sol/harness/registry.py`
- Create: `src/fablized_sol/harness/workspace_tools.py`
- Create: `src/fablized_sol/harness/hooks.py`
- Test: `tests/harness/test_registry.py`
- Test: `tests/harness/test_workspace_tools.py`
- Test: `tests/harness/test_hooks.py`

**Interfaces:**
- Consumes: `Ledger`, `ToolName`, `ToolKind`, and `ChangeKind`.
- Produces: `ToolRegistry.create(specs: tuple[ToolSpec, ...]) -> ToolRegistry`, `kind_for(name: ToolName) -> ToolKind`, and `validate_exposed(names: tuple[ToolName, ...]) -> None`.
- Produces: `FablizedContext(workspace: Path, verify_argv: tuple[str, ...], ledger: Ledger, registry: ToolRegistry, arm: HoldoutArm, retry_limit: int)`.
- Produces SDK function tools `list_files`, `read_file`, `write_file`, and `run_verification`.

- [ ] **Step 1: Write failing registry and path-confinement tests**

```python
def test_registry_rejects_duplicate_tool_names() -> None:
    spec = ToolSpec(ToolName("read_file"), ToolKind.READ)
    with pytest.raises(DuplicateToolError):
        ToolRegistry.create((spec, spec))


def test_write_file_rejects_parent_escape(context: FablizedContext) -> None:
    with pytest.raises(WorkspaceEscapeError):
        write_text(context, "../outside.py", "unsafe")


def test_verification_returns_exit_code_without_output_parsing(context: FablizedContext) -> None:
    result = anyio.run(run_verification_process, context)
    assert result.exit_code == 0
    assert result.success is True
```

Create a hook test with a fake tool named `write_file` and a `MutationToolResult(path="src/x.py", change_kind=CODE)`; after `on_tool_end`, assert the ledger contains one mutation event. Add a verification result with exit code 1 and assert `success is False`.

Add adapter-drift cases for an unregistered tool and for registered mutation
and verification tools returning the wrong result type. Each case must append
`EvidenceRejectedEvent` and leave mutation indices and successful verification
indices unchanged. This contract is derived from GPT.C's observed outer/inner
event drift, but uses typed SDK callbacks instead of copying its JSON parser.

- [ ] **Step 2: Run focused tests and confirm red**

Run: `uv run pytest tests/harness/test_registry.py tests/harness/test_workspace_tools.py tests/harness/test_hooks.py -v`

Expected: target modules do not exist.

- [ ] **Step 3: Implement immutable registry and typed results**

```python
@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: ToolName
    kind: ToolKind

@dataclass(frozen=True, slots=True)
class VerificationToolResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.exit_code == 0

@dataclass(frozen=True, slots=True)
class MutationToolResult:
    path: str
    change_kind: ChangeKind

@dataclass(frozen=True, slots=True)
class FablizedContext:
    workspace: Path
    verify_argv: tuple[str, ...]
    ledger: Ledger
    registry: ToolRegistry
    arm: HoldoutArm
    retry_limit: int
```

`validate_exposed` requires all four local tools to be registered before agent
construction and raises `UnknownToolError` for an omission. `kind_for` returns
`ToolKind.UNKNOWN` for an unexpected runtime name so the hook can record it;
UNKNOWN never becomes mutation or verification evidence.

- [ ] **Step 4: Implement confined filesystem/process helpers before SDK decorators**

Resolve relative paths against `workspace.resolve()`, reject absolute paths, and require `resolved.is_relative_to(root)`. `write_text` creates parent directories and returns `MutationToolResult` with DOCS for `.md`, `.rst`, and `.txt`, otherwise CODE. `run_verification_process` calls `anyio.run_process(context.verify_argv, cwd=context.workspace, check=False)` with a 120-second `anyio.fail_after`, returning decoded stdout/stderr capped to the final 32 KiB.

Convert `TimeoutError` to a typed result with exit code 124 and
`FileNotFoundError` or `PermissionError` to exit code 127. The function tool
must always return `VerificationToolResult`; SDK-generated free-form error
strings must never reach the verification hook as evidence candidates.

Keep the pure helpers directly testable. Thin `@function_tool` wrappers receive `ToolContext[FablizedContext]` and call those helpers. `run_verification` accepts no model-supplied command, so the manifest owns the executable and arguments.

- [ ] **Step 5: Implement `LedgerHooks.on_tool_end`**

Subclass `RunHooks[FablizedContext]`. Look up kind by `tool.name`, then
exhaustively match the kind. READ appends `ReadToolEvent`; MUTATION requires
`MutationToolResult` and appends `MutationToolEvent`; VERIFICATION requires
`VerificationToolResult` and appends `VerificationToolEvent` with its success;
UNKNOWN and malformed typed results append `EvidenceRejectedEvent` and continue
without evidence credit. Never infer a fallback result from `str(result)`.
Use one targeted `# noqa: OBJECT_OK` on the SDK-mandated `result: object`
override and narrow immediately with typed parser helpers.

- [ ] **Step 6: Verify green, SDK signatures, and commit**

Run: `uv run pytest tests/harness/test_registry.py tests/harness/test_workspace_tools.py tests/harness/test_hooks.py -v`

Run: `uv run python -c 'from agents import RunHooks, function_tool; from fablized_sol.harness.hooks import LedgerHooks; print(RunHooks, LedgerHooks, function_tool)'`

Expected: tests pass and the smoke command prints the imported classes/function without an exception.

```bash
git add src/fablized_sol/harness tests/harness
git commit -m "Observe typed workspace tool evidence"
```

---

### Task 6: Output Guardrail And Bounded Correction Runs

**Files:**
- Create: `src/fablized_sol/harness/guardrails.py`
- Create: `src/fablized_sol/harness/run.py`
- Test: `tests/harness/test_guardrails.py`
- Test: `tests/harness/test_run.py`

**Interfaces:**
- Consumes: `decide_stop`, `Ledger`, `FablizedContext`, and Agents SDK `Runner`.
- Produces: SDK `verification_gate` output guardrail.
- Produces: `run_fablized(executor: AttemptExecutor, request: RunRequest) -> RunOutcome`.
- Produces outcomes `RunCompleted`, `RunExhausted`, and propagated typed live-run errors.

- [ ] **Step 1: Write failing guardrail and retry tests**

```python
def test_guardrail_blocks_deep_changed_unverified(context: FablizedContext) -> None:
    seed_deep_mutation(context.ledger)
    output = anyio.run(call_verification_gate, context, "claimed done")
    assert output.tripwire_triggered is True
    assert output.output_info.blocked_output == "claimed done"


def test_runner_retries_with_original_prompt_and_reason() -> None:
    executor = FakeExecutor(outcomes=(
        AttemptBlocked(
            action=GateAction.BLOCK,
            reason="verification missing",
            blocked_output="done",
        ),
        AttemptCompleted(output="verified"),
    ))
    result = anyio.run(run_fablized, executor, request(max_gate_retries=2))
    assert result == RunCompleted(output="verified", attempts=2)
    assert executor.inputs[1].startswith("ORIGINAL TASK")
    assert "verification missing" in executor.inputs[1]


def test_runner_returns_exhausted_not_success() -> None:
    executor = FakeExecutor(outcomes=(
        AttemptBlocked(action=GateAction.BLOCK, reason="verification missing", blocked_output="done"),
        AttemptBlocked(action=GateAction.BLOCK, reason="verification missing", blocked_output="done"),
        AttemptBlocked(action=GateAction.EXHAUSTED, reason="retry limit reached", blocked_output="done"),
    ))
    result = anyio.run(run_fablized, executor, request(max_gate_retries=2))
    assert result == RunExhausted(last_output="done", attempts=3, reason="retry limit reached")
```

- [ ] **Step 2: Run focused tests and confirm red**

Run: `uv run pytest tests/harness/test_guardrails.py tests/harness/test_run.py -v`

Expected: target modules do not exist.

- [ ] **Step 3: Implement model-free guardrail decision and SDK wrapper**

```python
class GuardrailInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    decision: GateAction
    reason: str
    blocked_output: str

@output_guardrail
async def verification_gate(
    ctx: RunContextWrapper[FablizedContext],
    agent: Agent[FablizedContext],
    output: str,
) -> GuardrailFunctionOutput:
    decision = decide_stop(ctx.context.ledger.state(), ctx.context.arm, ctx.context.retry_limit)
    return GuardrailFunctionOutput(
        output_info=GuardrailInfo(
            decision=decision.action,
            reason=decision.reason,
            blocked_output=output,
        ),
        tripwire_triggered=decision.action is not GateAction.ALLOW,
    )
```

For BLOCK and EXHAUSTED, append `GateFireEvent` before returning. OFF-arm
decisions never append a gate event.

- [ ] **Step 4: Implement pure retry orchestration**

Define the exact domain surface before the loop:

```python
@dataclass(frozen=True, slots=True)
class RunRequest:
    original_prompt: str
    max_gate_retries: int

@dataclass(frozen=True, slots=True)
class AttemptRequest:
    input_text: str

@dataclass(frozen=True, slots=True)
class AttemptCompleted:
    output: str

@dataclass(frozen=True, slots=True)
class AttemptBlocked:
    action: Literal[GateAction.BLOCK, GateAction.EXHAUSTED]
    reason: str
    blocked_output: str

class AttemptExecutor(Protocol):
    @abstractmethod
    async def execute(self, request: AttemptRequest) -> AttemptCompleted | AttemptBlocked:
        raise NotImplementedError

@dataclass(frozen=True, slots=True)
class RunCompleted:
    output: str
    attempts: int

@dataclass(frozen=True, slots=True)
class RunExhausted:
    last_output: str
    attempts: int
    reason: str

type RunOutcome = RunCompleted | RunExhausted
```

Define `AttemptExecutor` as a Protocol returning
`AttemptCompleted | AttemptBlocked`; `AttemptBlocked` carries
`action: Literal[GateAction.BLOCK, GateAction.EXHAUSTED]`. Use `match` plus
`assert_never`. The correction input must contain the original prompt, state
that the workspace may already be modified, include the exact gate reason, and
require the narrowest configured verification. BLOCK starts another attempt
while budget remains. EXHAUSTED, or a BLOCK after `max_gate_retries + 1` total
attempts, returns `RunExhausted` with the blocked output stored in
`GuardrailInfo`.

- [ ] **Step 5: Implement SDK executor exception translation**

Construct an `Agent[FablizedContext]` with explicit model, tools, instructions,
and `[verification_gate]` only for ON runs. Call
`Runner.run(agent, request.input_text, context=context, hooks=LedgerHooks())`.
Catch only `OutputGuardrailTripwireTriggered`, parse
`exc.guardrail_result.output.output_info` through
`GuardrailInfo.model_validate`, and return `AttemptBlocked`. Other SDK/API
exceptions propagate to the CLI boundary.

- [ ] **Step 6: Verify green and commit**

Run: `uv run pytest tests/harness/test_guardrails.py tests/harness/test_run.py -v`

Expected: all guardrail and bounded-run tests pass without an API key.

```bash
git add src/fablized_sol/harness/guardrails.py src/fablized_sol/harness/run.py tests/harness
git commit -m "Block unverified completion with bounded retries"
```

---

### Task 7: Shadow Measurement And Day 0 A/B CLI

**Files:**
- Create: `src/fablized_sol/eval/__init__.py`
- Create: `src/fablized_sol/eval/manifest.py`
- Create: `src/fablized_sol/eval/day0_ab.py`
- Create: `src/fablized_sol/measure/shadow.py`
- Create: `eval/tasks.example.json`
- Create: `eval/PREREGISTRATION.md`
- Create: `eval/fixtures/python_logic/calc.py`
- Create: `eval/fixtures/python_logic/test_calc.py`
- Test: `tests/measure/test_shadow.py`
- Test: `tests/eval/test_manifest.py`
- Test: `tests/eval/test_day0_ab.py`

**Interfaces:**
- Consumes: holdout, router, workspace tools, and bounded runner.
- Produces: `TaskManifest.load(path: Path) -> TaskManifest`.
- Produces: `ShadowWriter.append(event: ShadowEvent) -> None`.
- Produces: `run_evaluation(options: EvalOptions) -> int`.
- Produces CLI `fablized-sol-eval --tasks PATH --output-dir PATH --run-id ID [--dry-run]`.

- [ ] **Step 1: Write failing manifest, shadow, and CLI tests**

```python
def test_manifest_rejects_shell_string_for_verification(tmp_path: Path) -> None:
    path = write_manifest(tmp_path, verify_argv="pytest -q")
    with pytest.raises(ManifestParseError):
        TaskManifest.load(path)


def test_shadow_event_keeps_arm_out_of_instruction_payload(tmp_path: Path) -> None:
    writer = ShadowWriter(tmp_path / "events.jsonl")
    writer.append(RunStarted(session_id=SessionId("s1"), arm=HoldoutArm.OFF, model="gpt-5.5"))
    raw = (tmp_path / "events.jsonl").read_text(encoding="utf-8")
    assert '"arm":"off"' in raw
    assert "instructions" not in raw


def test_dry_run_emits_two_models_without_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = runner.invoke(app, [
        "--tasks", str(example_manifest(tmp_path)),
        "--output-dir", str(tmp_path / "out"),
        "--run-id", "day0-test",
        "--dry-run",
    ])
    assert result.exit_code == 0
    rows = read_jsonl(tmp_path / "out" / "day0-test" / "events.jsonl")
    assert {row["model"] for row in rows if row["event"] == "run_planned"} == {
        "gpt-5.6-sol", "gpt-5.5"
    }
```

- [ ] **Step 2: Run focused tests and confirm red**

Run: `uv run pytest tests/measure/test_shadow.py tests/eval -v`

Expected: manifest, shadow, and CLI modules do not exist.

- [ ] **Step 3: Implement boundary schemas**

Use frozen Pydantic models:

```python
class TaskSpec(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    prompt: str = Field(min_length=1)
    fixture: Path
    verify_argv: tuple[str, ...] = Field(min_length=1)

class TaskManifest(BaseModel):
    model_config = ConfigDict(frozen=True)
    tasks: tuple[TaskSpec, ...] = Field(min_length=1)

class EvalOptions(BaseModel):
    model_config = ConfigDict(frozen=True)
    tasks: Path
    output_dir: Path
    run_id: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    models: tuple[str, str]
    max_gate_retries: int = Field(ge=0, le=5)
    dry_run: bool
```

`load` reads UTF-8 JSON and wraps file, JSON, and Pydantic errors in
`ManifestParseError`. Reject duplicate task IDs and non-directory fixture paths.
Fixture directories are read-only inputs. Add a deterministic fixture whose
`calc.py` subtracts in `add(left, right)` and whose `test_calc.py` expects
`add(2, 3) == 5`. The example manifest prompts the model to diagnose and fix the
failure and uses
`verify_argv: ["uv", "run", "--with", "pytest", "pytest", "-q"]`.
Resolve relative fixture paths against the manifest file's parent directory,
not the caller's current working directory.

- [ ] **Step 4: Implement the separate shadow stream**

Define discriminated `RunPlanned`, `RunStarted`, and `RunFinished` schemas. `RunFinished` includes `status`, `wall_time_seconds`, `tool_calls`, `failed_verifications`, `gate_blocks`, `input_tokens`, `output_tokens`, `final_defect_found: bool | None`, and `error_type: str | None`. It must not include prompts, instructions, pack text, or model output. Append one JSON line under a local lock.

Write `eval/PREREGISTRATION.md` before any live run. Declare
`final_defect_found` as the primary quality outcome, with wall time, tool calls,
failed verification count, gate blocks, and input/output tokens as cost
guardrails. Compare ON/OFF within each model and Sol/baseline within the same
arm, include exhausted/error/abandoned runs, and forbid claims based only on a
50-session count without effect size and uncertainty. Keep this document out of
model instructions.

- [ ] **Step 5: Implement dry-run and sequential live execution**

Typer options:

```python
def evaluate(
    tasks: Annotated[Path, typer.Option(exists=True, dir_okay=False)],
    output_dir: Annotated[Path, typer.Option()],
    run_id: Annotated[str, typer.Option()],
    sol_model: Annotated[str, typer.Option()] = "gpt-5.6-sol",
    baseline_model: Annotated[str, typer.Option()] = "gpt-5.5",
    max_gate_retries: Annotated[int, typer.Option(min=0, max=5)] = 2,
    dry_run: Annotated[bool, typer.Option()] = False,
) -> None:
    """Run a paired model evaluation; the CLI signature is the option contract."""
    options = EvalOptions(
        tasks=tasks,
        output_dir=output_dir,
        run_id=run_id,
        models=(sol_model, baseline_model),
        max_gate_retries=max_gate_retries,
        dry_run=dry_run,
    )
    exit_code = anyio.run(run_evaluation, options)
    if exit_code != 0:
        raise typer.Exit(exit_code)
```

Set `run_root = output_dir / run_id` and fail before writing if it already
exists; this prevents repeated invocations from appending into a prior sample.
Derive a paired assignment key from `sha256(f"{run_id}:{task.id}")` so both
models receive the same ON/OFF arm. Derive a unique session ID from
`sha256(f"{run_id}:{task.id}:{model}")`. Write `RunPlanned` for every task/model
pair. Dry-run stops there with exit 0. Live mode requires `OPENAI_API_KEY` and
copies each fixture into `run_root / "workspaces" / session_id` before running,
so Sol and baseline never observe each other's mutations. Create one
`run_root / "ledgers" / f"{session_id}.jsonl"` per run. Build instructions once
and append its `ClassifyEvent` to that ledger before the first attempt, then
construct tools/registry/context/agent, run sequentially, and record
completed/exhausted/error status. Catch broad exceptions only at this top-level
CLI boundary with `# noqa: BROAD_EXCEPT_OK`, write `error_type`, then return a
non-zero exit code after all planned runs are recorded.

Create `app = typer.Typer(no_args_is_help=True)` and register `evaluate` as the
default command. Define `main() -> None` as `app()` so the console-script target
is concrete. `run_evaluation(options: EvalOptions) -> int` owns I/O and live
execution; `evaluate` only parses options and translates its exit code.

- [ ] **Step 6: Verify green and commit**

Run: `uv run pytest tests/measure/test_shadow.py tests/eval -v`

Run: `uv run fablized-sol-eval --tasks eval/tasks.example.json --output-dir /tmp/fablized-sol-dry --run-id day0-smoke --dry-run`

Expected: tests pass; dry-run exits 0 and writes planned events for both models without reading an API key.

```bash
git add src/fablized_sol/eval src/fablized_sol/measure/shadow.py eval tests/eval tests/measure
git commit -m "Add out-of-band Day 0 evaluation runner"
```

---

### Task 8: Distribution Documentation, CI, And Full Verification

**Files:**
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `.github/workflows/ci.yml`
- Modify: `pyproject.toml`
- Test: `tests/test_package_smoke.py`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: a documented package, repeatable quality gate, and build artifacts.

- [ ] **Step 1: Write the failing installed-package smoke test**

```python
def test_console_script_is_registered() -> None:
    script = entry_points(group="console_scripts", name="fablized-sol-eval")
    assert len(script) == 1


def test_package_exports_version() -> None:
    assert fablized_sol.__version__ == "0.1.0"
```

- [ ] **Step 2: Run smoke test and confirm red**

Run: `uv run pytest tests/test_package_smoke.py -v`

Expected: `__version__` is missing or console script metadata is not available in the editable environment.

- [ ] **Step 3: Finish package metadata and operational docs**

Expose `__version__` through `importlib.metadata.version("fablized-sol")`. README sections must include:

1. philosophy and non-goals;
2. Python/uv bootstrap;
3. `uv sync --dev`;
4. dry-run command;
5. live command and limited-preview/API-access caveat;
6. task manifest schema with argv arrays rather than shell strings;
7. ledger versus shadow-stream separation;
8. gate decision table and EXHAUSTED semantics;
9. default quality gate;
10. known limitation for hosted/built-in tool observation.

`AGENTS.md` must contain only repository engineering rules and verification commands; it must not promote experimental packs to always-on model instructions.

- [ ] **Step 4: Add CI**

Create a workflow for pushes and pull requests on Ubuntu with Python 3.12 and pinned `astral-sh/setup-uv`. Run:

```yaml
- run: uv sync --locked --dev
- run: uv run ruff format --check .
- run: uv run ruff check .
- run: uv run basedpyright
- run: uv run pytest --cov=fablized_sol --cov-report=term-missing
- run: uv build
```

Do not add `OPENAI_API_KEY` or run live tests in CI.

- [ ] **Step 5: Run mandatory post-write audits**

Run:

```bash
uv run ruff format .
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest --cov=fablized_sol --cov-report=term-missing
uv build
```

Expected: every command exits 0.

Measure every Python file:

```bash
find src tests -name '*.py' -print0 | xargs -0 -n1 sh -c 'printf "%s " "$0"; awk "NF && !/^[[:space:]]*#/ {n++} END {print n+0}" "$0"'
```

Expected: every reported count is at most 250.

Run the skill audit if its path exists:

```bash
uv run /Users/sionchoi/.codex/plugins/cache/sisyphuslabs/omo/4.16.0/skills/programming/scripts/python/check-no-excuse-rules.py src tests
```

Expected: no violations.

- [ ] **Step 6: Verify dry-run from the built interface**

Run: `uv run fablized-sol-eval --tasks eval/tasks.example.json --output-dir .fablized/smoke --run-id day0-smoke --dry-run`

Expected: exit 0; `events.jsonl` contains exactly two `run_planned` events per example task and no prompt/instruction/output fields.

- [ ] **Step 7: Commit the distribution slice**

```bash
git add README.md AGENTS.md .github pyproject.toml src/fablized_sol/__init__.py tests/test_package_smoke.py
git commit -m "Document and verify the Fablized SOL package"
```

## Release Checkpoint

After Task 8, stop before creating a remote repository, publishing to PyPI, or running billable live evaluations. Report:

- commit list since the design/plan baseline;
- exact quality-gate results;
- dry-run event counts;
- whether `OPENAI_API_KEY` and GPT-5.6 preview access are available without printing secrets;
- remaining release actions requiring the repository owner: GitHub remote visibility/name and PyPI publishing target.

The first billable live A/B run is a separate explicit action because it consumes preview quota and may mutate task workspaces.
