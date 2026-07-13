# Super SOL v0.8 confirmatory benchmark

This directory contains the public, aggregate evidence used to decide the `v0.8.0` stable promotion.
The design is a 12-task, four-arm, two-repetition crossover with complete within-model pairing.

- `analysis.json`: preregistered paired estimates and promotion-gate decisions
- `audit.json`: fail-closed lattice, provenance, retry, and contamination audit
- `attempts.csv`: 103 redacted attempts, including seven censored observations and retry links
- `slots.csv`: 96 valid scored observations without local worktree paths
- `slots.json`: the same 96 valid observations in redacted structured form
- `manifest.json`: hashes for the generated aggregate output set
- `preregistration.json`: frozen design before task-pack execution
- `preregistration-amendment-1.json`: prospective operational amendment
- `scoring-amendment-1.json`: prospective scoring clarification
- `brief-en.md`, `brief-ko.md`: short generated summaries

The candidate code is the immutable `v0.8.0-rc1` tag. Seven infrastructure-censored attempts are
preserved as unscored rows in the redacted `attempts.csv` ledger. Their linked replacements are
represented in `slots.csv` and `slots.json`. Detailed private records containing machine-local paths,
prompts, or model payloads are not published.

The stable claim is limited to noninferior quality with bounded overhead. Quality uplift was not
proven on this task pack.
