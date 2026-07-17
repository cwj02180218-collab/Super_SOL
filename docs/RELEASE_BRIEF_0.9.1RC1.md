# Super SOL v0.9.1-rc1 Release Brief

Status: product candidate, not stable.

`v0.9.1-rc1 is a prerelease.` It adds selective semantic intervention for exact normalized
`gpt-5.6-sol` and `gpt-5.6-terra` profiles. High-confidence task routes may emit one prompt context.
After two successful distinct edits without an observed verifier, the candidate may emit one
evidence context. Every context is bounded to 180 Unicode code points.

The no-progress loop fuse remains exact-Sol only. Unknown profiles and ambiguous tasks are observed
without model-visible context. There are no model calls, no retries, no continuations, no model
switching, no automatic subagents, and no process killer.

The package stores candidate assets under `fablized_sol/_release/v0_9/`. v0.8.0 remains the stable
release. Quality uplift has not been established. The new 240 valid slots have not run, and no
performance claim is made from the implementation tests.

Before candidate implementation, the unchanged v0.9.0 baseline passed 465 tests with 90.56%
coverage. Candidate Gate 0 passed at product commit
`e8418af2967b8685687f2bea640117649b1df27a`: 480/480 tests passed in 45.34 seconds with 90.64%
coverage. Ruff, format checking, BasedPyright, package build, archive inventory, container audit,
credential-stripped lifecycle replay, and dependency provenance passed.

Fresh latency measurement passed with hook p95 `57.45559616480023 ms` and incremental p95
`34.92545976769179 ms`, below the registered `100/70 ms` limits. Loop replay passed 12/12 with zero
unexpected contexts, zero successful network calls, and `billable_calls: 0`. Container scans found
zero vulnerable packages in both verifier and grader images. The first container-audit attempt was
infrastructure-censored before scanning because Docker was not running; the unchanged command
passed after daemon readiness was established.

Machine-readable results are
[`v091-gate0.json`](../benchmarks/v0.9-loop-replay/v091-gate0.json),
[`v091-audit.json`](../benchmarks/v0.9-loop-replay/v091-audit.json), and
[`v091-latency.json`](../benchmarks/v0.9-loop-replay/v091-latency.json). Candidate Gate 0 is complete,
but the new 240 valid slots have not run. Quality uplift has not been established, and stable
promotion remains disabled. The frozen comparison rules are in
[`V0.9.1_PROMOTION_PROTOCOL.md`](V0.9.1_PROMOTION_PROTOCOL.md).
