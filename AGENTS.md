# Repository Engineering Rules

- Use Python 3.12 or later and manage environments, dependencies, and builds with `uv`.
- Follow red-green-refactor: add a focused failing test before changing runtime behavior.
- Keep production and test Python files at or below 250 non-comment, non-blank lines.
- Maintain strict typing under `basedpyright` and Ruff's `ALL` rule set; do not add untyped
  escape hatches or blanket suppressions.
- Use immutable typed models at internal boundaries and Pydantic models for untrusted input.
- Match tagged variants exhaustively and keep IDs, tool kinds, outcomes, and events typed.
- Preserve the separation between model-visible instructions, enforcement ledgers, and
  out-of-band measurement data.
- Keep runtime model instructions in package assets and their routing code, not in this file.
- Keep the default test suite and CI non-live. Do not run billable API evaluations without an
  explicit repository-owner request.
- Make atomic commits and do not publish packages, create remotes, or expose credentials.

## Verification Commands

```bash
uv sync --locked --dev
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest --cov=fablized_sol --cov-report=term-missing
uv build
find src tests -name '*.py' -print0 | xargs -0 -n1 sh -c 'printf "%s " "$0"; awk "NF && !/^[[:space:]]*#/ {n++} END {print n+0}" "$0"'
```
