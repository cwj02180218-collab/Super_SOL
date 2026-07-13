# Super SOL 0.8.0rc1 candidate brief

Date: 2026-07-13  
Status: release candidate; Gate 0 and Sol/high validation pending

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

Task 4 records the candidate metadata and contract only. Task 5 must add fresh observed results for
the full suite, plugin suite, coverage, static checks, archive inspection, dependency and secret
audits, isolated lifecycle, hook p95 measurements, and CI/container-security workflows. Until those
observations exist, this brief makes no release-readiness claim and `v0.3.1` remains the stable
release.
