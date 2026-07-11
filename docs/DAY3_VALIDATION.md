# Super Sol Day 1-3 Validation

The three-day gate validates the benchmark before it is used for product claims.
It does not treat a small pilot as evidence that GPT-5.5 exceeds Fable or GPT-5.6
Sol.

## Day 1: Comparable experiment cells

Use the crossover design so every task is run in both harness arms for both
models. The four-task pilot therefore plans sixteen isolated sessions.

```bash
uv run fablized-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir .fablized/day1 \
  --run-id day1-crossover \
  --arm-design crossover \
  --dry-run
```

The default `holdout` design remains available for longer operational sampling.
The crossover design is the credible small-sample choice because ON/OFF results
share the same tasks.

## Day 2: Out-of-band grader controls

The model-callable verifier image contains only visible workspace checks. A
separate grader image contains root-only task-specific checks under `/opt/grader/tests` and runs
once after the model turn. Its stdout and stderr never return to the model; only
a boolean enters the shadow stream. Before a live pilot, every buggy fixture
must fail and local reference controls must pass in the digest-pinned,
network-disabled grader container.

The pilot covers four failure shapes:

- local arithmetic logic;
- cached-state invalidation;
- filesystem traversal containment;
- a calculation split across two modules.

Reference controls exist only for local image QA. They are not published or
copied into live workspaces.

## Day 3: Quality, productivity, and lazy escalation

After the live run, an evaluator grades each session in a separate JSON file:

```json
{
  "grades": [
    {"session_id": "sha256-session-id", "final_defect_found": false}
  ]
}
```

Every planned session needs exactly one terminal event and one external grade.
Missing or duplicate evidence fails the report instead of lowering the
denominator silently.

```bash
uv run fablized-sol-report \
  --events .fablized/live/day3-live/events.jsonl \
  --grades .fablized/live/day3-live/grades.json \
  --output .fablized/live/day3-live/report.json
```

The command writes both `report.json` and the sibling `report.md`.

The report rejects anything short of the complete two-model by two-arm task
lattice. It records defect-free rate, token volume, time, tool calls, failed
verification, gate blocks, paired effects, and 95% intervals. It also computes
an operational lazy cascade: use GPT-5.5 first and escalate only when the
baseline run fails completion or its out-of-band grader. External human defect
labels score the resulting route but never decide it. The cascade reports
quality, escalation rate, and token-volume savings against always using the
reference model.

Token volume is a cost proxy, not a dollar claim. Dollar cost should be added
only from the actual billed usage and current account pricing.

## Promotion gate

Do not claim parity with Fable from the four-task pilot. Promotion requires at
least fifty completed crossover task groups, externally graded outcomes, paired
effect sizes with uncertainty, an unpublished grader pack, and frozen verifier
and grader digests. Until then, the result supports harness engineering
decisions only.
