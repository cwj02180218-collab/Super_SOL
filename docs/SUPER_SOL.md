# Super Sol Profile

Super Sol is the merged operating profile for `fablized-sol` and
`cuj0218/GPT.C`.

It keeps `fablized-sol` as the measured product surface and treats GPT.C as the
Codex operational reference surface. That split matters: GPT.C's wrapper and
ontology are useful for how Codex work should feel, while `fablized-sol` owns the
stricter benchmark evidence boundary.

## Adopt Now

- Verification must be newer than the latest code mutation.
- Live verification must run inside a digest-pinned Docker image.
- Only typed local tool results receive mutation or verification credit.
- Holdout labels and shadow-stream measurements stay outside model context.

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
2. Build or load a local verifier image pinned by immutable digest.
3. Run a small live pilot with `OPENAI_API_KEY` and `VERIFICATION_IMAGE` set only
   in the local shell.
4. Grade `final_defect_found` out of band; the runner intentionally records it as
   `null`.
