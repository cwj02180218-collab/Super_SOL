# Super SOL v0.9.1-rc1 Release Brief

Status: product candidate, not stable.

`v0.9.1-rc1 is a prerelease.` It adds selective semantic intervention for exact normalized
`gpt-5.6-sol` and `gpt-5.6-terra` profiles. High-confidence task routes may emit one prompt context.
After two successful distinct edits without an observed verifier, the candidate may emit one
evidence context. Every context is bounded to 180 Unicode code points.

The no-progress loop fuse remains exact-Sol only. Unknown profiles and ambiguous tasks are observed
without model-visible context. There are no model calls, no retries, no continuations, no model
switching, no automatic subagents, and no process killer.

The package stores candidate assets under `fablized_sol/_release/v0_9_1/`. v0.8.0 remains the stable
release. Quality uplift has not been established. The new 240 valid slots have not run, and no
performance claim is made from the implementation tests.

Before candidate implementation, the unchanged v0.9.0 baseline passed 465 tests with 90.56%
coverage. Candidate Gate 0 results and exact hashes will be recorded here only after observed runs.
The frozen comparison rules are in
[`V0.9.1_PROMOTION_PROTOCOL.md`](V0.9.1_PROMOTION_PROTOCOL.md).
