"""Fake-session coverage for the ML Lab EDA writer. No live Snowflake connection."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime

import pytest

from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    REFUSED_DATABASE,
    SMALL_CELL_MINIMUM,
    EdaMetric,
    EdaRun,
    EdaWriteError,
    prepare_eda_metric,
    write_eda_results,
    write_eda_results_from_environment,
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
SMALL_COUNT = 4
SMALL_VALUE = 9876.5
LARGE_COUNT = SMALL_CELL_MINIMUM
LARGE_VALUE = 40.0


def _run(**overrides: object) -> EdaRun:
    values: dict[str, object] = {
        "run_id": "eda-159",
        "purpose": "Aggregate county EDA for issue 159",
        "issue_number": 159,
        "status": "succeeded",
    }
    values.update(overrides)
    return EdaRun(**values)  # type: ignore[arg-type]


def _metric(**overrides: object) -> EdaMetric:
    values: dict[str, object] = {
        "metric_name": "county_count",
        "n_underlying": LARGE_COUNT,
        "metric_value": LARGE_VALUE,
        "geography_type": "state",
        "geography_id": "08",
        "unit": "count",
    }
    values.update(overrides)
    return EdaMetric(**values)  # type: ignore[arg-type]


class FakeSession:
    def __init__(self, role: str = ML_AGENT_ROLE) -> None:
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []
        self.role = role
        self.fail_identity = False
        self.identity_row: tuple[object, ...] | None = None
        self.identity_rows: list[tuple[object, ...]] | None = None
        self.fail_execute = False

    def query(self, sql: str) -> list[tuple[object, ...]]:
        self.calls.append((sql, None))
        if self.fail_identity:
            raise StatementError(permission_denied=False)
        if self.identity_rows is not None:
            return self.identity_rows
        if self.identity_row is not None:
            return [self.identity_row]
        return [(self.role, "OH_LYME_ML_LAB_XS_WH", ML_LAB_DATABASE)]

    def execute(self, sql: str, params: Sequence[object]) -> None:
        bound = tuple(params)
        self.calls.append((sql, bound))
        if self.fail_execute:
            raise StatementError(permission_denied=True)


def _statements(session: FakeSession) -> list[str]:
    return [sql for sql, _params in session.calls]


def _bound(session: FakeSession) -> list[tuple[object, ...]]:
    return [params for _sql, params in session.calls if params is not None]


def test_small_cell_minimum_is_eleven() -> None:
    assert SMALL_CELL_MINIMUM == 11


def test_prepare_suppresses_counts_below_eleven_and_keeps_the_boundary() -> None:
    suppressed = prepare_eda_metric(
        _metric(n_underlying=SMALL_CELL_MINIMUM - 1, metric_value=SMALL_VALUE)
    )
    kept = prepare_eda_metric(_metric())
    zero = prepare_eda_metric(_metric(n_underlying=0, metric_value=1.0))

    assert suppressed.is_suppressed is True
    assert suppressed.n_underlying is None
    assert suppressed.metric_value is None
    assert SMALL_VALUE not in suppressed.bind("eda-159")
    assert SMALL_CELL_MINIMUM - 1 not in suppressed.bind("eda-159")

    assert kept.is_suppressed is False
    assert kept.n_underlying == SMALL_CELL_MINIMUM
    assert kept.metric_value == LARGE_VALUE
    assert zero.is_suppressed is True
    assert zero.metric_value is None


def test_writer_stores_run_and_metrics_under_one_run_id() -> None:
    session = FakeSession()
    receipt = write_eda_results(
        session,
        _run(),
        (
            _metric(),
            _metric(
                metric_name="share",
                n_underlying=SMALL_COUNT,
                metric_value=SMALL_VALUE,
                geography_id="99",
            ),
        ),
    )

    assert receipt.run_id == "eda-159"
    assert receipt.database == ML_LAB_DATABASE
    assert receipt.metrics_written == 2
    assert receipt.metrics_suppressed == 1
    assert _statements(session) == [
        IDENTITY_SQL,
        f"INSERT INTO {ML_LAB_DATABASE}.REGISTRY.RUNS (\n"
        "    RUN_ID, ISSUE_NUMBER, AGENT_ID, PURPOSE,\n"
        "    GIT_REPO, GIT_BRANCH, GIT_COMMIT,\n"
        "    SOURCE_ENVIRONMENT, SOURCE_RELEASE_ID, SOURCE_OBJECTS,\n"
        "    INPUT_SNAPSHOT_TS, PARAMETERS, RANDOM_SEED, STATUS, NOTES\n"
        ")\n"
        "SELECT\n"
        "    %s, %s, %s, %s,\n"
        "    %s, %s, %s,\n"
        "    %s, %s, PARSE_JSON(%s),\n"
        "    %s, PARSE_JSON(%s), %s, %s, %s",
        f"INSERT INTO {ML_LAB_DATABASE}.EDA.METRICS_LONG (\n"
        "    RUN_ID, METRIC_NAME, GEOGRAPHY_TYPE, GEOGRAPHY_ID,\n"
        "    PERIOD_START, PERIOD_END, DIMENSIONS, METRIC_VALUE, UNIT,\n"
        "    N_UNDERLYING, IS_SUPPRESSED\n"
        ")\n"
        "SELECT\n"
        "    %s, %s, %s, %s,\n"
        "    %s, %s, PARSE_JSON(%s), %s, %s,\n"
        "    %s, %s",
        f"INSERT INTO {ML_LAB_DATABASE}.EDA.METRICS_LONG (\n"
        "    RUN_ID, METRIC_NAME, GEOGRAPHY_TYPE, GEOGRAPHY_ID,\n"
        "    PERIOD_START, PERIOD_END, DIMENSIONS, METRIC_VALUE, UNIT,\n"
        "    N_UNDERLYING, IS_SUPPRESSED\n"
        ")\n"
        "SELECT\n"
        "    %s, %s, %s, %s,\n"
        "    %s, %s, PARSE_JSON(%s), %s, %s,\n"
        "    %s, %s",
    ]
    run_params, kept_params, hidden_params = _bound(session)
    assert run_params[0] == "eda-159"
    assert run_params[1] == 159
    assert kept_params[0] == "eda-159"
    assert kept_params[1] == "county_count"
    assert kept_params[7] == LARGE_VALUE
    assert kept_params[9] == LARGE_COUNT
    assert kept_params[10] is False
    assert hidden_params[0] == "eda-159"
    assert hidden_params[7] is None
    assert hidden_params[9] is None
    assert hidden_params[10] is True
    assert SMALL_VALUE not in hidden_params
    assert SMALL_COUNT not in hidden_params
    rendered = " ".join(_statements(session))
    assert PROD_DATABASE not in rendered
    assert str(SMALL_VALUE) not in rendered
    assert TOKEN not in rendered


@pytest.mark.parametrize(
    "database",
    [
        PROD_DATABASE,
        PROD_DATABASE.lower(),
        "ONE_HEALTH_LYME_GAP_ATLAS_DEV",
        f"{ML_LAB_DATABASE}.EDA",
        "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION",
        "",
        "PROD; DROP TABLE REGISTRY.RUNS",
    ],
)
def test_writes_targeting_other_databases_are_rejected(database: str) -> None:
    session = FakeSession()
    with pytest.raises(EdaWriteError, match=REFUSED_DATABASE):
        write_eda_results(session, _run(), (_metric(),), database=database)
    assert session.calls == []


def test_lowercase_lab_database_is_accepted() -> None:
    session = FakeSession()
    receipt = write_eda_results(
        session,
        _run(),
        (_metric(),),
        database=ML_LAB_DATABASE.lower(),
    )
    assert receipt.database == ML_LAB_DATABASE
    assert ML_LAB_DATABASE in _statements(session)[1]


def test_wrong_role_and_incomplete_session_write_nothing() -> None:
    wrong_role = FakeSession(role="ACCOUNTADMIN")
    with pytest.raises(EdaWriteError, match=REFUSED_ROLE):
        write_eda_results(wrong_role, _run(), (_metric(),))
    assert _statements(wrong_role) == [IDENTITY_SQL]

    incomplete = FakeSession()
    incomplete.identity_row = (ML_AGENT_ROLE, "", ML_LAB_DATABASE)
    with pytest.raises(EdaWriteError, match="session context is incomplete"):
        write_eda_results(incomplete, _run(), (_metric(),))
    assert _statements(incomplete) == [IDENTITY_SQL]

    failed = FakeSession()
    failed.fail_identity = True
    with pytest.raises(EdaWriteError, match="session context is incomplete"):
        write_eda_results(failed, _run(), (_metric(),))
    assert all(params is None for _sql, params in failed.calls)


def test_invalid_metric_is_rejected_before_any_statement() -> None:
    session = FakeSession()
    with pytest.raises(EdaWriteError, match="n_underlying"):
        write_eda_results(session, _run(), (_metric(n_underlying=-1),))
    with pytest.raises(EdaWriteError, match="n_underlying"):
        write_eda_results(session, _run(), (_metric(n_underlying=True),))
    with pytest.raises(EdaWriteError, match="metric_name"):
        write_eda_results(session, _run(), (_metric(metric_name="county'; DROP TABLE runs"),))
    assert session.calls == []


def test_free_text_fields_are_rejected() -> None:
    session = FakeSession()
    with pytest.raises(EdaWriteError, match="free-text"):
        write_eda_results(
            session,
            _run(),
            (_metric(dimensions={"part_text": "record text"}),),
        )
    assert session.calls == []


def test_statement_failure_does_not_echo_the_driver_message() -> None:
    session = FakeSession()
    session.fail_execute = True
    with pytest.raises(EdaWriteError, match="statement failed") as caught:
        write_eda_results(session, _run(), (_metric(),))
    assert TOKEN not in str(caught.value)
    assert "Insufficient" not in str(caught.value)


def _env(**overrides: str) -> dict[str, str]:
    values = {
        "SNOWFLAKE_ACCOUNT": "test-account",
        "SNOWFLAKE_USER": "test-user",
        "SNOWFLAKE_ROLE": ML_AGENT_ROLE,
        "SNOWFLAKE_WAREHOUSE": "OH_LYME_ML_LAB_XS_WH",
        "SNOWFLAKE_DATABASE": ML_LAB_DATABASE,
        "SNOWFLAKE_PAT": TOKEN,
    }
    values.update(overrides)
    return values


class RecordingCursor:
    def __init__(self, connection: RecordingConnection) -> None:
        self._connection = connection
        self.description: tuple[str, ...] | None = None
        self._sql = ""

    def __enter__(self) -> RecordingCursor:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def execute(self, sql: str, params: Sequence[object] | None = None) -> None:
        self._sql = sql
        bound = None if params is None else tuple(params)
        self._connection.calls.append((sql, bound))
        self.description = ("role",) if sql == IDENTITY_SQL else None
        if sql.startswith("INSERT") and self._connection.fail_insert:
            denied = StatementError(permission_denied=True)
            denied.add_note(f"token={TOKEN}")
            raise denied

    def fetchall(self) -> list[tuple[object, ...]]:
        if self._sql == IDENTITY_SQL:
            return [(ML_AGENT_ROLE, "OH_LYME_ML_LAB_XS_WH", ML_LAB_DATABASE)]
        return []


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []
        self.closed = False
        self.fail_insert = False

    def cursor(self) -> RecordingCursor:
        return RecordingCursor(self)

    def close(self) -> None:
        self.closed = True


def test_environment_writer_uses_a_fake_session_and_closes_it() -> None:
    connection = RecordingConnection()
    opened: list[MlAgentConnectionSettings] = []

    def opener(settings: MlAgentConnectionSettings) -> RecordingConnection:
        opened.append(settings)
        return connection

    receipt = write_eda_results_from_environment(
        _env(),
        _run(git_commit="abc1234", parameters={"seed_policy": "fixed"}),
        (
            _metric(
                period_start=date(2024, 1, 1),
                period_end=date(2024, 12, 31),
            ),
        ),
        opener=opener,
    )
    assert receipt.run_id == "eda-159"
    assert receipt.metrics_suppressed == 0
    assert connection.closed is True
    assert len(opened) == 1
    assert TOKEN not in repr(opened[0])
    sql_text = " ".join(sql for sql, _params in connection.calls)
    assert f"{ML_LAB_DATABASE}.REGISTRY.RUNS" in sql_text
    assert f"{ML_LAB_DATABASE}.EDA.METRICS_LONG" in sql_text
    assert PROD_DATABASE not in sql_text
    metric_params = [params for sql, params in connection.calls if "METRICS_LONG" in sql][0]
    assert metric_params is not None
    assert metric_params[0] == "eda-159"
    assert metric_params[4] == date(2024, 1, 1)
    assert metric_params[10] is False


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"SNOWFLAKE_DATABASE": PROD_DATABASE}, "PROD"),
        ({"SNOWFLAKE_DATABASE": "ONE_HEALTH_LYME_GAP_ATLAS_DEV"}, REFUSED_DATABASE),
        ({"SNOWFLAKE_ROLE": "ACCOUNTADMIN"}, REFUSED_ROLE),
    ],
)
def test_environment_writer_refuses_prod_and_does_not_connect(
    overrides: dict[str, str],
    match: str,
) -> None:
    def opener(_settings: MlAgentConnectionSettings) -> object:
        raise AssertionError("connection should not open")

    with pytest.raises(EdaWriteError, match=match):
        write_eda_results_from_environment(_env(**overrides), _run(), (_metric(),), opener=opener)


def test_driver_error_text_stays_out_of_the_fake_session_failure() -> None:
    connection = RecordingConnection()
    connection.fail_insert = True

    def opener(_settings: MlAgentConnectionSettings) -> RecordingConnection:
        return connection

    with pytest.raises(EdaWriteError, match="statement failed") as caught:
        write_eda_results_from_environment(_env(), _run(), (_metric(),), opener=opener)
    assert TOKEN not in str(caught.value)
    assert connection.closed is True


def test_period_order_and_timezone_are_required() -> None:
    with pytest.raises(EdaWriteError, match="period_end"):
        prepare_eda_metric(_metric(period_start=date(2024, 2, 1), period_end=date(2024, 1, 1)))
    with pytest.raises(EdaWriteError, match="timezone"):
        write_eda_results(
            FakeSession(),
            _run(input_snapshot_ts=datetime(2024, 1, 1)),
            (),
        )
    session = FakeSession()
    receipt = write_eda_results(
        session,
        _run(input_snapshot_ts=datetime(2024, 1, 1, tzinfo=UTC)),
        (),
    )
    assert receipt.metrics_written == 0
    assert _bound(session)[0][10] == datetime(2024, 1, 1, tzinfo=UTC)
