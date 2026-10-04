"""Offline adapter tests: no actual Snowflake values or credentials."""

from types import SimpleNamespace

import pytest

from lyme_gap_atlas_ml.snowflake.context import ContextError
from lyme_gap_atlas_ml.snowflake.evidence_65 import acquire


class FakeCursor:
    sfqid = "fixture-query"

    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, parameters=None, **options):
        self.connection.calls.append((query, parameters, options))
        if "CURRENT_RELEASE_V" in query:
            error = RuntimeError("fixture sensitive message that must not be retained")
            raise error
        return self

    def fetchone(self):
        return (
            "MATTHEWCARAWAY",
            self.connection.role,
            "ONE_HEALTH_LYME_GAP_ATLAS_DEV",
            "PRESENTATION",
            "OH_LYME_DEV_INGEST_XS_WH",
        )


def connection(role):
    value = SimpleNamespace(role=role, calls=[])
    value.cursor = lambda: FakeCursor(value)
    return value


def test_wrong_context_never_queries_release():
    fake = connection("ACCOUNTADMIN")
    with pytest.raises(ContextError):
        acquire(fake)
    assert len(fake.calls) == 1


def test_denial_stops_before_data_counts_unavailable_and_no_secret_message():
    fake = connection("OH_LYME_DEV_READ")
    result = acquire(fake)
    assert len(fake.calls) == 2
    assert fake.calls[1][2]["timeout"] == 30
    assert result["counts"] is None
    assert result["scientific_estimability"] == "UNASSESSED"
    assert result["queries"][0]["status"] == "ACCESS_OR_EXECUTION_BLOCKED"
    assert "sensitive" not in str(result)


class IdentityCursor(FakeCursor):
    def execute(self, query, parameters=None, **options):
        self.connection.calls.append((query, parameters, options))
        if "CURRENT_RELEASE_V" in query:
            self.names = ["RELEASE_ID", "BUNDLE_SHA256"]
            self.rows = [("fixture-release", "a" * 64)]
        elif "CURRENT_SOURCE_METADATA_V" in query:
            self.names = ["RELEASE_VERSION", "SOURCE_KEY", "SOURCE_ID", "DATASET_ID", "VINTAGE"]
            self.rows = [
                (
                    "fixture-release",
                    key,
                    "cdc_arbonet_tick_module",
                    dataset,
                    self.connection.vintage,
                )
                for key, dataset in (
                    ("tick", "cdc-ixodes-county-status-2025"),
                    ("pathogen", "cdc-ixodes-pathogen-status-2025"),
                )
            ]
        elif "CURRENT_COUNTY_ATLAS_V" in query:
            self.names = ["RELEASE_ID", "FIPS"]
            self.rows = [("fixture-release", "01001")]
        else:
            self.names, self.rows = [], []
        self.description = [(name,) for name in self.names]
        return self

    def fetchmany(self, maximum):
        self.connection.fetch_bounds.append(maximum)
        return self.rows[:maximum]


@pytest.mark.parametrize(
    "vintage,expected", [("through 2025-12-31", "ACQUIRED"), ("annual 2025", "BLOCKED")]
)
def test_pinned_source_period_and_bound_parameters_before_county_read(vintage, expected):
    fake = connection("OH_LYME_DEV_READ")
    fake.vintage = vintage
    fake.fetch_bounds = []
    fake.cursor = lambda: IdentityCursor(fake)
    result = acquire(fake)
    assert result["status"] == expected
    assert fake.calls[2][1] == ("fixture-release",)
    assert fake.fetch_bounds[:2] == [3, 4]
    if expected == "ACQUIRED":
        assert len(fake.calls) == 4
        assert fake.calls[3][1] == ("fixture-release",)
        assert fake.fetch_bounds[-1] == 3146
    else:
        assert len(fake.calls) == 3  # no county read after changed period
