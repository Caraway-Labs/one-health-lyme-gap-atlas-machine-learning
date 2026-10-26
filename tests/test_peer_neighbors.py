"""Fake-session tests for the issue 192 neighbor table. No live Snowflake connection."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from lyme_gap_atlas_ml.peer_lookup import ExperimentMetric, ExperimentRow, NeighborRow
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE
from lyme_gap_atlas_ml.snowflake.ml_agent_access import IDENTITY_SQL, ML_AGENT_ROLE
from lyme_gap_atlas_ml.snowflake.peer_neighbors import (
    NEIGHBOR_TABLE,
    READER_ROLES,
    RunAlreadyWritten,
    mark_run_finished,
    neighbor_table_sql,
    write_neighbor_tables,
)


class FakeSession:
    def __init__(self, existing: int = 0) -> None:
        self.existing = existing
        self.calls: list[str] = []
        self.params: list[tuple[object, ...]] = []

    def query(self, sql: str, params: Sequence[object] | None = None) -> list[tuple[object, ...]]:
        self.calls.append(sql)
        if sql == IDENTITY_SQL:
            return [(ML_AGENT_ROLE, "OH_LYME_ML_LAB_XS_WH", ML_LAB_DATABASE)]
        if sql.startswith("SELECT COUNT"):
            return [(self.existing,)]
        if sql.startswith("SHOW GRANTS"):
            return [(role, "SELECT", NEIGHBOR_TABLE) for role in READER_ROLES]
        raise AssertionError(sql if params is None else f"{sql} {params}")

    def execute(self, sql: str, params: Sequence[object]) -> None:
        self.calls.append(sql)
        self.params.append(tuple(params))


def _neighbor() -> NeighborRow:
    return NeighborRow(
        fips="48001",
        county_name="Example",
        state="TX",
        cluster_id=1,
        situation="other",
        prototype_cluster_id=1,
        euclidean_neighbors="48003,48005,48007,48009,48011",
        cosine_neighbors="48003,48005,48007,48009,48013",
        euclidean_distance_k=0.4,
        baseline_peer_n=12,
        leave_state_type_agreement=0.6,
    )


def _experiment() -> ExperimentRow:
    return ExperimentRow(
        experiment_id="11111111-1111-1111-1111-111111111111",
        hypothesis="Euclidean neighbors.",
        model_family="euclidean_knn",
        config={"k": 5},
        split_definition={"unit": "county"},
        status="succeeded",
        metrics=(
            ExperimentMetric("national", "lso_jaccard", 0.2, 100, 0.1, 0.3),
            ExperimentMetric("national", "tiny", 1.0, 4, None, None),
        ),
    )


def test_table_sql_is_insert_only_in_the_lab() -> None:
    sql = neighbor_table_sql()
    assert ML_LAB_DATABASE in sql
    assert "PEER_COUNTY_NEIGHBORS_192" in sql
    assert "DELETE" not in sql.upper()


def test_write_grants_both_reader_roles_and_skips_a_small_metric() -> None:
    session = FakeSession()
    result = write_neighbor_tables(
        session,
        "192-peer-county-lookup-20261026T1800Z",
        [_neighbor()],
        [_experiment()],
    )
    assert result["neighbors"] == 1
    grants = str(result["grants"])
    assert grants == "OH_LYME_PROD_READ=pass,OH_LYME_ML_LAB_READ=pass"
    joined = "\n".join(session.calls)
    bound = " ".join(str(item) for params in session.params for item in params)
    for role in READER_ROLES:
        assert f"GRANT SELECT ON TABLE {NEIGHBOR_TABLE} TO ROLE {role}" in joined
    assert "tiny" not in bound
    assert "lso_jaccard" in bound
    assert "DELETE" not in joined.upper()


def test_second_write_is_refused() -> None:
    session = FakeSession(existing=1)
    with pytest.raises(RunAlreadyWritten):
        write_neighbor_tables(
            session,
            "192-peer-county-lookup-20261026T1800Z",
            [_neighbor()],
            [_experiment()],
        )


def test_finished_at_is_one_update() -> None:
    session = FakeSession()
    assert mark_run_finished(session, "192-peer-county-lookup-20261026T1800Z") == "pass"
    assert any(sql.startswith("UPDATE") and "FINISHED_AT" in sql for sql in session.calls)
    assert all("DELETE" not in sql.upper() for sql in session.calls)
