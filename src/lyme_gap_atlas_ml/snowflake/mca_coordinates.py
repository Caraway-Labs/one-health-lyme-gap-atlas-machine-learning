"""Write issue 121 MCA coordinates and experiment rows to the ML Lab.

County coordinates stay in the lab table. Inserts are insert-only. This role
cannot DELETE, so a run id that already has rows is refused. The optional
SELECT grant is attempted once for the reader role.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from lyme_gap_atlas_ml.county_mca import CoordinateRow, ExperimentRow
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaSession,
    EdaWriteError,
    _require_agent_session,
    require_ml_lab_database,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import StatementError

COORDINATE_TABLE = f"{ML_LAB_DATABASE}.EDA.COUNTY_MCA_COORDINATES_121"
READER_ROLE = "OH_LYME_PROD_READ"
_COLUMNS = (
    "RUN_ID",
    "FIPS",
    "COUNTY_NAME",
    "STATE",
    "AXIS_1",
    "AXIS_2",
    "AXIS_3",
    "IN_ALIGNED",
    "IN_DOUBLE_GAP",
    "IN_WIDER_GAP",
    "IN_HUMAN_AHEAD",
    "IN_UNDOCUMENTED",
)
_CREATE = f"""
CREATE TABLE IF NOT EXISTS {COORDINATE_TABLE} (
    RUN_ID VARCHAR NOT NULL,
    FIPS VARCHAR NOT NULL,
    COUNTY_NAME VARCHAR,
    STATE VARCHAR,
    AXIS_1 FLOAT,
    AXIS_2 FLOAT,
    AXIS_3 FLOAT,
    IN_ALIGNED BOOLEAN,
    IN_DOUBLE_GAP BOOLEAN,
    IN_WIDER_GAP BOOLEAN,
    IN_HUMAN_AHEAD BOOLEAN,
    IN_UNDOCUMENTED BOOLEAN
)
""".strip()
_INSERT = (
    f"INSERT INTO {COORDINATE_TABLE} ({', '.join(_COLUMNS)}) "
    f"VALUES ({', '.join('%s' for _ in _COLUMNS)})"
)
_EXPERIMENT_INSERT = f"""
INSERT INTO {ML_LAB_DATABASE}.EXPERIMENTS.EXPERIMENTS (
    EXPERIMENT_ID, RUN_ID, HYPOTHESIS, MODEL_FAMILY, CONFIG, SPLIT_DEFINITION, STATUS
)
SELECT %s, %s, %s, %s, PARSE_JSON(%s), PARSE_JSON(%s), %s
""".strip()
_METRIC_INSERT = f"""
INSERT INTO {ML_LAB_DATABASE}.EXPERIMENTS.MODEL_METRICS (
    EXPERIMENT_ID, RUN_ID, SPLIT_NAME, METRIC_NAME, METRIC_VALUE, CI_LOW, CI_HIGH, N
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
""".strip()
_GRANT = f"GRANT SELECT ON TABLE {COORDINATE_TABLE} TO ROLE {READER_ROLE}"


class RunAlreadyWritten(EdaWriteError):
    """This run id already has lab rows. Do not insert them again."""


def coordinate_table_sql() -> str:
    """Return the coordinate-table DDL. Tests use it to reject a non-lab target."""
    if ML_LAB_DATABASE not in _CREATE or "DELETE" in _CREATE.upper():
        raise EdaWriteError("coordinate table SQL is not an insert-only ML Lab table")
    return _CREATE


def write_mca_tables(
    executor: EdaSession,
    run_id: str,
    coordinates: Sequence[CoordinateRow],
    experiments: Sequence[ExperimentRow],
) -> dict[str, int | bool]:
    """Insert this run's coordinates and experiment rows. Refuse a second write."""
    require_ml_lab_database(ML_LAB_DATABASE)
    _require_agent_session(executor)
    if _existing_rows(executor, run_id):
        raise RunAlreadyWritten("run id already has coordinate or experiment rows")
    granted = False
    try:
        executor.execute(_CREATE, ())
        granted = _grant(executor)
        _insert_coordinates(executor, run_id, coordinates)
        _insert_experiments(executor, run_id, experiments)
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    return {
        "coordinates": len(coordinates),
        "experiments": len(experiments),
        "granted": granted,
    }


def _grant(executor: EdaSession) -> bool:
    try:
        executor.execute(_GRANT, ())
    except StatementError:
        return False
    return True


def _existing_rows(executor: EdaSession, run_id: str) -> bool:
    statements = (
        f"SELECT COUNT(*) FROM {COORDINATE_TABLE} WHERE RUN_ID = %s",
        f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EXPERIMENTS.EXPERIMENTS WHERE RUN_ID = %s",
        f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EXPERIMENTS.MODEL_METRICS WHERE RUN_ID = %s",
        f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.REGISTRY.RUNS WHERE RUN_ID = %s",
    )
    for sql in statements:
        try:
            rows = _query(executor, sql, (run_id,))
        except StatementError:
            continue
        if rows and _count(rows) > 0:
            return True
    return False


def _insert_coordinates(
    executor: EdaSession,
    run_id: str,
    coordinates: Sequence[CoordinateRow],
) -> None:
    rows = tuple(_coordinate_params(run_id, row) for row in coordinates)
    many = getattr(executor, "executemany", None)
    if callable(many):
        many(_INSERT, rows)
        return
    for params in rows:
        executor.execute(_INSERT, params)


def _coordinate_params(run_id: str, row: CoordinateRow) -> tuple[object, ...]:
    return (
        run_id,
        row.fips,
        row.county_name,
        row.state,
        row.axis_1,
        row.axis_2,
        row.axis_3,
        row.in_aligned,
        row.in_double_gap,
        row.in_wider_gap,
        row.in_human_ahead,
        row.in_undocumented,
    )


def _insert_experiments(
    executor: EdaSession,
    run_id: str,
    experiments: Sequence[ExperimentRow],
) -> None:
    for experiment in experiments:
        executor.execute(
            _EXPERIMENT_INSERT,
            (
                experiment.experiment_id,
                run_id,
                experiment.hypothesis,
                experiment.model_family,
                _json(experiment.config),
                _json(experiment.split_definition),
                experiment.status,
            ),
        )
        for metric in experiment.metrics:
            if metric.metric_value is None or metric.n is None or 0 < metric.n < 11:
                continue
            executor.execute(
                _METRIC_INSERT,
                (
                    experiment.experiment_id,
                    run_id,
                    metric.split_name,
                    metric.metric_name,
                    metric.metric_value,
                    None,
                    None,
                    metric.n,
                ),
            )


def _query(executor: EdaSession, sql: str, params: tuple[object, ...]) -> list[tuple[object, ...]]:
    query = getattr(executor, "query", None)
    if not callable(query):
        raise EdaWriteError("session cannot query")
    try:
        rows = query(sql, params)
    except TypeError:
        if params:
            raise EdaWriteError("session cannot bind a query") from None
        rows = query(sql)
    return [tuple(row) for row in rows]


def _count(rows: Sequence[Sequence[object]]) -> int:
    if len(rows) != 1 or isinstance(rows[0], (str, bytes)) or len(rows[0]) != 1:
        raise EdaWriteError("lookup did not return one count")
    value = rows[0][0]
    if isinstance(value, bool) or not isinstance(value, int):
        raise EdaWriteError("lookup did not return one count")
    return value


def _json(value: dict[str, object]) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    if "GRANT" in text.upper() or "DELETE" in text.upper():
        raise EdaWriteError("experiment payload is not a grant or a delete")
    return text
