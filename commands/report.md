---
description: Aggregate a Super SOL run into a report and summarize it within the evidence boundary.
argument-hint: "[run directory]"
---

Aggregate and interpret a Super SOL run, following the `super-sol` skill
(section 3).

1. Resolve the run directory from `$ARGUMENTS`; if absent, list run
   directories under `${CLAUDE_PLUGIN_ROOT}/.fablized/` and ask which one.
2. Run:
   ```bash
   cd "${CLAUDE_PLUGIN_ROOT}" && uv run super-sol-report --run-dir <run-dir>
   ```
3. Summarize the emitted report: per-cell quality rate and token volume, then
   paired effects **with confidence intervals**. State plainly when a CI
   crosses zero ("not established").
4. End every summary with the interpretation boundary: below the preregistered
   promotion threshold, results are pilot/engineering evidence — never a
   parity, superiority, or leaderboard claim.
