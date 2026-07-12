# Super SOL 0.7.0rc1 candidate brief

Date: 2026-07-13  
Status: release candidate; holdout pending

## Candidate contract

- Package: `0.7.0rc1`
- Plugin: `0.7.0-rc1`
- Runtime: raw-first; one model-visible injection maximum per turn
- Context limit: 220 Unicode code points
- Automatic model calls, model switches, subagents, and test retries: zero
- Persisted prompt, source, command, output, and environment bytes: zero

## Prior evidence

The disclosed v0.6 crossover produced Terra -0.71 points with CI [-6.09, 4.51] and Sol +2.53 points
with CI [-1.28, 6.70]. Token ratios were 1.07 for both; wall-time ratios were 1.12 and 1.29. This
motivated the redesign but cannot validate it.

## Gate 0 and claim boundary

| Check | Observed result |
|---|---|
| Full Python suite | 273 passed |
| Plugin suite | 62 passed |
| Coverage | 90.15%, floor 90% |
| Ruff and basedpyright | clean; 0 errors and 0 warnings |
| Package build | `0.7.0rc1` wheel and sdist built |
| Production dependency audit | no known vulnerabilities found |
| Archive privacy | 177 sdist and 50 wheel members; 0 forbidden members |
| Tracked secret shapes | 0 production matches |
| Isolated plugin lifecycle | install, remove, reinstall; one `0.7.0-rc1` plugin and one skill |
| Hook performance | 200 real invocations within the frozen absolute and incremental p95 gates |
| Local container refresh | images built; Docker Scout remote pull stalled with no result |

The local container result is infrastructure-censored, not a pass. RC publication remains blocked
until the GitHub container-security workflow scans both images successfully. The candidate SHA is
recorded in the benchmark preregistration generated immediately after the freeze commit.

Stable promotion requires the frozen T117-T124 four-cell crossover with 64 valid slots and every
gate in `V0.7_PROMOTION_PROTOCOL.md`. Until that audit completes, this RC is not a
performance-uplift claim and v0.3.1 remains the stable release.
