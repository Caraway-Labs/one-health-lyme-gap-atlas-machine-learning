#!/usr/bin/env bash
set -euo pipefail

missing=()
require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    missing+=("$name")
  fi
}

require_var SNOWFLAKE_CONNECTION_NAME
require_var SNOWFLAKE_ACCOUNT
require_var SNOWFLAKE_USER
require_var SNOWFLAKE_ROLE
require_var SNOWFLAKE_DATABASE
require_var SNOWFLAKE_SCHEMA
require_var SNOWFLAKE_WAREHOUSE

if [[ -z "${SNOWFLAKE_PAT:-}" && -z "${SNOWFLAKE_PASSWORD:-}" ]]; then
  missing+=("SNOWFLAKE_PAT or SNOWFLAKE_PASSWORD")
fi

if ((${#missing[@]} > 0)); then
  echo "bootstrap_cloud_snowflake_connection: missing required environment variables:" >&2
  for name in "${missing[@]}"; do
    echo "  - $name" >&2
  done
  exit 1
fi

if ! command -v snow >/dev/null 2>&1; then
  echo "bootstrap_cloud_snowflake_connection: snow CLI is not on PATH; see docs/runbooks/cursor-cloud-agent.md" >&2
  exit 1
fi

CONFIG_DIR="${SNOWFLAKE_CLI_CONFIG_DIR:-${SNOWFLAKE_CONFIG_DIR:-$HOME/.snowflake}}"
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

export SNOWFLAKE_CLI_CONFIG_DIR="$CONFIG_DIR"

python3 <<'PY'
import os
from pathlib import Path

config_dir = Path(os.environ["SNOWFLAKE_CLI_CONFIG_DIR"])
config_dir.mkdir(parents=True, exist_ok=True)
config_dir.chmod(0o700)

connection_name = os.environ["SNOWFLAKE_CONNECTION_NAME"]
connections_file = config_dir / "connections.toml"

fields = {
    "account": os.environ["SNOWFLAKE_ACCOUNT"],
    "user": os.environ["SNOWFLAKE_USER"],
    "role": os.environ["SNOWFLAKE_ROLE"],
    "warehouse": os.environ["SNOWFLAKE_WAREHOUSE"],
    "database": os.environ["SNOWFLAKE_DATABASE"],
    "schema": os.environ["SNOWFLAKE_SCHEMA"],
}

lines = [f"[{connection_name}]"]
for key, value in fields.items():
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    lines.append(f'{key} = "{escaped}"')

pat = os.environ.get("SNOWFLAKE_PAT", "")
password = os.environ.get("SNOWFLAKE_PASSWORD", "")
if pat:
    token_file = config_dir / f"cloud_agent_{connection_name}_pat"
    token_file.write_text(pat, encoding="utf-8")
    token_file.chmod(0o600)
    token_path = str(token_file).replace("\\", "\\\\")
    lines.append('authenticator = "PROGRAMMATIC_ACCESS_TOKEN"')
    lines.append(f'token_file_path = "{token_path}"')
elif password:
    escaped = password.replace("\\", "\\\\").replace('"', '\\"')
    lines.append(f'password = "{escaped}"')
else:
    raise SystemExit("missing SNOWFLAKE_PAT or SNOWFLAKE_PASSWORD")

connections_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
connections_file.chmod(0o600)
PY

echo "bootstrap_cloud_snowflake_connection: wrote connection definition (no secret values logged)"

if [[ "${SNOWFLAKE_BOOTSTRAP_SKIP_CONTEXT_CHECK:-}" == "1" ]]; then
  exit 0
fi

snow sql -c "$SNOWFLAKE_CONNECTION_NAME" -q \
  'SELECT CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE()'
