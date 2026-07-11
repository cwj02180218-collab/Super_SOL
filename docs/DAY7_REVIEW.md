# Super SOL Day 7 Review

Date: 2026-07-11  
Release candidate: `v0.2.0`

## Decision

| Gate | Decision | Evidence |
| --- | --- | --- |
| Open-source harness release | **PASS** | Strict typing, 131 tests, build, CLI QA, isolated verifier/grader, aggregate report |
| Reproducible pilot execution | **PASS** | 16/16 sessions completed; 16/16 out-of-band grader checks passed |
| Baseline-first efficiency hypothesis | **PROMISING** | 11.2% to 14.9% token-volume savings with zero escalations in four tasks |
| ON-arm quality uplift | **NOT OBSERVED** | Both arms scored 100%; ON used more tokens for both models |
| Fable parity or broad benchmark promotion | **HOLD** | Four task groups cannot support the claim |

Super SOL is ready to ship as an experimental, evidence-gated harness. The
benchmark is not ready to support a parity or superiority claim.

## Seven-day review trace

### Day 0: Execution contract

The CLI parses a strict manifest, creates isolated session workspaces, keeps
model roles distinct, and fails closed when live credentials or digest-pinned
images are absent.

### Day 1: Comparable cells

The crossover design runs every task under both models and both harness arms.
The four-task pilot creates sixteen deterministic sessions.

### Day 2: Independent grading

The model-callable verifier contains only visible checks. A separate,
digest-pinned grader runs after the turn with no network and returns only a
boolean to the shadow stream.

### Day 3: Quality and efficiency

The final contract-v2 pilot completed all sixteen sessions and passed every
grader check. GPT-5.5 used fewer tokens in aggregate, while quality was tied.

### Day 4: Contract audit

The ambiguous fractional-cent task was corrected. The public acceptance example
and hidden grader case use different numbers, preserving generalization value.

### Day 5: Security and leakage audit

Environment files and live artifacts are ignored. Containers receive no parent
API key, no network, a read-only root filesystem, and only the intended
workspace bind mount. Published evidence is aggregate only.

### Day 6: Reproducibility and release QA

Offline formatting, linting, strict typing, tests, package builds, primary CLI
commands, compatibility aliases, archive contents, and GitHub CI are the release
gate. Billable live evaluation is excluded from routine CI.

### Day 7: Promotion review

Five independent review lanes cover goal completeness, hands-on QA, code
quality, security, and missed repository context. The software can be released
when all lanes pass. Benchmark promotion remains on hold until the evidence
threshold below is met.

## Promotion threshold

Fable-parity, general model-superiority, or production-routing claims require:

- at least 50 completed crossover task groups;
- an unpublished, versioned grader pack;
- frozen verifier and grader image digests;
- exactly one external final-defect label per session;
- paired effect sizes and uncertainty supporting the specific claim;
- cost calculated from actual billed usage rather than token volume alone;
- a rerun on a preregistered task set that was not used to tune prompts or packs.

Until those conditions are met, published results are engineering evidence, not
a leaderboard claim.
