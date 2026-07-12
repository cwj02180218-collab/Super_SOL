# Super SOL 0.6.0rc1 free Gate 0 brief

Date: 2026-07-12  
Status: diagnostic candidate; no paid performance result

## Candidate identity

- Candidate code and metadata commit: `2bb0933541f095a052600cc2c66445a6a1cd7c6f`
- Package: `0.6.0rc1`
- Plugin: `0.6.0-rc1`
- `uv.lock` SHA-256: `54f9d9a113cccf5d54ddb85d19a04ca99604d8b0b9615b33bca99f8138971030`
- Verifier image: `super-sol-verifier@sha256:f993250850f26d40f73f8b98c668a0ba2c4477ef452ca900d5075504d774a357`
- Grader image: `super-sol-grader@sha256:5dc6b3201e10a1c578b06a6de11483678fd097198b009b77decbe44cda39e134`
- Temporary verifier SBOM SHA-256: `20950b67b7c6d71d6543cbf4fd5ae36218e4b7a168c455bd98fd179a0e08bcfa`
- Temporary grader SBOM SHA-256: `4001facdb1f1cdd43c7ff922c60919719c2bab8f28a80657427bfd413f4755c2`

## Observed verification

| Check | Result |
|---|---|
| Full Python suite | 255 passed |
| Plugin suite | 45 passed |
| Coverage | 90.15%, floor 90% |
| Ruff lint and format | clean |
| basedpyright | 0 errors, 0 warnings |
| Package build | wheel and sdist built as `0.6.0rc1` |
| Archive privacy | no `.env`, `auth.json`, `.fablized`, or session member |
| Tracked secret shapes | 0 matching credential files |
| Production dependency audit | no known vulnerabilities found |
| Isolated plugin lifecycle | install, remove, reinstall; one plugin and one skill |
| Container scan | verifier and grader each `0C 0H 0M 0L` |

## What changed

- General failure-atomicity routing now recognizes all-or-nothing persistence, staged commit,
  temporary replacement, cleanup after mid-operation failure, and duplicate side-effect prevention.
- Negative tests keep generic retry and configuration work on pass-through.
- `router-observe` records the natural route but emits no procedure or repair.
- `procedure-forced` applies one independently selected frozen pack without changing the prompt.
- Invalid diagnostic environment controls fall back to adaptive behavior and are recorded privately.
- Normal users remain on adaptive mode. No automatic model switch, API call, subagent, or retry was
  added.

## Claim and paid boundary

No v0.6 model slot was executed. The 64-slot T109-T116 study is diagnostic-only and cannot promote
the product. A performance claim requires the diagnostic routing gates to pass first, followed by an
independently authored sealed T125-T132 holdout, a new preregistration, independent audit, and fresh
billable approval.

Remaining risks include phrase-based routing false positives, externally supplied forced-label
quality, Terra/medium capability ceilings, Linux-arm64-only local container evidence, and the absence
of any v0.6 quality-uplift result. Diagnostic environment variables are measurement controls, not a
security boundary.
