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

For the Day 1-3 pilot, use the crossover arm design so each task has all four model/arm cells.
Report the GPT-5.5-first lazy cascade separately from the observed cells: a baseline result is used
only when it completed and the out-of-band machine grader passed; otherwise the reference result is
selected. The external final-defect label scores the selected route but never controls selection.
Report escalation rate, cascade quality, token volume, and token-volume savings against always
selecting the reference result.

## Retention And Interpretation

Retain completed, exhausted, error, and abandoned runs in the raw event record. The confirmatory
report fails closed unless every preregistered crossover session starts, finishes, and receives an
external grade; it never silently drops abandoned or incomplete sessions. Report effect sizes and
uncertainty for quality and cost outcomes. A count of 50 sessions alone is not evidence and cannot
support a claim without an effect estimate and uncertainty interval.

The four-task Day 1-3 pilot validates instrumentation only. Fable parity or model-uplift claims
require at least fifty completed crossover task groups, frozen verifier and grader digests, an
unpublished grader pack, externally graded outcomes, paired effect sizes with uncertainty, and a
leakage review.
