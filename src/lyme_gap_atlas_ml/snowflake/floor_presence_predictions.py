"""Write issue 188 predictions and experiment rows to the ML Lab.

County predictions stay in the lab table. Inserts are insert-only. This role
cannot DELETE, so a run id that already has rows is refused. The optional
SELECT grant is attempted once for the reader role.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal

from lyme_gap_atlas_ml.floor_presence import ExperimentRow, PredictionRow
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaSession,
    EdaWriteError,
    _require_agent_session,
    require_ml_lab_database,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import StatementError

PREDICTION_TABLE = f"{ML_LAB_DATABASE}.EXPERIMENTS.FLOOR_PRESENCE_PREDICTIONS_188"
READER_ROLE = "OH_LYME_PROD_READ"
_COLUMNS = (
    "RUN_ID",
    "FIPS",
    "STATE",
    "PUBLISHED_FLOOR_PRESENT",
    "MODEL_FAMILY",
    "SEED",
    "BASELINE_PROBABILITY",
    "CHALLENGER_PROBABILITY",
    "OOF_REGIME",
)
_CREATE = f"""
CREATE TABLE IF NOT EXISTS {PREDICTION_TABLE} (
    RUN_ID VARCHAR NOT NULL,
    FIPS VARCHAR NOT NULL,
    STATE VARCHAR,
    PUBLISHED_FLOOR_PRESENT NUMBER,
    MODEL_FAMILY VARCHAR,
    SEED NUMBER,
    BASELINE_PROBABILITY FLOAT,
    CHALLENGER_PROBABILITY FLOAT,
    OOF_REGIME NUMBER
)
""".strip()
_INSERT_PREFIX = f"INSERT INTO {PREDICTION_TABLE} ({', '.join(_COLUMNS)})"
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
_GRANT = f"GRANT SELECT ON TABLE {PREDICTION_TABLE} TO ROLE {READER_ROLE}"
_BATCH = 80


class RunAlreadyWritten(EdaWriteError):
    """This run id already has lab rows. Do not insert them again."""


def prediction_table_sql() -> str:
    """Return the prediction-table DDL. Tests use it to reject a non-lab target."""
    if ML_LAB_DATABASE not in _CREATE or "DELETE" in _CREATE.upper():
        raise EdaWriteError("prediction table SQL is not an insert-only ML Lab table")
    return _CREATE


def write_prediction_tables(
    executor: EdaSession,
    run_id: str,
    predictions: Sequence[PredictionRow],
    experiments: Sequence[ExperimentRow],
) -> dict[str, int | bool]:
    """Insert this run's predictions and experiment rows. Refuse a second write."""
    require_ml_lab_database(ML_LAB_DATABASE)
    _require_agent_session(executor)
    if _existing_rows(executor, run_id):
        raise RunAlreadyWritten("run id already has prediction or experiment rows")
    granted = False
    try:
        executor.execute(_CREATE, ())
        granted = _grant(executor)
        _insert_predictions(executor, run_id, predictions)
        _insert_experiments(executor, run_id, experiments)
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    return {
        "predictions": len(predictions),
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
        f"SELECT COUNT(*) FROM {PREDICTION_TABLE} WHERE RUN_ID = %s",
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


def _insert_predictions(
    executor: EdaSession,
    run_id: str,
    predictions: Sequence[PredictionRow],
) -> None:
    rows = tuple(_prediction_params(run_id, row) for row in predictions)
    width = len(_COLUMNS)
    for start in range(0, len(rows), _BATCH):
        batch = rows[start : start + _BATCH]
        values = ", ".join("(" + ", ".join(["%s"] * width) + ")" for _ in batch)
        flat = tuple(item for row in batch for item in row)
        executor.execute(f"{_INSERT_PREFIX} VALUES {values}", flat)


def _prediction_params(run_id: str, row: PredictionRow) -> tuple[object, ...]:
    return (
        run_id,
        row.fips,
        row.state,
        row.published,
        row.model_family,
        row.seed,
        row.baseline_probability,
        row.challenger_probability,
        row.oof_regime,
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
                    metric.ci_low,
                    metric.ci_high,
                    metric.n,
                ),
            )


def _json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


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
    if isinstance(value, bool):
        raise EdaWriteError("lookup did not return one count")
    if isinstance(value, Decimal):
        value = int(value)
    if not isinstance(value, int):
        raise EdaWriteError("lookup did not return one count")
    return value
