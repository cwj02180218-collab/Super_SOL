# Fablized SOL

Fablized SOL is an evidence-gated procedure harness for paired GPT-5.6 Sol
evaluations. It measures whether narrowly routed procedures improve outcomes; it
does not claim to increase a model's capability ceiling.

## Philosophy And Non-goals

The harness judges observed tool execution rather than claims in generated text.
Deterministic code owns enforcement, experimental guidance is routed only when a
task signal matches, and holdout labels stay outside model-visible context.

This v0.1 slice does not automatically grade defects, inspect hidden reasoning,
support distributed ledgers, treat arbitrary remote tools as evidence, or infer
statistical lift from an initial small sample.

## Experimental Packs Versus Always-on Rules

The investigation, grounding, and multi-story text packs are experimental. They
are selected by prompt signals only for harness-ON sessions. A holdout/OFF
session receives the base workspace and verification instructions byte-for-byte,
without pack, mode, risk, or arm labels. Do not copy these packs into
`AGENTS.md`, system prompts, or other always-on instructions before holdout
evidence supports promotion.

Runtime correctness boundaries are always on: manifest parsing is strict,
workspace tools are confined to the copied task fixture, exposed local tools
must be registered by kind, and only typed tool results become ledger evidence.
The completion evidence gate itself is enabled only for the ON arm so the OFF
arm remains a valid experimental control.

## Bootstrap

Install [uv](https://docs.astral.sh/uv/), then provision Python 3.12 and the
locked development environment:

```bash
uv python install 3.12
uv sync --dev
```

## Task Manifest

The CLI accepts a strict JSON manifest with one or more tasks:

```json
{
  "tasks": [
    {
      "id": "python-logic",
      "prompt": "Diagnose and fix the failing test, then verify the result.",
      "fixture": "fixtures/python_logic",
      "verify_argv": ["uv", "run", "pytest", "-q"]
    }
  ]
}
```

Each task has a non-empty `id`, `prompt`, fixture directory, and
`verify_argv`. Relative fixtures resolve from the manifest directory. Verification
commands are argument arrays, never shell strings: each array element is passed
as one process argument without shell interpolation.

## Dry Run

Validate the manifest, deterministic model pairing, holdout assignment, and
output path without API credentials or model calls:

```bash
uv run fablized-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/smoke \
  --run-id day0-smoke \
  --dry-run
```

The command creates
`.fablized/smoke/day0-smoke/events.jsonl` with two `run_planned` events per
task, one for each configured model. Run IDs cannot be reused within the same
output directory.

## Live Paired Evaluation

Live execution is billable and may modify the copied task workspaces. It
requires `OPENAI_API_KEY` and access to both configured models:

```bash
OPENAI_API_KEY=... uv run fablized-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/live \
  --run-id day0-live
```

The defaults are `gpt-5.6-sol` and `gpt-5.5`, with two gate correction retries.
GPT-5.6 Sol is a limited preview, so API access is not implied by installing this
package. Use `--sol-model`, `--baseline-model`, and `--max-gate-retries` to
override the defaults. A live run should be an explicit quota and workspace
decision, not part of routine verification or CI.

## Ledger And Shadow Stream

These append-only JSONL streams have separate purposes and trust boundaries:

| Stream | Location | Contents | Consumer |
| --- | --- | --- | --- |
| Session ledger | `<run>/ledgers/<session-id>.jsonl` | Classification, observed local tool calls, rejected evidence, and gate fires | Deterministic evidence gate |
| Shadow stream | `<run>/events.jsonl` | Arm/model assignment, lifecycle status, timing, usage, and aggregate cost counts | Out-of-band experiment analysis |

The shadow stream is never injected into model instructions. It does not store
prompts, routed instructions, pack text, or model output. The ledger records
enforcement evidence, while the shadow stream records experimental labels and
outcomes; they must not be merged.

## Gate Decisions

The v0.1 policy evaluates chronological ledger state. A successful verification
must be newer than the most recent mutation.

| Condition | Decision |
| --- | --- |
| Holdout/OFF arm | `ALLOW` |
| No observed mutation | `ALLOW` |
| Fresh successful verification after the latest mutation | `ALLOW` |
| QUICK task | `ALLOW` |
| NORMAL task | `ALLOW` in v0.1 |
| DEEP task with documentation-only mutations | `ALLOW` |
| DEEP task with code mutation and no fresh successful verification | `BLOCK` |
| The same DEEP task reaches its gate retry limit | `EXHAUSTED` |

`EXHAUSTED` is a terminal non-success outcome containing the last blocked output
and gate reason. It never converts unsupported completion into success and
prevents an unbounded correction loop.

## Default Quality Gate

The default gate is non-live and requires no API key:

```bash
uv sync --locked --dev
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest --cov=fablized_sol --cov-report=term-missing
uv build
```

## Known Limitations

Hosted tools and SDK built-ins that bypass the local function-tool lifecycle
hooks cannot be observed as mutation or verification evidence in v0.1. They
remain outside the enforcement boundary and must not be registered as though
the harness can observe them. Ledger locking is process-local, every session
must own a separate ledger, and final defect grading remains out of band.
