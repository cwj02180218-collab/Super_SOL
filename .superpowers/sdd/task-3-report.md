# Task 3 Report: UserPromptSubmit Fast Path

## Outcome

Implemented a bounded, conservative `UserPromptSubmit` dispatcher without weakening the approved
absolute p95 below 100 ms or incremental p95 below 70 ms gates.

The configured prompt command now invokes `prompt_dispatcher.py`. Clearly generic, valid prompt
events exit silently without importing `super_sol_routes` or `super_sol_state`. All other inputs
delegate to `super_sol_hook.process_raw`, including non-prompt events, malformed or oversized JSON,
diagnostic environments, secret-shaped prompts, billing/control phrases, explicit Super SOL
controls, and every phrase in both production signal tables.

The full hook owns JSON error handling and all existing routing/state-machine behavior. The
dispatcher does not persist or cache prompt data.

## TDD Evidence

- Initial dispatcher run: 5 failed and 12 errors because `prompt_dispatcher.py` did not exist.
- First green dispatcher run: 17 passed.
- Prompt parity, lifecycle, state-machine, and model-gate focused run: 54 passed in 10.30 seconds.
- Final focused dispatcher run after conservative guard compression: 17 passed in 0.97 seconds.
- The exhaustive signal test derives every phrase from both live production signal tables and
  requires each one to delegate to the full processor.
- Dispatcher/full-hook parity covers generic, specialist, explicit-control, secret, and malformed
  prompt inputs.

## Performance Gate

`tests/plugin/test_v07_budgets.py` ran 300 configured prompt-command samples and 150 empty Python
floor samples with the unchanged inclusive percentile calculation. Result: 3 passed in 20.47
seconds, including both `<100 ms` absolute and `<70 ms` incremental p95 assertions.

The prior debug sample dump was removed because it violated Ruff. Consequently the successful run
proved both thresholds but did not print the individual p95 numbers; no outliers were deleted and
the percentile math was not changed.

## Privacy And Safety

- Preserved the uncommitted all-profile Sol, Terra, Luna, missing-model, and malformed-model privacy
  test coverage.
- Preserved the 4096-byte state-file ceiling and raw fixture exclusion checks.
- Secret-shaped inputs and billing authorization/control prompts always use the full hook.
- Diagnostic environment variables always use the full hook.
- Malformed, oversized, and non-prompt events always use the full hook.

## Verification Notes

- Focused Ruff check reported `All checks passed!` before the final phrase-only guard additions.
- Focused basedpyright reported 0 errors, 0 warnings, and 0 notes before those phrase-only additions.
- A complete plugin/package run initially found the compressed guard omitted four production
  phrases. Those exact phrases were added, and the exhaustive dispatcher suite then passed 17/17.
- A final complete plugin/package invocation was interrupted after progress output and did not
  provide a captured completion summary, so this report does not claim a final full-suite pass.
