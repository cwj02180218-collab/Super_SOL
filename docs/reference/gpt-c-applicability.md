# GPT.C Applicability Decisions

Reference: [`cuj0218/GPT.C` at `e1cf849`](https://github.com/cuj0218/GPT.C/tree/e1cf849ec0f4467d47da5fb4de7c0fb77be1577a), inspected 2026-07-10.

## Adopt Now

- Freeze SDK adapter drift behavior: unknown tools and malformed typed results
  produce observable rejection events and receive no mutation or verification
  credit.
- Pre-register the harness-paradox analysis before live evaluation. Quality
  lift must be interpreted together with latency, tool-call, failure, and token
  costs.
- Preserve provenance and lifecycle status for future experimental packs and
  gates.

## Park For Evidence

- Promise-without-action text regexes.
- Repeated-failure disclosure heuristics.
- A validated experiment registry with `off`, `pilot`, `promoted`, and
  `rejected` states.
- A larger ontology only after multiple adapters or policy versions create a
  demonstrated synchronization problem.

## Reject

- `codex exec --json` plus concurrency-ambiguous `resume --last` when the Agents
  SDK provides typed lifecycle and guardrail boundaries.
- Snapshot ledgers that rewrite state or allow verification older than the
  latest mutation.
- Command/output regex inference for mutation or verification.
- Fail-open paths that report an evidence gap while returning apparent success.
- Global installation of experimental policy or model-tier-to-task-mode maps.
- Benchmark tables as efficacy evidence for this harness.

## Provenance

The decisions above are based on GPT.C's event parser, ledger, verification
state, driver, ontology, and measurement documents at the pinned commit. The
full inspection report remains an out-of-band development artifact; this file
records only durable project decisions.
