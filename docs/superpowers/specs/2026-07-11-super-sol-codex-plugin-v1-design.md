# Super SOL Codex Plugin v1 Design

**Date:** 2026-07-11
**Target release:** Super SOL 0.3.0
**Status:** Approved for implementation

## Outcome

Super SOL 0.3.0 will add a repo-distributed Codex plugin that improves the reliability of ordinary
Codex work without making direct model or API calls. A beginner installs the plugin, reviews and
trusts its local hooks once, and then continues to ask for work in normal language. Deterministic
local hooks select a small task procedure, record observable mutation and verification events, and
allow at most one automatic continuation when changed code lacks fresh verification.

The plugin is a quality-control harness around the active Codex session. It is not a new model, an
ontology, or a claim that the harness raises a model's intrinsic capability ceiling.

## User Contract

The default user journey is:

1. Add the Super SOL repository marketplace and install `super-sol`.
2. Review and trust the plugin's local hooks once, as required by Codex.
3. Start a new Codex task and make a normal request in Korean or English.
4. See short beginner-facing status text only when intervention is useful.
5. Receive a completion only after the active task's observable verification boundary is satisfied
   or after Super SOL has explicitly disclosed that it could not observe verification.

The beginner-facing vocabulary is limited to phrases such as `간단 작업`, `작업 중`, `검증 필요`,
and `추가 과금 호출 없음`. Model slugs, reasoning-effort names, holdout arms, and harness internals
stay out of routine status messages.

## Hard Invariants

### No automatic billable calls

- Plugin code has no OpenAI SDK, HTTP client, MCP server, or remote service dependency.
- Plugin hooks never read `OPENAI_API_KEY` and never launch the benchmark CLI.
- The plugin operates only through the already active Codex session.
- Obvious direct OpenAI API commands and live Super SOL evaluation commands are denied unless the
  current prompt contains explicit billable-run authorization.
- A live benchmark additionally requires the CLI flag `--confirm-billable`.
- Dry-run remains the CLI's safe, non-live path and never needs an API key.

Codex hooks are a guardrail rather than a complete operating-system enforcement boundary. The
project will therefore claim that the plugin itself has no automatic billable path and that known
billable CLI/API paths are guarded. It will not claim that hooks can intercept arbitrary user code
or every future Codex tool implementation.

### Stock Codex only

- No LazyCodex, OMO, `ulw`, wrapper agent, or third-party orchestration dependency is bundled.
- Daily operation does not create subagents automatically.
- Five release reviews may use independent stock Codex reviewers because that review was explicitly
  requested, but review orchestration is not part of the installed plugin's default behavior.

### Minimal always-on context

Only the following concepts are always injected:

- act on actionable work using the active Codex tools;
- after changing behavior, run and read the narrowest relevant verification;
- do not report an observed pass without an observed run;
- do not make direct billable API calls automatically;
- explain outcomes in beginner-friendly language.

Debugging, release, research, and documentation procedures are injected only when deterministic
prompt signals select them. Existing experimental harness packs remain isolated from always-on
plugin instructions until separate evidence supports promotion.

## Plugin Package

The repository will expose a repo/team marketplace:

```text
.agents/plugins/marketplace.json
plugins/super-sol/
├── .codex-plugin/plugin.json
├── hooks/
│   ├── hooks.json
│   └── super_sol_hook.py
└── skills/
    └── super-sol/
        ├── SKILL.md
        └── agents/openai.yaml
```

The manifest contains no MCP or app declaration. Codex discovers `hooks/hooks.json` and the skill
from their standard plugin locations. The marketplace entry is `AVAILABLE`, requires no external
authentication, and points to `./plugins/super-sol`.

## Hook Architecture

One Python 3 standard-library script handles five lifecycle events. The hook command receives JSON
on standard input and writes only documented Codex hook JSON to standard output.

### `SessionStart`

Inject the minimal always-on context. Do not create state, inspect the repository, or print setup
noise. If `PLUGIN_DATA` is unavailable, continue without persistent enforcement and surface one
short warning.

### `UserPromptSubmit`

1. Reject a prompt containing a likely OpenAI API key without echoing the key.
2. Classify the request with local string rules into one of:
   - `conversation`: discussion or explanation with no requested mutation;
   - `action`: ordinary implementation or file work;
   - `debug`: diagnosis or repair of a failure;
   - `release`: release, deployment, security, or full stability work.
3. Determine whether the prompt explicitly authorizes a billable live/API run. Negative phrases
   such as `과금 없이`, `API 호출하지`, and `no API call` take precedence.
4. Persist only the profile, authorization boolean, and schema version. Never persist prompt text.
5. Inject the smallest profile-specific developer context.

### `PreToolUse`

For supported shell-tool inputs, deny these known billable paths unless the turn state explicitly
authorizes billing:

- a command addressing `api.openai.com`;
- `super-sol-eval` or its compatibility alias without `--dry-run`;
- a live evaluation command lacking `--confirm-billable` even when billing was authorized.

Other tools continue unchanged. The hook does not auto-approve permission requests and does not
rewrite arbitrary commands.

### `PostToolUse`

Write one immutable event file per observed tool call under `PLUGIN_DATA`. Event filenames use
hashes of Codex identifiers, not raw identifiers. Record only:

- event schema version;
- hashed tool-use identifier;
- event observation time;
- whether the event was an observed file mutation;
- whether it was a recognized verification command;
- whether that verification returned a structured zero exit code.

Do not persist commands, tool output, file contents, prompts, model output, credentials, or
environment values. `apply_patch` is the initial reliable mutation boundary. Recognized
verification commands include common Python, JavaScript, Rust, Go, and build checks. Unstructured
or ambiguous output does not count as passing evidence.

### `Stop`

For `action`, `debug`, and `release` profiles:

- allow completion when no observed mutation exists;
- allow completion when a successful recognized verification is newer than the latest mutation;
- otherwise request exactly one continuation explaining that fresh verification is missing;
- on the continued stop, allow termination and surface an honest unverified warning instead of
  creating a loop.

`conversation` never triggers a verification continuation.

## Local State and Privacy

State lives only under `PLUGIN_DATA/super-sol/v1`. Session and turn directory names are SHA-256
hashes. Files are created with owner-only permissions where supported and written via temporary
file plus atomic replace. Parallel tool completions write distinct files, avoiding a shared mutable
counter or process lock.

All input is bounded before parsing. Invalid JSON, oversized input, missing fields, unwritable
state, or unknown events fail open with a short warning because a local productivity plugin must
not deadlock Codex. Secret detection and recognized billable-command denial fail closed.

## Skill Behavior

The `super-sol` skill triggers for implementation, debugging, verification, release-readiness, and
requests to explain or diagnose Super SOL itself. Its body is concise and tells Codex to:

- use plain language first;
- work autonomously within the request's authority;
- keep edits scoped;
- verify behavioral changes with observed commands;
- distinguish observed results from recommendations;
- avoid direct API/model calls unless the user explicitly requests a billable run;
- never imply that the harness changes intrinsic model capability.

The skill contains no duplicate user documentation and no executable resources; deterministic
behavior stays in the hook script.

## Benchmark Reproducibility

The live harness remains optional and separate from daily plugin operation. Version 0.3.0 changes
its comparison contract as follows:

- default product model: `gpt-5.6-terra`;
- default reference model: `gpt-5.6-sol`;
- explicit `--product-effort` and `--reference-effort`, both defaulting to `medium`;
- accepted effort values match the pinned OpenAI SDK: `none`, `minimal`, `low`, `medium`, `high`,
  and `xhigh`;
- `ModelSettings.reasoning.effort` is passed to every SDK agent run;
- reasoning effort is included in deterministic session identity and every plan, start, and finish
  shadow event;
- report joins reject effort mismatches and report the effort beside each model cell;
- live execution requires `--confirm-billable` in addition to an API key and two digest-pinned
  container images.

Codex product guidance may mention the newer `max` and `ultra` settings, but this API harness will
not accept values absent from its pinned SDK type contract. `ultra` is also unsuitable for a
single-agent reproducibility comparison because it changes orchestration topology.

The existing GPT-5.5 versus GPT-5.6 Sol pilot remains a frozen historical artifact. It is not
rewritten to imply current default guidance.

## Current Model Guidance

User documentation will be dated 2026-07-11 and link to OpenAI's 2026-07-09 general-availability
announcement. Guidance is:

- Terra for routine work and the default reproducible product arm;
- Sol for the hardest open-ended work and the controlled reference arm;
- Luna for clear, repeatable, high-volume work;
- start at the lowest effort that meets the task and escalate only after observed failure;
- use `max` for unusually hard single-agent work and `ultra` only for cleanly separable parallel
  work when the user's plan and quota permit it.

The documentation states that model availability depends on the user's ChatGPT/Codex plan and
workspace policy. The plugin never changes the selected model or effort automatically.

## Container Supply Chain

Both verifier images move from the vulnerable Debian slim base to the multi-platform digest-pinned
official `python:3.12-alpine` image. The release gate will:

1. build verifier and grader images locally;
2. run Docker Scout for critical and high vulnerabilities;
3. fail the documented release gate when either severity is present;
4. generate SPDX JSON SBOMs for both images;
5. preserve digest-pinned runtime use and existing no-network/read-only/capability controls;
6. run the verifier and grader control tests against the new images.

The repository will contain a deterministic policy check for pinned bases and a CI container job.
Generated SBOMs are release evidence and may be refreshed without changing runtime behavior.

## Validation and Stability Gates

Implementation is complete only after all of these are observed:

- plugin manifest validator passes;
- skill validator passes;
- hook unit and protocol tests pass, including malformed input, secret blocking, billing guard,
  privacy, task routing, mutation evidence, successful verification, and one-retry exhaustion;
- hook script is manually driven through SessionStart, prompt, mutation, verification, and Stop;
- CLI `--help`, dry-run happy path, and live-without-confirmation rejection are observed;
- Ruff format/lint, basedpyright, full pytest with coverage, package build, and file-size policy pass;
- both Alpine images build;
- Docker Scout reports zero critical and high findings for both built images;
- SPDX SBOMs are generated;
- existing container isolation/control tests pass;
- five independent stock Codex reviews cover code quality, security/privacy, beginner UX,
  benchmark methodology/reproducibility, and release/operations;
- all actionable review findings are fixed and the affected gates are rerun.

## Non-goals

- Automatically purchasing or invoking API capacity.
- Automatically switching the user's Codex model or effort.
- Automatically spawning subagents in normal use.
- Replacing Codex permissions, sandboxing, or operating-system security controls.
- Claiming Fable parity from the four-task historical pilot.
- Installing experimental prompt packs globally.
- Hiding failed or unobserved verification behind a success message.
