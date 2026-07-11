# Super SOL v0.3.0 Release Brief

Date: 2026-07-11

## Release decision

**GO** for the stock-Codex plugin and optional offline/dry-run harness. **HOLD** for a new live model
performance claim, Fable parity, or model-superiority marketing.

## What ships

- A beginner-facing Codex plugin that automatically supplies work/verification guidance inside the
  current task.
- No API key dependency, background service, automatic subagent, model switch, effort switch, or
  automatic billable call in the everyday path.
- An optional Python 3.12 benchmark CLI with explicit paid-run confirmation, digest-pinned verifier
  and grader images, crossover arms, external grading, and machine-readable reports.
- A canonical v3 run identity whose digest is independently recomputed during reporting. The identity
  includes task content, preregistration content, harness content, dependency lock, resolved runtime,
  Python/platform, model/effort cells, arm design, retries, and image references.
- Hash-locked container dependencies, exact base-image digest, CI/local build gates, and SPDX SBOMs.

## Model guidance

The plugin does not choose models. The documented default is GPT-5.6 Terra at medium effort for most
work, with GPT-5.6 Sol as an explicit escalation for difficult open-ended work. This is guidance, not
an automatic router and not a benchmark result from this release.

## Verification record

Release verification covers:

- Ruff formatting and lint;
- basedpyright strict typing, including shipped hook scripts;
- the complete pytest suite with coverage;
- wheel and source archive construction and contents;
- official plugin and skill validators;
- isolated marketplace add/install/list/remove;
- free crossover dry-run and refusal of live execution without explicit confirmation;
- actual `/usr/bin/python3` hook execution on macOS;
- verifier and grader container build controls plus committed SPDX evidence.

Exact final command counts and commit/tag are recorded in the published Git ref and CI run rather than
hard-coded before the release commit exists.

## Independent review

Five stock-Codex lanes cover code, beginner experience, reproducibility, release/package readiness,
and hands-on QA. The release is tagged only after all actionable findings are fixed and the same five
lanes receive the final commit for recheck.

## Known limits

- Hook-based mutation tracking covers the documented Codex edit tools; arbitrary shell and MCP changes
  may not be observed.
- A warning does not force the model to continue, which intentionally avoids hidden extra usage.
- The committed v0.2.1 pilot is historical and cannot be upgraded into v3 provenance after the fact.
- No billable v3 live run is part of v0.3.0, so no new performance ceiling claim is made.
- Image SBOMs describe the locally audited image subjects. A future public live pilot must preserve an
  evidence manifest binding its registry image digests and SBOM hashes to that run.

## Install, update, rollback

Install the formal release with `--ref v0.3.0`, then add `super-sol@super-sol`, restart Codex, and
inspect `/hooks`. Updating or rolling back a tag-pinned installation requires removing the plugin and
marketplace, re-adding the desired plugin-bearing tag, adding the plugin again, listing it, restarting,
and reviewing the hook path/events. Tags before v0.3.0 do not contain this Codex plugin.
