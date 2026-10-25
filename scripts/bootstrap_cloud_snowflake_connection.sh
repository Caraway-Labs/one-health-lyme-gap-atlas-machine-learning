#!/usr/bin/env bash
# Build a named Snowflake CLI connection from environment variables.
# Level B (any role other than the ML agent) still requires
# SNOWFLAKE_CONNECTION_NAME, SNOWFLAKE_SCHEMA, and SNOWFLAKE_PAT or
# SNOWFLAKE_PASSWORD. Level C (role OH_LYME_ML_AGENT) reads only
# SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_ROLE, SNOWFLAKE_WAREHOUSE,
# SNOWFLAKE_DATABASE, and SNOWFLAKE_PAT. This script never prints secrets.
set -euo pipefail

missing=()
require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    missing+=("$name")
  fi
}

require_var SNOWFLAKE_ACCOUNT
require_var SNOWFLAKE_USER
require_var SNOWFLAKE_ROLE
require_var SNOWFLAKE_WAREHOUSE
require_var SNOWFLAKE_DATABASE

role_key="$(printf '%s' "${SNOWFLAKE_ROLE:-}" | tr '[:lower:]' '[:upper:]' | tr -d '[:space:]')"
if [[ "$role_key" == "OH_LYME_ML_AGENT" ]]; then
  require_var SNOWFLAKE_PAT
  if [[ -z "${SNOWFLAKE_CONNECTION_NAME:-}" ]]; then
    SNOWFLAKE_CONNECTION_NAME="atlas_ml_agent"
    export SNOWFLAKE_CONNECTION_NAME
  fi
  if [[ -z "${SNOWFLAKE_SCHEMA:-}" ]]; then
    SNOWFLAKE_SCHEMA="SCRATCH"
    export SNOWFLAKE_SCHEMA
  fi
else
  require_var SNOWFLAKE_CONNECTION_NAME
  require_var SNOWFLAKE_SCHEMA
  if [[ -z "${SNOWFLAKE_PAT:-}" && -z "${SNOWFLAKE_PASSWORD:-}" ]]; then
    missing+=("SNOWFLAKE_PAT or SNOWFLAKE_PASSWORD")
  fi
fi

if ((${#missing[@]} > 0)); then
  echo "bootstrap_cloud_snowflake_connection: missing required environment variables:" >&2
  for name in "${missing[@]}"; do
    echo "  - $name" >&2
  done
  exit 1
fi

if [[ "${SNOWFLAKE_BOOTSTRAP_SKIP_CONTEXT_CHECK:-}" != "1" ]]; then
  if ! command -v snow >/dev/null 2>&1; then
    echo "bootstrap_cloud_snowflake_connection: snow CLI is not on PATH; see docs/runbooks/cursor-cloud-agent.md" >&2
    exit 1
  fi
fi

CONFIG_DIR="${SNOWFLAKE_CLI_CONFIG_DIR:-${SNOWFLAKE_CONFIG_DIR:-$HOME/.snowflake}}"
mkdir -p "$CONFIG_DIR"
chmod 700 "$CONFIG_DIR"

export SNOWFLAKE_CLI_CONFIG_DIR="$CONFIG_DIR"

python3 <<'PY'
import os
import re
from pathlib import Path

config_dir = Path(os.environ["SNOWFLAKE_CLI_CONFIG_DIR"])
config_dir.mkdir(parents=True, exist_ok=True)
config_dir.chmod(0o700)

connection_name = os.environ["SNOWFLAKE_CONNECTION_NAME"]
if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", connection_name) is None:
    raise SystemExit("invalid connection name")

connections_file = config_dir / "connections.toml"
role = os.environ["SNOWFLAKE_ROLE"].strip().upper()

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
password = "" if role == "OH_LYME_ML_AGENT" else os.environ.get("SNOWFLAKE_PASSWORD", "")
if role == "OH_LYME_ML_AGENT" and not pat:
    raise SystemExit("missing SNOWFLAKE_PAT")
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
