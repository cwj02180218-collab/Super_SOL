# GPT.C applicability decisions

Reference: [`cuj0218/GPT.C` at `e1cf849`](https://github.com/cuj0218/GPT.C/tree/e1cf849ec0f4467d47da5fb4de7c0fb77be1577a), inspected 2026-07-10.

GPT.C informed Super SOL's procedure and evidence rules. Its wrapper and ontology are not embedded
as a second runtime. Super SOL remains a Codex plugin plus an optional, separately invoked benchmark
harness.

## Adopt now

- Reject unknown tools and malformed typed results instead of granting mutation or verification
  credit.
- Require successful verification newer than the last observed mutation.
- Interpret quality together with latency, tool calls, failures, token volume, and actual billed
  cost when available.
- Keep holdout assignment, grader outcomes, and experiment provenance outside model context.
- Keep the everyday plugin free of API keys, hidden model switching, and automatic billable calls.

## Park for evidence

- Promise-without-action text regexes.
- Repeated-failure disclosure heuristics.
- A larger experiment registry with `off`, `pilot`, `promoted`, and `rejected` states.
- A larger ontology after multiple adapters or policy versions demonstrate a synchronization need.
- Automatic Terra-to-Sol or effort escalation after preregistered routing evidence exists.

## Reject

- `codex exec --json` plus concurrency-ambiguous `resume --last` when typed SDK lifecycle and
  guardrail boundaries are available.
- Snapshot ledgers that rewrite state or accept verification older than the latest mutation.
- Command/output regex inference as benchmark mutation or verification evidence.
- Fail-open paths that report an evidence gap while returning apparent success.
- Global installation of experimental policy or model-tier maps.
- Benchmark tables as stand-alone efficacy evidence.

## Provenance

These decisions derive from GPT.C's event parser, ledger, verification state, driver, ontology, and
measurement documents at the pinned commit. The complete inspection remains an out-of-band
development artifact; this file records only durable product decisions.
