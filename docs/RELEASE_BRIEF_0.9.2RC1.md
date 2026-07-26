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

Full Gate 0 is **NOT RUN** at this document revision. Coverage, complete-suite count, latency,
replay, supply-chain audit, artifact hashes, and candidate commit will be recorded only after their
commands complete. Paid Gate 1 is **NOT RUN** and requires separate explicit billable approval.

The frozen decision rules are in
[`V0.9.2_PROMOTION_PROTOCOL.md`](V0.9.2_PROMOTION_PROTOCOL.md).
