---
description: Bootstrap Super SOL (uv + Python 3.12 + locked deps) and prove it with an offline dry-run smoke.
---

Run the automated bootstrap and report the result:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh"
```

- On success, relay the smoke summary line (`Smoke OK: ...`) and mention the
  next steps: `/super-sol:eval` for evaluations, `/super-sol:report` for
  aggregation.
- If `uv` is missing, the script prints install instructions and exits
  nonzero. Relay the instructions and stop — installing uv is the user's
  decision (global install).
- Never run a live (billable) evaluation from this command.
