# Super SOL 0.8.0 stable release brief

Date: 2026-07-13
Status: stable-promotion decision passed; GitHub release requires green CI

## Release contract

- Package: `0.8.0`
- Plugin: `0.8.0`
- Frozen candidate: `v0.8.0-rc1` at `e6c78493c8f3309cb3481481938e2ad40509e5a7`
- Active profile: normalized model identifier exactly `gpt-5.6-sol`
- Non-Sol profiles: observation-only, with zero model-visible context
- Runtime: raw-first; at most one context after observed edit plus verification
- Context limit: 180 Unicode code points
- Additional model calls, switches, subprocesses, subagents, retries, and test reruns: zero

## Confirmatory evidence

The preregistered four-arm crossover completed 96/96 valid slots: 12 unseen tasks, four arms,
two repetitions, and complete within-model pairing. Seven infrastructure-censored attempts were
preserved as unscored records and replaced only by linked clean-room retries. The final audit passed
all lattice, provenance, contamination, retry-linkage, and artifact checks.

Super SOL versus Codex raw:

- mean paired score delta: 0.00
- 95% clustered bootstrap CI: [0.00, 0.00]
- full-pass count: 24/24 versus 24/24
- paired token ratio: 0.9767 (2.33% lower)
- paired wall-time ratio: 1.0791 (7.91% higher)
- verifier-observation rate delta: 0.00
- repeated regressions of at least 10 points: zero

Every frozen stable-promotion gate passed. The permitted claim is **noninferior quality with bounded
overhead**. **quality uplift was not proven**: the score delta and its confidence interval are exactly
zero. This result evaluates the end-to-end harness on one task pack and does not show that Super SOL
raises the underlying model's intelligence.

For context, Fablize improved Claude Fable by 6.04 points with a 95% clustered bootstrap interval of
[3.13, 8.54], while increasing paired tokens by 27.30% and wall time by 26.26%. That cross-ecosystem
comparison is descriptive; the primary causal estimates are the two within-model harness contrasts.

## Evidence hashes

| Artifact | SHA-256 |
|---|---|
| Aggregate analysis | `ea79d54af78f6c0ecfffedc15bac4a38c878e31a3a3034ad408285969a1e18b7` |
| Redacted 103-attempt ledger | `b8bad479add16a057f46134f0cf71eeaafdd96fb9d351d261ba4c1cd93412979` |
| Fail-closed audit | `5d4492bf5d942de33f7e822ab08b1ba731cd49557eb82c0a1310b8d38f0d3021` |
| 96-slot CSV | `80b0fff309fa474f1de42f6254b09de0691d333180988afc392e7b21b34ffdfb` |
| 96-slot JSON | `65939ac87f469d7e915e6d6b84a9c428976b4c748dba494c5e0da28e4dd2f907` |
| Result manifest | `c1d1b8c657aaa56040cfcd3dd2559e145526f02fc7cecad6fc992725cf501ff9` |
| Dashboard HTML | `8e85e47c5fba579b9d57bd35bee8a00cd9e9347633dbd817e60e32492849cf6a` |
| arXiv-style paper PDF | `e925dfd71ce1f6a31c6985dfa75f6e181caacfdfce19a778a8a027524b8c0cb4` |
| Paper source ZIP | `fbb83e30055527be86b5bb1171cc94ae0cd2d7977efd1dbfed6e2c69c222d969` |

The public evidence lives in `benchmarks/v0.8-confirmatory/`, including a redacted attempt ledger and
path-free scored observations. Detailed private records containing local paths, prompts, or model
payloads are intentionally excluded. The dashboard, paper, and source archive are attached to the
GitHub release.
