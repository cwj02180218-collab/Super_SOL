# Contributing to Super SOL

## Development setup

```bash
uv python install 3.12
uv sync --locked --dev
```

## Required checks

```bash
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest --cov=fablized_sol --cov-report=term-missing
uv build
```

Routine development and CI must not require `OPENAI_API_KEY` or perform live,
billable evaluation. Use `super-sol-eval --dry-run` for manifest and assignment
changes. A live benchmark requires an explicit quota decision, new run ID, and
two distinct digest-pinned images.

## Benchmark changes

- Add a visible acceptance test before changing a task contract.
- Keep hidden grader cases distinct from public examples.
- Preserve model, arm, and task pairing when comparing runs.
- Publish aggregate evidence, not raw workspaces or model output.
- Do not infer Fable parity or general model superiority from pilot samples.

## Pull requests

Keep commits atomic and include the exact checks you ran. Security-boundary
changes need tests for both the permitted path and the rejected path.
