"""Fake-session coverage for the ML agent access-boundary check."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import types
from collections.abc import Callable, Mapping, Sequence
from io import StringIO
from pathlib import Path

import pytest

from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    DEFAULT_PROD_READ_OBJECT,
    IDENTITY_SQL,
    REFUSED_ROLE,
    AccessCheckConfig,
    ConfigError,
    CursorStatementExecutor,
    MlAgentConnectionSettings,
    StatementError,
    connect_kwargs,
    is_permission_error,
    load_ml_agent_request,
    main,
    open_ml_agent_connection,
    redact_text,
    run_ml_agent_access_checks,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_ml_agent_context.py"
TOKEN = "test-only-pat"
ACCOUNT = "test-account"
USER = "test-user"


def _env(**overrides: str) -> dict[str, str]:
    values = {
        "SNOWFLAKE_ACCOUNT": ACCOUNT,
        "SNOWFLAKE_USER": USER,
        "SNOWFLAKE_ROLE": "OH_LYME_ML_AGENT",
        "SNOWFLAKE_WAREHOUSE": "OH_LYME_ML_LAB_XS_WH",
        "SNOWFLAKE_DATABASE": "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB",
        "SNOWFLAKE_PAT": TOKEN,
    }
    values.update(overrides)
    return values


def _config(**overrides: str) -> AccessCheckConfig:
    _settings, config = load_ml_agent_request(_env(**overrides))
    return config


class FakeExecutor:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.role = "OH_LYME_ML_AGENT"
        self.warehouse = "OH_LYME_ML_LAB_XS_WH"
        self.database = "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB"
        self.select_error = False
        self.scratch_create_error = False
        self.scratch_drop_error = False
        self.prod_create = "deny"
        self.prod_drop_error = False
        self.identity_row: tuple[object, ...] | None = None
        self.identity_rows: Sequence[Sequence[object]] | None = None

    def query(self, sql: str) -> list[tuple[object, ...]]:
        self.statements.append(sql)
        if sql == IDENTITY_SQL:
            if self.identity_rows is not None:
                return [tuple(row) for row in self.identity_rows]
            if self.identity_row is not None:
                return [self.identity_row]
            return [(self.role, self.warehouse, self.database)]
        if sql.startswith("SELECT 1 FROM "):
            if self.select_error:
                raise StatementError(permission_denied=True)
            return [(1,)]
        if sql.startswith("CREATE TEMPORARY TABLE "):
            if self.scratch_create_error:
                raise StatementError(permission_denied=True)
            return []
        if sql.startswith("CREATE TABLE "):
            if self.prod_create == "deny":
                raise StatementError(permission_denied=True)
            if self.prod_create == "other":
                raise StatementError(permission_denied=False)
            return []
        if sql.startswith("DROP TABLE IF EXISTS ") and ".SCRATCH." in sql:
            if self.scratch_drop_error:
                raise StatementError(permission_denied=False)
            return []
        if sql.startswith("DROP TABLE IF EXISTS "):
            if self.prod_drop_error:
                raise StatementError(permission_denied=False)
            return []
        raise AssertionError(sql)


def _names() -> object:
    pending = iter(("CTX_SCRATCH", "CTX_PROD"))

    def factory() -> str:
        return next(pending)

    return factory


def _run(executor: FakeExecutor, **overrides: str) -> object:
    factory = _names()
    assert callable(factory)
    return run_ml_agent_access_checks(executor, _config(**overrides), table_name_factory=factory)


def test_three_checks_pass_and_print_context() -> None:
    executor = FakeExecutor()
    report = _run(executor)
    assert report.exit_code() == 0
    assert report.prod_write_allowed is False
    rendered = report.render()
    assert rendered == (
        "role: OH_LYME_ML_AGENT\n"
        "warehouse: OH_LYME_ML_LAB_XS_WH\n"
        "database: ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB\n"
        "prod_select: pass\n"
        "scratch_write: pass\n"
        "prod_write_denied: pass\n"
    )
    assert executor.statements == [
        IDENTITY_SQL,
        f"SELECT 1 FROM {DEFAULT_PROD_READ_OBJECT} LIMIT 1",
        "CREATE TEMPORARY TABLE ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.SCRATCH.CTX_SCRATCH "
        "(PROBE_OK NUMBER)",
        "DROP TABLE IF EXISTS ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.SCRATCH.CTX_SCRATCH",
        "CREATE TABLE ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CTX_PROD (PROBE_OK NUMBER)",
    ]
    assert TOKEN not in rendered
    assert "TEMPORARY" not in executor.statements[-1]


def test_prod_write_allowed_fails_and_drops_the_table() -> None:
    executor = FakeExecutor()
    executor.prod_create = "allow"
    report = _run(executor)
    assert report.exit_code() == 1
    assert report.prod_write_allowed is True
    assert "prod_write_denied: fail" in report.render()
    assert executor.statements[-1] == (
        "DROP TABLE IF EXISTS ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CTX_PROD"
    )


def test_prod_write_cleanup_failure_stays_nonzero() -> None:
    executor = FakeExecutor()
    executor.prod_create = "allow"
    executor.prod_drop_error = True
    report = _run(executor)
    assert report.exit_code() == 1
    assert report.cleanup_failed is True
    rendered = report.render()
    assert "prod_write_denied: fail" in rendered
    assert "prod_write_cleanup: fail" in rendered
    assert any(sql.startswith("DROP TABLE IF EXISTS ") for sql in executor.statements)


def test_non_permission_prod_error_is_not_a_denial() -> None:
    executor = FakeExecutor()
    executor.prod_create = "other"
    report = _run(executor)
    assert report.exit_code() == 1
    assert report.prod_write_allowed is False
    assert report.checks[-1].status == "fail"
    prod_drops = [
        sql for sql in executor.statements if sql.startswith("DROP") and "PRESENTATION" in sql
    ]
    assert prod_drops == []


def test_wrong_session_role_skips_the_three_checks() -> None:
    executor = FakeExecutor()
    executor.role = "ACCOUNTADMIN"
    report = _run(executor)
    assert report.exit_code() == 1
    assert report.refused == REFUSED_ROLE
    assert executor.statements == [IDENTITY_SQL]
    assert "prod_select:" not in report.render()
    assert "role: ACCOUNTADMIN" in report.render()


def test_lowercase_session_role_is_accepted() -> None:
    executor = FakeExecutor()
    executor.role = "oh_lyme_ml_agent"
    report = _run(executor)
    assert report.exit_code() == 0


def test_incomplete_session_refuses_before_checks() -> None:
    executor = FakeExecutor()
    executor.identity_row = ("OH_LYME_ML_AGENT", "", "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB")
    report = _run(executor)
    assert report.exit_code() == 1
    assert report.refused == "session context is incomplete"
    assert executor.statements == [IDENTITY_SQL]


def test_select_and_scratch_failures_still_attempt_prod_denial() -> None:
    executor = FakeExecutor()
    executor.select_error = True
    executor.scratch_create_error = True
    report = _run(executor)
    assert report.exit_code() == 1
    assert [check.status for check in report.checks] == ["fail", "fail", "pass"]
    assert not any("SCRATCH" in sql and sql.startswith("DROP") for sql in executor.statements)
    assert any(sql.startswith("CREATE TABLE ") for sql in executor.statements)


def test_scratch_drop_failure_fails_the_check() -> None:
    executor = FakeExecutor()
    executor.scratch_drop_error = True
    report = _run(executor)
    assert report.checks[1].status == "fail"
    assert report.exit_code() == 1


def test_configurable_allow_listed_object_is_used() -> None:
    executor = FakeExecutor()
    object_name = "one_health_lyme_gap_atlas_prod.feature_store.tier1_review_batches"
    report = _run(executor, ATLAS_ML_AGENT_PROD_READ_OBJECT=object_name)
    assert report.exit_code() == 0
    assert (
        "SELECT 1 FROM ONE_HEALTH_LYME_GAP_ATLAS_PROD.FEATURE_STORE.TIER1_REVIEW_BATCHES LIMIT 1"
        in executor.statements
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"ATLAS_ML_AGENT_PROD_READ_OBJECT": "ONE_HEALTH_LYME_GAP_ATLAS_PROD.GOVERNANCE.USERS"},
        {"ATLAS_ML_AGENT_PROD_READ_OBJECT": "ONE_HEALTH_LYME_GAP_ATLAS_PROD.RAW.EVENTS"},
        {"ATLAS_ML_AGENT_PROD_READ_OBJECT": "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.BAD NAME"},
        {
            "ATLAS_ML_AGENT_PROD_WRITE_SCHEMA": "ONE_HEALTH_LYME_GAP_ATLAS_PROD.GOVERNANCE",
        },
        {"ATLAS_ML_AGENT_SCRATCH_SCHEMA": "ONE_HEALTH_LYME_GAP_ATLAS_PROD.SCRATCH"},
        {"SNOWFLAKE_DATABASE": "ONE_HEALTH_LYME_GAP_ATLAS_PROD"},
    ],
)
def test_targets_outside_the_allow_list_are_rejected(overrides: dict[str, str]) -> None:
    with pytest.raises(ConfigError) as caught:
        _config(**overrides)
    message = str(caught.value)
    assert TOKEN not in message
    assert "BAD NAME" not in message
    assert "GOVERNANCE" not in message


def test_missing_environment_names_the_variables_not_the_values() -> None:
    with pytest.raises(ConfigError, match="SNOWFLAKE_PAT") as caught:
        load_ml_agent_request({"SNOWFLAKE_ROLE": "OH_LYME_ML_AGENT"})
    assert TOKEN not in str(caught.value)


def test_settings_repr_and_connect_kwargs_keep_the_token_out_of_repr() -> None:
    settings, _config_value = load_ml_agent_request(_env())
    text = repr(settings)
    assert TOKEN not in text
    assert ACCOUNT not in text
    assert USER not in text
    kwargs = connect_kwargs(settings)
    assert kwargs["authenticator"] == "PROGRAMMATIC_ACCESS_TOKEN"
    assert kwargs["token"] == TOKEN
    assert kwargs["schema"] == "SCRATCH"
    assert "password" not in kwargs


def test_connection_errors_are_redacted() -> None:
    raw = f"auth failed token={TOKEN} account {ACCOUNT} user {USER} role OH_LYME_ML_AGENT"
    redacted = redact_text(raw, (TOKEN, ACCOUNT, USER))
    assert TOKEN not in redacted
    assert ACCOUNT not in redacted
    assert USER not in redacted
    assert "OH_LYME_ML_AGENT" in redacted
    assert "token=[REDACTED]" in redacted


def test_permission_error_detection() -> None:
    class Denied(Exception):
        errno = 3001
        sqlstate = "42501"

    assert is_permission_error(Denied("Insufficient privileges to operate on schema"))
    assert is_permission_error(Exception("access control error"))
    assert not is_permission_error(Exception("SQL compilation error: invalid identifier"))


def test_cursor_adapter_maps_permission_errors_without_the_driver_message() -> None:
    class Denied(Exception):
        errno = 3001
        sqlstate = "42501"

        def __str__(self) -> str:
            return f"003001 (42501): Insufficient privileges token={TOKEN}"

    class Cursor:
        description = None

        def __enter__(self) -> Cursor:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def execute(self, sql: str) -> None:
            if sql.startswith("CREATE TABLE "):
                raise Denied()

        def fetchall(self) -> list[tuple[object, ...]]:
            return []

    class Connection:
        def cursor(self) -> Cursor:
            return Cursor()

    executor = CursorStatementExecutor(Connection())
    statement = (
        "CREATE TABLE ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CTX_PROD (PROBE_OK NUMBER)"
    )
    with pytest.raises(StatementError) as caught:
        executor.query(statement)
    assert caught.value.permission_denied is True
    assert TOKEN not in str(caught.value)


def test_main_refuses_wrong_role_without_connecting() -> None:
    def opener(_settings: MlAgentConnectionSettings) -> object:
        raise AssertionError("connection should not open")

    code, output, error = _invoke(opener, _env(SNOWFLAKE_ROLE="ACCOUNTADMIN"))
    assert code == 1
    assert "role: ACCOUNTADMIN\n" in output
    assert "warehouse: OH_LYME_ML_LAB_XS_WH\n" in output
    assert "database: ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB\n" in output
    assert f"refused: {REFUSED_ROLE}" in output
    assert "prod_select:" not in output
    assert TOKEN not in output + error
    assert error == ""


def test_main_redacts_opener_failures_and_closes_on_success() -> None:
    def opener(settings: MlAgentConnectionSettings) -> object:
        raise RuntimeError(f"login failed for {settings.token} at {settings.account}")

    code, output, error = _invoke(opener, _env())
    assert code == 1
    assert output == ""
    assert "connection failed:" in error
    assert TOKEN not in error
    assert ACCOUNT not in error

    closed = {"value": False}

    class Connection:
        def close(self) -> None:
            closed["value"] = True

    executor = FakeExecutor()
    code, output, error = _invoke(
        lambda _settings: Connection(),
        _env(),
        executor_factory=lambda _connection: executor,
    )
    assert code == 0
    assert closed["value"] is True
    assert "prod_write_denied: pass" in output
    assert TOKEN not in output + error


def test_open_uses_programmatic_access_token_kwargs(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    package = types.ModuleType("snowflake")
    connector = types.ModuleType("snowflake.connector")

    def connect(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    connector.connect = connect  # type: ignore[attr-defined]
    package.connector = connector  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "snowflake", package)
    monkeypatch.setitem(sys.modules, "snowflake.connector", connector)
    logger = logging.getLogger("snowflake.connector")
    previous = logger.level
    try:
        settings, _config_value = load_ml_agent_request(_env())
        open_ml_agent_connection(settings)
        assert logger.level == logging.CRITICAL
    finally:
        logger.setLevel(previous)
    assert captured["authenticator"] == "PROGRAMMATIC_ACCESS_TOKEN"
    assert captured["token"] == TOKEN
    assert "password" not in captured


def test_script_refuses_wrong_role_without_a_live_connection() -> None:
    env = _child_env(_env(SNOWFLAKE_ROLE="OH_LYME_DEV_READ"))
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 1
    assert f"refused: {REFUSED_ROLE}" in result.stdout
    assert TOKEN not in combined
    assert ACCOUNT not in combined


def test_script_missing_env_does_not_echo_values() -> None:
    env = _child_env({})
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 2
    assert "SNOWFLAKE_PAT" in result.stderr
    assert "missing required environment variables" in result.stderr


def _invoke(
    opener: Callable[[MlAgentConnectionSettings], object],
    environ: Mapping[str, str],
    executor_factory: Callable[[object], FakeExecutor] | None = None,
) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    code = main(
        environ=environ,
        opener=opener,
        executor_factory=executor_factory,
        stdout=stdout,
        stderr=stderr,
    )
    return code, stdout.getvalue(), stderr.getvalue()


def _child_env(updates: Mapping[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(("SNOWFLAKE_", "ATLAS_")):
            env.pop(key, None)
    env.update(updates)
    return env
