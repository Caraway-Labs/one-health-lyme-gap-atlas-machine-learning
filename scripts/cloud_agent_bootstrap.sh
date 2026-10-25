#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Pinned to the standalone installer documented at
# https://docs.astral.sh/uv/getting-started/installation/
UV_VERSION="0.13.5"

install_uv_if_missing() {
  if command -v uv >/dev/null 2>&1; then
    return 0
  fi

  echo "cloud_agent_bootstrap: uv is not on PATH; installing ${UV_VERSION}"
  if ! command -v curl >/dev/null 2>&1; then
    echo "cloud_agent_bootstrap: curl is required to install uv" >&2
    exit 1
  fi

  local install_dir="${HOME}/.local/bin"
  mkdir -p "${install_dir}"
  curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" \
    | env UV_UNMANAGED_INSTALL="${install_dir}" sh
  if [[ ! -x "${install_dir}/uv" ]]; then
    echo "cloud_agent_bootstrap: uv installer did not produce ${install_dir}/uv" >&2
    exit 1
  fi

  # Login shells pick up ~/.local/bin from ~/.profile only when that directory
  # already exists at shell start. Copy onto /usr/local/bin, which is on the
  # default PATH for later agent commands, including non-login shells.
  if ! command -v sudo >/dev/null 2>&1; then
    echo "cloud_agent_bootstrap: sudo is required to install uv into /usr/local/bin" >&2
    exit 1
  fi
  sudo install -m 0755 "${install_dir}/uv" /usr/local/bin/uv
  if [[ -x "${install_dir}/uvx" ]]; then
    sudo install -m 0755 "${install_dir}/uvx" /usr/local/bin/uvx
  fi
  hash -r
  if ! command -v uv >/dev/null 2>&1; then
    echo "cloud_agent_bootstrap: uv is still not on PATH after install" >&2
    exit 1
  fi
}

install_uv_if_missing

SNOWFLAKE_ENABLED=0
if [[ -n "${SNOWFLAKE_ACCOUNT:-}" ]]; then
  SNOWFLAKE_ENABLED=1
  echo "cloud_agent_bootstrap: configuring Snowflake CLI connection from Runtime secrets"
  # Writes the named connection only. Skip the identity query here so install
  # never opens a live session. The ML agent access-boundary check is a
  # separate command and is not invoked from this script.
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
