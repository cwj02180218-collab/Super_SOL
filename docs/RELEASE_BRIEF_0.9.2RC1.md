# Super SOL v0.9.2-rc1 Release Brief

Status: product candidate, not stable.

`v0.9.2-rc1 is a prerelease.` This is the Safety and Evidence candidate for stock Codex. Exact
`gpt-5.6-sol` retains the bounded loop fuse, but the default path has no default quality context.
Prompt routes, residual checks, repair prompts, and verification-debt reminders are disabled unless
an experiment explicitly sets `SUPER_SOL_QUALITY_MODE=selective`.

Safety incidents use a bounded local ledger containing only typed event, reason, decision, and
timestamp fields. It does not store prompts, commands, paths, tool responses, model output, or
environment values. `SUPER_SOL_BENCHMARK_GUARD=1` enables fail-closed test-mutation protection only
for controlled evaluations with validated repository-relative test roots. Ordinary sessions may
edit tests.

There are no model calls, no retries, no continuations, no model switching, no automatic subagents,
and no process killer. Release assets remain under `fablized_sol/_release/v0_9/`. v0.8.0 remains the
stable release. Quality uplift has not been established, and the prospective crossover has not run.

## Observed Evidence

Focused red-green implementation tests for default silence, explicit selective compatibility,
bounded incident auditing, audit privacy, benchmark test protection, and transient provider
censoring passed before the full candidate freeze.

Gate 0 completed against candidate commit `8092adf6ef916e2a5d43e2cf917c67ba71bbc1d1`.
The complete suite passed 500/500 tests in 48.03 seconds with 90.84% combined source and hook
coverage. Ruff formatting, Ruff lint, BasedPyright with zero errors and warnings, package build,
archive inventory, dependency-lock provenance, stock hook lifecycle, and credential-stripped replay
passed.

The v0.9.2 safety replay passed 12/12 with zero unexpected contexts, zero network calls, and zero
billable calls. Hook latency passed with absolute p95 `88.03094197646716 ms` and incremental p95
`59.81898153549992 ms`, below the registered `100/70 ms` limits. Docker Scout found zero known
vulnerable packages in both 57-package verifier and grader images and regenerated both SPDX SBOMs.

The source-size audit found no new v0.9.2 production module above 250 non-comment, non-blank lines.
It also found 12 pre-existing oversized source or test files; this legacy debt is disclosed rather
than treated as completed refactoring outside the candidate scope.

Machine-readable evidence is stored in
[`v092-gate0.json`](../benchmarks/v0.9-loop-replay/v092-gate0.json),
[`v092-audit.json`](../benchmarks/v0.9-loop-replay/v092-audit.json),
[`v092-latency.json`](../benchmarks/v0.9-loop-replay/v092-latency.json), and
[`v092-report.json`](../benchmarks/v0.9-loop-replay/v092-report.json).

## Gate 1 and Corrected Replication

Paid Gate 1 ran after explicit approval on 12 sealed external PR tasks under Sol/high and
Terra/xhigh. The first complete 96-slot collection cannot support product promotion: its runner
enabled `SUPER_SOL_BENCHMARK_GUARD=1` for candidate arms without supplying the required validated
test roots. The product correctly failed closed and blocked production edits. Those candidate
observations are retained only as a benchmark-guard stress test. The 48 raw records were unaffected
and were frozen with SHA-256
`70075acfda1f3d757ea055b5f8b853df3676c9f59ee82629d5b424d2be5be83d`.

A mechanically corrected 48-slot candidate replication then disabled the optional guard, matching
the default product configuration. It used the unchanged candidate, task pack, prompts, graders,
models, and efforts, and paired against the frozen raw records. All 48 candidate slots completed
normally and passed their hidden semantic graders. Audit checks found zero infrastructure
censoring, contamination, test mutation, hidden-marker leakage, retained credentials, or missing
telemetry.

| Tier | Arm | Pass rate | Mean tokens | Token ratio vs raw | Mean time | Time ratio vs raw |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Sol/high | raw one-shot | 100% | 414,681 | 1.000 | 164.2 s | 1.000 |
| Sol/high | safety-only | 100% | 347,973 | 0.839 | 151.4 s | 0.922 |
| Sol/high | selective | 100% | 413,085 | 0.996 | 171.6 s | 1.045 |
| Terra/xhigh | raw one-shot | 100% | 400,708 | 1.000 | 152.0 s | 1.000 |
| Terra/xhigh | safety-only | 100% | 396,522 | 0.990 | 148.9 s | 0.980 |
| Terra/xhigh | selective | 100% | 329,046 | 0.821 | 129.0 s | 0.849 |

Safety-only passed every registered diagnostic noninferiority and 3% efficiency check in both
tiers. It also removed the one exact-command loop heuristic observed in Sol raw. Selective was
quality-neutral; it was efficient on Terra but exceeded the Sol wall-time threshold.

These results do not establish quality uplift because every raw and candidate task passed. They also
do not authorize stable promotion: the preregistered replay policy allowed replacement only for
infrastructure-censored slots, not for a runner-configuration correction after task exposure. The
candidate remains `v0.9.2-rc1`, and v0.8.0 remains the stable release. A stable v0.9.2 requires a
new sealed task pack with enough raw failures to measure quality and no post-freeze protocol repair.

Machine-readable evidence is stored in
[`v092-gate1-corrected-report.json`](../benchmarks/v0.9-loop-replay/v092-gate1-corrected-report.json),
[`v092-gate1-corrected-audit.json`](../benchmarks/v0.9-loop-replay/v092-gate1-corrected-audit.json),
and
[`v092-gate1-classification.json`](../benchmarks/v0.9-loop-replay/v092-gate1-classification.json).

The frozen decision rules are in
[`V0.9.2_PROMOTION_PROTOCOL.md`](V0.9.2_PROMOTION_PROTOCOL.md).
