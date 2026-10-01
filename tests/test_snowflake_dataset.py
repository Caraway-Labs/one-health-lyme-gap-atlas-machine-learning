"""Offline proof of the one bounded, governed DEV dataset read."""

import pytest

from lyme_gap_atlas_ml.snowflake import CONTEXT_SQL, ContextError, ExpectedContext
from lyme_gap_atlas_ml.snowflake.connector import read_dev_county_sample

EXPECTED = ExpectedContext(
    "OH_LYME_DEV_READ", "ONE_HEALTH_LYME_GAP_ATLAS_DEV", "PRESENTATION", "DEV_WH"
)


class FakeConnection:
    def __init__(self, rows: list[tuple[object, ...]], role: str = "OH_LYME_DEV_READ") -> None:
        self.rows = rows
        self.role = role
        self.queries: list[str] = []

    def cursor(self) -> "FakeConnection":
        return self

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def execute(self, query: str) -> None:
        self.queries.append(query)

    def fetchone(self) -> tuple[str, ...]:
        return (
            "fixture-reader",
            self.role,
            "ONE_HEALTH_LYME_GAP_ATLAS_DEV",
            "PRESENTATION",
            "DEV_WH",
        )

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows


def test_read_checks_context_first_and_preserves_source_states() -> None:
    rows = [
        ("fixture-null", None, "MISSING"),
        ("fixture-status", "NO_COUNTY_LINKED_RECORD", "NO_COUNTY_LINKED_RECORD"),
    ]
    connection = FakeConnection(rows)
    assert read_dev_county_sample(connection, EXPECTED) == rows
    assert connection.queries[0] == CONTEXT_SQL
    query = connection.queries[1]
    assert "FROM ONE_HEALTH_LYME_GAP_ATLAS_DEV.PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V" in query
    assert "WHERE county_fips = '01001'" in query
    assert "ORDER BY measure_id, county_fips, period_start, observation_id" in query
    assert "LIMIT 10;" in query
    assert "release_version" in query and "observation_limitations" in query


def test_context_mismatch_blocks_dataset_query() -> None:
    connection = FakeConnection([], role="OH_LYME_PROD_READ")
    with pytest.raises(ContextError, match="current_role"):
        read_dev_county_sample(connection, EXPECTED)
    assert connection.queries == [CONTEXT_SQL]


@pytest.mark.parametrize(
    "role,database",
    [
        ("ACCOUNTADMIN", "ONE_HEALTH_LYME_GAP_ATLAS_DEV"),
        ("OH_LYME_DEV_OWNER", "ONE_HEALTH_LYME_GAP_ATLAS_DEV"),
        ("OH_LYME_DEV_READ", "ONE_HEALTH_LYME_GAP_ATLAS_PROD"),
    ],
)
def test_unsafe_expected_context_blocks_all_queries(role: str, database: str) -> None:
    connection = FakeConnection([])
    with pytest.raises(ContextError, match="approved DEV read context"):
        read_dev_county_sample(
            connection, ExpectedContext(role, database, "PRESENTATION", "DEV_WH")
        )
    assert not connection.queries


def test_unexpected_row_overflow_fails() -> None:
    with pytest.raises(ContextError, match="row bound"):
        read_dev_county_sample(FakeConnection([(None,)] * 11), EXPECTED)


def test_schema_selection_is_session_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from lyme_gap_atlas_ml.snowflake import connector

    calls = []

    class FakeConnector:
        def connect(self, **kwargs: object) -> object:
            calls.append(kwargs)
            return object()

    monkeypatch.setattr(connector, "import_module", lambda _name: FakeConnector())
    connector.open_local_connection("fixture-selector")
    connector.open_local_connection("fixture-selector", schema="PRESENTATION")
    assert calls == [
        {"connection_name": "fixture-selector"},
        {"connection_name": "fixture-selector", "schema": "PRESENTATION"},
    ]
