# Super SOL 0.8.0rc1 candidate brief

Date: 2026-07-13  
Status: local Gate 0 passed; CI and Sol/high validation pending

## Candidate contract

- Package: `0.8.0rc1`
- Plugin: `0.8.0-rc1`
- Active profile: normalized model identifier exactly `gpt-5.6-sol`
- Non-Sol profiles: observation-only, with zero model-visible context
- Runtime: raw-first; at most one context after observed edit plus verification
- Context limit: 180 Unicode code points
- Extra model calls, model switches, subprocesses, subagents, retries, and test reruns: zero
- Persisted prompt, source, command, output, model output, environment value, path, and secret bytes: zero

Terra, Luna, missing model metadata, malformed model metadata, and unknown model identifiers retain
secret-shaped prompt and billable-command safety checks without semantic intervention. The shipped
`prompt_dispatcher.py` hook remains a bounded local fast path; guarded inputs delegate to the full
hook and no hook makes an additional API call.

## Evidence boundary

No confirmatory v0.8 Sol/high model slot has been executed. Sol/high validation is pending, and this
candidate is not a performance-uplift claim. The prior v0.6 Sol result was not confirmatory and its
confidence interval included zero. Stable promotion may claim only noninferior quality with bounded
overhead after every gate in [V0.8 promotion protocol](V0.8_PROMOTION_PROTOCOL.md) passes. Quality
uplift was not proven.

## Gate 0 record

The immutable local candidate is `e5cb8065c1db665c2d87d0acbec65070d9a4e097`. Fresh observations
from that candidate are:

| Gate | Observed result |
|---|---|
| Locked environment | 60 packages resolved; 58 installed packages checked |
| Full test and coverage gate | 319 passed; 90.10% combined package and hook line coverage |
| Ruff | lint clean; all 108 Python files formatted |
| basedpyright | 0 errors, 0 warnings, 0 notes |
| Distribution build | wheel and sdist built successfully |
| Archive privacy | 50 wheel members; 183 sdist members; 0 forbidden runtime or T125-T136 artifacts |
| Production dependency audit | 0 known vulnerabilities in the locked non-development dependency export |
| Tracked production secret shapes | 0 matches in `src`, `plugins`, `eval`, and `.github` |
| Hook performance | 300 hook and 150 floor samples; 60.078 ms absolute p95; 37.725 ms incremental p95 |
| Verifier container | 57 packages; 0 Critical, High, Medium, or Low vulnerabilities |
| Grader container | 57 packages; 0 Critical, High, Medium, or Low vulnerabilities |
| Isolated plugin lifecycle | install, list, remove, reinstall, and list passed |
| Installed topology | 1 enabled plugin, 1 skill, 3 hook groups, and no unrelated configuration |

The dependency audit uses a locked production export with the local editable project omitted;
auditing the repository environment directly is not a valid production result because `pip-audit`
rejects the editable root distribution. Test fixtures contain deliberate non-live secret-shaped
strings, so the release-blocking scan is scoped to tracked production and workflow paths.

Local Gate 0 is complete. GitHub CI and container checks must still pass before the RC tag is
published. No confirmatory T125-T136 slot has run, no uplift is claimed, and `v0.3.1` remains the
stable release until the promotion protocol is satisfied.
