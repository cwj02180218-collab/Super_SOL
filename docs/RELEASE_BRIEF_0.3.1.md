# Super SOL v0.3.1 Release Brief

## Decision

Super SOL v0.3.1 makes
[`cwj02180218-collab/Super_SOL`](https://github.com/cwj02180218-collab/Super_SOL)
the canonical standalone repository. It preserves the existing Git history and contributor
attribution while moving active badges, installation commands, security reporting, package URLs,
and plugin metadata to the canonical location.

This release does not claim that Super SOL changes a model's intrinsic capability. Super SOL
remains a beginner-oriented Codex verification plugin plus an optional, explicitly billable
benchmark harness.

## User-visible changes

- Canonical v0.3.1 installation command:

  ```bash
  codex plugin marketplace add cwj02180218-collab/Super_SOL --ref v0.3.1
  codex plugin add super-sol@super-sol
  ```

- README and social-ready Korean visual guides explain when to use the plugin, free dry-run, and
  explicitly approved live evaluation.
- Package and plugin metadata point to the standalone repository.
- The private vulnerability reporting link points to the canonical repository. The repository
  owner must enable the GitHub feature before that endpoint becomes usable.

## Security and cost boundary

- The plugin does not read `OPENAI_API_KEY`, use an HTTP client, start an MCP server, or make an
  automatic billable model call.
- Live benchmark execution still requires the local API key, two distinct digest-pinned images,
  `--confirm-billable`, and an explicit user confirmation.
- Verifier and grader containers remain network-disabled and resource constrained at runtime.
- Container CI retains immutable Action references, a digest-pinned base image, hash-locked Python
  requirements, SPDX SBOM generation, and fail-closed Critical/High scans.
- Plugin hooks are quality guardrails, not an operating-system security boundary.

## Verification record

The final release commit must record the observed results for:

| Check | Required result |
| --- | --- |
| Ruff format and lint | pass |
| basedpyright | 0 errors |
| pytest | all tests pass |
| coverage | report retained in the release brief update |
| `uv build` | v0.3.1 wheel and source archive built |
| installed dependency audit | no known third-party vulnerabilities |
| current-tree and history credential scan | no real credential found |
| free release smoke | completes without model or API call |
| GitHub CI | CI and Container security pass on the release commit |

## Evidence claims

The visual guide's `198 tests passed` and `93% coverage` chips describe the independently reviewed
v0.3.0 snapshot that approved the visual design. Final v0.3.1 verification is reported separately
and does not silently rewrite those historical chips.

No new live benchmark is required for this metadata and documentation release, and no Fable parity
or model-performance ceiling claim is introduced.

## Owner-only follow-up

The repository owner should require pull requests and successful `CI` plus `Container security`
checks on `main`, enable private vulnerability reporting, enable dependency alerts and security
updates, and confirm secret scanning availability. Removing collaborators or rewriting authorship
is not a security control and is not part of this release.
