# Super SOL Public Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the current validated harness and preserved history as the public `cuj0218/Super-SOL` repository and GitHub release `v0.2.0`, including an honest Day 7 decision.

**Architecture:** Keep the stable `fablized_sol` import package and add Super SOL distribution and CLI branding at the packaging boundary. Publish only aggregate benchmark evidence, then use non-live CI and immutable action pins to validate every commit without API credentials.

**Tech Stack:** Python 3.12, uv, Hatchling, Typer, pytest, Ruff, Basedpyright, GitHub Actions, GitHub CLI.

## Global Constraints

- Preserve the complete locally available Git history.
- Never commit or print `.env`, API credentials, live workspaces, ledgers, or raw model output.
- Keep `fablized-sol-eval` and `fablized-sol-report` working in version `0.2.0`.
- Publish `super-sol-eval` and `super-sol-report` as the primary commands.
- CI is offline with respect to OpenAI and must never run a billable evaluation.
- Public evidence must state that four tasks cannot establish Fable parity or general model uplift.
- GitHub Actions must be pinned by immutable commit SHA.

---

### Task 1: Super SOL package surface

**Files:**
- Modify: `tests/test_package_smoke.py`
- Modify: `pyproject.toml`
- Modify: `src/fablized_sol/__init__.py`
- Modify: `uv.lock`

**Interfaces:**
- Produces distribution `super-sol-harness==0.2.0`.
- Produces primary commands `super-sol-eval` and `super-sol-report`.
- Preserves compatibility commands `fablized-sol-eval` and `fablized-sol-report`.

- [ ] **Step 1: Write failing packaging tests**

Add tests that select all four console scripts from installed metadata, assert
`fablized_sol.__version__ == "0.2.0"`, and assert the project metadata name is
`super-sol-harness`.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_package_smoke.py -q`

Expected: failures because only the two legacy commands exist and the installed
version is `0.1.0` under distribution `fablized-sol`.

- [ ] **Step 3: Implement the packaging boundary**

Set project name to `super-sol-harness`, version to `0.2.0`, description to
`Evidence-gated coding-agent harness with reproducible model comparisons`, add
the two primary scripts, retain the two legacy scripts, and update the exported
version fallback only if the package currently hard-codes it.

- [ ] **Step 4: Refresh and verify metadata**

Run: `uv lock && uv sync --locked --dev && uv run pytest tests/test_package_smoke.py -q`

Expected: package smoke tests pass and the lock contains
`name = "super-sol-harness"`.

- [ ] **Step 5: Commit**

Commit message: `Publish Super SOL package surface`.

### Task 2: Public evidence and Day 7 decision

**Files:**
- Create: `benchmarks/day3-contract-v2/report.json`
- Create: `benchmarks/day3-contract-v2/README.md`
- Create: `docs/DAY7_REVIEW.md`
- Modify: `README.md`
- Modify: `docs/SUPER_SOL.md`
- Modify: `pyproject.toml`
- Modify: `tests/test_package_smoke.py`

**Interfaces:**
- Publishes aggregate evidence only.
- Adds `benchmarks`, `LICENSE`, `NOTICE`, `SECURITY.md`, and `CONTRIBUTING.md` to the source distribution allowlist in later tasks.

- [ ] **Step 1: Write the failing source-distribution allowlist test**

Extend `test_sdist_uses_an_explicit_source_allowlist` to require
`/benchmarks`, `/LICENSE`, `/NOTICE`, `/SECURITY.md`, and `/CONTRIBUTING.md`.

- [ ] **Step 2: Verify RED**

Run: `uv run pytest tests/test_package_smoke.py::test_sdist_uses_an_explicit_source_allowlist -q`

Expected: failure showing the five missing public release roots.

- [ ] **Step 3: Publish aggregate pilot evidence**

Copy the final report values from
`.fablized/live/day3-live-sol-contract-v2/report.json` into the committed report.
The companion README must state 16/16 completion and grader success, model token
totals `20,932` and `24,096`, lazy savings `11.2%` to `14.9%`, and the four-task
claim limitation.

- [ ] **Step 4: Write the Day 7 decision**

Document separate decisions: open-source release `PASS`; Fable-parity and broad
benchmark promotion `HOLD`. State the promotion requirements of 50 completed
crossover task groups, unpublished grader tests, frozen digests, external
labels, and paired uncertainty supporting the intended claim.

- [ ] **Step 5: Rebrand the public README**

Lead with Super SOL, primary CLI names, security boundaries, quick-start dry
run, reproducible live-run prerequisites, aggregate evidence, Day 7 link, and
compatibility aliases. Keep the existing detailed operational documentation.

- [ ] **Step 6: Update the source allowlist and verify GREEN**

Run: `uv run pytest tests/test_package_smoke.py -q`

Expected: source-distribution allowlist and packaging surface tests pass.

- [ ] **Step 7: Commit**

Commit message: `Document Super SOL Day 7 evidence`.

### Task 3: License, contributor guidance, and CI hardening

**Files:**
- Create: `LICENSE`
- Create: `NOTICE`
- Create: `SECURITY.md`
- Create: `CONTRIBUTING.md`
- Modify: `.gitignore`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- CI runs only `uv sync --locked --dev`, Ruff format/check, Basedpyright, pytest with coverage, and `uv build`.
- CI receives no OpenAI or Docker secrets.

- [ ] **Step 1: Verify upstream license terms**

Read the licenses from `cuj0218/GPT.C` and `fivetaku/fablize`. Use MIT only if
both permit it; otherwise preserve the stricter required notice.

- [ ] **Step 2: Add release policies**

Add MIT license text, attribution notice, disclosure instructions that forbid
publicly posting live secrets, and contribution rules requiring non-live tests
and preservation of verifier/grader isolation.

- [ ] **Step 3: Harden ignored local state**

Add `.DS_Store` without changing the existing environment and runtime-output
exclusions.

- [ ] **Step 4: Pin CI actions and keep CI non-live**

Resolve immutable commit SHAs from the official `actions/checkout` and
`astral-sh/setup-uv` repositories. Use those SHAs in the existing workflow and
verify no secret or live-evaluation step is present.

- [ ] **Step 5: Verify repository policy files**

Run: `uv run ruff format --check . && uv run ruff check . && uv run basedpyright && uv run pytest -q && uv build`

Expected: every command exits zero and the distribution archives are named for
`super-sol-harness` version `0.2.0`.

- [ ] **Step 6: Commit**

Commit message: `Harden Super SOL public release`.

### Task 4: Release-candidate QA and review

**Files:**
- Inspect: built wheel and source archive
- Inspect: repository diff and tracked file list

**Interfaces:**
- Produces verified release assets under `dist/`.

- [ ] **Step 1: Run primary and compatibility CLI smoke tests**

Run `--help` for all four commands and perform a crossover dry run with
`super-sol-eval` against `eval/tasks.example.json`.

Expected: all help commands exit zero and the dry run emits 16 planned sessions
without an API key.

- [ ] **Step 2: Inspect build contents**

List wheel and sdist members. Assert they include package sources, docs,
benchmarks, license, notice, security and contribution files, and exclude
`.env`, `.fablized`, `.DS_Store`, coverage, caches, and live evidence.

- [ ] **Step 3: Run five independent reviews**

Require PASS from goal, QA, code-quality, security, and repository-context
review lanes. Fix every blocker and rerun affected lanes.

- [ ] **Step 4: Commit any review corrections**

Use one atomic commit per corrected concern; do not fold unrelated review fixes
together.

### Task 5: GitHub repository and release deployment

**Files:**
- External: GitHub repository `cuj0218/Super-SOL`
- External: GitHub release `v0.2.0`

**Interfaces:**
- Public repository default branch is `main`.
- Release assets are the verified wheel and source archive from Task 4.

- [ ] **Step 1: Create the public repository**

Use GitHub CLI without auto-initializing files. Set the description to
`Evidence-gated coding-agent harness with reproducible GPT-5.5 and GPT-5.6 Sol comparisons`.

- [ ] **Step 2: Preserve and push history**

Add a separate `super-sol` remote, push local `main` with tracking disabled for
the existing `origin`, and verify the remote head equals local `HEAD`.

- [ ] **Step 3: Configure repository metadata**

Set topics `ai-agents`, `coding-agents`, `benchmark`, `openai`, `gpt-5`,
`evaluation`, and `python`. Confirm public visibility and default branch.

- [ ] **Step 4: Observe CI**

Wait for the pushed workflow run to complete. A missing, cancelled, or failed
run blocks the release.

- [ ] **Step 5: Publish release `v0.2.0`**

Create release notes that state the Day 7 split decision and attach only the
verified wheel and source archive. Do not attach local benchmark workspaces or
environment files.

- [ ] **Step 6: Verify the public surface**

Open repository and release metadata through GitHub, confirm asset names and
checksums, and verify the release tag points to local `HEAD`.
