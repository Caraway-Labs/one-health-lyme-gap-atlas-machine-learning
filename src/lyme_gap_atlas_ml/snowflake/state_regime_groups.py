"""Write issue 123 state-group assignments and experiment rows to the ML Lab.

Inserts are insert-only. This role cannot DELETE, so a run id that already has
rows is refused. The optional SELECT grant is attempted once for the reader role.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaSession,
    EdaWriteError,
    _require_agent_session,
    require_ml_lab_database,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import StatementError
from lyme_gap_atlas_ml.state_regimes import AssignmentRow, ExperimentRow

GROUP_TABLE = f"{ML_LAB_DATABASE}.EDA.STATE_REGIME_GROUPS_123"
READER_ROLE = "OH_LYME_PROD_READ"
_COLUMNS = (
    "RUN_ID",
    "STATE",
    "COUNTY_N",
    "PUBLISHED_SHARE",
    "TICK_ESTABLISHED_SHARE",
    "PATHOGEN_PRESENT_SHARE",
    "MEDIAN_PUBLISHED_FLOOR",
    "RURAL_NONMETRO_SHARE",
    "DESCRIPTIVE_GROUP",
    "PUBLICATION_FREE_GROUP",
    "ZERO_PUBLISHED",
)
_CREATE = f"""
CREATE TABLE IF NOT EXISTS {GROUP_TABLE} (
    RUN_ID VARCHAR NOT NULL,
    STATE VARCHAR NOT NULL,
    COUNTY_N NUMBER,
    PUBLISHED_SHARE FLOAT,
    TICK_ESTABLISHED_SHARE FLOAT,
    PATHOGEN_PRESENT_SHARE FLOAT,
    MEDIAN_PUBLISHED_FLOOR FLOAT,
    RURAL_NONMETRO_SHARE FLOAT,
    DESCRIPTIVE_GROUP NUMBER,
    PUBLICATION_FREE_GROUP NUMBER,
    ZERO_PUBLISHED BOOLEAN
)
""".strip()
_INSERT = (
    f"INSERT INTO {GROUP_TABLE} ({', '.join(_COLUMNS)}) "
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
_GRANT = f"GRANT SELECT ON TABLE {GROUP_TABLE} TO ROLE {READER_ROLE}"


class RunAlreadyWritten(EdaWriteError):
    """This run id already has lab rows. Do not insert them again."""


def group_table_sql() -> str:
    """Return the assignment-table DDL. Tests use it to reject a non-lab target."""
    if ML_LAB_DATABASE not in _CREATE or "DELETE" in _CREATE.upper():
        raise EdaWriteError("group table SQL is not an insert-only ML Lab table")
    return _CREATE


def write_group_tables(
    executor: EdaSession,
    run_id: str,
    assignments: Sequence[AssignmentRow],
    experiments: Sequence[ExperimentRow],
) -> dict[str, int | bool]:
    """Insert this run's assignments and experiment rows. Refuse a run that already has rows."""
    require_ml_lab_database(ML_LAB_DATABASE)
    _require_agent_session(executor)
    if _existing_rows(executor, run_id):
        raise RunAlreadyWritten("run id already has group or experiment rows")
    granted = False
    try:
        executor.execute(_CREATE, ())
        granted = _grant(executor)
        _insert_assignments(executor, run_id, assignments)
        _insert_experiments(executor, run_id, experiments)
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    return {"groups": len(assignments), "experiments": len(experiments), "granted": granted}


def _grant(executor: EdaSession) -> bool:
    try:
        executor.execute(_GRANT, ())
    except StatementError:
        return False
    return True


def _existing_rows(executor: EdaSession, run_id: str) -> bool:
    statements = (
        f"SELECT COUNT(*) FROM {GROUP_TABLE} WHERE RUN_ID = %s",
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
        row.state,
        row.county_n,
        row.published_share,
        row.tick_established_share,
        row.pathogen_present_share,
        row.median_published_floor,
        row.rural_nonmetro_share,
        row.descriptive_group,
        row.publication_free_group,
        row.zero_published,
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
            if metric.metric_value is None or metric.n is None:
                continue
            if 0 < metric.n < 11:
                continue
            executor.execute(
                _METRIC_INSERT,
                (
                    experiment.experiment_id,
                    run_id,
                    metric.split_name,
                    metric.metric_name,
                    metric.metric_value,
                    metric.ci_low,
                    metric.ci_high,
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
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
