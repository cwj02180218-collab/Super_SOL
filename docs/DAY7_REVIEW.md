# Super SOL Day 7 Review

Date: 2026-07-11

Stable release: `v0.3.1`

Failed historical candidate: `0.4.0-rc1`

Successor candidate: `0.5.0-rc1` (unproven performance amplifier)

## 2026-07-12 evidence update

The completed 72-slot clean-room study blocked both broad Super SOL candidates: v0.3.1 tied raw
quality with +26.86% tokens and +30.86% time; v0.4rc1 tied quality with -0.50% tokens but +11.08%
time, narrowly exceeding its fixed 10% Gate 1 ceiling. v0.4 Gate 2 did not run.

v0.5 replaces the generic sweep with four conservative specialist routes and one evidence-triggered
repair inside the existing turn. Its fixed cells are Terra/medium raw, Terra/medium with v0.5,
Sol/high raw, and Sol/max raw. It remains an RC until the new T117-T124 sealed holdout and independent
audit pass every gate in [the v0.5 protocol](V0.5_PERFORMANCE_PROTOCOL.md).

## Decision

| Gate | Decision | Evidence |
| --- | --- | --- |
| Beginner Codex plugin | **GO** | Local-only hooks, no automatic model/API call, explicit paid-run consent, verified install/remove path |
| Package and CLI stability | **GO** | Formatting, lint, strict typing including shipped hooks, tests, archives, CLI smoke |
| Container build evidence | **GO** | Digest-pinned base, hash-locked Python dependencies, verifier/grader SBOMs, local audit |
| v3 benchmark contract | **GO** | Run and session identities are recomputed from task, runtime, lockfile, model, effort, arm, and image inputs |
| New v3 live benchmark claim | **HOLD** | No billable v3 live run was authorized for this release |
| Fable parity or superiority | **HOLD** | The only live pilot is a frozen v0.2.1 four-task historical artifact |
| v0.4 lean default promotion | **NO-GO** | The completed 72-slot study exceeded the fixed wall-time ceiling; Gate 2 correctly did not run |
| v0.5 amplifier promotion | **HOLD** | Gate 0 and the new T117-T124 sealed holdout protocol are not complete |

Super SOL v0.3.1 remains the stable beginner-friendly Codex quality plugin and optional experimental
benchmark harness. v0.4 is a failed, immutable candidate. v0.5 is unproven until its separate gates
pass, so neither candidate is evidence that a model became smarter or that Super SOL beats Fable.

## Seven-day trace

### Day 0: Safe default

The normal product path is the stock-Codex plugin. It needs no API key or Docker and never starts a
billable benchmark automatically. Live evaluation requires both a prompt-level authorization line and
the CLI `--confirm-billable` flag.

### Day 1: Beginner workflow

One marketplace command installs the plugin. The guide shows the exact Python executable, expected
hook path and events, update, plugin-only removal, full removal, and tag-pinned rollback.

### Day 2: Verification behavior

The hook distinguishes explanation-only prompts from work requests, observes supported file edits,
recognizes common verification commands, and warns without creating another model response. It does
not claim to observe arbitrary shell or MCP mutations.

### Day 3: Benchmark identity

The v3 event stream contains a canonical run identity. It binds the complete task set, preregistration
content, harness content, dependency lock, resolved dependencies, Python/platform, models, efforts,
arm design, retry limit, and verifier/grader image references. Report generation recomputes run and
session digests before joining external grades.

### Day 4: Measurement contract

Final-defect labels remain external to the model-visible stream. Crossover reports require complete
paired cells, state the Hoeffding quality interval and paired Student-t resource interval, and render
quality, token, and wall-time effects.

### Day 5: Container reproducibility

Verifier and grader builds use an exact multi-platform base digest and hash-locked Python packages.
The local audit builds both images, emits SPDX SBOMs before both release scans, and preserves the
evidence even when a later gate fails.

### Day 6: Release QA

The release gate covers the full test suite, coverage, formatting, lint, strict typing of package and
plugin hooks, package build, archive contents, isolated marketplace install/remove, free dry-run, and
the no-confirmation live refusal path.

### Day 7: Independent review

Five stock-Codex review lanes examined code correctness, beginner UX, reproducibility, release
packaging, and hands-on QA. Their first pass found concrete blockers in Python compatibility, consent,
hook command parsing, provenance validation, interval reporting, and release documentation. Each
accepted finding was fixed and returned to the same lane for recheck before release.

For v0.4, independent review is encoded as a separate raw-record auditor. A statistical candidate
cannot set final `promote=true`; the auditor must independently reproduce the core aggregates and find
zero missing public artifacts and zero hidden-test or credential leakage.

## Evidence boundary

The directory `benchmarks/day3-contract-v2` is retained only as a historical v0.2.1 snapshot. Its raw
events, grades, exact preregistration, and v3 run identity do not exist, so its missing fields are never
guessed and it cannot be parsed as v3 evidence.

A new performance claim requires the separately authorized clean-room Gate 2 run that preserves the complete
event stream, external grade file, exact task manifest and fixtures, preregistration commit, image
references, candidate report, independent audit, and final decision. Gate 1 tuning results cannot be
used for a public performance claim.
