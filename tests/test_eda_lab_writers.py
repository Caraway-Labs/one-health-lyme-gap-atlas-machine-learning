"""Fake-session coverage for the ML Lab EDA table writers. No live Snowflake connection."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from lyme_gap_atlas_ml.snowflake.eda_lab_writers import (
    COLUMN_PROFILE_COLUMNS,
    COLUMN_PROFILE_SQL,
    CORRELATION_COLUMNS,
    CORRELATION_SQL,
    FINDINGS_COLUMNS,
    FINDINGS_SQL,
    MISSINGNESS_COLUMNS,
    MISSINGNESS_SQL,
    QUERY_COLUMNS,
    QUERY_SQL,
    ColumnProfileRecord,
    CorrelationRecord,
    FindingRecord,
    MissingnessRecord,
    QueryRecord,
    prepare_column_profile,
    prepare_correlation,
    prepare_finding,
    prepare_missingness,
    prepare_query,
    write_column_profiles,
    write_correlations,
    write_findings,
    write_missingness,
    write_missingness_from_environment,
    write_queries,
)
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    REFUSED_DATABASE,
    SMALL_CELL_MINIMUM,
    EdaWriteError,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    IDENTITY_SQL,
    ML_AGENT_ROLE,
    PROD_DATABASE,
    REFUSED_ROLE,
    MlAgentConnectionSettings,
    StatementError,
)

TOKEN = "test-only-pat"
ATLAS = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V"
FINDING_ID = "11111111-1111-1111-1111-111111111111"
RUN_ID = "109-coverage-missingness-20261025T0000Z"
PERCENTILES = {
    "p01": 1.0,
    "p05": 2.0,
    "p25": 3.0,
    "p50": 4.0,
    "p75": 5.0,
    "p95": 6.0,
    "p99": 7.0,
}


class FakeSession:
    def __init__(self, role: str = ML_AGENT_ROLE) -> None:
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []
        self.role = role
        self.fail_execute = False

    def query(self, sql: str) -> list[tuple[object, ...]]:
        self.calls.append((sql, None))
        if sql == IDENTITY_SQL:
            return [(self.role, "OH_LYME_ML_LAB_XS_WH", ML_LAB_DATABASE)]
        raise AssertionError(sql)

    def execute(self, sql: str, params: Sequence[object]) -> None:
        self.calls.append((sql, tuple(params)))
        if self.fail_execute:
            raise StatementError(permission_denied=True)


def _env(**overrides: str) -> dict[str, str]:
    values = {
        "SNOWFLAKE_ACCOUNT": "account",
        "SNOWFLAKE_USER": "OH_LYME_ML_AGENT_SVC",
        "SNOWFLAKE_ROLE": ML_AGENT_ROLE,
        "SNOWFLAKE_WAREHOUSE": "OH_LYME_ML_LAB_XS_WH",
        "SNOWFLAKE_DATABASE": ML_LAB_DATABASE,
        "SNOWFLAKE_PAT": TOKEN,
    }
    values.update(overrides)
    return values


def test_insert_sql_uses_the_live_columns_and_omits_defaults() -> None:
    expected = {
        "EDA.FINDINGS": (FINDINGS_SQL, FINDINGS_COLUMNS),
        "EDA.MISSINGNESS": (MISSINGNESS_SQL, MISSINGNESS_COLUMNS),
        "EDA.COLUMN_PROFILES": (COLUMN_PROFILE_SQL, COLUMN_PROFILE_COLUMNS),
        "EDA.CORRELATIONS": (CORRELATION_SQL, CORRELATION_COLUMNS),
        "REGISTRY.QUERIES": (QUERY_SQL, QUERY_COLUMNS),
    }
    for table, (sql, columns) in expected.items():
        assert sql.startswith(f"INSERT INTO {ML_LAB_DATABASE}.{table} (")
        assert "CREATED_AT" not in sql
        assert "EXECUTED_AT" not in sql
        assert "ISSUE" not in sql.split("SELECT", maxsplit=1)[0]
        assert "FILE_NAME" not in sql
        assert "DRIVE_LINK" not in sql
        head = sql.split(" SELECT ", maxsplit=1)[0]
        for column in columns:
            assert column in head
        assert PROD_DATABASE not in sql


def test_missingness_suppresses_small_gaps_and_small_complements() -> None:
    kept = prepare_missingness(
        MissingnessRecord(ATLAS, "HUMAN_STATUS", missing_n=2493, total_n=3144)
    )
    zero = prepare_missingness(
        MissingnessRecord(ATLAS, "SVI_PERCENTILE", missing_n=0, total_n=3144)
    )
    small_gap = prepare_missingness(
        MissingnessRecord(ATLAS, "HUMAN_STATUS", missing_n=SMALL_CELL_MINIMUM - 1, total_n=3144)
    )
    small_complement = prepare_missingness(
        MissingnessRecord(ATLAS, "NLCD", missing_n=3142, total_n=3144)
    )
    small_total = prepare_missingness(
        MissingnessRecord(ATLAS, "HUMAN_STATUS", missing_n=2, total_n=5)
    )

    assert kept.suppressed is False
    assert kept.missing_n == 2493
    assert kept.missing_pct == pytest.approx(2493 / 3144)
    assert zero.suppressed is False
    assert zero.missing_n == 0
    assert zero.missing_pct == 0.0
    assert small_gap.missing_n is None
    assert small_gap.missing_pct is None
    assert small_gap.total_n == 3144
    assert small_complement.missing_n is None
    assert small_complement.total_n == 3144
    assert 3142 not in small_complement.bind(RUN_ID)
    assert small_total.total_n is None
    assert small_total.missing_n is None
    assert 2 not in small_total.bind(RUN_ID)
    assert 5 not in small_total.bind(RUN_ID)


def test_profile_clears_small_samples_and_small_level_lists() -> None:
    cleared = prepare_column_profile(
        ColumnProfileRecord(ATLAS, "CASE_COUNT_FLOOR_2023", row_count=4, null_count=1, mean_value=9)
    )
    assert cleared.row_count is None
    assert cleared.mean_value is None
    assert 4 not in cleared.bind(RUN_ID)

    levels = prepare_column_profile(
        ColumnProfileRecord(
            ATLAS,
            "HUMAN_STATUS",
            row_count=100,
            null_count=0,
            top_values=(
                {"value": "published_count_floor", "n": 90},
                {"value": "rare_level", "n": 10},
            ),
        )
    )
    assert levels.top_values_json is None
    assert levels.suppressed is True
    assert 10 not in levels.bind(RUN_ID)

    safe = prepare_column_profile(
        ColumnProfileRecord(
            ATLAS,
            "HUMAN_STATUS",
            row_count=3144,
            null_count=0,
            distinct_count=2,
            percentiles=PERCENTILES,
            top_values=(
                {"value": "published_count_floor", "n": 651},
                {"value": "no_county_linked_record", "n": 2493},
            ),
        )
    )
    assert safe.suppressed is False
    assert safe.top_values_json is not None
    assert "no_county_linked_record" in safe.top_values_json
    assert safe.percentiles[3] == 4.0

    extremes = prepare_column_profile(
        ColumnProfileRecord(
            ATLAS,
            "STATE_UNALLOCATED_RECORDS_2023",
            row_count=51,
            null_count=0,
            min_value="3",
            max_value="293",
            count_extremes=True,
        )
    )
    assert extremes.min_value is None
    assert extremes.max_value == "293"
    assert "3" not in extremes.bind(RUN_ID)


def test_correlation_and_finding_drop_small_cells() -> None:
    hidden = prepare_correlation(
        CorrelationRecord("SVI_PERCENTILE", "RUCC_2023", "pearson", n=8, coefficient=0.4)
    )
    assert hidden.n is None
    assert hidden.coefficient is None
    assert 8 not in hidden.bind(RUN_ID)
    assert 0.4 not in hidden.bind(RUN_ID)

    shown = prepare_correlation(
        CorrelationRecord("SVI_PERCENTILE", "RUCC_2023", "pearson", n=651, coefficient=0.2)
    )
    assert shown.n == 651
    assert shown.coefficient == pytest.approx(0.2)

    finding = prepare_finding(
        FindingRecord(
            topic="headline_reproduction",
            statement="2,493 counties have no county-linked human record.",
            disposition="keep",
            n_underlying=3144,
            evidence={"published_floor": 651, "sparse_cell": 4, "share": 0.2},
            effect_size=2493 / 3144,
        ),
        finding_id=FINDING_ID,
    )
    assert finding.suppressed is True
    assert finding.evidence_json is not None
    assert '"sparse_cell":null' in finding.evidence_json
    assert finding.effect_size == pytest.approx(2493 / 3144)

    small = prepare_finding(
        FindingRecord(
            topic="sparse",
            statement="A coverage cell is below the small-cell minimum.",
            disposition="follow-up",
            n_underlying=4,
            effect_size=0.5,
            ci_low=0.1,
            ci_high=0.9,
        ),
        finding_id=FINDING_ID,
    )
    assert small.effect_size is None
    assert small.ci_low is None
    assert small.ci_high is None


def test_query_keeps_result_cardinality_and_rejects_free_text() -> None:
    kept = prepare_query(
        QueryRecord(
            "SELECT COUNT(*) AS N FROM "
            "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
            rows_returned=1,
            elapsed_ms=20,
            snowflake_query_id="01b2c3d4-1111-2222-3333-444444444444",
        )
    )
    assert kept.rows_returned == 1
    assert len(kept.sql_sha256) == 64

    null_check = prepare_query(
        QueryRecord(
            "SELECT SUM(IFF(GEOMETRY_JSON IS NULL, 1, 0)) AS GEOMETRY_NULL_N FROM atlas",
            rows_returned=1,
            elapsed_ms=5,
        )
    )
    assert "GEOMETRY_JSON IS NULL" in null_check.sql_text

    with pytest.raises(EdaWriteError, match="geometry"):
        prepare_query(QueryRecord("SELECT GEOMETRY_JSON FROM atlas", rows_returned=1, elapsed_ms=1))
    with pytest.raises(EdaWriteError, match="free-text"):
        prepare_query(QueryRecord("SELECT PART_TEXT FROM atlas", rows_returned=1, elapsed_ms=1))
    with pytest.raises(EdaWriteError, match="one statement"):
        prepare_query(QueryRecord("SELECT 1; SELECT 2", rows_returned=1, elapsed_ms=1))


def test_writers_insert_under_the_run_id_and_refuse_other_databases() -> None:
    session = FakeSession()
    missing = write_missingness(
        session,
        RUN_ID,
        (MissingnessRecord(ATLAS, "SVI_PERCENTILE", missing_n=0, total_n=3144),),
    )
    profiles = write_column_profiles(
        session,
        RUN_ID,
        (ColumnProfileRecord(ATLAS, "POPULATION", row_count=3144, null_count=0),),
    )
    correlations = write_correlations(
        session,
        RUN_ID,
        (CorrelationRecord("SVI_PERCENTILE", "POPULATION", "pearson", n=4, coefficient=0.1),),
    )
    findings = write_findings(
        session,
        RUN_ID,
        (
            FindingRecord(
                topic="headline_reproduction",
                statement="The headline counts match the October 13 reference.",
                disposition="keep",
                n_underlying=3144,
            ),
        ),
        ids=(FINDING_ID,),
    )
    queries = write_queries(
        session,
        RUN_ID,
        (
            QueryRecord(
                "SELECT COUNT(*) AS N FROM "
                "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
                rows_returned=1,
                elapsed_ms=8,
            ),
        ),
    )

    assert missing.rows_written == 1
    assert missing.table == "EDA.MISSINGNESS"
    assert profiles.table == "EDA.COLUMN_PROFILES"
    assert correlations.rows_suppressed == 1
    assert findings.rows_written == 1
    assert queries.database == ML_LAB_DATABASE
    inserted = [sql for sql, params in session.calls if params is not None]
    assert inserted[0] == MISSINGNESS_SQL
    assert inserted[1] == COLUMN_PROFILE_SQL
    assert inserted[2] == CORRELATION_SQL
    assert inserted[3] == FINDINGS_SQL
    assert inserted[4] == QUERY_SQL
    assert all(params is not None and RUN_ID in params for _sql, params in session.calls if params)

    with pytest.raises(EdaWriteError, match="ML_LAB"):
        write_findings(
            session,
            RUN_ID,
            (),
            database=PROD_DATABASE,
        )


def test_environment_writer_refuses_prod_without_connecting() -> None:
    def opener(_settings: MlAgentConnectionSettings) -> object:
        raise AssertionError("connection should not open")

    with pytest.raises(EdaWriteError, match="PROD"):
        write_missingness_from_environment(
            _env(SNOWFLAKE_DATABASE=PROD_DATABASE),
            RUN_ID,
            (MissingnessRecord(ATLAS, "POPULATION", missing_n=0, total_n=3144),),
            opener=opener,
        )
    with pytest.raises(EdaWriteError, match=REFUSED_DATABASE):
        write_missingness_from_environment(
            _env(SNOWFLAKE_DATABASE="ONE_HEALTH_LYME_GAP_ATLAS_DEV"),
            RUN_ID,
            (),
            opener=opener,
        )
    with pytest.raises(EdaWriteError, match=REFUSED_ROLE):
        write_missingness_from_environment(
            _env(SNOWFLAKE_ROLE="ACCOUNTADMIN"),
            RUN_ID,
            (),
            opener=opener,
        )


def test_statement_text_does_not_keep_a_driver_error() -> None:
    session = FakeSession()
    session.fail_execute = True
    with pytest.raises(EdaWriteError, match="statement failed") as caught:
        write_queries(
            session,
            RUN_ID,
            (QueryRecord("SELECT 1 AS N", rows_returned=1, elapsed_ms=1),),
        )
    assert TOKEN not in str(caught.value)
