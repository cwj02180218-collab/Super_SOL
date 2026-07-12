# Super SOL v0.4 benchmark postmortem

Date: 2026-07-12  
Status: immutable failed-candidate evidence

## Observed result

The final study completed **72 paid slots** in Orca clean-room worktrees. It does not support a
general claim that Super SOL or SOLTELU improves Codex.

| Candidate | Quality | Tokens | Wall time | Decision |
|---|---:|---:|---:|---|
| Super SOL v0.3.1 | tied with raw | +26.86% | +30.86% | failed |
| Super SOL v0.4.0-rc1 | tied with raw | -0.50% | +11.08% | Gate 1 failed |

The v0.4 preregistration allowed at most 10% additional wall time. The observed 11.08% crossed that
fixed limit, so Gate 2 did not run. The result is not reinterpreted after observation and commit
`777c9bd` is not retried under the same candidate identity.

## SOLTELU signal

SOLTELU's disclosed holdout mean was +4.58 score points with a paired 95% confidence interval of
[-4.39, +16.06]. Tokens increased 18.23% and wall time decreased 6.64%. The interval includes both a
material regression and an improvement, so general uplift was not established.

The effect was concentrated:

- T112 authentication refresh race: +57.5 points in both repetitions;
- T109 log normalization: -8.75 points;
- T113 order migration: -12.08 points.

This supports testing narrow concurrency procedures. It does not support broad model routing.

## Product correction

v0.3.1 and v0.4 tested generic wrappers around the same strong model. The original product question
was different: whether a balanced model plus a task-specific harness can approach a stronger raw
reference. v0.5 therefore removes the generic 154-character sweep and activates a frozen procedure
only for a high-confidence concurrency, security, migration, or failure-atomicity request.

T109-T116 are now disclosed. They cannot be called an unseen v0.5 holdout.
