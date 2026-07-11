# Security Policy

## Supported version

Security fixes target the latest tagged release and `main`.

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/cuj0218/Super-SOL/security/advisories/new).

Do not open a public issue containing API keys, environment files, raw live workspaces, model output
that may contain private data, or verifier/grader bypass instructions. Revoke any credential that
may have been exposed before sharing a redacted reproduction.

## Beginner plugin boundary

The Super SOL Codex plugin is local and has no OpenAI SDK, HTTP client, remote MCP server,
background service, or automatic subagent. It does not read `OPENAI_API_KEY` and never initiates a
billable model evaluation. State contains only a random-session hash, timestamps, route label, and
verification booleans; prompts, commands, tool output, model output, paths, and environment values
are not retained. State files are created owner-only under the plugin data directory.

The hook blocks recognized direct OpenAI API and unconfirmed Super SOL live-evaluation commands,
but hooks are quality guardrails rather than an operating-system security boundary. They cannot
prove interception of every future tool, nested script, user-authored binary, or external
integration. Use Codex permissions, sandboxing, network policy, and organization controls for hard
enforcement. Review and trust plugin hooks before enabling them.

## Benchmark trust boundary

The model-callable verifier and out-of-band grader must be different digest-pinned images. Both run
without network access or the parent process environment. The grader workspace is read-only and its
tests and output never return to the model. Only registered local tools with typed results
participate in the deterministic evidence gate; arbitrary hosted tools do not receive evidence
credit.

Both example images pin one reviewed base digest. The release audit builds each image, fails closed
on Docker Scout Critical/High findings, and emits SPDX 2.3 SBOMs under `security/sbom`. Re-run the
audit for every new digest or downstream image. The current SBOM is point-in-time evidence, not a
guarantee that the same digest remains vulnerability-free forever.

## Secrets and release artifacts

- Keep API keys only in the local shell and never commit `.env` or live output.
- Do not publish raw model workspaces, grader output, hidden tests, or prompt-bearing logs.
- Publish aggregate benchmark evidence only after leakage review.
- Treat third-party Actions, base images, and scanner output as supply-chain inputs that require
  immutable references and periodic refresh.
