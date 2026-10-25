"""Offline checks for Cloud Agent Snowflake bootstrap scripts."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from lyme_gap_atlas_ml.snowflake.ml_agent_access import ML_AGENT_CONNECTION_NAME

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap_cloud_snowflake_connection.sh"
CLOUD_BOOTSTRAP = ROOT / "scripts" / "cloud_agent_bootstrap.sh"
TOKEN = "test-only-pat"
PASSWORD = "test-only-password"
ACCOUNT = "test-account"


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
    assert TOKEN not in result.stdout + result.stderr


def test_level_b_still_requires_connection_name_and_schema(tmp_path: Path) -> None:
    env = _env(tmp_path)
    env.update(
        {
            "SNOWFLAKE_ACCOUNT": ACCOUNT,
            "SNOWFLAKE_USER": "test-user",
            "SNOWFLAKE_PASSWORD": PASSWORD,
            "SNOWFLAKE_ROLE": "OH_LYME_DEV_READ",
            "SNOWFLAKE_DATABASE": "ONE_HEALTH_LYME_GAP_ATLAS_DEV",
            "SNOWFLAKE_WAREHOUSE": "DEV_WH",
        }
    )
    result = _run(env)
    assert result.returncode != 0
    assert "SNOWFLAKE_CONNECTION_NAME" in result.stderr
    assert "SNOWFLAKE_SCHEMA" in result.stderr
    assert PASSWORD not in result.stdout + result.stderr
    assert not (tmp_path / "snowflake" / "connections.toml").exists()


def test_ml_agent_bootstrap_uses_only_the_six_variables(tmp_path: Path) -> None:
    calls = tmp_path / "snow-called"
    _install_fake_snow(tmp_path, calls)
    env = _env(tmp_path)
    env.update(
        {
            "SNOWFLAKE_ACCOUNT": ACCOUNT,
            "SNOWFLAKE_USER": "test-user",
            "SNOWFLAKE_ROLE": "OH_LYME_ML_AGENT",
            "SNOWFLAKE_WAREHOUSE": "OH_LYME_ML_LAB_XS_WH",
            "SNOWFLAKE_DATABASE": "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB",
            "SNOWFLAKE_PAT": TOKEN,
            "SNOWFLAKE_PASSWORD": PASSWORD,
            "PATH": f"{tmp_path / 'bin'}:{env['PATH']}",
        }
    )
    result = _run(env)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert "wrote connection definition" in result.stdout
    assert TOKEN not in combined
    assert PASSWORD not in combined
    assert ACCOUNT not in combined
    assert "test-user" not in combined
    assert not calls.exists()

    config_dir = tmp_path / "snowflake"
    parsed = tomllib.loads((config_dir / "connections.toml").read_text(encoding="utf-8"))
    connection = parsed[ML_AGENT_CONNECTION_NAME]
    assert connection["authenticator"] == "PROGRAMMATIC_ACCESS_TOKEN"
    assert connection["schema"] == "SCRATCH"
    assert connection["role"] == "OH_LYME_ML_AGENT"
    assert connection["database"] == "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB"
    assert "password" not in connection
    token_file = Path(str(connection["token_file_path"]))
    assert token_file.read_text(encoding="utf-8") == TOKEN
    assert TOKEN not in (config_dir / "connections.toml").read_text(encoding="utf-8")
    assert PASSWORD not in (config_dir / "connections.toml").read_text(encoding="utf-8")
    assert token_file.stat().st_mode & 0o777 == 0o600
    assert (config_dir / "connections.toml").stat().st_mode & 0o777 == 0o600


def test_ml_agent_password_without_pat_is_rejected(tmp_path: Path) -> None:
    env = _env(tmp_path)
    env.update(
        {
            "SNOWFLAKE_ACCOUNT": ACCOUNT,
            "SNOWFLAKE_USER": "test-user",
            "SNOWFLAKE_ROLE": "OH_LYME_ML_AGENT",
            "SNOWFLAKE_WAREHOUSE": "OH_LYME_ML_LAB_XS_WH",
            "SNOWFLAKE_DATABASE": "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB",
            "SNOWFLAKE_PASSWORD": PASSWORD,
        }
    )
    result = _run(env)
    assert result.returncode != 0
    assert "SNOWFLAKE_PAT" in result.stderr
    assert PASSWORD not in result.stdout + result.stderr
    assert not (tmp_path / "snowflake" / "connections.toml").exists()


def test_level_b_password_connection_still_writes(tmp_path: Path) -> None:
    env = _env(tmp_path)
    env.update(
        {
            "SNOWFLAKE_CONNECTION_NAME": "dev_read",
            "SNOWFLAKE_ACCOUNT": ACCOUNT,
            "SNOWFLAKE_USER": "test-user",
            "SNOWFLAKE_PASSWORD": PASSWORD,
            "SNOWFLAKE_ROLE": "OH_LYME_DEV_READ",
            "SNOWFLAKE_DATABASE": "ONE_HEALTH_LYME_GAP_ATLAS_DEV",
            "SNOWFLAKE_SCHEMA": "PRESENTATION",
            "SNOWFLAKE_WAREHOUSE": "DEV_WH",
        }
    )
    result = _run(env)
    assert result.returncode == 0, result.stderr
    toml_text = (tmp_path / "snowflake" / "connections.toml").read_text(encoding="utf-8")
    parsed = tomllib.loads(toml_text)
    assert parsed["dev_read"]["password"] == PASSWORD
    assert "authenticator" not in parsed["dev_read"]
    assert PASSWORD not in result.stdout + result.stderr


def test_cloud_bootstrap_does_not_invoke_the_live_context_check() -> None:
    text = CLOUD_BOOTSTRAP.read_text(encoding="utf-8")
    assert "check_ml_agent_context.py" not in text
    assert "SNOWFLAKE_BOOTSTRAP_SKIP_CONTEXT_CHECK" in text


def _env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("SNOWFLAKE_", "ATLAS_")):
            env.pop(key, None)
    env["SNOWFLAKE_CLI_CONFIG_DIR"] = str(tmp_path / "snowflake")
    env["SNOWFLAKE_BOOTSTRAP_SKIP_CONTEXT_CHECK"] = "1"
    return env


def _run(env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    if sys.platform == "win32":
        pytest.skip("bootstrap shell script is exercised on Linux CI")
    return subprocess.run(
        ["bash", str(BOOTSTRAP)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _install_fake_snow(tmp_path: Path, calls: Path) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "snow"
    fake.write_text(
        "#!/bin/sh\n" + f"echo called > '{calls}'\n" + "exit 99\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
