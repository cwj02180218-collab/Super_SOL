---
description: Run a Super SOL paired evaluation — dry-run by default; live billable runs only with explicit confirmation.
argument-hint: "[manifest.json] [--live]"
---

Run a paired evaluation with the Super SOL harness, following the `super-sol`
skill (sections 1–2) exactly.

1. If `$ARGUMENTS` names a manifest file, use it; otherwise use
   `eval/tasks.example.json` inside `${CLAUDE_PLUGIN_ROOT}`.
2. Default to a **dry run** with a fresh timestamped `--run-id`. Show the
   command, run it, and summarize the planned sessions from
   `events.jsonl` (models, arms, task count).
3. Only when the user explicitly passed `--live` or asked for a live run:
   verify the fail-closed preconditions from the skill (API key, digest-pinned
   images present locally, Docker), state that the run is **billable and may
   modify copied task workspaces**, and get an explicit confirmation before
   executing. If any precondition is missing, report exactly what is missing
   and stop.
4. After a live run completes, offer `/super-sol:report` on the run directory.
