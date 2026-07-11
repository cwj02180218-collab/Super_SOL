# Day 0 Paired Evaluation Preregistration

This analysis is fixed before any billable live evaluation. The shadow stream and this document
must never be included in model instructions.

## Primary outcome

The primary quality outcome is the out-of-band evaluator's `final_defect_found` judgment. The
runner records this field as `null`; grading occurs later without exposing the arm or judgment to
the evaluated model.

## Frozen cells

The current default product cell is `gpt-5.6-terra/medium`; the reference cell is
`gpt-5.6-sol/medium`. A changed model or reasoning effort creates a different experimental cell and
must be recorded in the plan, start, finish, session identity, and report. Do not pool different
efforts under one model label.

Compare ON versus OFF within each model and effort. Separately compare the reference versus product
cell within the same arm. Pair by task and deterministic assignment key. For the Day 1-3 pilot, use
crossover so every task has all four model/arm cells.

## Cost guardrails and routing analysis

For every planned run, retain wall time, tool-call count, failed-verification count, gate-block
count, input tokens, and output tokens. A quality result is not interpreted without paired cost
deltas. Token volume is a proxy; dollar cost requires actual billed usage and contemporaneous
account pricing.

Report the Terra-first lazy cascade separately from observed cells. Select the product result only
when it completed and the out-of-band machine grader passed; otherwise select the Sol reference
result. The external final-defect label scores the selected route but never controls selection.
Report escalation rate, cascade quality, token volume, and token-volume savings against always
selecting the reference result. This is analysis only; the beginner plugin never changes models or
makes API calls automatically.

## Retention and interpretation

Retain completed, exhausted, error, and abandoned runs in the raw event record. The report fails
closed unless every preregistered crossover session starts, finishes, and receives exactly one
external grade. It never silently drops abandoned or incomplete sessions.

The four-task pilot validates instrumentation only. Fable parity or model-uplift claims require at
least fifty completed crossover task groups, frozen verifier and grader digests, an unpublished
versioned grader pack, externally graded outcomes, paired effect sizes with uncertainty, actual
billed cost, leakage review, and a preregistered rerun on tasks not used to tune the harness.
