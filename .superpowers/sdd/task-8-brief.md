### Task 8: Run Gate 0, Audit Gate 1, and Publish the RC

**Files:**
- Modify after observed results: `docs/RELEASE_BRIEF_0.9.0RC1.md`
- Generate: `benchmarks/v0.9-loop-replay/gate0.json`
- Generate: `benchmarks/v0.9-loop-replay/audit.json`

**Interfaces:**
- Consumes: the frozen candidate commit and every previous task artifact.
- Produces: immutable free-gate evidence, reviewed GitHub PR, tag `v0.9.0-rc1`, and prerelease.

- [ ] **Step 1: Freeze the candidate and run the complete quality gate**

Run each command separately and retain its exit code and summary in `gate0.json`:

```bash
uv run pytest --cov=src --cov=plugins/super-sol/hooks --cov-report=term-missing --cov-fail-under=90
uv run ruff check .
uv run ruff format --check .
uv run basedpyright
uv build
uv run super-sol-container-audit
git diff --check
```

Expected: all commands exit 0, coverage is at least 90%, and dependency and secret scans report zero
production findings.

- [ ] **Step 2: Run install and latency checks in a fresh CODEX_HOME**

Use the repository's existing clean-room helpers to install, inventory, remove, and reinstall the
candidate. After the clean-room install, run
`uv run super-sol-hook-latency --plugin-root plugins/super-sol --output <fresh>` and retain the
fresh report with the Gate 0 evidence.

Expected: exactly one Super SOL plugin and skill; one hook path per event; absolute p95 below 100 ms;
incremental p95 below 70 ms; no extra API call, model switch, retry, continuation, or spawned agent.

- [ ] **Step 3: Re-run and audit the adversarial gate from the frozen commit**

Run:

```bash
uv run python eval/v09_loop_replay.py --manifest eval/v09_loop_sequences.json --output benchmarks/v0.9-loop-replay/report.json
env -u OPENAI_API_KEY -u CODEX_API_KEY uv run pytest tests/eval/test_v09_loop_replay.py tests/eval/test_codex_hook_compat.py tests/eval/test_codex_hook_runtime.py -q
```

Write `audit.json` with candidate commit, plugin-tree digest, manifest digest, report digest, Codex
version, hook-event inventory, case count, pass count, failure count, and `billable_calls: 0`.

Expected: 12/12 replay cases pass and all digests match the frozen tree.

- [ ] **Step 4: Update the release brief from observed evidence and commit artifacts**

Replace planned result language with exact test count, coverage, latency, package, audit, and replay
values. Keep Gate 2 marked not run.

```bash
git add docs/RELEASE_BRIEF_0.9.0RC1.md benchmarks/v0.9-loop-replay/gate0.json benchmarks/v0.9-loop-replay/audit.json benchmarks/v0.9-loop-replay/report.json
git commit -m "chore: record v0.9 release gate evidence"
```

- [ ] **Step 5: Push the feature branch and open the reviewed pull request**

```bash
git push -u origin feature/v0.9-loop-fuse
gh pr create --base main --head feature/v0.9-loop-fuse --title "Super SOL v0.9 loop fuse" --body-file docs/RELEASE_BRIEF_0.9.0RC1.md
gh pr checks --watch
```

Expected: GitHub CI and container-security checks pass. Address only release-blocking findings; any
behavior change after freeze requires a new RC commit and fresh Gate 0/1 evidence.

- [ ] **Step 6: Merge, tag, and publish the prerelease**

After required checks pass:

```bash
gh pr merge --squash --delete-branch
git fetch origin main --tags
git tag -a v0.9.0-rc1 origin/main -m "Super SOL v0.9.0-rc1"
git push origin v0.9.0-rc1
gh release create v0.9.0-rc1 --prerelease --title "Super SOL v0.9.0-rc1" --notes-file docs/RELEASE_BRIEF_0.9.0RC1.md
```

Expected: `main` contains the reviewed implementation; the immutable tag points to the merged
candidate; GitHub shows a prerelease with honest Gate 0/1 results and Gate 2 explicitly pending.

---

## Plan Completion Criteria

- Every task has its own passing focused tests and atomic commit.
- The full suite, coverage, Ruff, formatting, basedpyright, package, supply-chain, and secret gates pass.
- Codex hook doctor observes all six required events without a model request.
- Twelve adversarial sequences pass with no network or billing activity.
- Normal v0.8 Sol behavior and all non-Sol pass-through fixtures remain unchanged.
- No shipped `Stop` hook, process killer, automatic continuation, retry, replacement agent, or hidden model call exists.
- `v0.9.0-rc1` is published only after reviewed CI passes; `v0.9.0` stable remains gated on the separately approved 32-slot Gate 2.
