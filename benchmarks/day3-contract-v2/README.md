# Day 3 Contract-v2 Pilot

This directory publishes aggregate evidence from the final
`day3-live-sol-contract-v2` crossover run. Raw workspaces, model output,
ledgers, environment files, and API credentials are intentionally excluded.

## Observed result

| Model | Arm | Completed | Grader passed | Quality | Tokens |
| --- | --- | ---: | ---: | ---: | ---: |
| GPT-5.5 | OFF | 4/4 | 4/4 | 100% | 10,346 |
| GPT-5.5 | ON | 4/4 | 4/4 | 100% | 10,586 |
| GPT-5.6 Sol | OFF | 4/4 | 4/4 | 100% | 11,657 |
| GPT-5.6 Sol | ON | 4/4 | 4/4 | 100% | 12,439 |

Across both arms, GPT-5.5 used 20,932 tokens and GPT-5.6 Sol used 24,096.
The GPT-5.5-first lazy route escalated zero of four tasks and used 11.2% fewer
tokens in the OFF arm and 14.9% fewer in the ON arm than always using the
reference model.

## Interpretation boundary

All sixteen sessions completed and passed the out-of-band grader. Both models
therefore scored 100% on this four-task pilot. The ON arm did not improve
quality and used more tokens on average for both models.

This result validates benchmark plumbing and supports the baseline-first routing
hypothesis. It does not establish Fable parity, general GPT-5.5 superiority, or
a quality uplift from Super SOL. Promotion requires the larger evidence gate in
[the Day 7 review](../../docs/DAY7_REVIEW.md).

`report.json` is the frozen machine-readable v0.2.1 report. It predates the v0.3 provenance and
reasoning-effort schema and is intentionally not accepted by the current `super-sol-report` parser.
No missing effort or provenance has been guessed during migration.
