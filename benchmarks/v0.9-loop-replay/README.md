# v0.9 Loop Replay Gate

`report.json` is the deterministic Gate 1 record for the twelve sealed loop-fuse
sequences. Runtime validation rejects any change to the IDs, event counts,
payloads, expected action profiles, corrupt-state setup, or required hook-event
coverage. Each event invokes the exact command selected from the shipped
`hooks.json` with an isolated `PLUGIN_DATA` tree.

The launcher constructs subprocess input with only `PLUGIN_ROOT`, `PLUGIN_DATA`,
`PATH`, and `PYTHONUTF8`; the report records these as `launcher_env_keys`. The
actual hook process may also contain non-secret runtime variables injected by
the OS, shell, or Python launcher. A real temporary hook runs under a
deterministically hostile parent environment and proves that OpenAI, Codex,
forced-route, and representative AWS credential keys, plus their raw fixture
values, are absent. The stable key list is recorded as
`credential_keys_absent`; platform-specific runtime variables are not serialized.

Kernel network denial is mandatory. On macOS, the runner requires
`/usr/bin/sandbox-exec` with `(deny network*)`. On Linux, it requires a supported
architecture and libseccomp, then loads a default-allow filter that denies the
socket syscall family plus network-capable `io_uring`, `bpf`, and descriptor
acquisition before `/bin/sh` executes. The filter is inherited across child
processes. Both adapters must pass a startup self-test proving that a benign
child succeeds while socket creation/connect and socket creation/bind are
denied. Missing, unsupported, or ineffective isolation aborts report
generation; there is no unsandboxed fallback.

The command and AST audit is defense in depth, not the security boundary. It
checks the exact hook command inventory, scans Python code for common network
and process escapes, and rejects symlinks and executable non-Python hook files.
The report binds that audit to SHA-256 digests of the command inventory and the
complete plugin tree, and verifies that the tree is unchanged after replay.

`network_calls: 0` and `successful_network_calls: 0` mean that successful
network operations were prevented by the enforced kernel policy. They do not
claim packet, syscall-attempt, or API-call instrumentation; `calls_counted` is
therefore false. The replay uses synthetic structured payloads only and invokes
no model, API client, or network service.

The implementation is split into focused modules, each below the repository's
250 non-comment, non-blank line limit:

- `eval/v09_loop_contract.py`: sealed manifest contract
- `eval/v09_loop_audit.py`: command, tree, and AST audit
- `eval/v09_loop_seccomp.py`: Linux libseccomp ABI and rules
- `eval/v09_loop_isolation.py`: kernel wrappers and environment evidence
- `eval/v09_loop_runtime.py`: hook replay and corrupt-state recovery
- `eval/v09_loop_replay.py`: public API, report assembly, and unchanged CLI

Focused coverage is split across `tests/eval/test_v09_loop_replay.py`,
`tests/eval/test_v09_loop_audit.py`, and
`tests/eval/test_v09_loop_isolation.py`, with typed loading support in
`tests/eval/v09_loop_test_support.py`.

Any isolation failure, credential leak, capability finding, hook timeout,
nonzero exit, malformed JSON, extra model-visible context, action mismatch, or
missed denial fails the gate. The healthy progress-separated-compactions case
starts with a synthetic corrupt ledger. Its first hook must quarantine and
replace the state before the sequence can pass, and the report records that
evidence.

Observed result: 12/12 passed, 0 failed, 0 unexpected contexts, 0 successful
network operations, and evidenced corrupt-state recovery. The report schema is
`super-sol-loop-replay/v1`. Regenerate and verify it with:

```bash
env -u OPENAI_API_KEY -u CODEX_API_KEY PYTHONDONTWRITEBYTECODE=1 uv run python eval/v09_loop_replay.py --manifest eval/v09_loop_sequences.json --output benchmarks/v0.9-loop-replay/report.json
env -u OPENAI_API_KEY -u CODEX_API_KEY PYTHONDONTWRITEBYTECODE=1 uv run pytest tests/eval/test_v09_loop_replay.py tests/eval/test_codex_hook_compat.py tests/eval/test_codex_hook_runtime.py tests/eval/test_v09_loop_audit.py tests/eval/test_v09_loop_isolation.py -q -p no:cacheprovider
```

## Latency evidence

`latency-attempt5.json` is the current privacy-safe Gate 0 latency artifact for
product candidate `ec5a153e1487065f3f3a33aab5394ed48f453377`. Its SHA-256 is
`6689e3b8b7d75f25ec5a5da4e2d5fcf7baf6d1d5523cbacd515a99564bdcec00`.
It records 300 hook samples and 150 floor samples, with hook p95
`59.684106236090884 ms` and paired incremental p95
`37.984207982663065 ms`; both required thresholds passed. The parent process
ran the official measurement exactly once for attempt 5. Evidence recording
verified the generated artifact unchanged and did not rerun it.

Attempts 1-4 remain textual history in `gate0.json` and the Task 8 report.
Attempt 4's original digest and metrics are retained there, but its raw artifact
is deliberately not published because it contained a local absolute path.
Gate 2 has not run. Status: **NOT RUN**; no performance or uplift claim is made.
