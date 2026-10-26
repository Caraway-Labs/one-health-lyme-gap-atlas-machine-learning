"""Fake-session tests for the issue 190 flag table. No live Snowflake connection."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from lyme_gap_atlas_ml.doc_outliers import ExperimentMetric, ExperimentRow, FlagRow
from lyme_gap_atlas_ml.snowflake.doc_outlier_flags import (
    FLAG_TABLE,
    READER_ROLE,
    RunAlreadyWritten,
    flag_table_sql,
    write_flag_tables,
)
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE
from lyme_gap_atlas_ml.snowflake.ml_agent_access import IDENTITY_SQL, ML_AGENT_ROLE


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
            return [(READER_ROLE, "SELECT", FLAG_TABLE)]
        raise AssertionError(sql if params is None else f"{sql} {params}")

    def execute(self, sql: str, params: Sequence[object]) -> None:
        self.calls.append(sql)
        self.params.append(tuple(params))


def _flag() -> FlagRow:
    return FlagRow(
        fips="48001",
        county_name="Example",
        state="TX",
        state_n=254,
        complete_n=254,
        size_band="100_plus",
        scored=True,
        incomplete=False,
        score_robust_z=1.0,
        flag_robust_z=False,
        score_if_primary=0.2,
        flag_if_primary=True,
        score_if_seed_b=0.1,
        flag_if_seed_b=False,
        score_lof=1.2,
        flag_lof=False,
        bootstrap_rate_if=0.8,
        dominant_feature="floor_present",
        stable_useful=False,
        situation_121="other",
        cluster_id_120=None,
    )


def _experiment() -> ExperimentRow:
    return ExperimentRow(
        experiment_id="11111111-1111-1111-1111-111111111111",
        hypothesis="Within-state isolation forest.",
        model_family="isolation_forest",
        config={"trees": 100},
        split_definition={"unit": "county"},
        status="succeeded",
        metrics=(
            ExperimentMetric("within_state", "flag_rate", 0.05, 100, 0.01, 0.08),
            ExperimentMetric("within_state", "tiny", 1.0, 4, None, None),
        ),
    )


def test_table_sql_is_insert_only_in_the_lab() -> None:
    sql = flag_table_sql()
    assert ML_LAB_DATABASE in sql
    assert "COUNTY_DOC_FLAGS_190" in sql
    assert "DELETE" not in sql.upper()


def test_write_grants_select_and_skips_a_small_metric() -> None:
    session = FakeSession()
    result = write_flag_tables(
        session,
        "190-within-state-doc-outliers-20261026T1700Z",
        [_flag()],
        [_experiment()],
    )
    assert result["granted"] is True
    assert result["grant_verified"] == "pass"
    assert result["flags"] == 1
    joined = "\n".join(session.calls)
    bound = " ".join(str(item) for params in session.params for item in params)
    assert f"GRANT SELECT ON TABLE {FLAG_TABLE} TO ROLE {READER_ROLE}" in joined
    assert "tiny" not in bound
    assert "flag_rate" in bound


def test_second_write_is_refused() -> None:
    session = FakeSession(existing=1)
    with pytest.raises(RunAlreadyWritten):
        write_flag_tables(
            session,
            "190-within-state-doc-outliers-20261026T1700Z",
            [_flag()],
            [_experiment()],
        )
