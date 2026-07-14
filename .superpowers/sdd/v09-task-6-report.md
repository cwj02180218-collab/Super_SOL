# Task 6 Report: v0.9 Adversarial Loop Replay Gate

## Files

- `eval/v09_loop_sequences.json`
- `eval/v09_loop_replay.py`
- `eval/v09_loop_contract.py`
- `eval/v09_loop_audit.py`
- `eval/v09_loop_seccomp.py`
- `eval/v09_loop_isolation.py`
- `eval/v09_loop_runtime.py`
- `tests/eval/v09_loop_test_support.py`
- `tests/eval/test_v09_loop_replay.py`
- `tests/eval/test_v09_loop_audit.py`
- `tests/eval/test_v09_loop_isolation.py`
- `benchmarks/v0.9-loop-replay/report.json`
- `benchmarks/v0.9-loop-replay/README.md`
- `.superpowers/sdd/v09-task-6-report.md`

## Final Review Fixes

- The connect and bind self-test snippets now create their sockets inside the
  caught scope. `PermissionError` from either `socket()` or the requested
  operation is an expected denial and exits 0.
- Typed fake-libseccomp tests verify ABI argument/result types, all denied
  syscall rules, pre-exec filter load, idempotent single release, and release on
  rule-installation failure. A live Linux backend must still pass its own
  benign/connect/bind startup test before report generation.
- The launcher remains restricted to `PLUGIN_ROOT`, `PLUGIN_DATA`, `PATH`, and
  `PYTHONUTF8`, now honestly reported as `launcher_env_keys`. No claim is made
  that these are the actual process's only variables.
- A real isolated temporary hook runs with deterministic hostile OpenAI, Codex,
  forced-route, and AWS parent credentials. Report generation fails if any key
  or raw fixture value reaches the process. The report serializes the stable
  six-key `credential_keys_absent` evidence and omits platform-added runtime
  variables.
- The 763-NCNB runner and 255-NCNB test were split into focused contract, audit,
  seccomp, isolation, runtime, facade, and test modules. Every Task 6 production
  and test Python file is now at or below 250 NCNB lines.
- Exact manifest sealing, the mandatory kernel boundary, missing-sandbox bypass
  regression, immutable report, and corrupt-state recovery evidence remain
  intact.

## TDD Evidence

The final-review behavior contracts were first observed RED:

```text
FFFF
4 failed, 25 deselected in 6.63s
```

The failures covered missing socket-probe and environment-probe APIs, stale
environment report semantics, and NCNB counts of 763/306. Before adding the
seccomp helper, its ABI and cleanup tests separately failed because
`v09_loop_isolation` did not exist. After implementation, the isolation slice
reported `7 passed in 0.33s`. The full split suite then reached
`1 failed, 30 passed in 7.43s`; the only failure was byte comparison against the
intentionally stale immutable report. Regenerating the report produced the
final green suite. A final exception-cleanup regression then failed with an
uncaught `ctypes.ArgumentError`; releasing the context before converting that
failure to `kernel_isolation` made the focused regression pass.

## Exact Verification

Report generation:

```bash
env -u OPENAI_API_KEY -u CODEX_API_KEY PYTHONDONTWRITEBYTECODE=1 uv run python eval/v09_loop_replay.py --manifest eval/v09_loop_sequences.json --output benchmarks/v0.9-loop-replay/report.json
```

Observed: exit 0, no stdout/stderr.

Focused and adversarial suite, including report byte equality:

```bash
env -u OPENAI_API_KEY -u CODEX_API_KEY PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/eval/test_v09_loop_replay.py tests/eval/test_v09_loop_audit.py tests/eval/test_v09_loop_isolation.py -q -p no:cacheprovider
```

Observed: `32 passed in 7.32s`.

Dedicated adversarial slice:

```bash
env -u OPENAI_API_KEY -u CODEX_API_KEY PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/eval/test_v09_loop_replay.py tests/eval/test_v09_loop_audit.py tests/eval/test_v09_loop_isolation.py -q -p no:cacheprovider -k 'empty_events or short_sequence or altered_expected or altered_required or network_capability or kernel_network or unsupported_platform or linux_without or missing_sandbox or socket_creation or hostile_parent or seccomp or ncnb'
```

Observed: `30 passed, 2 deselected in 0.63s`.

Independent report regeneration and byte equality:

```bash
env -u OPENAI_API_KEY -u CODEX_API_KEY PYTHONDONTWRITEBYTECODE=1 uv run python eval/v09_loop_replay.py --manifest eval/v09_loop_sequences.json --output <temporary-report.json>
cmp -s <temporary-report.json> benchmarks/v0.9-loop-replay/report.json
```

Observed: both commands exited 0 with no stdout/stderr.

Static verification and NCNB assertion:

```bash
uv run ruff format --check eval/v09_loop_*.py tests/eval/*v09_loop*.py
uv run ruff check eval/v09_loop_*.py tests/eval/*v09_loop*.py
uv run basedpyright eval/v09_loop_*.py tests/eval/*v09_loop*.py
find eval tests/eval -maxdepth 1 -name '*v09_loop*.py' -print0 | xargs -0 -n1 sh -c 'printf "%s " "$0"; awk "NF && !/^[[:space:]]*#/ {n++} END {print n+0}" "$0"'
git diff --check
```

Observed: `10 files already formatted`, `All checks passed!`,
`0 errors, 0 warnings, 0 notes`, all ten NCNB counts between 33 and 204,
and clean `git diff --check` output.

Exact NCNB counts:

```text
eval/v09_loop_contract.py 146
eval/v09_loop_audit.py 194
eval/v09_loop_replay.py 96
eval/v09_loop_isolation.py 204
eval/v09_loop_runtime.py 166
eval/v09_loop_seccomp.py 113
tests/eval/test_v09_loop_replay.py 127
tests/eval/test_v09_loop_isolation.py 181
tests/eval/test_v09_loop_audit.py 62
tests/eval/v09_loop_test_support.py 33
```

## Gate 1 Report

- Schema: `super-sol-loop-replay/v1`
- Cases: 12 total, 12 passed, 0 failed
- Unexpected contexts: 0
- Successful network operations: 0; calls were not counted
- Kernel network denial: required and enforced
- Self-test: benign child passed; connect denied; bind denied
- Launcher environment keys: `PATH`, `PLUGIN_DATA`, `PLUGIN_ROOT`, `PYTHONUTF8`
- Credential keys absent: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
  `AWS_SESSION_TOKEN`, `CODEX_API_KEY`, `OPENAI_API_KEY`,
  `SUPER_SOL_FORCED_ROUTE`
- Corrupt-state recovery: evidenced
- Manifest SHA-256: `9412d22d97e6558adb645b59be48de38f0d8187f4e83a8a61cc9b644197c98b5`
- Canonical manifest SHA-256: `d68858f2fb29aa535cecaa5ffb072dcc7e66859dcf0146cbbb2d623a82026273`
- Plugin-tree SHA-256: `8014af1aac8c437f530cc8fde89b15c19e29cc3d1ce7a0bac1dc8bf7b0ea8370`
- Hook-command SHA-256: `de9a57c4fb8e3d18284c8685813a7d0ab4fdb98a0f77d122b660ed4ddc7eb000`

## Commit

- Atomic commit: `fix: finalize v0.9 replay isolation evidence`
- Commit SHA: returned with the completion summary because a commit cannot
  contain its own SHA without changing that SHA.

## Residual Risks

- The immutable report was generated on macOS. The Linux ABI and cleanup are
  deterministically tested here, but Linux must pass its live libseccomp
  startup self-test before it can generate a passing report.
- OS, shell, and Python launchers may add non-secret runtime variables. The gate
  proves the named credential keys and raw hostile fixture values are absent;
  it does not claim a four-variable actual process environment.
- Network values are enforced successful-operation results, not packet,
  syscall-attempt, or API-call counters.
- This remains a synthetic hook replay, not a live model or Codex app-server
  run.
