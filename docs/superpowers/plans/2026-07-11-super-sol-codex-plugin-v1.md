# Super SOL Codex Plugin v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release Super SOL 0.3.0 as a beginner-friendly, automatic Codex quality harness with no
automatic billable API path, reproducible model/effort benchmarks, and a scanned container supply
chain.

**Architecture:** A repo marketplace packages a stock Codex skill and one standard-library hook
runtime. Hooks classify prompts without a model call, store privacy-minimized evidence under
`PLUGIN_DATA`, deny known unapproved billable paths, and request one verification continuation.
The existing Python harness remains an optional explicit live benchmark and gains typed reasoning
effort plus a billable confirmation gate.

**Tech Stack:** Codex plugin manifest and hooks, Python 3.12 standard library, Pydantic 2,
OpenAI Agents SDK 0.17.4, OpenAI SDK 2.38.0, Typer, pytest, Ruff, basedpyright, Docker Scout.

## Global Constraints

- Use stock Codex only; do not bundle LazyCodex, OMO, wrappers, or automatic subagents.
- The plugin must not import an HTTP or OpenAI client, read `OPENAI_API_KEY`, or start the eval CLI.
- Do not persist prompt text, commands, tool output, model output, environment values, or secrets.
- Allow at most one automatic Stop continuation per turn.
- Keep production and test Python files at or below 250 non-comment, non-blank lines.
- Add every runtime behavior with an observed red-green TDD cycle.
- Keep live evaluation opt-in and require `--confirm-billable`.
- Use digest-pinned multi-platform `python:3.12-alpine` for both verifier images.
- Preserve the historical v0.2.1 benchmark artifact without rewriting its claims.

## File Map

- `.agents/plugins/marketplace.json`: repo marketplace entry for `super-sol`.
- `plugins/super-sol/.codex-plugin/plugin.json`: validation-ready plugin metadata.
- `plugins/super-sol/hooks/hooks.json`: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse,
  and Stop registrations.
- `plugins/super-sol/hooks/super_sol_hook.py`: bounded hook protocol and privacy-minimized state.
- `plugins/super-sol/skills/super-sol/SKILL.md`: concise implicit skill instructions.
- `plugins/super-sol/skills/super-sol/agents/openai.yaml`: skill UI metadata.
- `tests/plugin/conftest.py`: real subprocess driver for the hook executable.
- `tests/plugin/test_prompt_hooks.py`: session, routing, secret, privacy, and malformed-input tests.
- `tests/plugin/test_tool_hooks.py`: billing, evidence, and bounded Stop tests.
- `tests/plugin/test_plugin_contract.py`: marketplace, manifest, hooks, and dependency tests.
- `src/fablized_sol/eval/manifest.py`: typed effort pair and billable confirmation boundary.
- `src/fablized_sol/eval/day0_ab.py`: current defaults, CLI options, effort-aware plan identity.
- `src/fablized_sol/eval/live.py`: carry effort into the SDK executor and terminal events.
- `src/fablized_sol/harness/run.py`: construct `ModelSettings(reasoning=...)`.
- `src/fablized_sol/measure/shadow.py`: persist effort in every event.
- `src/fablized_sol/measure/report*.py`: validate and report model/effort pairs.
- `src/fablized_sol/eval/supply_chain.py`: deterministic Dockerfile policy and local audit CLI.
- `tests/eval/test_supply_chain.py`: pinned-base and command-plan tests.
- `eval/verifier/Dockerfile*`: Alpine multi-platform digest.
- `.github/workflows/container-security.yml`: pinned CI build and critical/high scan gate.
- `security/sbom/*.spdx.json`: generated release SBOM evidence.
- `README.md`, `docs/SUPER_SOL.md`, `docs/DAY7_REVIEW.md`: beginner setup, current models, and
  dated release review.
- `pyproject.toml`, `uv.lock`: version and console entry point.

---

### Task 1: Scaffold the repo plugin and establish failing protocol tests

**Files:**
- Create: `.agents/plugins/marketplace.json`
- Create: `plugins/super-sol/.codex-plugin/plugin.json`
- Create: `plugins/super-sol/hooks/hooks.json`
- Create: `plugins/super-sol/skills/super-sol/SKILL.md`
- Create: `plugins/super-sol/skills/super-sol/agents/openai.yaml`
- Create: `tests/plugin/conftest.py`
- Create: `tests/plugin/test_prompt_hooks.py`
- Create: `tests/plugin/test_tool_hooks.py`
- Create: `tests/plugin/test_plugin_contract.py`

**Interfaces:**
- Consumes: Codex lifecycle JSON with `session_id`, `turn_id`, `hook_event_name`, and event fields.
- Produces: executable `plugins/super-sol/hooks/super_sol_hook.py` contract exercised by a real
  subprocess; plugin version `0.3.0`.

- [ ] **Step 1: Generate only plugin and skill configuration skeletons**

Run the official plugin scaffold with repo-local marketplace output, then the official skill
initializer under the scaffolded `skills/` directory. Replace every generated template marker
before validation.

```bash
python3 ~/.codex/skills/.system/plugin-creator/scripts/create_basic_plugin.py \
  super-sol --path ./plugins --with-skills --with-hooks --with-marketplace \
  --marketplace-path ./.agents/plugins/marketplace.json \
  --marketplace-name super-sol --category Productivity

python3 ~/.codex/skills/.system/skill-creator/scripts/init_skill.py \
  super-sol --path ./plugins/super-sol/skills \
  --interface display_name="Super SOL" \
  --interface short_description="검증까지 챙기는 초보자용 Codex 작업 도우미" \
  --interface default_prompt="Use $super-sol to complete and verify this task in plain language."
```

Expected: both commands exit 0 and create no MCP or app files.

- [ ] **Step 2: Write the failing real-process tests**

The shared driver must execute the eventual hook script, send one JSON object on stdin, set an
isolated `PLUGIN_DATA`, and parse stdout only when non-empty:

```python
@dataclass(frozen=True, slots=True)
class HookResult:
    returncode: int
    stdout: dict[str, JsonValue] | None
    stderr: str


def run_hook(plugin_data: Path, payload: dict[str, JsonValue]) -> HookResult:
    completed = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env={"PLUGIN_DATA": str(plugin_data), "PLUGIN_ROOT": str(PLUGIN_ROOT)},
    )
    output = completed.stdout.strip()
    parsed = _JSON_OBJECT.validate_json(output) if output else None
    return HookResult(completed.returncode, parsed, completed.stderr)
```

Tests must cover: minimal SessionStart context, Korean and English profile routing, API-key blocking
without echo, no prompt persistence, malformed and oversized input, unapproved live/API command
denial, authorized live command requiring `--confirm-billable`, dry-run allowance, mutation without
verification continuation, fresh passing verification allowance, stale verification rejection,
conversation allowance, and one-continuation exhaustion.

- [ ] **Step 3: Run tests and observe the expected red state**

Run: `uv run pytest tests/plugin -q`

Expected: FAIL because `plugins/super-sol/hooks/super_sol_hook.py` does not exist.

- [ ] **Step 4: Commit the red contract**

```bash
git add .agents plugins/super-sol tests/plugin
git commit -m "Test Super SOL Codex plugin contract"
```

Expected: one commit containing configuration plus failing runtime-contract tests, but no hook
runtime implementation.

---

### Task 2: Implement the privacy-minimized automatic hook runtime

**Files:**
- Create: `plugins/super-sol/hooks/super_sol_hook.py`
- Modify: `plugins/super-sol/hooks/hooks.json`
- Modify: `plugins/super-sol/.codex-plugin/plugin.json`
- Modify: `plugins/super-sol/skills/super-sol/SKILL.md`
- Modify: `plugins/super-sol/skills/super-sol/agents/openai.yaml`
- Test: `tests/plugin/test_prompt_hooks.py`
- Test: `tests/plugin/test_tool_hooks.py`

**Interfaces:**
- Consumes: at most 1 MiB of UTF-8 JSON from stdin and `PLUGIN_DATA`/`PLUGIN_ROOT`.
- Produces: `main() -> int`, documented hook JSON, and private state at
  `PLUGIN_DATA/super-sol/v1/<session-hash>/<turn-hash>/`.

- [ ] **Step 1: Implement bounded input, hashing, and atomic private JSON writes**

Use these exact boundaries:

```python
_MAX_INPUT_BYTES = 1_048_576
_SCHEMA_VERSION = 1


def _identifier(value: object) -> str:
    text = value if isinstance(value, str) else "missing"
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def _write_private_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, separators=(",", ":"), sort_keys=True)
    os.replace(temporary, path)
```

Invalid input returns a warning object with `continue: true`. Secret and recognized billable
denials remain fail closed.

- [ ] **Step 2: Implement prompt routing and authorization without storing prompt text**

Use negative billing phrases before positive phrases. Store only:

```json
{"schema_version":1,"profile":"debug","billable_authorized":false}
```

Return `hookSpecificOutput.additionalContext` for non-secret prompts. A likely key matching
`sk-[A-Za-z0-9_-]{20,}` returns `decision: block` and a generic rotation warning.

- [ ] **Step 3: Implement billable-command and evidence hooks**

Recognize command strings only at `tool_input.command`. Deny a non-dry-run eval unless state is
authorized and the command includes `--confirm-billable`. Deny `api.openai.com` unless authorized.
For PostToolUse, create one event file containing booleans and `time.time_ns()`; count a
verification pass only when a recursive structured search finds integer `exit_code == 0`.

- [ ] **Step 4: Implement the bounded Stop gate**

Sort event payloads by `observed_at_ns`. If the latest passing verification is not newer than the
latest mutation, return:

```json
{
  "decision": "block",
  "reason": "변경 사항을 확인할 수 있는 가장 좁은 테스트를 실행하고 결과를 읽어주세요."
}
```

When `stop_hook_active` is true, return `continue: true` plus a short `systemMessage` stating that
verification remains unobserved. Do not write a shared retry counter.

- [ ] **Step 5: Run plugin tests to green**

Run: `uv run pytest tests/plugin -q`

Expected: all plugin tests PASS with no warnings.

- [ ] **Step 6: Validate plugin and skill packaging**

```bash
python3 ~/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/super-sol
python3 ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  plugins/super-sol/skills/super-sol
```

Expected: both validators report success and no generated template marker remains.

- [ ] **Step 7: Commit the working plugin**

```bash
git add plugins/super-sol tests/plugin .agents/plugins/marketplace.json
git commit -m "Build automatic Super SOL Codex plugin"
```

---

### Task 3: Make live evaluation explicitly billable and effort-reproducible

**Files:**
- Modify: `src/fablized_sol/eval/manifest.py`
- Modify: `src/fablized_sol/eval/day0_ab.py`
- Modify: `src/fablized_sol/eval/live.py`
- Modify: `src/fablized_sol/harness/run.py`
- Modify: `src/fablized_sol/measure/shadow.py`
- Modify: `src/fablized_sol/measure/report_events.py`
- Modify: `src/fablized_sol/measure/report_models.py`
- Modify: `src/fablized_sol/measure/report.py`
- Modify: `src/fablized_sol/measure/report_cli.py`
- Test: `tests/eval/test_manifest.py`
- Test: `tests/eval/test_day0_ab.py`
- Test: `tests/eval/test_live_eval.py`
- Test: `tests/harness/test_sdk_compatibility.py`
- Test: `tests/measure/test_day3_report.py`

**Interfaces:**
- Produces: `ReasoningEffort`, `ComparisonEfforts`, `EvalOptions.efforts`,
  `EvalOptions.confirm_billable`, `PlannedRun.reasoning_effort`, and required
  `reasoning_effort` on shadow events.
- Consumes: OpenAI SDK effort values `none|minimal|low|medium|high|xhigh`.

- [ ] **Step 1: Add failing tests for the new CLI and event contract**

Required assertions:

```python
assert result.exit_code != 0
assert "--confirm-billable" in result.output

assert {(row["model"], row["reasoning_effort"]) for row in planned} == {
    ("gpt-5.6-terra", "medium"),
    ("gpt-5.6-sol", "medium"),
}
```

The offline SDK model must capture `model_settings.reasoning` and assert its effort. Report tests
must reject start/finish effort disagreement.

- [ ] **Step 2: Run the focused tests and observe red**

Run:

```bash
uv run pytest tests/eval/test_manifest.py tests/eval/test_day0_ab.py \
  tests/eval/test_live_eval.py tests/harness/test_sdk_compatibility.py \
  tests/measure/test_day3_report.py -q
```

Expected: FAIL because effort and billable-confirmation fields do not exist.

- [ ] **Step 3: Add typed effort and confirmation boundaries**

Define:

```python
type ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]
type ComparisonEfforts = tuple[ReasoningEffort, ReasoningEffort]
```

`EvalOptions.require_live_verification_image` must raise `billable_confirmation_required` before
accepting live options when `confirm_billable` is false. Dry-run ignores the confirmation flag.

- [ ] **Step 4: Carry effort through planning, execution, events, and reports**

Zip models and efforts as fixed role pairs before any crossover-order reversal. Include effort in
session hashing. Add `model_settings=ModelSettings(reasoning={"effort": self.reasoning_effort})`
to `Agent`. Require plan/start/finish `(model, arm, reasoning_effort)` equality and expose effort on
cells and report role metadata.

- [ ] **Step 5: Run focused tests to green and commit**

```bash
uv run pytest tests/eval tests/harness/test_sdk_compatibility.py \
  tests/measure/test_day3_report.py -q
git add src/fablized_sol tests
git commit -m "Record benchmark reasoning effort"
```

Expected: focused tests PASS and every new event includes an effort.

---

### Task 4: Replace the vulnerable base and add a reproducible container audit

**Files:**
- Modify: `eval/verifier/Dockerfile`
- Modify: `eval/verifier/Dockerfile.grader`
- Create: `src/fablized_sol/eval/supply_chain.py`
- Create: `tests/eval/test_supply_chain.py`
- Create: `.github/workflows/container-security.yml`
- Create: `security/sbom/.gitkeep`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `validate_pinned_base(path: Path) -> str`,
  `build_audit_commands(repo_root: Path, sbom_dir: Path) -> tuple[tuple[str, ...], ...]`, and
  console command `super-sol-container-audit`.
- Consumes: Docker Engine plus Docker Scout only; no network model call.

- [ ] **Step 1: Write failing policy and command-plan tests**

Test that tag-only and non-sha bases raise `SupplyChainPolicyError`, while the exact base
`python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df`
passes. Assert the audit plan builds both Dockerfiles, scans `critical,high` with an exit code, and
writes two SPDX JSON files.

- [ ] **Step 2: Run the focused test and observe red**

Run: `uv run pytest tests/eval/test_supply_chain.py -q`

Expected: FAIL because `fablized_sol.eval.supply_chain` does not exist.

- [ ] **Step 3: Implement policy and audit runner**

Use `subprocess.run(argv, cwd=repo_root, check=False)` with argument arrays. Stop on the first
nonzero command and return its code. The command order is build verifier, build grader, scan both,
then write both SBOMs. Create the SBOM directory before commands run.

- [ ] **Step 4: Replace both Docker bases and add pinned CI actions**

Both Dockerfiles use the multi-platform digest recorded above. CI checks out the repository,
builds both images, invokes Docker Scout with critical/high failure, and uploads SPDX artifacts.
Every GitHub Action `uses:` value is pinned to a full commit SHA and annotated with its release tag.

- [ ] **Step 5: Run policy tests and commit**

```bash
uv run pytest tests/eval/test_supply_chain.py tests/harness/test_container_verification.py -q
git add eval/verifier src/fablized_sol/eval/supply_chain.py tests/eval/test_supply_chain.py \
  .github/workflows/container-security.yml security/sbom pyproject.toml uv.lock
git commit -m "Harden verifier container supply chain"
```

Expected: focused tests PASS.

---

### Task 5: Update beginner documentation and current model guidance

**Files:**
- Modify: `README.md`
- Modify: `docs/SUPER_SOL.md`
- Modify: `docs/DAY7_REVIEW.md`
- Modify: `eval/verifier/README.md`
- Modify: `eval/PREREGISTRATION.md`
- Modify: `pyproject.toml`
- Test: `tests/test_package_smoke.py`

**Interfaces:**
- Consumes: OpenAI's 2026-07-09 GPT-5.6 general-availability announcement.
- Produces: beginner installation flow, dated model table, explicit live command, container audit
  instructions, and package/plugin version `0.3.0`.

- [ ] **Step 1: Add failing package/document contract assertions**

Assert package metadata is `0.3.0`, README names `gpt-5.6-terra` as default, removes the limited
preview claim, documents `--confirm-billable`, and links the official GA announcement.

- [ ] **Step 2: Run the contract test and observe red**

Run: `uv run pytest tests/test_package_smoke.py -q`

Expected: FAIL against 0.2.1 and stale preview copy.

- [ ] **Step 3: Rewrite the entry path for beginners**

Lead README with two choices: install the free automatic Codex plugin, or explicitly run the
optional benchmark. State the one-time hook trust step, no API-key requirement for plugin use,
and the exact limitation that hooks are not an OS security boundary.

- [ ] **Step 4: Update current model and release evidence**

Date guidance 2026-07-11. Explain Terra/Sol/Luna, medium defaults, max/ultra product guidance, and
why the API harness accepts only pinned-SDK efforts. Preserve v0.2.1 pilot numbers as historical.

- [ ] **Step 5: Run contract test and commit**

```bash
uv lock
uv run pytest tests/test_package_smoke.py -q
git add README.md docs eval/PREREGISTRATION.md pyproject.toml uv.lock tests/test_package_smoke.py
git commit -m "Document Super SOL plugin release"
```

Expected: package/document contract PASS.

---

### Task 6: Verify the installed surfaces, scan images, and close five reviews

**Files:**
- Generate: `security/sbom/verifier.spdx.json`
- Generate: `security/sbom/grader.spdx.json`
- Create: `docs/RELEASE_BRIEF_0.3.0.md`
- Modify: any task-owned file required by an observed failure or actionable review finding.

**Interfaces:**
- Consumes: finished plugin, harness, images, test suite, and five independent review reports.
- Produces: observed release evidence and a commit-ready stability brief.

- [ ] **Step 1: Run static and unit quality gates**

```bash
uv sync --locked --dev
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest --cov=fablized_sol --cov-report=term-missing
uv build
find src tests -name '*.py' -print0 | xargs -0 -n1 sh -c \
  'awk "NF && !/^[[:space:]]*#/ {n++} END {if (n > 250) {print FILENAME, n; exit 1}}" "$0"'
```

Expected: every command exits 0; pytest reports no skipped live calls and no warnings.

- [ ] **Step 2: Manually drive the plugin protocol**

Pipe real JSON through the hook executable in this sequence: SessionStart, Korean action prompt,
PostToolUse apply_patch, Stop, PostToolUse successful pytest, Stop. Also send an API-key prompt and
an unapproved live command.

Expected: context, one verification continuation, then allowance; secret and live command are
blocked without their sensitive input being echoed or stored.

- [ ] **Step 3: Drive CLI happy and failure paths**

```bash
uv run super-sol-eval --help
uv run super-sol-eval --tasks eval/tasks.example.json \
  --output-dir .fablized/smoke --run-id v030-smoke --dry-run
uv run super-sol-eval --tasks eval/tasks.example.json \
  --output-dir .fablized/live --run-id must-refuse
```

Expected: help exits 0; dry-run writes Terra/Sol medium plans; live command exits nonzero and names
`--confirm-billable` before any model call.

- [ ] **Step 4: Build, scan, SBOM, and run container controls**

```bash
uv run super-sol-container-audit --repo-root . --sbom-dir security/sbom
uv run pytest tests/harness/test_container_verification.py \
  tests/harness/test_container_runtime.py tests/eval/test_grader.py -q
```

Expected: both images build, Docker Scout reports zero critical/high vulnerabilities, both SPDX
files exist and parse as JSON, and container controls PASS.

- [ ] **Step 5: Run five independent stock Codex reviews**

Dispatch read-only reviewers with non-overlapping scopes: code quality, security/privacy, beginner
UX, benchmark methodology/reproducibility, and release/operations. Each must inspect the finished
diff and return PASS or actionable findings with file references. Fix every substantiated finding
using a new failing test when behavior changes, then rerun the affected gate.

- [ ] **Step 6: Write release brief and final commit**

`docs/RELEASE_BRIEF_0.3.0.md` records commit hashes, exact observed commands, test totals, plugin and
skill validator results, image names/digests, Scout severity counts, SBOM paths, five review
outcomes, known hook interception limits, and whether public release is GO or NO-GO.

```bash
git add -A
git diff --cached --check
git commit -m "Release Super SOL 0.3.0 Codex plugin"
git status --short --branch
```

Expected: final commit succeeds and the worktree is clean.
