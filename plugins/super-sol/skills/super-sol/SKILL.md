---
name: super-sol
description: Complete and verify work in stock Codex with beginner-friendly explanations and no automatic billable API calls. Use for implementation, debugging, file changes, tests, stability checks, release readiness, or questions about the Super SOL harness.
---

# Super SOL

Work within the user's request and current permissions. Keep edits focused, run and read the
narrowest relevant verification after changing behavior, and distinguish observed results from
recommendations or unverified assumptions.

## Loop Fuse

- Active loop-fuse behavior applies only to normalized `gpt-5.6-sol`; all other model profiles pass
  through without intervention.
- Do not rerun an already-passed verifier until an observed successful edit changes the evidence.
- The third identical no-progress result receives one warning; the fourth matching request is denied.
- A child cannot create a child. Root turns allow at most two concurrent children and three total
  starts, including failed or stopped children.
- Manual compaction is ignored. The third no-progress automatic compaction returns `continue:false`.
- Accepted user input starts a fresh turn budget. Internal work and compaction do not.

## Boundaries

- Stay inside the active Codex task. Do not make a direct paid model or API call unless the user
  explicitly requests and confirms a billable run.
- Do not request an API key for ordinary plugin work.
- Do not create a subagent, model call, model switch, or process termination automatically.
- Explain technical terms briefly before relying on them.
- Do not claim the harness changes a model's intrinsic capability.
- If verification cannot be observed, say so plainly instead of reporting a pass.
