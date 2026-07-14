# Task 7 Report: v0.9.0-rc1 Review Fixes

## Scope

- Package version: `0.9.0rc1`
- Plugin version: `0.9.0-rc1`
- Original Task 7 commit: `51f6b567a623e89e2e54f3c3159537ef118eb0da`
- Review-fix commit message: `fix: package v0.9 release evidence`

## Review Fixes

The Gate 1 report was regenerated after the Task 7 plugin manifest and skill changes. Its candidate
plugin tree SHA-256 is
`05a205c92432172962b32ee28d2347e0476a0378e6f8c09ae74934bb44815ef1`, independently matched to an
unchanged `HEAD` plugin tree. The immutable replay report SHA-256 is
`a4dacf4ce7e8efc479d80a414fec66f909ffad482205985bc62b2a00d5c318cf`; manifest SHA-256 remains
`9412d22d97e6558adb645b59be48de38f0d8187f4e83a8a61cc9b644197c98b5`.

Hatch now preserves the normal `fablized_sol` package and force-includes an explicit 27-file release
surface under the stable wheel path `fablized_sol/_release/v0_9/`. Both wheel and sdist contain the
plugin manifest, every hook and skill file, every `eval/v09_loop*` helper, the two v0.9 release docs,
and replay README/report. The sdist allowlist excludes tests, unrelated benchmark trees, and broad
plugin/eval roots.

Gate 0 wording now distinguishes six loop lifecycle capability events from the separate
`UserPromptSubmit` reset check. The shipped manifest has seven top-level events and no `Stop` hook.

## TDD Evidence

The first review-contract RED run was:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest \
  tests/plugin/test_plugin_contract.py tests/test_package_smoke.py \
  -q -p no:cacheprovider
```

Observed: `3 failed, 21 passed in 0.75s`. Failures proved the missing wheel mapping, absent wheel
assets, and ambiguous Gate 0 wording. A narrower sdist RED run then observed `2 failed, 16 deselected
in 0.68s`, proving the broad `/tests`, `/benchmarks`, `/eval`, and `/plugins` selection remained.

Final GREEN result for the same focused Task 7 command: `24 passed in 0.89s`.

## Gate 1 Evidence

Regeneration:

```bash
env -u OPENAI_API_KEY -u CODEX_API_KEY PYTHONDONTWRITEBYTECODE=1 \
  uv run python eval/v09_loop_replay.py \
  --manifest eval/v09_loop_sequences.json \
  --output benchmarks/v0.9-loop-replay/report.json
```

Observed: exit 0 with no stdout or stderr.

Immutable replay, audit, and isolation suite:

```bash
env -u OPENAI_API_KEY -u CODEX_API_KEY PYTHONDONTWRITEBYTECODE=1 \
  uv run pytest tests/eval/test_v09_loop_replay.py \
  tests/eval/test_v09_loop_audit.py tests/eval/test_v09_loop_isolation.py \
  -q -p no:cacheprovider
```

Observed final result: `32 passed in 7.48s`, including immutable report byte equality.

## Build and Archive Evidence

Fresh build:

```bash
uv build --out-dir <temporary-build-dir>
```

Observed: wheel and sdist built successfully from the final source tree.

| Artifact | Files | SHA-256 |
| --- | ---: | --- |
| `super_sol_harness-0.9.0rc1.tar.gz` | 130 | `4fcfe3557898e2c93cc9be3ff3bbc3f12170b4fa4f9c4ddfe995649644068942` |
| `super_sol_harness-0.9.0rc1-py3-none-any.whl` | 78 | `c632b67c4162d2e395ca275a632266ad9a3f8488c4e49131ac99ba871e248df0` |

Structured `tarfile`/`zipfile` inspection observed 27 required assets in each archive, 0 missing
sdist assets, 0 missing wheel assets, 0 forbidden sdist matches, and 0 forbidden wheel matches.
Every mapped asset byte-matched its source. Forbidden checks covered tests, `.venv`, plugin data,
`.loop-key`, loop/state files, private conversation source, and unrelated benchmark data.

## Final Verification

```bash
uv lock --check
uv run ruff format --check tests/plugin/test_plugin_contract.py tests/test_package_smoke.py
uv run ruff check --no-cache tests/plugin/test_plugin_contract.py tests/test_package_smoke.py
uv run basedpyright tests/plugin/test_plugin_contract.py tests/test_package_smoke.py
git diff --check
```

Observed: `uv lock --check` resolved 60 packages in 20 ms; Ruff reported two files already formatted
and all checks passed; basedpyright reported `0 errors, 0 warnings, 0 notes`; `git diff --check`
produced no output.

## Residual Risks

- Task 8 must still observe the final full-suite, coverage, install, latency, dependency, and secret
  Gate 0 values.
- Gate 2's 32 paid slots have not run; stable performance and uplift remain unproven.
- The loop fuse cannot interrupt an in-flight sampler before a lifecycle hook, and it does not repair
  Codex Desktop cancellation or OS process cleanup.
