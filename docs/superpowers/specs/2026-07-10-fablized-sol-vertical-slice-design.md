# Fablized SOL Minimum Vertical Slice

## Status

Approved on 2026-07-10. This specification defines the first deployable unit of
the Fablized SOL harness for the OpenAI Agents SDK for Python.

## Objective

Build a small end-to-end harness that measures and enforces procedure without
claiming to increase model capability. The slice must:

1. classify a task and route only relevant instruction packs;
2. observe tool execution in an append-only ledger;
3. block unsupported completion after mutations without successful verification;
4. assign a deterministic 80/20 harness-on/holdout split outside model context;
5. run the same evaluation task against GPT-5.6 Sol and a baseline model; and
6. remain testable without API access.

The default model IDs are `gpt-5.6-sol` and `gpt-5.5`. Both are configurable at
the command line because GPT-5.6 access is limited during preview.

## Principles

- Judge observed tool executions, never completion claims in generated text.
- Put enforcement in deterministic code and guidance in routed context packs.
- Reject evidence-free completion at the gate boundary.
- Keep unproven procedures experimental and out of always-on instructions.
- Keep measurement labels and holdout assignment outside model-visible context.

## Architecture

### Model-independent core

`engine/` contains pure Python logic with no Agents SDK imports:

- `types.py`: enums and immutable value objects for task mode, tool kind, arm,
  events, aggregate state, and gate decisions.
- `ledger.py`: append-only JSONL writes and deterministic state aggregation.
- `classify_task.py`: conservative Korean and English task classification.
- `verify_state.py`: the stop decision table.
- `goals.py`: story ledger invariants and evidence-aware completion.

This boundary makes enforcement independently testable and prevents SDK API
changes from changing policy semantics.

### Agents SDK adapter

`harness/` owns all SDK-specific behavior:

- `registry.py`: an explicit immutable `tool.name -> ToolKind` mapping.
- `hooks.py`: a `RunHooks.on_tool_end` adapter that records observed tool calls.
- `guardrails.py`: an output guardrail factory bound to the current run context.
- `router.py`: instruction construction from classification and pack signals.
- `run.py`: bounded correction runs and an explicit terminal run status.

The current `function_tool` decorator does not expose an arbitrary metadata
argument. The harness therefore uses a separate registry instead of attaching
undocumented attributes to SDK tool objects.

### Measurement

`measure/` contains code that is never injected into model instructions:

- `holdout.py`: assign `on` unless `sha256(session_id) % 5 == 0`.
- `shadow.py`: append arm, timing, gate, and outcome events to `events.jsonl`.

The ledger records enforcement evidence. The shadow stream records experimental
labels. They remain separate so measurement metadata cannot affect the subject.

### Evaluation

`eval/day0_ab.py` runs a task manifest against both configured models. It
supports:

- `--dry-run` for configuration and assignment validation without API calls;
- deterministic session IDs and arm assignment;
- JSONL results for every attempt, including failures and abandoned runs;
- configurable model IDs, task manifest, output directory, and retry limit.

The first slice does not attempt automatic defect grading. It records observable
run data and leaves `final_defect_found` for an out-of-band evaluator.

## Data Flow

1. The CLI loads one task and derives a stable session ID.
2. Holdout assignment is calculated and written only to the shadow stream.
3. The router classifies the prompt, records the classification in the ledger,
   and builds instructions. Holdout runs receive base instructions only.
4. The SDK runner executes the agent. Tool hooks look up the tool kind in the
   registry and append a `tool_call` event after execution.
5. For harness-on runs, the output guardrail aggregates ledger state and applies
   the decision table.
6. A blocked run appends `gate_fire` and starts a bounded correction run that
   includes the original task and the exact missing evidence requirement.
7. Success, error, or retry exhaustion is written to the shadow result stream.

## Gate Semantics

The stop gate returns one of `allow`, `block`, or `exhausted`.

| Condition | Decision |
| --- | --- |
| Holdout arm | allow |
| Quick task | allow |
| No mutation observed | allow |
| Documentation-only mutations | allow |
| Successful verification observed after mutation | allow |
| Deep task, code mutation, no successful verification | block |
| Retry limit reached while still blocked | exhausted |

`exhausted` is returned to the caller with the last available output and gate
reason. It is not represented as successful completion. This preserves the
no-fake-pass invariant and prevents infinite loops.

Verification evidence must be newer than the most recent relevant mutation.
Running tests before changing code cannot satisfy the gate.

## Tool Observation

The registry requires every exposed local tool to have an explicit kind:
`read`, `mutation`, or `verification`. Unknown tools are recorded as `unknown`
and never count as verification. Verification success is supplied by a typed
tool result contract containing an exit code; free-form output text is not
parsed to infer success.

Hosted tools and SDK built-ins that do not pass through local function-tool
hooks are outside the enforcement boundary in this slice. The CLI must reject a
configuration that claims such a tool is a mutation or verification tool.

## Packs

Three minimal packs are stored as text assets:

- investigation: reproduce, isolate, test the hypothesis, then change code;
- grounding: inspect the actual artifact and render or execute it before judging;
- multi-story: split independent outcomes and close each with evidence.

Packs are routed by prompt signals only in harness-on runs. They are experimental
components, not always-on policy, until holdout evidence supports promotion.

## Goals Invariants

The story ledger enforces:

- unique stable goal IDs;
- terminal completion only with non-empty evidence;
- the final verification goal requires both `verify_cmd` and
  `verify_evidence`;
- invalid transitions fail with typed domain errors rather than process exit.

The original `sys.exit` behavior is adapted to exceptions so the engine can be
embedded and tested. The CLI converts those errors to non-zero exit codes.

## Error Handling

- Malformed JSONL fails closed with the file and line number.
- Ledger appends use one serialized write under a process-local lock.
- Tool registry omissions produce a configuration error before a live run.
- SDK import or missing API credentials affect only live execution; dry runs and
  core tests remain available.
- API and SDK exceptions are recorded as failed attempts and propagated to the
  CLI exit status.

Cross-process ledger locking and distributed workers are out of scope for the
first slice. Each evaluation session owns a separate ledger file.

## Testing

Implementation follows red-green-refactor in this order:

1. classification and holdout determinism;
2. ledger append, parsing, and chronological aggregation;
3. gate decision table, especially verification-after-mutation ordering;
4. goals invariants;
5. router pack isolation;
6. registry and hook observation with fake tools;
7. bounded runner outcomes with a fake runner;
8. installed Agents SDK import and callback signature smoke tests;
9. Day 0 CLI dry-run integration.

The project gate is `ruff check .`, `basedpyright`, and `pytest`. Live API tests
are opt-in and excluded from the default suite.

## Packaging And Distribution

Use a `src/fablized_sol` Python package managed by `uv`, Python 3.12 or later,
strict basedpyright settings, Ruff, and pytest. Provide a console script named
`fablized-sol-eval`. GitHub Actions runs the default quality gate. Publication
to PyPI and creation of a public GitHub repository are separate release steps
after the local vertical slice passes.

## Non-goals

- Raising GPT-5.6 Sol's capability ceiling.
- Automatic style imitation or hidden-reasoning inspection.
- Shipping the promise-without-action regex before SOL-specific measurement.
- Claiming statistical lift from the initial small sample.
- Supporting arbitrary hosted or remote tools as mutation evidence in v0.1.

## Official References

- [Agents SDK lifecycle hooks](https://openai.github.io/openai-agents-python/ref/lifecycle/)
- [Agents SDK guardrails](https://openai.github.io/openai-agents-python/guardrails/)
- [Agents SDK function tools](https://openai.github.io/openai-agents-python/tools/)
- [GPT-5.6 preview availability](https://help.openai.com/en/articles/20001325-a-preview-of-gpt-5-6-sol-terra-and-luna)
