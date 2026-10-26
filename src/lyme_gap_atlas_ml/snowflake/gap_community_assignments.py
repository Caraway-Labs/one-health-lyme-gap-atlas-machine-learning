"""Write issue 120 cluster assignments and experiment rows to the ML Lab.

County names stay in the assignment table. Inserts are insert-only. This role
cannot DELETE, so a run id that already has rows is refused. The optional
SELECT grant is attempted once for the reader role.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from lyme_gap_atlas_ml.gap_communities import AssignmentRow, ExperimentRow
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaSession,
    EdaWriteError,
    _require_agent_session,
    require_ml_lab_database,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import StatementError

ASSIGNMENT_TABLE = f"{ML_LAB_DATABASE}.EDA.GAP_COMMUNITY_ASSIGNMENTS_120"
READER_ROLE = "OH_LYME_PROD_READ"
_COLUMNS = (
    "RUN_ID",
    "FIPS",
    "COUNTY_NAME",
    "STATE",
    "CLUSTER_ID",
    "IN_DOUBLE_GAP",
    "POPULATION",
    "SVI_PERCENTILE",
    "UNINSURED_PERCENTILE",
    "RUCC_2023",
    "SCAPULARIS_STATUS",
    "PACIFICUS_STATUS",
    "BURGDORFERI_STATUS",
)
_CREATE = f"""
CREATE TABLE IF NOT EXISTS {ASSIGNMENT_TABLE} (
    RUN_ID VARCHAR NOT NULL,
    FIPS VARCHAR NOT NULL,
    COUNTY_NAME VARCHAR,
    STATE VARCHAR,
    CLUSTER_ID NUMBER,
    IN_DOUBLE_GAP BOOLEAN,
    POPULATION FLOAT,
    SVI_PERCENTILE FLOAT,
    UNINSURED_PERCENTILE FLOAT,
    RUCC_2023 VARCHAR,
    SCAPULARIS_STATUS VARCHAR,
    PACIFICUS_STATUS VARCHAR,
    BURGDORFERI_STATUS VARCHAR
)
""".strip()
_INSERT = (
    f"INSERT INTO {ASSIGNMENT_TABLE} ({', '.join(_COLUMNS)}) "
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
_GRANT = f"GRANT SELECT ON TABLE {ASSIGNMENT_TABLE} TO ROLE {READER_ROLE}"


class RunAlreadyWritten(EdaWriteError):
    """This run id already has lab rows. Do not insert them again."""


def assignment_table_sql() -> str:
    """Return the assignment-table DDL. Tests use it to reject a non-lab target."""
    if ML_LAB_DATABASE not in _CREATE or "DELETE" in _CREATE.upper():
        raise EdaWriteError("assignment table SQL is not an insert-only ML Lab table")
    return _CREATE


def write_assignment_tables(
    executor: EdaSession,
    run_id: str,
    assignments: Sequence[AssignmentRow],
    experiments: Sequence[ExperimentRow],
) -> dict[str, int | bool]:
    """Insert this run's assignments and experiment rows. Refuse a second write."""
    require_ml_lab_database(ML_LAB_DATABASE)
    _require_agent_session(executor)
    if _existing_rows(executor, run_id):
        raise RunAlreadyWritten("run id already has assignment or experiment rows")
    granted = False
    try:
        executor.execute(_CREATE, ())
        granted = _grant(executor)
        _insert_assignments(executor, run_id, assignments)
        _insert_experiments(executor, run_id, experiments)
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    return {
        "assignments": len(assignments),
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
        f"SELECT COUNT(*) FROM {ASSIGNMENT_TABLE} WHERE RUN_ID = %s",
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


def _insert_assignments(
    executor: EdaSession,
    run_id: str,
    assignments: Sequence[AssignmentRow],
) -> None:
    rows = tuple(_assignment_params(run_id, row) for row in assignments)
    many = getattr(executor, "executemany", None)
    if callable(many):
        many(_INSERT, rows)
        return
    for params in rows:
        executor.execute(_INSERT, params)


def _assignment_params(run_id: str, row: AssignmentRow) -> tuple[object, ...]:
    return (
        run_id,
        row.fips,
        row.county_name,
        row.state,
        row.cluster_id,
        row.in_double_gap,
        row.population,
        row.svi,
        row.uninsured,
        row.rucc,
        row.scapularis_status,
        row.pacificus_status,
        row.burgdorferi_status,
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
            raise
        rows = query(sql)
    return [tuple(row) for row in rows]


def _count(rows: Sequence[Sequence[object]]) -> int:
    value = rows[0][0]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EdaWriteError("count is not numeric")
    return int(value)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
