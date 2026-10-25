"""Write issue 122 county scores and experiment rows to the ML Lab.

County names stay in the score table. Aggregate experiment metrics omit a
numerator from 1 to 10. This module does not open a connection by itself.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from lyme_gap_atlas_ml.class_anomaly import ExperimentRow, ScoredCounty
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaSession,
    EdaWriteError,
    _require_agent_session,
    require_ml_lab_database,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import StatementError

SCORE_TABLE = f"{ML_LAB_DATABASE}.EDA.COUNTY_ANOMALY_SCORES_122"
_SCORE_COLUMNS = (
    "RUN_ID",
    "FIPS",
    "COUNTY_NAME",
    "STATE",
    "CENSUS_REGION",
    "POPULATION",
    "LOG_POPULATION",
    "SVI_PERCENTILE",
    "UNINSURED_PERCENTILE",
    "RUCC_2023",
    "ROBUST_Z_LOG_POPULATION",
    "ROBUST_Z_SVI",
    "ROBUST_Z_UNINSURED",
    "ROBUST_Z_RUCC",
    "ROBUST_Z_MAX_ABS",
    "MAHALANOBIS_SQUARED",
    "IF_SCORE_PRIMARY",
    "IF_SCORE_SEED_B",
    "FLAG_ROBUST_Z",
    "FLAG_MAHALANOBIS",
    "FLAG_IF_PRIMARY",
    "FLAG_IF_SEED_B",
    "FLAG_IF_C02",
    "FLAG_IF_C10",
    "DOMINANT_FEATURE",
    "IN_DOUBLE_GAP_228",
    "IN_GAP_810",
    "HUMAN_STATUS",
    "BURGDORFERI_STATUS",
    "TICK_STATUS",
)
_CREATE_SCORES = f"""
CREATE TABLE IF NOT EXISTS {SCORE_TABLE} (
    RUN_ID VARCHAR NOT NULL,
    FIPS VARCHAR NOT NULL,
    COUNTY_NAME VARCHAR,
    STATE VARCHAR,
    CENSUS_REGION VARCHAR,
    POPULATION FLOAT,
    LOG_POPULATION FLOAT,
    SVI_PERCENTILE FLOAT,
    UNINSURED_PERCENTILE FLOAT,
    RUCC_2023 NUMBER,
    ROBUST_Z_LOG_POPULATION FLOAT,
    ROBUST_Z_SVI FLOAT,
    ROBUST_Z_UNINSURED FLOAT,
    ROBUST_Z_RUCC FLOAT,
    ROBUST_Z_MAX_ABS FLOAT,
    MAHALANOBIS_SQUARED FLOAT,
    IF_SCORE_PRIMARY FLOAT,
    IF_SCORE_SEED_B FLOAT,
    FLAG_ROBUST_Z BOOLEAN,
    FLAG_MAHALANOBIS BOOLEAN,
    FLAG_IF_PRIMARY BOOLEAN,
    FLAG_IF_SEED_B BOOLEAN,
    FLAG_IF_C02 BOOLEAN,
    FLAG_IF_C10 BOOLEAN,
    DOMINANT_FEATURE VARCHAR,
    IN_DOUBLE_GAP_228 BOOLEAN,
    IN_GAP_810 BOOLEAN,
    HUMAN_STATUS VARCHAR,
    BURGDORFERI_STATUS VARCHAR,
    TICK_STATUS VARCHAR
)
""".strip()
_INSERT_SCORES = (
    f"INSERT INTO {SCORE_TABLE} ({', '.join(_SCORE_COLUMNS)}) "
    f"VALUES ({', '.join('%s' for _ in _SCORE_COLUMNS)})"
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
_RUN_COUNT = f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.REGISTRY.RUNS WHERE RUN_ID = %s"
# REGISTRY.QUERIES is insert-only for this role. A partial query row for a
# run id that never reached REGISTRY.RUNS is left in place. A finished run is
# refused before this cleanup.
_DELETE_TARGETS = (
    SCORE_TABLE,
    f"{ML_LAB_DATABASE}.EXPERIMENTS.MODEL_METRICS",
    f"{ML_LAB_DATABASE}.EXPERIMENTS.EXPERIMENTS",
    f"{ML_LAB_DATABASE}.EDA.FINDINGS",
    f"{ML_LAB_DATABASE}.EDA.METRICS_LONG",
)


class RunAlreadyWritten(EdaWriteError):
    """This run id already has a registry row. Do not write it again."""


def score_table_sql() -> str:
    """Return the score-table DDL. Tests use it to reject a non-lab target."""
    if ML_LAB_DATABASE not in _CREATE_SCORES or "COUNTY_NAME" not in _CREATE_SCORES:
        raise EdaWriteError("score table SQL is not the ML Lab county table")
    return _CREATE_SCORES


def write_score_tables(
    executor: EdaSession,
    run_id: str,
    counties: Sequence[ScoredCounty],
    experiments: Sequence[ExperimentRow],
) -> dict[str, int]:
    """Replace this run's score and experiment rows. Refuse a run that already finished."""
    require_ml_lab_database(ML_LAB_DATABASE)
    _require_agent_session(executor)
    try:
        count_rows = _query_params(executor, _RUN_COUNT, (run_id,))
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    if _count(count_rows) > 0:
        raise RunAlreadyWritten("run id already has a registry row")
    try:
        executor.execute(_CREATE_SCORES, ())
        for table in _DELETE_TARGETS:
            executor.execute(f"DELETE FROM {table} WHERE RUN_ID = %s", (run_id,))
        _insert_scores(executor, run_id, counties)
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
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    return {"scores": len(counties), "experiments": len(experiments)}


def _insert_scores(executor: EdaSession, run_id: str, counties: Sequence[ScoredCounty]) -> None:
    rows = tuple(_score_params(run_id, county) for county in counties)
    many = getattr(executor, "executemany", None)
    if callable(many):
        many(_INSERT_SCORES, rows)
        return
    for params in rows:
        executor.execute(_INSERT_SCORES, params)


def _score_params(run_id: str, county: ScoredCounty) -> tuple[object, ...]:
    z = county.z_map()
    return (
        run_id,
        county.fips,
        county.county_name,
        county.state,
        county.region,
        county.population,
        county.log_population,
        county.svi_percentile,
        county.uninsured_percentile,
        county.rucc,
        z.get("log_population"),
        z.get("svi_percentile"),
        z.get("uninsured_percentile"),
        z.get("rucc_2023"),
        county.robust_z_max_abs,
        county.mahalanobis_squared,
        county.if_score_primary,
        county.if_score_seed_b,
        county.flag_robust_z,
        county.flag_mahalanobis,
        county.flag_if_primary,
        county.flag_if_seed_b,
        county.flag_if_c02,
        county.flag_if_c10,
        county.dominant_feature,
        county.in_double_gap,
        county.in_gap_810,
        county.human_status,
        county.burgdorferi_status,
        county.tick_status,
    )


def _query_params(
    executor: EdaSession,
    sql: str,
    params: tuple[object, ...],
) -> Sequence[Sequence[object]]:
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
        raise EdaWriteError("run lookup did not return one count")
    value = rows[0][0]
    if isinstance(value, bool) or not isinstance(value, int):
        raise EdaWriteError("run lookup did not return one count")
    return value


def _json(value: dict[str, object]) -> str:
    try:
        return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise EdaWriteError("experiment config is not JSON data") from error
