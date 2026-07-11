# Super SOL

[![CI](https://github.com/cuj0218/Super-SOL/actions/workflows/ci.yml/badge.svg)](https://github.com/cuj0218/Super-SOL/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776AB)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Super SOL is an evidence-gated coding-agent harness for GPT-5.5, with GPT-5.6
Sol as a controlled same-adapter reference comparator and GPT.C plus Codex CLI
as a separate operational reference. It measures whether narrowly routed
procedures improve observable outcomes; it does not claim to increase a model's
capability ceiling.

## Why Super SOL

This repository carries a Super SOL profile that merges the useful GPT.C Codex
wrapper framing with this harness's stricter evidence boundary. Super SOL is the
measured product surface and GPT.C remains the Codex operational reference
surface. Dry-run and live shadow streams include
the profile name and version on every planned run so results can be traced back
without exposing measurement labels to the model.

See [docs/SUPER_SOL.md](docs/SUPER_SOL.md) for the adopted, parked, and rejected
GPT.C decisions.

The Day 1-3 validation path adds a same-task ON/OFF crossover, verifier-private
tests, and a report that measures quality, token volume, time, tool activity,
and GPT-5.5-first lazy escalation. See
[docs/DAY3_VALIDATION.md](docs/DAY3_VALIDATION.md).

The final contract-v2 pilot completed and passed all 16 model/arm sessions. On
the four pilot tasks, GPT-5.5-first routing used 11.2% to 14.9% fewer tokens than
always using the reference model. Both models scored 100%, so this result is
evidence for harness plumbing and a routing hypothesis, not Fable parity or
model superiority. See the [published aggregate report](benchmarks/day3-contract-v2/)
and [Day 7 review](docs/DAY7_REVIEW.md).

## Philosophy And Non-goals

The harness judges observed tool execution rather than claims in generated text.
Deterministic code owns enforcement, experimental guidance is routed only when a
task signal matches, and holdout labels stay outside model-visible context.

This v0.2 release runs an out-of-band machine grader but does not automatically
produce the separate external `final_defect_found` label. It does not inspect
hidden reasoning, support distributed ledgers, treat arbitrary remote tools as
evidence, or infer statistical lift from an initial small sample.

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
      "verify_argv": ["uv", "run", "pytest", "-q"],
      "grader_argv": ["uv", "run", "pytest", "-q", "/opt/grader/tests/task"]
    }
  ]
}
```

Each task has a non-empty `id`, `prompt`, fixture directory, model-callable
`verify_argv`, and post-turn `grader_argv`. Relative fixtures resolve from the
manifest directory and cannot escape it. Commands are argument arrays, never
shell strings: each element is passed without shell interpolation. Fixtures
containing symbolic links are rejected before they can be copied.

## Dry Run

Validate the manifest, deterministic model pairing, holdout assignment, and
output path without API credentials or model calls:

```bash
uv run super-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/smoke \
  --run-id day0-smoke \
  --dry-run
```

The command creates
`.fablized/smoke/day0-smoke/events.jsonl` with two `run_planned` events per
task, one for each configured model. Run IDs cannot be reused within the same
output directory.

For small, directly comparable experiments, pass `--arm-design crossover`.
This plans each task for both models in both ON and OFF arms. The default
`holdout` design remains appropriate for longer operational sampling.

## Live Paired Evaluation

Live execution is billable and may modify the copied task workspaces. It
requires `OPENAI_API_KEY`, access to both configured models, and distinct
digest-pinned `VERIFICATION_IMAGE` and `GRADER_IMAGE` references:

```bash
OPENAI_API_KEY=... uv run super-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/live \
  --run-id day0-live \
  --verification-image "$VERIFICATION_IMAGE" \
  --grader-image "$GRADER_IMAGE"
```

The defaults are product model `gpt-5.5` followed by controlled reference model
`gpt-5.6-sol`, with two gate correction retries.
GPT-5.6 Sol is a limited preview, so API access is not implied by installing this
package. Use `--product-model`, `--reference-model`, and `--max-gate-retries` to
override the defaults. A live run should be an explicit quota and workspace
decision, not part of routine verification or CI.

Live evaluation requires a working Docker runtime and two images pinned by
immutable `sha256` digests. The verifier image is model-callable and contains
only visible checks. The grader image runs once after the model turn, returns
only a boolean to the shadow stream, and is never exposed through a tool result.
Both images must already contain every dependency named by their manifest argv
and must already exist locally because pulls are disabled.
The example manifest can use the minimal verifier image in
[`eval/verifier/`](eval/verifier/); its README shows how to build a local
registry-backed `localhost:5050/...@sha256:...` reference for
`VERIFICATION_IMAGE` and `GRADER_IMAGE`.
The model-callable verifier receives a read-write bind mount of the copied
session workspace at `/workspace` and drops all Linux capabilities. The grader
receives the workspace read-only; it runs as root to read image-baked tests,
drops all other capabilities, and retains only `SETUID` and `SETGID` so its
subject worker can execute the model's code as `nobody`. Both containers receive
no parent environment, no API keys, and no network. Their root filesystems are
read-only, privilege escalation is disabled, process count, memory, and CPU are
limited, and only an isolated temporary filesystem is writable outside the
workspace.
Image-baked environment defaults may still exist inside the container. A
harness-generated container name supports forced cleanup if the Docker client is
cancelled. Cleanup has its own bounded deadline; timeout or nonzero removal is a
typed evaluation error with bounded diagnostics rather than a silent success.
Missing Docker, a missing image, or image reuse between verifier and grader
fails closed and cannot produce successful evidence.

The example grader image bakes task-specific pilot checks into root-only `/opt/grader/tests`.
They are absent from the model-callable verifier image. Published checks validate
instrumentation only; a promoted benchmark must build its grader image from an
unpublished test pack.

## Day 3 Report

`super-sol-report` joins the append-only shadow stream with a separate
external grade file. It refuses incomplete or duplicate evidence and emits
per-model/per-arm quality and resource cells plus a GPT-5.5-first lazy cascade.
Token volume is reported as a cost proxy; it is not converted to dollars without
actual billing data.

Version 0.2.0 retains `fablized-sol-eval` and `fablized-sol-report` as
compatibility aliases. New automation should use the `super-sol-*` names.

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

The current policy evaluates tool completion sequence rather than JSONL append order.
A successful verification must be newer than the most recent code mutation;
documentation edits after verified code do not stale that code evidence. Sequence
tokens stay in harness context and are never exposed in model-visible tool output.

| Condition | Decision |
| --- | --- |
| Holdout/OFF arm | `ALLOW` |
| No observed mutation | `ALLOW` |
| Fresh successful verification after the latest code mutation | `ALLOW` |
| QUICK task | `ALLOW` |
| NORMAL task | `ALLOW` in the current policy |
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
hooks cannot be observed as mutation or verification evidence in this release. They
remain outside the enforcement boundary and must not be registered as though
the harness can observe them. Ledger locking is process-local, every session
must own a separate ledger, and final defect grading remains out of band. The
workspace bind mount is intentionally writable so the verifier can inspect the
model's edits; digest pinning makes the verifier image reproducible, but image
provenance and vulnerability review remain deployment responsibilities.
