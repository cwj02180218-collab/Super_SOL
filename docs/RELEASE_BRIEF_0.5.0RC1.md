# Super SOL 0.5.0rc1 Gate 0 release brief

Date: 2026-07-12  
Status: free Gate 0 complete; paid Gate 1 blocked by design

## Frozen inputs

- Candidate behavior commit: `f3844e9ef986c7510ef8b6719a4b7cb7f70596e1`
- Benchmark harness commit: `fbbb70a707888413474ba97c291479003a0067b5`
- Python package: `0.5.0rc1`
- Codex plugin: `0.5.0-rc1`
- Verifier image: `super-sol-verifier@sha256:4a27f903226e7ce76e0b2949f8313d487a519e936e6edd092b0113aefda8a0f9`
- Grader image: `super-sol-grader@sha256:744584b90b63c92e45aa1386fa378f87614f92802b89eabbb0865070690513b8`
- Verifier SBOM SHA-256: `ee194ccb861134a1ce78b7bbf0b88ff2310cc27d26c473451be8ce72475a3352`
- Grader SBOM SHA-256: `a8c31a41f46a6941edcd02d219886d867a4f95151394c1ff96079da02810c425`
- `uv.lock` SHA-256: `79b48a7f6cc29e3f8ab52c51fb9e4c90475f455638ba697f1129fee6411c5abb`
- T117-T124 holdout-seal digest: **unavailable; external sealed pack not supplied**

The candidate behavior commit is the immutable code and supply-chain checkpoint. This brief is a
later documentation-only commit and does not redefine the candidate.

## Observed free Gate 0

| Check | Observed result |
|---|---|
| Super SOL plugin tests | 39 passed |
| Super SOL full tests | 247 passed |
| Coverage | 90.15%, fixed floor 90% |
| Ruff lint / format | clean; 102 files formatted |
| basedpyright | 0 errors, 0 warnings |
| Package build | wheel and sdist built as `0.5.0rc1` |
| Archive privacy | no `.env`, `auth.json`, `.fablized`, or session members |
| Tracked secret shapes | 0 matching GitHub/OpenAI credential files |
| Production dependency audit | no known vulnerabilities found |
| Container scan | verifier and grader each `0C 0H 0M 0L` |
| Isolated plugin lifecycle | install, remove, reinstall; 1 manifest, 1 skill, version match |
| Benchmark harness tests | 63 passed |
| Benchmark lint | clean |
| Broken subject fixture | exactly 4 expected failures under `scripts/verify.sh` |
| Gate 1 dry-run | exactly 32 `slot.planned` rows; no model or Orca slot creation |
| Orca runtime | ready and reachable, runtime `2d10e8ee-bbbe-497e-8101-d5c73df5012a` |
| Orca target repo | `a27487e7-0754-4fe4-bf32-6394d1b07072` |

The benchmark subject failures are deliberate. Harness tests live under `tests/`; the intentionally
broken checkout task lives under `target_tests/`, so repository QA and agent-task verification no
longer contaminate each other.

## Paid boundary

No v0.5 performance result exists. No Terra, Sol, grader, or paid benchmark slot was started during
Gate 0. A live command now exits before any Orca mutation unless it receives all of the following:

1. an externally supplied regular T117-T124 holdout seal;
2. a generated regular `cleanroom/v05-preregistration.json` bound to the exact candidate, benchmark,
   target, four cells, 32-slot Gate 1, 64-slot Gate 2, seed `20260712`, and grader image digest;
3. a clean candidate and benchmark checkout matching those commits;
4. the standalone approval phrase `SUPER SOL 유료 실행 승인` in the controlling user turn;
5. the CLI flag `--confirm-billable`.

The preregistration file was intentionally not generated because item 1 is absent. This is the
expected fail-closed state, not a partial performance result.

## Remaining risks

- Selective routing and the one-repair policy are locally verified but have no paid comparative result.
- GPT-5.6 Terra/medium and Sol/high availability depends on the user's current plan and workspace;
  the plugin cannot create a Pro entitlement or change account limits.
- The external T117-T124 tasks and private graders still require independent authorship and review.
- Gate 1 requires 32 billable slots. Gate 2 requires 64 additional slots and cannot run until Gate 1
  and the independent aggregate audit pass.
- The observed Docker images are Linux arm64 local builds. Remote CI and other architectures remain
  separate release evidence.
- The candidate and benchmark branches must be reviewed and integrated before any public RC tag.

Until those risks are closed, public wording must remain “unproven performance-amplifier candidate,”
not “Pro equivalent,” “Fable-beating,” or “model intelligence increase.”
