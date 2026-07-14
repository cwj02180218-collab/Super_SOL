# Super SOL v0.9 Latency Gate Correction

## Scope

This change removes the host-load-sensitive 450-process timing loop from the normal pytest suite.
It introduces `super-sol-hook-latency`, a separate Gate 0 command intended for the clean-room Task 8
procedure. No plugin hook behavior, release evidence JSON, release brief, or publishing state changed.

## Implemented Contract

- The CLI exposes only required `--plugin-root` and fresh `--output` paths. Samples and thresholds
  are not public flags.
- The release gate is frozen at 300 hook samples, 150 floor samples, 100 ms absolute p95, and 70 ms
  paired incremental p95.
- The command reads the single `UserPromptSubmit` command from `hooks.json`, expands only
  `$PLUGIN_ROOT`, and accepts only `/usr/bin/python3 -S` followed by the real, regular,
  non-symlinked `hooks/prompt_dispatcher.py` under the plugin root. Alternate executables, scripts,
  symlinks, extra arguments, duplicate handlers, and invalid configured timeouts fail closed.
- A temporary `PLUGIN_DATA` directory and a child environment limited to `PATH`, `PLUGIN_DATA`,
  `PLUGIN_ROOT`, and `PYTHONUTF8` isolate every sample set.
- The sample schedule is hook, hook, floor, repeated 150 times. Both hooks are paired with their
  triplet-local floor before computing incremental percentiles.
- Hook and floor children have a fixed five-second timeout. Timeouts exit 2 without a final report.
- Reports are fsynced to same-directory exclusive temporary files and atomically published without
  replacing an existing output.
- The JSON report includes schema version, command and plugin digests, sample counts, hook/floor
  p50/p95/p99/min/max, incremental p50/p95/p99, platform/cpu/load-average snapshots, thresholds,
  and the boolean verdict.
- Exit status is 0 only for `hook p95 < 100 ms` and `incremental p95 < 70 ms`; a failed measured
  gate exits 1, while configuration, child-process, and report failures exit 2.

## Test Coverage

`tests/eval/test_hook_latency.py` uses fake clocks and process runners to cover command selection,
the 2:1 interleaving schedule, child environment allowlisting, inclusive percentile math, malformed
hook manifests, a hanging child, nonzero children, threshold exit behavior, and frozen defaults.

`tests/eval/test_hook_latency_report.py` covers paired incremental distributions, including the
reviewer's adversarial 79 ms paired-p95 failure that quantile subtraction would report as 69 ms,
official report-field validation, fresh-output refusal, fsync publication, and interrupted-write
cleanup without a final-named partial report.

`tests/plugin/test_v07_budgets.py` now retains deterministic prompt-command and frozen-gate-contract
assertions. It no longer performs 450 real process launches during the default suite.

`tests/test_release_gate_contract.py` freezes the exact official coverage and latency commands across
the README, CI, implementation plan, and report. The former 453-NCNB package smoke module is split
into focused smoke, archive, and release-history modules with one shared typed support module while
preserving its 18 tests.

## Verification Results

| Command | Observed result |
| --- | --- |
| Focused adversarial/package tests | `53 passed in 1.01s`. |
| `uv run pytest --collect-only -q` | `463 tests collected in 0.68s`; the pre-change baseline was 442. |
| `uv run pytest --cov=src --cov=plugins/super-sol/hooks --cov-report=term-missing --cov-fail-under=90` | `463 passed in 43.86s`; total coverage `90.55%`. |
| `uv run ruff format --check .` | Passed; 147 files already formatted. |
| `uv run ruff check .` | Passed. |
| `uv run basedpyright` | `0 errors, 0 warnings, 0 notes`. |
| `uv build` | Built `super_sol_harness-0.9.0rc1.tar.gz` and `super_sol_harness-0.9.0rc1-py3-none-any.whl`. |
| `uv run super-sol-container-audit` | Verifier and grader images passed with `0C 0H 0M 0L`; generated SBOM churn was restored. |
| Dependency digest | `uv.lock` SHA-256 matched `DEPENDENCY_LOCK.sha256`: `c82fc4b58a9661d3b4adde7751b744d948758029ac53f9b8b0de78b0fe89e39e`. |
| Installed-wheel smoke | A disposable venv installed the wheel; `super-sol-hook-latency --help` exited 0 and exposed only `--plugin-root` and `--output` beyond standard help. |
| NCNB audit | Every changed Python file is at or below 250 NCNB; the maximum is 236 in `hook_latency.py`. |
| `git diff --check` | Passed. |

The official latency invocation is
`uv run super-sol-hook-latency --plugin-root plugins/super-sol --output <fresh>` after clean-room
installation. It remains separate from the default pytest/CI suite.

## Deliberate Non-Execution

The 300-hook/150-floor measurement was not executed as part of this implementation change. The
approved architecture assigns that host-sensitive measurement to the separately invoked clean-room
Task 8 Gate 0 command. No new Gate 0 evidence was generated or published here.
