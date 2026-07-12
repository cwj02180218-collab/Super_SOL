# Super SOL v0.6 benchmark postmortem

Date: 2026-07-13  
Study: six-cell Orca crossover, T109-T116, two repetitions, 96 valid observations

## Result

| Comparison | Mean score delta | 95% bootstrap CI | Full pass | Token ratio | Wall-time ratio |
|---|---:|---:|---:|---:|---:|
| Terra + Super SOL vs raw | Terra -0.71 | [-6.09, 4.51] | 8/16 vs 9/16 | 1.07 | 1.12 |
| Sol + Super SOL vs raw | Sol +2.53 | [-1.28, 6.70] | 12/16 vs 10/16 | 1.07 | 1.29 |

Neither model established reliable uplift. Both confidence intervals include zero. Both exceeded
the desired token ratio <= 1.05, and both exceeded the wall-time ratio <= 1.10. Terra also lost one
full pass. The v0.6 result is therefore a failed stable-promotion attempt, not evidence of a better
default.

## What failed

- T109 improved by 17.5 points twice on both models even though it naturally passed through.
- T112 received concurrency guidance without a quality gain.
- T113 alternated between gains and a 13.06-point Sol regression.
- T115 regressed Terra by 20 points in both repetitions.
- Up-front procedures increased token use by about 7% and Sol wall time by about 29%.

The key lesson is that more procedure is not automatically more capability. An early checklist can
displace a correct raw plan or broaden a patch. v0.7 therefore keeps raw reasoning first and spends
at most one bounded intervention only after observed edit and verification evidence.

## Claim boundary

These disclosed tasks informed the redesign and cannot validate v0.7. Only a separately frozen
T117-T124 holdout may decide promotion. The RC is not a performance-uplift claim.
