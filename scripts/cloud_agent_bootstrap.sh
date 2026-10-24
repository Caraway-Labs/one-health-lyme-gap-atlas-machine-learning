#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "cloud_agent_bootstrap: uv is not on PATH; see docs/runbooks/cursor-cloud-agent.md" >&2
  exit 1
fi

echo "cloud_agent_bootstrap: syncing locked dev dependencies"
uv sync --locked --extra dev

echo "cloud_agent_bootstrap: running offline verification"
uv run python scripts/verify.py

echo "cloud_agent_bootstrap: complete"
