# Super SOL v0.9.0-rc1 release brief

Status: local Gate 0 and Gate 1 passed for product candidate
`ec5a153e1487065f3f3a33aab5394ed48f453377`; evidence-only wording and record updates follow the
candidate and do not change product behavior; publication was not performed

## Candidate contract

- Package: `0.9.0rc1`
- Plugin: `0.9.0-rc1`
- Packaged release root: `fablized_sol/_release/v0_9/`
- Active model gate: normalized `gpt-5.6-sol`; non-Sol profiles pass through.
- Passed verifier replay is blocked until edit.
- The third identical no-progress result warns; fourth blocks.
- Maximum depth is one; maximum 2 concurrent children; maximum 3 total starts including failures.
- Manual compaction is excluded. The third no-progress automatic `PostCompact` returns
  `continue:false`.
- Accepted user input resets the turn budget; internal work and manual compaction do not.

No process killer, `Stop` hook, retry, continuation, substitute model, or replacement agent is
shipped. An in-flight sampler cannot be interrupted before a lifecycle hook. The candidate does not
repair Codex Desktop cancellation or OS process cleanup.

## Gate 0

Attempt 5 passed for the frozen product candidate
`ec5a153e1487065f3f3a33aab5394ed48f453377`.

| Check | Observed result |
| --- | --- |
| Full suite and coverage | `465 passed in 40.87s`; `90.56%` coverage; exit 0 |
| Ruff | lint clean; 147 files already formatted; both exits 0 |
| basedpyright | 0 errors, 0 warnings, 0 notes; exit 0 |
| Distribution build | `0.9.0rc1` wheel and sdist built; exit 0 |
| Archive inventory/privacy | 27/27 required assets in both; 133 sdist files, 81 wheel files; 0 missing, forbidden, or byte mismatches |
| Installed-wheel CLI | dependency-complete disposable install; approved latency CLI options and packaged manifest present |
| Dependency lock | exact SHA-256 match `c82fc4b58a9661d3b4adde7751b744d948758029ac53f9b8b0de78b0fe89e39e` |
| Tracked production privacy | 99 files scanned; 0 secret-shape, local-path, or forbidden-name matches |
| Container audit | verifier and grader each indexed 57 packages and reported `0C 0H 0M 0L`; exit 0 |
| Stock Codex lifecycle | Codex `0.144.1`; install/list/remove/absence/reinstall/relist passed in a deleted temporary home |
| Installed topology | exactly 1 plugin, 1 `super-sol` skill, 7 events, 1 command per event, and 0 `Stop` events |

The privacy-safe attempt-5 latency artifact is
`benchmarks/v0.9-loop-replay/latency-attempt5.json`, with SHA-256
`6689e3b8b7d75f25ec5a5da4e2d5fcf7baf6d1d5523cbacd515a99564bdcec00`. It records 300 hook
and 150 floor samples. Hook p50/p95/p99 were
`51.8779584672302/59.684106236090884/70.47763176844444 ms`; floor p50/p95/p99 were
`21.424166508950293/25.30089111533016/40.682711384724755 ms`; paired incremental p50/p95/p99
were `30.51731240702793/37.984207982663065/49.48958753026079 ms`. The required p95 gates passed:
`59.684106236090884 < 100 ms` absolute and `37.984207982663065 < 70 ms` incremental. Its normalized
command evidence is `/usr/bin/python3`, `-S`, `$PLUGIN_ROOT/hooks/prompt_dispatcher.py`, with command
SHA-256 `d33a440ae3bce96c1231bbd5e2b7134d9e85c7192aa3445e2f3a08cc6d2673eb`.

The parent process ran the official 450-process measurement exactly once for attempt 5 after the
privacy repair. This evidence-recording pass verified that artifact unchanged and did not rerun the
official measurement.

Attempts 1-4 remain preserved textually in `gate0.json` and the Task 8 report. Attempt 1 failed two
stale provenance contracts. Attempt 2 failed report immutability and absolute latency at
`106.79754642769694 ms`. Attempt 3 failed absolute latency at `147.90276812855154 ms`. Attempt 4
passed 463 tests at 90.55% coverage with absolute p95 `59.967531589791186 ms` and incremental p95
`36.61352920462378 ms`; its original artifact SHA-256 was
`5dfb63f492a0b37559998d6a389d71917b606573d6323ac3628d24f120be235b`. The attempt-4 raw artifact
is deliberately not published because it contained a local absolute path. Its metrics and digest
remain as historical evidence, but attempt 5 is the current published artifact.

Before the final attempt-5 full-suite result, two evidence-document runs each reported 464 passes
and one failure at 90.56% coverage. They identified two stale release-brief contract phrases: the
explicit Gate 2 status wording and the packaged release root. Only this owned evidence document was
corrected; the focused contract then passed and the final full suite passed 465/465. Product source,
tests, CI, plans, the repository README, and package metadata were unchanged.

## Observer setup corrections

Three attempt-4 observer setup corrections remain explicitly disclosed:

1. The first latency schema preflight addressed nonexistent flat fields and did not fail fast. It
   was discarded before publication; the accepted fail-fast check used `sample_counts`, `hook_ms`,
   and `incremental_ms` and verified the exact artifact digest.
2. The first installed-wheel smoke used `--no-deps`, so the CLI could not import declared dependency
   `pydantic`. The release smoke was rerun with normal dependency installation and passed.
3. The first Codex lifecycle summary parser expected a `plugins` array, while Codex 0.144.1 returns
   `installed` and `available`. Its fail-safe removed that temporary home; the full lifecycle passed
   in a new home using the observed schema.

None of these observer corrections changed candidate files, thresholds, or product behavior.

## Gate 1

The frozen 12-case replay regenerated with exit 0 and remained byte-identical at SHA-256
`50219870b1ad89d72f03ed97e1125047e0315f226d278ae518e8f1dbe9cae048`. The exact
credential-stripped five-file replay, Codex hook compatibility/runtime, static audit, and
kernel-isolation suite passed `42/42` in `9.73s`.

Gate 1 recorded 12 passes, 0 failures, 0 unexpected contexts, and `billable_calls: 0`. Kernel
network denial was required and enforced; benign child execution passed, connect and bind were
denied, and the audited launcher environment omitted named credentials. Codex was
`codex-cli 0.144.1` with binary SHA-256
`29915529b97697def1a957b0505e770aa6a45744435d62fc263e98d7619e167a`. The plugin tree SHA-256 is
`ab7ff273f66c0ea3a7472484a0ecca05b7a7aef5876d959129946443388d7f74`; the manifest SHA-256 is
`9412d22d97e6558adb645b59be48de38f0d8187f4e83a8a61cc9b644197c98b5`.

## Promotion boundary

Gate 2 has not run. Status: **NOT RUN**. The separately approved live confirmation still requires
32 valid paid slots. Stable performance and uplift remain unproven, and this release brief makes no
performance or uplift claim.

No push, pull request, merge, tag, package publication, or GitHub release was performed. Install the
candidate after publication with `codex plugin marketplace add cwj02180218-collab/Super_SOL --ref
v0.9.0-rc1`. `v0.8.0` remains the stable release until the full Gate 2 contract in
[V0.9_PROMOTION_PROTOCOL.md](V0.9_PROMOTION_PROTOCOL.md) passes.
