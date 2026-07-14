# Task 8 Gate Evidence Report

## Scope

- Attempt 5 product candidate: `ec5a153e1487065f3f3a33aab5394ed48f453377`.
- Prior evidence commit: `78a39ea2c09ba73cafdd4e9e39d24fdded13d45a`.
- The commit containing this report is evidence-only: wording, evidence records, artifact replacement,
  and digests. It does not change product source, tests, CI, plans, the repository README, or package
  metadata.
- Scope completed: Task 8 local Gate 0 and Gate 1 evidence only.
- Publication actions: not performed. No push, PR, merge, tag, publish, or release was attempted.
- Gate 2: **NOT RUN**; no performance or uplift claim is made.

## Preserved attempt history

Attempt 1 remains preserved at evidence commit `fe91cf17e18a664fb62a9aefb55e851706443ee1`.
It collected 431 tests: 429 passed and 2 failed with 90.58% coverage. The failures were stale
harness-version and packaged dependency-lock provenance contracts.

Attempt 2 remains preserved at evidence commit `6bf857b84acb10ba551c2161a09291a5c3cf045c`.
It collected 431 tests: 429 passed and 2 failed with 90.58% coverage. The replay report was not
immutable, and the observed 300-invocation absolute p95 was `106.79754642769694 ms`.

Attempt 3 remains preserved at candidate `9c91a5d30ab5a7720e7eefe7fd4ebcd2b65174b9`.
It collected 431 tests: 430 passed and 1 failed with 90.58% coverage. The observed 300-invocation
absolute p95 was `147.90276812855154 ms`.

Attempt 4 remains preserved at candidate `2ce7fc8ce951a3c5027a13dd39abe5e8a033d935` and evidence
commit `78a39ea2c09ba73cafdd4e9e39d24fdded13d45a`. It passed 463/463 tests with 90.55% coverage.
Its latency artifact had SHA-256
`5dfb63f492a0b37559998d6a389d71917b606573d6323ac3628d24f120be235b`, absolute p95
`59.967531589791186 ms`, and paired incremental p95 `36.61352920462378 ms`. The raw attempt-4
artifact is deliberately not published because it contained a local absolute path. Its metrics and
original digest remain textual history.

## Gate 0 attempt 5

| Command | Exit | Observed result |
| --- | ---: | --- |
| `uv run pytest --cov=src --cov=plugins/super-sol/hooks --cov-report=term-missing --cov-fail-under=90` | 0 | 465 passed in 40.87s; coverage 90.56% |
| `uv run ruff check .` | 0 | All checks passed |
| `uv run ruff format --check .` | 0 | 147 files already formatted |
| `uv run basedpyright` | 0 | 0 errors, 0 warnings, 0 notes |
| `uv build` | 0 | built the final evidence-document `0.9.0rc1` sdist and wheel |
| `uv run super-sol-container-audit` | 0 | verifier and grader: 57 packages each, `0C 0H 0M 0L` |
| `git diff --check` | 0 | no output |
| dependency-lock value comparison | 0 | both digests `c82fc4b58a9661d3b4adde7751b744d948758029ac53f9b8b0de78b0fe89e39e` |
| structured archive inventory/privacy | 0 | 27/27 assets in both; 0 missing, forbidden, or byte mismatches |
| dependency-complete installed-wheel CLI smoke | 0 | `0.9.0rc1`; approved CLI options and packaged manifest present |
| tracked production secret/privacy scan | 0 | 99 files; 0 content or forbidden-name matches |

The final packaged-document build produced a 133-file sdist with SHA-256
`9159b4affd03b24039f2acc22452f2cecd039f5dd6d69346daaa3c1c22873839` and an 81-file wheel with
SHA-256 `eafceb0d592fe0cbc809eceb544723b00d5439ea615eb4d61c4745c2608eac6e`.
The container verifier rewrote the two tracked SBOMs during observation; both were restored and
`cmp` verified byte equality with their pre-audit copies.

The first two full-suite observations each reported 464 passes, 1 failure, and 90.56% coverage.
They exposed two stale owned release-brief contract phrases: first the explicit Gate 2 status
wording, then the packaged release root. Only the release brief was corrected. The focused contract
passed 1/1, and the final full suite passed 465/465. These were evidence-document corrections, not
product candidate repairs.

## Latency evidence

`benchmarks/v0.9-loop-replay/latency-attempt5.json` was verified unchanged at SHA-256
`6689e3b8b7d75f25ec5a5da4e2d5fcf7baf6d1d5523cbacd515a99564bdcec00`. It has schema
`super-sol-hook-latency.v1`, normalized command argv `/usr/bin/python3`, `-S`,
`$PLUGIN_ROOT/hooks/prompt_dispatcher.py`, command SHA-256
`d33a440ae3bce96c1231bbd5e2b7134d9e85c7192aa3445e2f3a08cc6d2673eb`, 300 hook samples, 150
floor samples, and `passed:true`.

- Hook p50/p95/p99: `51.8779584672302/59.684106236090884/70.47763176844444 ms`
- Floor p50/p95/p99: `21.424166508950293/25.30089111533016/40.682711384724755 ms`
- Paired incremental p50/p95/p99:
  `30.51731240702793/37.984207982663065/49.48958753026079 ms`
- Gates: absolute p95 `59.684106236090884 < 100 ms`; incremental p95
  `37.984207982663065 < 70 ms`

The parent process ran the official 450-process measurement exactly once for attempt 5 after the
privacy repair. This recording pass independently verified the generated artifact and did not rerun
the official measurement.

## Stock Codex lifecycle

Codex version was freshly observed as `codex-cli 0.144.1`, with binary SHA-256
`29915529b97697def1a957b0505e770aa6a45744435d62fc263e98d7619e167a`. In one new temporary
`CODEX_HOME`, local marketplace add, plugin add, plugin list, plugin remove, marketplace remove,
absent list, marketplace re-add, plugin re-add, and final list all exited 0. Installed and
reinstalled states each had exactly one Super SOL plugin, one `super-sol` skill, one hook manifest,
seven events, one configured command per event, and no `Stop`. Removed state had zero plugins,
skills, and hook manifests. The home was deleted after the final assertion. No model command ran.

## Observer setup corrections

Three attempt-4 observer setup corrections remain disclosed:

1. The first latency schema preflight addressed nonexistent flat fields and did not fail fast. It
   was discarded before publication; the accepted fail-fast check used `sample_counts`, `hook_ms`,
   and `incremental_ms` and verified the exact artifact digest.
2. The first installed-wheel smoke used `--no-deps`, so the CLI could not import declared dependency
   `pydantic`. The release smoke was rerun with normal dependency installation and passed.
3. The first Codex lifecycle summary parser expected a `plugins` array, while Codex 0.144.1 returns
   `installed` and `available`. Its fail-safe removed that home, and the complete lifecycle passed in
   a new home using the observed schema.

None changed candidate files or thresholds. Separately, an attempt-5 dependency comparison
preflight compared text formatting and returned 1 solely because the packaged digest file omits a
trailing newline. The accepted fail-fast value comparison returned 0 with exact digest equality.

## Gate 1

Replay regeneration from the frozen manifest exited 0 and left `report.json` byte-identical at
SHA-256 `50219870b1ad89d72f03ed97e1125047e0315f226d278ae518e8f1dbe9cae048`. The exact
credential-stripped five-file suite passed `42/42` in `9.73s`. The regenerated audit records:

- replay: 12 cases, 12 passed, 0 failed, 0 unexpected contexts
- `billable_calls: 0`; successful network calls: 0
- required kernel isolation enforced; benign child passed; connect and bind denied
- Codex binary SHA-256: `29915529b97697def1a957b0505e770aa6a45744435d62fc263e98d7619e167a`
- plugin tree SHA-256: `ab7ff273f66c0ea3a7472484a0ecca05b7a7aef5876d959129946443388d7f74`
- manifest SHA-256: `9412d22d97e6558adb645b59be48de38f0d8187f4e83a8a61cc9b644197c98b5`
- report SHA-256: `50219870b1ad89d72f03ed97e1125047e0315f226d278ae518e8f1dbe9cae048`
- audit SHA-256: `db619a1a2d39459ac051db15fb310f05976901255862bdbeaa779ca593273332`

## Final verification

The final credential-stripped focused evidence suite passed `80/80` in `10.02s`. It covered the
five Gate 1 replay/audit files, hook latency report, package archives and smoke, release gate and
history, and plugin release-contract checks. JSON validity, artifact digests, privacy scans, and
`git diff --check` were run separately before commit.

The final privacy audit scanned 78 files changed from `origin/main` through the working tree and 49
packaged documentation entries. It reported zero unexpected local paths, token shapes,
source-identifying conversation provenance, local usernames, user prompts, or private runtime
artifacts. Six matches were explicit synthetic detector fixtures in tests; docs and release
artifacts had no allowances and no findings.

## Disposition

Local Gate 0 and Gate 1 evidence support RC review. Publication remains intentionally unperformed,
and stable promotion remains blocked on the separately approved 32-slot Gate 2. Gate 2 is **NOT
RUN**, so stable performance and uplift remain unproven.
