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

## Observed verification record

| Command or check | Observed result |
| --- | --- |
| `uv run ruff format --check .` | 89 files already formatted |
| `uv run ruff check .` | All checks passed |
| `uv run basedpyright` | 0 errors, 0 warnings, 0 notes; shipped hook scripts included |
| `uv run pytest --cov=fablized_sol --cov-report=term-missing` | 195 passed; 93% total coverage |
| `uv build` | `super_sol_harness-0.3.0` wheel and source archive built |
| plugin validator | `Plugin validation passed` |
| skill validator | `Skill is valid!` |
| isolated stock-Codex install | marketplace add, plugin add/list at 0.3.0, plugin remove, marketplace remove all exit 0 |
| crossover dry-run | 16 plans, 16 unique sessions, one recomputed run digest, canonical identity on every plan |
| live without `--confirm-billable` | exit 2 before output directory creation |
| configured hook runtime | `/usr/bin/python3` 3.9.6 executed the hook tests successfully |
| container controls | four intentionally broken fixtures rejected; all 16 historical solved workspaces accepted |

The local container audit built both roles from
`python:3.12-alpine@sha256:6d43704baacd1bfbe7c295d7f13079d5d8104ed33568873133f8fc69980419df`.
Docker Scout reported `0 Critical / 0 High` for both images and indexed 57 packages; each SPDX document
contains 58 packages.

| Role | Audited OCI digest | SBOM path | SBOM SHA-256 |
| --- | --- | --- | --- |
| verifier | `sha256:5da9bd46c355f55b4eb30d70cd3f20867cdc23cbac0447a585e79fa065d56ad5` | `security/sbom/verifier.spdx.json` | `7767e144d06f0b2a529d4706ce40246c702c77ad172b991c4622637194426df4` |
| grader | `sha256:2eac99cd44b8726bac3de3a6a5d89d0d576c53aa6e573ac06573e5ec70c7126e` | `security/sbom/grader.spdx.json` | `f44652afe683049fc966f01b823fa28e6040daa91042d01a2dc039f53fb44320` |

The verifier Dockerfile hash is
`5946ca18a919f9513b39db4af7a5f3292664c4fec900362f61145b4508f61130`, the grader Dockerfile hash is
`4d707ec07522007f1c6a3c6258839fe98a0256d00e16d0795c5e6a1a98576407`, and their shared locked
requirements hash is `370d57e152e28cb91c2daabd58df5a53c4a0104ea57d8b31b61d6f47f3f993c0`.

## Independent review

Five stock-Codex lanes cover code, beginner experience, reproducibility, release/package readiness,
and hands-on QA. The final tag is created only after the table below contains no open blocker.

| Lane | Latest result | Disposition |
| --- | --- | --- |
| Code correctness | Recheck pending | complete current `uv run` value-option parser fix added |
| Beginner experience | Conditional | all documentation findings resolved; formal tag must exist before public install |
| Reproducibility | PASS | canonical run/session/cell/role/arm identities reject coordinated substitution |
| Release/package | PASS | archives, versions, install flow and this observed evidence record verified |
| Hands-on QA | PASS | changed surface, full suite, build, validators, install and CLI behavior observed |

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
