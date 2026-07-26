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

Paid Gate 1 is **NOT RUN** and requires separate explicit billable approval. Quality uplift remains
unestablished, so v0.8.0 remains the stable release and v0.9.2-rc1 remains a prerelease.

The frozen decision rules are in
[`V0.9.2_PROMOTION_PROTOCOL.md`](V0.9.2_PROMOTION_PROTOCOL.md).
