# Super SOL Public Release Design

## Goal

Publish the validated harness as the independent public repository
`cuj0218/Super-SOL`, preserving the existing commit history while presenting a
coherent Super SOL product surface and an evidence-backed Day 7 decision.

## Release shape

- Create a new public GitHub repository rather than renaming or replacing
  `cuj0218/fablized-sol`.
- Push the complete locally available commit history to `main`.
- Publish GitHub release `v0.2.0` with the built wheel and source archive.
- Do not publish to PyPI in this release.
- Keep the existing `fablized_sol` Python import package so history and internal
  compatibility remain intact.
- Publish `super-sol-eval` and `super-sol-report` as the primary command names,
  while retaining `fablized-sol-eval` and `fablized-sol-report` as compatibility
  aliases.

## Public product framing

Super SOL is the evidence-gated harness product. GPT-5.5 is the baseline product
model, GPT-5.6 Sol is a controlled same-adapter reference comparator, and GPT.C
plus Codex remains a separate operational reference. The repository must not
claim that the harness raises a model's capability ceiling.

The public README will lead with observable guarantees:

- isolated task workspaces;
- typed local tool evidence;
- verification after the latest mutation;
- digest-pinned, network-disabled verifier and grader containers;
- append-only measurement streams;
- same-task ON/OFF crossover analysis;
- GPT-5.5-first lazy escalation analysis.

## Evidence publication

Commit only aggregate, non-secret benchmark evidence from the final
`day3-live-sol-contract-v2` run. Do not commit live workspaces, ledgers, raw model
output, environment files, API keys, or Docker-local state.

The published pilot record must state:

- 16 of 16 sessions completed;
- 16 of 16 out-of-band grader checks passed;
- both models scored 100 percent on four pilot tasks;
- GPT-5.5 used 20,932 tokens and GPT-5.6 Sol used 24,096 tokens;
- lazy baseline-first routing saved 11.2 to 14.9 percent token volume in this
  pilot because no escalation was required;
- this sample is not evidence of Fable parity, general model superiority, or a
  quality uplift from the ON arm.

## Day 7 decision

Day 7 has two separate decisions:

1. **Open-source harness release: PASS.** Packaging, deterministic controls,
   security boundaries, tests, build, documentation, and reproducible aggregate
   evidence are release-ready.
2. **Benchmark promotion and Fable-parity claim: HOLD.** Promotion requires at
   least 50 completed crossover task groups, an unpublished grader pack, frozen
   image digests, external defect labels, and paired uncertainty that supports
   the intended claim.

This split allows the software to ship without turning a four-task pilot into a
marketing claim.

## Repository hardening

- Add an MIT license carrying the existing GPT.C and fablize attribution.
- Add a notice describing the relationship to `cuj0218/GPT.C` and
  `fivetaku/fablize`.
- Ignore `.DS_Store`, local environments, benchmark runtime output, coverage,
  and build artifacts.
- Add a non-live GitHub Actions workflow for formatting, linting, strict typing,
  tests, and package builds. CI must never require an API key or run billable
  evaluations.
- Pin third-party GitHub Actions by immutable commit SHA.
- Add security and contribution guidance that preserves the verifier/grader
  trust boundary.

## Versioning and compatibility

Release version is `0.2.0`. The Python distribution name becomes
`super-sol-harness`; the import package remains `fablized_sol`. Existing command
names remain functional as compatibility aliases for this release.

## Success criteria

- The complete offline quality gate passes.
- Both primary and compatibility CLI commands render help and perform a dry run.
- The wheel contains the runtime package and license files. The source archive
  additionally contains docs, benchmarks, evaluation fixtures, and tests. Neither
  archive contains local secrets or runtime evidence.
- Five independent final review lanes pass: goal, QA, code quality, security,
  and repository context.
- `cuj0218/Super-SOL` is public, `main` contains the preserved history, CI is
  green, and release `v0.2.0` exposes verified build artifacts.
