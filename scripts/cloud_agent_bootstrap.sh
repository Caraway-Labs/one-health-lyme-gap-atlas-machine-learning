#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v uv >/dev/null 2>&1; then
  echo "cloud_agent_bootstrap: uv is not on PATH; see docs/runbooks/cursor-cloud-agent.md" >&2
  exit 1
fi

SNOWFLAKE_ENABLED=0
if [[ -n "${SNOWFLAKE_ACCOUNT:-}" ]]; then
  SNOWFLAKE_ENABLED=1
  echo "cloud_agent_bootstrap: configuring Snowflake CLI connection from Runtime secrets"
  export SNOWFLAKE_BOOTSTRAP_SKIP_CONTEXT_CHECK="${SNOWFLAKE_BOOTSTRAP_SKIP_CONTEXT_CHECK:-1}"
  bash scripts/bootstrap_cloud_snowflake_connection.sh
fi

if [[ "$SNOWFLAKE_ENABLED" -eq 1 ]]; then
  echo "cloud_agent_bootstrap: syncing locked dev + snowflake dependencies"
  uv sync --locked --extra dev --extra snowflake
else
  echo "cloud_agent_bootstrap: syncing locked dev dependencies"
  uv sync --locked --extra dev
fi

echo "cloud_agent_bootstrap: running offline verification"
uv run python scripts/verify.py

echo "cloud_agent_bootstrap: complete"
