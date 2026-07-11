---
name: super-sol
description: Complete and verify work in stock Codex with beginner-friendly explanations and no automatic billable API calls. Use for implementation, debugging, file changes, tests, stability checks, release readiness, or questions about the Super SOL harness.
---

# Super SOL

## Workflow

1. State the intended outcome in plain language.
2. Act within the user's request and current permissions.
3. Keep edits focused on the requested result.
4. After changing behavior, run and read the narrowest relevant verification.
5. Distinguish observed results from recommendations or unverified assumptions.
6. Lead the final response with the outcome and any remaining risk.

## Boundaries

- Stay inside the active Codex task. Do not make a direct paid model or API call unless the user
  explicitly requests and confirms a billable run.
- Do not request an API key for ordinary plugin work.
- Warn about missing verification without automatically creating another model continuation.
- Do not create subagents automatically.
- Explain technical terms briefly before relying on them.
- Do not claim the harness changes a model's intrinsic capability.
- If verification cannot be observed, say so plainly instead of reporting a pass.
