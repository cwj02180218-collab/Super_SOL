# Day 0 Paired Evaluation Preregistration

This analysis is fixed before any billable live evaluation. The shadow stream and this document
must never be included in model instructions.

## Primary Outcome

The primary quality outcome is the out-of-band evaluator's `final_defect_found` judgment. The
runner records this field as `null`; grading occurs later without exposing the arm or judgment to
the evaluated model.

## Cost Guardrails

For every planned run, retain wall time, tool-call count, failed-verification count, gate-block
count, input tokens, and output tokens. A quality result is not interpreted without its paired
cost deltas.

## Comparisons

Compare ON versus OFF within each model. Separately compare GPT-5.6 Sol versus the baseline model
within the same arm. Pair comparisons by task and deterministic assignment key; do not pool across
arms or models in a way that breaks the pairing.

## Retention And Interpretation

Include completed, exhausted, error, and abandoned runs in the analysis. Report effect sizes and
uncertainty for quality and cost outcomes. A count of 50 sessions alone is not evidence and cannot
support a claim without an effect estimate and uncertainty interval.
