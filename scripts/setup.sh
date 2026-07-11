#!/usr/bin/env bash
# Super SOL plugin bootstrap: provision the locked environment and prove the
# harness works with an offline dry-run smoke. Never runs billable evaluation.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required but not installed." >&2
  echo "Install it first: https://docs.astral.sh/uv/getting-started/installation/" >&2
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 1
fi

echo "==> Provisioning Python 3.12 and locked dependencies"
uv python install 3.12
uv sync --locked --dev

echo "==> Offline dry-run smoke (no API key, no Docker, no billing)"
SMOKE_DIR=".fablized/plugin-smoke"
RUN_ID="plugin-smoke-$(date +%Y%m%d-%H%M%S)"
uv run super-sol-eval \
  --tasks eval/tasks.example.json \
  --output-dir "$SMOKE_DIR" \
  --run-id "$RUN_ID" \
  --dry-run

EVENTS="$SMOKE_DIR/$RUN_ID/events.jsonl"
if [[ ! -s "$EVENTS" ]]; then
  echo "ERROR: expected dry-run events at $EVENTS but found none." >&2
  exit 1
fi

PLANNED="$(grep -c '"run_planned"' "$EVENTS" || true)"
echo "==> Smoke OK: $PLANNED run_planned events in $EVENTS"
echo "==> Super SOL is ready. Try: /super-sol:eval (dry-run) or /super-sol:report"
