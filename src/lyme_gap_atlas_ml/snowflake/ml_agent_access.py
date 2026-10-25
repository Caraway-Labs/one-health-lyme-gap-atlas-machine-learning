"""ML agent access-boundary check. Live sessions stay behind an injected opener."""

from __future__ import annotations

import contextlib
import logging
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import Literal, Protocol, TextIO
from uuid import uuid4

ML_AGENT_ROLE = "OH_LYME_ML_AGENT"
ML_AGENT_CONNECTION_NAME = "atlas_ml_agent"
PROD_DATABASE = "ONE_HEALTH_LYME_GAP_ATLAS_PROD"
PROD_READ_SCHEMAS = frozenset({"CONFORMED", "FEATURE_STORE", "PRESENTATION"})
DEFAULT_PROD_READ_OBJECT = f"{PROD_DATABASE}.PRESENTATION.CURRENT_RELEASE_V"
DEFAULT_PROD_WRITE_SCHEMA = f"{PROD_DATABASE}.PRESENTATION"
REQUIRED_ENV = (
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_ROLE",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_PAT",
)
IDENTITY_SQL = "SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE()"
REFUSED_ROLE = "role is not OH_LYME_ML_AGENT"
REFUSED_INCOMPLETE = "session context is incomplete"
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_SECRET_ASSIGNMENT = re.compile(r"(?i)\b(token|password|passwd|secret|pat)\b(\s*[=:]\s*)(\S+)")
CheckStatus = Literal["pass", "fail"]


class ConfigError(ValueError):
    """Connection settings or check targets are missing or not allow-listed."""


class StatementError(Exception):
    """A statement failed. The message is generic so it cannot carry a secret."""

    def __init__(self, *, permission_denied: bool) -> None:
        super().__init__("statement failed")
        self.permission_denied = permission_denied


class StatementExecutor(Protocol):
    def query(self, sql: str) -> Sequence[Sequence[object]]: ...


@dataclass(frozen=True)
class CheckLine:
    name: str
    status: CheckStatus


@dataclass(frozen=True)
class MlAgentConnectionSettings:
    account: str
    user: str
    role: str
    warehouse: str
    database: str
    schema: str
    token: str

    def __repr__(self) -> str:
        return (
            "MlAgentConnectionSettings("
            f"role={self.role!r}, warehouse={self.warehouse!r}, "
            f"database={self.database!r}, schema={self.schema!r})"
        )


@dataclass(frozen=True)
class AccessCheckConfig:
    prod_read_object: str
    prod_write_schema: str
    scratch_schema: str
    lab_database: str

    def __post_init__(self) -> None:
        lab = _identifier(self.lab_database, "ML Lab database")
        if lab == PROD_DATABASE:
            raise ConfigError("ML Lab database must not be the PROD database")
        scratch = _qualified(self.scratch_schema, 2, "scratch schema")
        scratch_database, scratch_schema = scratch.split(".")
        if scratch_database != lab or scratch_schema != "SCRATCH":
            raise ConfigError("scratch write target must be the ML Lab SCRATCH schema")
        prod_write = _qualified(self.prod_write_schema, 2, "prod write schema")
        _require_prod_allow_list(prod_write)
        prod_read = _qualified(self.prod_read_object, 3, "prod read object")
        _require_prod_allow_list(prod_read.rsplit(".", 1)[0])
        object.__setattr__(self, "lab_database", lab)
        object.__setattr__(self, "scratch_schema", scratch)
        object.__setattr__(self, "prod_write_schema", prod_write)
        object.__setattr__(self, "prod_read_object", prod_read)


@dataclass(frozen=True)
class AccessReport:
    role: str
    warehouse: str
    database: str
    checks: tuple[CheckLine, ...]
    refused: str | None
    prod_write_allowed: bool
    cleanup_failed: bool

    def exit_code(self) -> int:
        if self.refused or self.prod_write_allowed or self.cleanup_failed:
            return 1
        if len(self.checks) != 3 or any(check.status != "pass" for check in self.checks):
            return 1
        return 0

    def render(self) -> str:
        lines = [
            f"role: {self.role}",
            f"warehouse: {self.warehouse}",
            f"database: {self.database}",
        ]
        if self.refused:
            lines.append(f"refused: {self.refused}")
        else:
            lines.extend(f"{check.name}: {check.status}" for check in self.checks)
            if self.cleanup_failed:
                lines.append("prod_write_cleanup: fail")
        return "\n".join(lines) + "\n"


def load_ml_agent_request(
    environ: Mapping[str, str],
) -> tuple[MlAgentConnectionSettings, AccessCheckConfig]:
    missing = [name for name in REQUIRED_ENV if not environ.get(name, "").strip()]
    if missing:
        raise ConfigError("missing required environment variables: " + ", ".join(missing))
    database = environ["SNOWFLAKE_DATABASE"].strip()
    settings = MlAgentConnectionSettings(
        account=environ["SNOWFLAKE_ACCOUNT"].strip(),
        user=environ["SNOWFLAKE_USER"].strip(),
        role=environ["SNOWFLAKE_ROLE"].strip(),
        warehouse=environ["SNOWFLAKE_WAREHOUSE"].strip(),
        database=database,
        schema="SCRATCH",
        token=environ["SNOWFLAKE_PAT"].strip(),
    )
    config = AccessCheckConfig(
        prod_read_object=environ.get("ATLAS_ML_AGENT_PROD_READ_OBJECT", "").strip()
        or DEFAULT_PROD_READ_OBJECT,
        prod_write_schema=environ.get("ATLAS_ML_AGENT_PROD_WRITE_SCHEMA", "").strip()
        or DEFAULT_PROD_WRITE_SCHEMA,
        scratch_schema=environ.get("ATLAS_ML_AGENT_SCRATCH_SCHEMA", "").strip()
        or f"{database}.SCRATCH",
        lab_database=database,
    )
    return settings, config


def connect_kwargs(settings: MlAgentConnectionSettings) -> dict[str, object]:
    """PAT kwargs for snowflake.connector.connect. Callers must not log the result."""
    return {
        "account": settings.account,
        "user": settings.user,
        "role": settings.role,
        "warehouse": settings.warehouse,
        "database": settings.database,
        "schema": settings.schema,
        "authenticator": "PROGRAMMATIC_ACCESS_TOKEN",
        "token": settings.token,
    }


def open_ml_agent_connection(settings: MlAgentConnectionSettings) -> object:
    """Open the ML agent session. The snowflake extra is optional."""
    try:
        connector = import_module("snowflake.connector")
    except ImportError as error:
        raise RuntimeError("Install the optional snowflake dependency group") from error
    logging.getLogger("snowflake.connector").setLevel(logging.CRITICAL)
    connect = connector.connect
    return connect(**connect_kwargs(settings))


def redact_text(text: str, secrets: Sequence[str]) -> str:
    redacted = text
    for secret in sorted((item for item in secrets if len(item) >= 4), key=len, reverse=True):
        redacted = redacted.replace(secret, "[REDACTED]")
    return _SECRET_ASSIGNMENT.sub(r"\1\2[REDACTED]", redacted)


def is_permission_error(error: BaseException) -> bool:
    errno = getattr(error, "errno", None)
    if isinstance(errno, int) and errno in {3001, 3041}:
        return True
    if isinstance(errno, str) and errno.isdigit() and int(errno) in {3001, 3041}:
        return True
    sqlstate = getattr(error, "sqlstate", None)
    if isinstance(sqlstate, str) and sqlstate == "42501":
        return True
    text = str(error).lower()
    return any(
        phrase in text
        for phrase in (
            "insufficient privileges",
            "not authorized",
            "access control error",
            "permission denied",
        )
    )


class CursorStatementExecutor:
    def __init__(self, connection: object) -> None:
        self._connection = connection

    def query(self, sql: str) -> list[tuple[object, ...]]:
        cursor_factory = getattr(self._connection, "cursor", None)
        if not callable(cursor_factory):
            raise StatementError(permission_denied=False)
        try:
            with cursor_factory() as cursor:
                cursor.execute(sql)
                description = cursor.description
                if description is None:
                    return []
                fetched = cursor.fetchall()
        except StatementError:
            raise
        except Exception as error:
            raise StatementError(permission_denied=is_permission_error(error)) from None
        return [tuple(row) for row in fetched]

    def execute(self, sql: str, params: Sequence[object] = ()) -> None:
        """Run one bound statement. Parameter values stay out of the SQL text."""
        cursor_factory = getattr(self._connection, "cursor", None)
        if not callable(cursor_factory):
            raise StatementError(permission_denied=False)
        try:
            with cursor_factory() as cursor:
                if params:
                    cursor.execute(sql, tuple(params))
                else:
                    cursor.execute(sql)
        except StatementError:
            raise
        except Exception as error:
            raise StatementError(permission_denied=is_permission_error(error)) from None


def default_table_name() -> str:
    return "CTX_" + uuid4().hex.upper()


def run_ml_agent_access_checks(
    executor: StatementExecutor,
    config: AccessCheckConfig,
    *,
    table_name_factory: Callable[[], str] = default_table_name,
) -> AccessReport:
    """Run the three boundary checks. Refuse before them unless the role matches."""
    try:
        rows = executor.query(IDENTITY_SQL)
    except StatementError:
        return _refused("", "", "", REFUSED_INCOMPLETE)
    if len(rows) != 1:
        return _refused("", "", "", REFUSED_INCOMPLETE)
    role, warehouse, database = (_cell(value) for value in _three(rows[0]))
    if not role or not warehouse or not database:
        return _refused(role, warehouse, database, REFUSED_INCOMPLETE)
    if role.upper() != ML_AGENT_ROLE:
        return _refused(role, warehouse, database, REFUSED_ROLE)

    select_line = _line("prod_select", _ok(executor, _select_sql(config.prod_read_object)))
    scratch_line = _scratch_write(executor, config.scratch_schema, table_name_factory)
    prod_line, prod_write_allowed, cleanup_failed = _prod_write_denied(
        executor, config.prod_write_schema, table_name_factory
    )
    checks = (select_line, scratch_line, prod_line)
    return AccessReport(
        role=role,
        warehouse=warehouse,
        database=database,
        checks=checks,
        refused=None,
        prod_write_allowed=prod_write_allowed,
        cleanup_failed=cleanup_failed,
    )


def main(
    *,
    environ: Mapping[str, str] | None = None,
    opener: Callable[[MlAgentConnectionSettings], object] | None = None,
    executor_factory: Callable[[object], StatementExecutor] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    env = os.environ if environ is None else environ
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    role = env.get("SNOWFLAKE_ROLE", "").strip()
    if role and role.upper() != ML_AGENT_ROLE:
        refusal = (
            f"role: {role}\n"
            f"warehouse: {env.get('SNOWFLAKE_WAREHOUSE', '').strip()}\n"
            f"database: {env.get('SNOWFLAKE_DATABASE', '').strip()}\n"
            f"refused: {REFUSED_ROLE}\n"
        )
        out.write(
            redact_text(
                refusal,
                (
                    env.get("SNOWFLAKE_PAT", ""),
                    env.get("SNOWFLAKE_PASSWORD", ""),
                    env.get("SNOWFLAKE_ACCOUNT", ""),
                    env.get("SNOWFLAKE_USER", ""),
                ),
            )
        )
        return 1
    try:
        settings, config = load_ml_agent_request(env)
    except ConfigError as error:
        print(str(error), file=err)
        return 2
    secrets = (
        settings.token,
        settings.account,
        settings.user,
        env.get("SNOWFLAKE_PASSWORD", ""),
    )
    try:
        connection = (opener or open_ml_agent_connection)(settings)
    except Exception as error:
        print(f"connection failed: {redact_text(str(error), secrets)}", file=err)
        return 1
    try:
        executor = (
            CursorStatementExecutor(connection)
            if executor_factory is None
            else executor_factory(connection)
        )
        report = run_ml_agent_access_checks(executor, config)
    except Exception as error:
        print(f"context check failed: {redact_text(str(error), secrets)}", file=err)
        return 1
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            with contextlib.suppress(Exception):
                close()
    out.write(report.render())
    return report.exit_code()


def _identifier(value: str, label: str) -> str:
    if _IDENT.fullmatch(value) is None:
        raise ConfigError(f"invalid Snowflake identifier for {label}")
    return value.upper()


def _qualified(value: str, parts: int, label: str) -> str:
    pieces = value.split(".")
    if len(pieces) != parts:
        raise ConfigError(f"invalid Snowflake identifier for {label}")
    return ".".join(_identifier(piece, label) for piece in pieces)


def _require_prod_allow_list(database_schema: str) -> None:
    database, schema = database_schema.split(".")
    if database != PROD_DATABASE or schema not in PROD_READ_SCHEMAS:
        raise ConfigError(
            "PROD object must be an allow-listed CONFORMED, FEATURE_STORE, or PRESENTATION object"
        )


def _table(name: str) -> str:
    if _IDENT.fullmatch(name) is None:
        raise ConfigError("invalid generated table name")
    return name.upper()


def _select_sql(object_name: str) -> str:
    return f"SELECT 1 FROM {object_name} LIMIT 1"


def _create_scratch_sql(schema: str, table: str) -> str:
    return f"CREATE TEMPORARY TABLE {schema}.{table} (PROBE_OK NUMBER)"


def _create_prod_sql(schema: str, table: str) -> str:
    return f"CREATE TABLE {schema}.{table} (PROBE_OK NUMBER)"


def _drop_sql(schema: str, table: str) -> str:
    return f"DROP TABLE IF EXISTS {schema}.{table}"


def _cell(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _three(row: Sequence[object]) -> tuple[object, object, object]:
    if isinstance(row, (str, bytes)) or len(row) != 3:
        return ("", "", "")
    return row[0], row[1], row[2]


def _refused(role: str, warehouse: str, database: str, reason: str) -> AccessReport:
    return AccessReport(
        role=role,
        warehouse=warehouse,
        database=database,
        checks=(),
        refused=reason,
        prod_write_allowed=False,
        cleanup_failed=False,
    )


def _line(name: str, passed: bool) -> CheckLine:
    return CheckLine(name, "pass" if passed else "fail")


def _ok(executor: StatementExecutor, sql: str) -> bool:
    try:
        executor.query(sql)
    except StatementError:
        return False
    return True


def _scratch_write(
    executor: StatementExecutor,
    schema: str,
    table_name_factory: Callable[[], str],
) -> CheckLine:
    table = _table(table_name_factory())
    created = _ok(executor, _create_scratch_sql(schema, table))
    dropped = created and _ok(executor, _drop_sql(schema, table))
    return _line("scratch_write", created and dropped)


def _prod_write_denied(
    executor: StatementExecutor,
    schema: str,
    table_name_factory: Callable[[], str],
) -> tuple[CheckLine, bool, bool]:
    table = _table(table_name_factory())
    try:
        executor.query(_create_prod_sql(schema, table))
    except StatementError as error:
        return _line("prod_write_denied", error.permission_denied), False, False
    cleanup_failed = not _ok(executor, _drop_sql(schema, table))
    return _line("prod_write_denied", False), True, cleanup_failed
