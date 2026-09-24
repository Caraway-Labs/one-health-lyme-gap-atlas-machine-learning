"""Read and validate session identity before any agent Snowflake operation."""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

CONTEXT_SQL = """SELECT
    CURRENT_USER() AS CURRENT_USER,
    CURRENT_ROLE() AS CURRENT_ROLE,
    CURRENT_DATABASE() AS CURRENT_DATABASE,
    CURRENT_SCHEMA() AS CURRENT_SCHEMA,
    CURRENT_WAREHOUSE() AS CURRENT_WAREHOUSE
"""
FIELDS = ("current_user", "current_role", "current_database", "current_schema", "current_warehouse")


class ContextError(ValueError):
    """A Snowflake identity or authorization prerequisite was not met."""


@dataclass(frozen=True)
class SnowflakeContext:
    current_user: str
    current_role: str
    current_database: str
    current_schema: str
    current_warehouse: str

    @classmethod
    def from_row(cls, row: Mapping[str, object] | Sequence[object]) -> "SnowflakeContext":
        if isinstance(row, Mapping):
            values = [row.get(field) or row.get(field.upper()) for field in FIELDS]
        else:
            values = list(row)
            if len(values) != len(FIELDS):
                raise ContextError("Snowflake context row has an unexpected shape")
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ContextError("Snowflake context is incomplete or ambiguous")
        return cls(*(str(value).strip() for value in values))


@dataclass(frozen=True)
class ExpectedContext:
    role: str
    database: str
    schema: str
    warehouse: str
    user: str | None = None

    def validate(self, actual: SnowflakeContext) -> None:
        expected = {
            "current_role": self.role,
            "current_database": self.database,
            "current_schema": self.schema,
            "current_warehouse": self.warehouse,
        }
        if self.user is not None:
            expected["current_user"] = self.user
        if any(not value.strip() for value in expected.values()):
            raise ContextError("Expected Snowflake context is incomplete")
        for field, value in expected.items():
            if getattr(actual, field).upper() != value.upper():
                raise ContextError(f"Snowflake {field} does not match authorized context")


class ContextReader(Protocol):
    def fetch_context_row(self) -> Mapping[str, object] | Sequence[object]: ...


def check_context(reader: ContextReader, expected: ExpectedContext) -> SnowflakeContext:
    actual = SnowflakeContext.from_row(reader.fetch_context_row())
    expected.validate(actual)
    return actual


def connection_name_from_environment(environ: Mapping[str, str] | None = None) -> str:
    values = os.environ if environ is None else environ
    name = values.get("SNOWFLAKE_CONNECTION_NAME", "").strip()
    if not name:
        raise ContextError("SNOWFLAKE_CONNECTION_NAME must select an approved local connection")
    return name
