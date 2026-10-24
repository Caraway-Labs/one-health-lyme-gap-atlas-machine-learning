"""Offline checks for Cloud Agent Snowflake bootstrap scripts."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap_cloud_snowflake_connection.sh"


def test_bootstrap_missing_env_fails_closed() -> None:
    if sys.platform == "win32":
        pytest.skip("bootstrap shell script is exercised on Linux CI")
    try:
        subprocess.run(["bash", "--version"], check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        pytest.skip(f"bash unavailable: {error}")
    env = os.environ.copy()
    for key in (
        "SNOWFLAKE_CONNECTION_NAME",
        "SNOWFLAKE_ACCOUNT",
        "SNOWFLAKE_USER",
        "SNOWFLAKE_PAT",
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_ROLE",
        "SNOWFLAKE_DATABASE",
        "SNOWFLAKE_SCHEMA",
        "SNOWFLAKE_WAREHOUSE",
    ):
        env.pop(key, None)
    result = subprocess.run(
        ["bash", str(BOOTSTRAP)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "missing required environment variables" in result.stderr
