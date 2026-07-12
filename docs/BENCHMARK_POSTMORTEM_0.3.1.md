# Super SOL v0.3.1 provisional benchmark postmortem

Date: 2026-07-11

## Decision

The provisional result is a real regression signal and a failed promotion result for the tested
Super SOL configuration. It is not a clean estimate of the plugin-only causal effect because the two
Codex arms did not use symmetric configuration loading. No performance claim may be made from this
run.

## Observed results

The scheduled experiment had 32 slots across four arms. Twenty-six results were valid when the
provisional report was produced; six Claude slots stopped at a session-limit 429 and remained missing.

| Arm | Mean score | Full pass | Mean tokens | Mean time |
| --- | ---: | ---: | ---: | ---: |
| Codex raw | 94.0 | 75% | 296k | 102s |
| Codex + Super SOL | 85.4 | 38% | 395k | 126s |
| Claude raw | 90.0 | 80% | 73k | 47s |
| Claude + Fablize | 90.3 | 60% | 109k | 61s |

For the paired Codex cells, Super SOL was 8.5 score points lower, used about 98.9k more tokens, and
took 23.7 seconds longer on average. The reported bootstrap interval for the score delta was negative,
while the sign test remained underpowered at the small sample size. These observations are sufficient
to reject the tested configuration, not to generalize a universal effect size.

## Where quality regressed

All measured score regressions came from three tasks whose visible tests passed:

- T105 made a shallow defensive copy and retained nested aliases instead of isolating caller-owned
  state.
- T106 returned the requested error code for an unknown command but omitted the required usage text
  on stderr.
- T107 recorded an item as attempted before success and incorrectly suppressed the required duplicate
  retry after the first attempt failed.

The pattern was semantic coverage, not failure to run visible tests. v0.3.1 observed verification but
did not focus Codex on ownership, input partitions, state transitions, and failure semantics that a
visible suite could miss.

## Where efficiency regressed

Token overhead was not a stable small hook tax. It was concentrated in a few tasks: T108 added roughly
379.7k tokens, T107 about 229.1k, and T102 about 121.2k. This concentration is consistent with extra
configuration, skills, or procedural context causing longer trajectories on selected tasks.

## Why this was not a clean plugin-only A/B

The raw Codex command used `--ignore-user-config`. The enhanced command loaded the user's complete
Codex configuration and enabled plugin set, including multiple global plugins. Some enhanced sessions
also resolved Super SOL material through more than one cached path. The arms therefore differed in
more than Super SOL, and the large token spikes cannot be assigned uniquely to this plugin.

The independent artifact audit found zero missing artifacts and zero hidden-test leakage. That confirms
the report faithfully describes the collected records; it does not repair the asymmetric treatment.

## Corrective action in v0.4

The v0.4 candidate removes `SessionStart` context, disables implicit Super SOL skill invocation, and
injects one 154-character contract sweep only for action and debug prompts. It does not start a second
turn, retry a model, select a model, create a subagent, or call an API.

A new clean-room runner creates raw and lean homes from the same minimal contract, verifies exactly one
Super SOL skill path in lean and none in raw, binds the local Git revision and plugin tree, and uses the
same Codex command template and environment names. Authentication is copied only into ephemeral live
homes, excluded from evidence, and deleted after use.

T105~T108 are tuning regressions only. A positive public claim requires the separately preregistered,
sealed T109~T116 holdout and every non-inferiority, efficiency, artifact, leakage, and independent-audit
gate in [`CODEX_AB_PREREGISTRATION.md`](CODEX_AB_PREREGISTRATION.md).
