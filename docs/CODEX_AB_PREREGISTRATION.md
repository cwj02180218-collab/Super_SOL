# Super SOL v0.4 clean-room Codex A/B preregistration

Frozen: 2026-07-11

## Candidate and comparator

- Comparator: stock Codex with no marketplace plugin in a minimal ephemeral `CODEX_HOME`.
- Candidate: the same stock Codex binary and configuration with exactly one digest-recorded Super SOL
  plugin at the preregistered immutable Git revision.
- Candidate behavior: the exact 154-character lean contract sweep recorded in the v0.4 design.
- Model and effort: supplied explicitly at run creation and held constant across arms.
- Repetitions: exactly two per task and arm.

The run identity binds the Codex binary path, version and digest; task and fixture digests; model and
effort; plugin revision and tree digest; command-template digest; environment variable names; timeout;
and grader image digest. A changed input creates a different run and slot identity.

## Isolation and execution

Task order alternates the first arm by task. Repetition two reverses repetition one's arm order. Both
arms use the same prompt, fixture, AGENTS instructions, `workspace-write` sandbox, `never` approval
policy, timeout, environment names, telemetry parser, and grader. `--ignore-user-config` is not used.
`--dangerously-bypass-approvals-and-sandbox` is forbidden. Hook trust may be bypassed only after local
plugin source and installed-home validation, and the flag is present symmetrically.

No slot is retried automatically. A 429, session limit, timeout, nonzero process exit, malformed or
duplicate terminal event, grader infrastructure error, image preflight failure, or artifact violation
is infrastructure-missing and never receives score zero. Resumption requires a fresh explicit approval,
an identical run identity, and an existing `slot.missing`; completed slots cannot run again.

## Gate 0: free local validation

Gate 0 starts no Codex model process and no Docker grader. It includes the full unit/type/lint suite,
exact hook golden tests, official stock Codex plugin install/list/remove/reinstall in an isolated home,
and `super-sol-codex-ab --dry-run`. Dry-run must produce only `slot.planned`, contain one lean Super SOL
skill path and zero raw paths, retain no authentication or temporary home, and create no workspace.

## Gate 1: tuning regression set

T105~T108 × two arms × two repetitions = 16 planned slots. T105~T107 cover the known semantic
regressions and T108 covers the prior token spike. Gate 1 requires a new standalone user approval and
the CLI `--confirm-billable`. It is tuning evidence only and cannot support public performance language.
Any failed promotion metric returns the candidate to observation-only behavior and blocks Gate 2.

## Gate 2: sealed unseen holdout

T109~T116 × two arms × two repetitions = 32 planned slots. The task fixtures, hidden grader, and
grader-image digest are sealed before Gate 1 begins. Hidden assertions and grader feedback cannot alter
the candidate instruction or implementation. Only this unseen holdout may support a v0.4 performance
statement.

## Metrics and fixed analysis

The primary paired value is lean score minus raw score for each task/repetition. The report uses seed
`20260711` and 10,000 paired bootstrap resamples. It also reports positive, negative, and tied pair
counts plus paired rank-biserial correlation. Provider cost is reported only when the provider exposes
it and is never imputed for Codex.

The candidate must pass all six statistical/resource conditions:

1. Mean paired score delta is at least 0 points.
2. Paired bootstrap 95% lower bound is at least -2 points.
3. Lean full-pass rate is at least raw full-pass rate.
4. Lean/raw mean total-token ratio is at most 1.05.
5. Lean/raw mean wall-time ratio is at most 1.10.
6. No task has a score delta of -10 points or lower in both repetitions.

Final promotion additionally requires all three independent-audit conditions:

7. Artifact omissions equal zero.
8. Hidden-test or credential leakage findings equal zero.
9. An independently implemented parser reproduces the published pair count and raw/lean score,
   full-pass, token, wall-time, and mean-delta aggregates.

Failure of any condition sets final `promote` to false. A statistical candidate remains explicitly
`awaiting_independent_audit` until the independent audit command creates the final decision.

## Publication and rollback

Raw authentication, raw prompts, session homes, plugin state, hidden tests, and grader diagnostics are
never public artifacts. Public records contain digests, sanitized terminal events, candidate metrics,
audit evidence, and the final decision. v0.3.1 remains stable while this protocol runs. A failed
candidate is corrected under a new commit and tag; an existing release or tag is never rewritten.
