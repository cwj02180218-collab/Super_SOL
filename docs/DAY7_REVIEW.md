# Super SOL Day 7 Review

Date: 2026-07-11

Release candidate: `v0.3.0`

## Decision

| Gate | Decision | Evidence |
| --- | --- | --- |
| Beginner Codex plugin | **GO** | Local-only hooks, no automatic model/API call, explicit paid-run consent, verified install/remove path |
| Package and CLI stability | **GO** | Formatting, lint, strict typing including shipped hooks, tests, archives, CLI smoke |
| Container build evidence | **GO** | Digest-pinned base, hash-locked Python dependencies, verifier/grader SBOMs, local audit |
| v3 benchmark contract | **GO** | Run and session identities are recomputed from task, runtime, lockfile, model, effort, arm, and image inputs |
| New v3 live benchmark claim | **HOLD** | No billable v3 live run was authorized for this release |
| Fable parity or superiority | **HOLD** | The only live pilot is a frozen v0.2.1 four-task historical artifact |

Super SOL v0.3.0 is releasable as a beginner-friendly Codex quality plugin and an optional
experimental benchmark harness. It is not evidence that a model became smarter, that Super SOL beats
Fable, or that the old pilot is reproducible under the new v3 schema.

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

## Evidence boundary

The directory `benchmarks/day3-contract-v2` is retained only as a historical v0.2.1 snapshot. Its raw
events, grades, exact preregistration, and v3 run identity do not exist, so its missing fields are never
guessed and it cannot be parsed as v3 evidence.

A new performance claim requires a separately authorized v3 live run that preserves the complete
event stream, external grade file, exact task manifest and fixtures, preregistration commit, image
references, and generated report. Broad parity or routing claims additionally require at least 50
completed crossover task groups and a held-out grader pack.
