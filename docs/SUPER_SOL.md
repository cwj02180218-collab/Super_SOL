# Super Sol Profile

Super Sol is the merged operating profile for `fablized-sol` and
`cuj0218/GPT.C`.

It keeps GPT-5.5 plus `fablized-sol` as the measured product surface. GPT-5.6
Sol uses the same adapter only as a controlled model comparator, while GPT.C
plus Codex CLI remains a separate operational reference whose scores are never
pooled with this benchmark. GPT.C's wrapper and ontology inform procedure
choices; `fablized-sol` owns the stricter benchmark evidence boundary.

## Adopt Now

- Verification must be newer than the latest code mutation.
- Model-callable verification and out-of-band grading must use separate,
  digest-pinned Docker images.
- Only typed local tool results receive mutation or verification credit.
- Holdout labels and shadow-stream measurements stay outside model context.
- Lazy routing is measured as a GPT-5.5-first operational cascade, with GPT-5.6
  Sol selected only when completion or the out-of-band grader fails.

## Park For Evidence

- Promise-without-action regexes.
- Repeated-failure disclosure heuristics.
- Global always-on policy blocks copied from GPT.C.

These may become useful Codex wrapper behavior after holdout evidence, but they
are not completion evidence in the benchmark harness.

## Reject

- Treating command output text or model prose as verification credit.
- Treating fail-open parser or verifier errors as successful completion.
- Mixing GPT.C wrapper runs and `fablized-sol` verifier runs into one score.

## Day 0 Execution Path

1. Run dry-run smoke to confirm manifest parsing, paired model assignment, and
   Super Sol profile metadata.
2. Build separate verifier and grader images pinned by immutable digests.
3. Run a small live pilot with `OPENAI_API_KEY`, `VERIFICATION_IMAGE`, and
   `GRADER_IMAGE` set only in the local shell.
4. Grade `final_defect_found` out of band; the runner intentionally records it as
   `null`.

## Day 1-3 Validation

The next gate adds task-level ON/OFF crossover cells, an out-of-band grader,
and a fail-closed quality and efficiency report. It also measures a lazy
baseline-first cascade that escalates GPT-5.5 failures to the GPT-5.6 Sol
reference instead of paying for the reference model on every task.

See [DAY3_VALIDATION.md](DAY3_VALIDATION.md) for the commands, evidence boundary,
and promotion threshold.
