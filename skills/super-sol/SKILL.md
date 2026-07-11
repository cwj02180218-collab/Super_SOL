---
name: super-sol
description: Evidence-gated paired evaluation harness for coding agents. Use when the user wants to run or interpret Super SOL evaluations — paired GPT-5.5 vs GPT-5.6 Sol crossover runs, dry-run smokes, live billable pilots, or aggregate reports — or says "super sol", "paired eval", "crossover eval", "baseline-first routing", "evidence gate", "run the benchmark".
---

# Super SOL — evidence-gated paired evaluation

> Principle: the harness judges observed tool execution, never claims in
> generated text. Everything fails closed: missing credentials, missing
> digest-pinned images, or parser errors are evaluation errors, not success.
> Published numbers below the preregistered threshold are engineering
> evidence, not leaderboard claims. Do not soften either rule when relaying
> results.

## 0. First run — bootstrap once

Check whether the environment is provisioned:

```bash
test -d "${CLAUDE_PLUGIN_ROOT}/.venv" && echo ready || echo bootstrap-needed
```

If bootstrap is needed, run the automated setup (installs Python 3.12 via uv,
syncs locked deps, and proves the CLI with an offline dry-run smoke — no API
key, no Docker, no billing):

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh"
```

If `uv` is missing the script exits with install instructions; relay them and
stop — do not install uv globally without the user's confirmation.

## 1. Dry-run evaluation (default, free)

Always start with a dry run. It validates the manifest, deterministic model
pairing, holdout assignment, and output paths without any API call:

```bash
cd "${CLAUDE_PLUGIN_ROOT}"
uv run super-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/dryrun \
  --run-id <fresh-run-id> \
  --dry-run
```

Rules:
- Run IDs cannot be reused within an output directory — generate a fresh one
  (e.g. timestamp-suffixed).
- To evaluate the user's own tasks, write a strict manifest first: each task
  needs a non-empty `id`, `prompt`, `fixture` directory, and `verify_argv` as
  an argument array (never a shell string). Fixtures with symlinks are
  rejected. Use `eval/tasks.example.json` as the template.

## 2. Live evaluation (billable — explicit confirmation required)

A live run calls the OpenAI API for both models and executes verification in
Docker. Before running, ALL of the following must hold, and you must confirm
with the user that they accept the cost — never start a live run implicitly:

1. `OPENAI_API_KEY` is set in the user's shell (never echo or persist it).
2. `VERIFICATION_IMAGE` (and `GRADER_IMAGE` for out-of-band grading) are
   complete `sha256`-digest-pinned references already present locally — pulls
   are disabled.
3. A working Docker runtime.
4. The user has access to both configured models (GPT-5.6 Sol is a limited
   preview; installation does not imply access).

```bash
cd "${CLAUDE_PLUGIN_ROOT}"
uv run super-sol-eval \
  --tasks <manifest.json> \
  --output-dir .fablized/live \
  --run-id <fresh-run-id> \
  --verification-image "$VERIFICATION_IMAGE"
```

Defaults: baseline `gpt-5.5`, reference `gpt-5.6-sol`, two gate retries.
Override with `--baseline-model`, `--sol-model`, `--max-gate-retries`.
If credentials or images are missing the run fails closed — report the exact
error; do not work around it by disabling isolation.

## 3. Reports and interpretation

Aggregate a run into a machine-readable report:

```bash
cd "${CLAUDE_PLUGIN_ROOT}"
uv run super-sol-report --run-dir <output-dir>/<run-id>
```

When summarizing a report, keep the evidence boundary:

- Quote per-cell quality rate, token volume, and paired effects with their
  confidence intervals. Wide CIs that cross zero mean "not established".
- The session ledger (enforcement evidence) and the shadow stream
  (experimental labels/outcomes) are separate trust boundaries — never merge
  them into one score.
- Fable-parity, general model-superiority, or production-routing claims
  require the preregistered promotion threshold (50+ crossover task groups,
  unpublished versioned grader pack, frozen image digests, external defect
  labels, paired effect sizes, billed-cost accounting, preregistered rerun).
  Below that, describe results as pilot/engineering evidence.

## 4. Troubleshooting

- `uv: command not found` — relay the install hint from `scripts/setup.sh`;
  ask before installing anything globally.
- Run-ID reuse error — pick a fresh `--run-id`; existing runs are immutable.
- Docker/image errors on live runs — expected fail-closed behavior; the image
  must exist locally with an immutable digest and contain every dependency
  named by `verify_argv`.
- Hosted or SDK built-in tools bypass the local lifecycle hooks and cannot be
  evidence — do not register them as observable tools.
