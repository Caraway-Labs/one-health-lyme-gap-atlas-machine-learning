import pytest

from lyme_gap_atlas_ml.snowflake import (
    CONTEXT_SQL,
    ContextError,
    ExpectedContext,
    SnowflakeContext,
    check_context,
    connection_name_from_environment,
)
from lyme_gap_atlas_ml.snowflake.connector import ConnectorContextReader
from lyme_gap_atlas_ml.snowflake.policy import ExecutionPolicy

ROW = ("reader", "OH_LYME_DEV_READ", "OH_LYME_DEV", "PUBLIC", "DEV_WH")
EXPECTED = ExpectedContext("OH_LYME_DEV_READ", "OH_LYME_DEV", "PUBLIC", "DEV_WH")


class FakeReader:
    def fetch_context_row(self) -> tuple[str, ...]:
        return ROW


class FakeCursor:
    def __init__(self) -> None:
        self.executed: str | None = None

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def execute(self, sql: str) -> None:
        self.executed = sql

    def fetchone(self) -> tuple[str, ...]:
        return ROW


class FakeConnection:
    def __init__(self) -> None:
        self.fake_cursor = FakeCursor()

    def cursor(self) -> FakeCursor:
        return self.fake_cursor


def test_valid_context_and_fake_session() -> None:
    assert check_context(FakeReader(), EXPECTED) == SnowflakeContext(*ROW)
    connection = FakeConnection()
    assert check_context(ConnectorContextReader(connection), EXPECTED).current_user == "reader"
    assert connection.fake_cursor.executed == CONTEXT_SQL


@pytest.mark.parametrize("missing", range(5))
def test_missing_context_fails(missing: int) -> None:
    row: list[object] = list(ROW)
    row[missing] = None
    with pytest.raises(ContextError, match="incomplete"):
        SnowflakeContext.from_row(row)


def test_mismatched_context_fails() -> None:
    with pytest.raises(ContextError, match="current_role"):
        ExpectedContext("ACCOUNTADMIN", "OH_LYME_DEV", "PUBLIC", "DEV_WH").validate(
            SnowflakeContext(*ROW)
        )


def test_missing_connection_configuration_fails() -> None:
    with pytest.raises(ContextError, match="SNOWFLAKE_CONNECTION_NAME"):
        connection_name_from_environment({})


def test_connection_name_stays_out_of_context_representation() -> None:
    assert connection_name_from_environment({"SNOWFLAKE_CONNECTION_NAME": "private_alias"}) == (
        "private_alias"
    )
    assert "private_alias" not in repr(SnowflakeContext(*ROW))


def test_read_only_default_requires_explicit_write_authorization() -> None:
    with pytest.raises(ContextError, match="Write requires"):
        ExecutionPolicy().require_write("ML_DEV")
    with pytest.raises(ContextError, match="Write requires"):
        ExecutionPolicy("ML_DEV", "story authorization").require_write("PROD")
    ExecutionPolicy("ML_DEV", "story authorization").require_write("ML_DEV")
