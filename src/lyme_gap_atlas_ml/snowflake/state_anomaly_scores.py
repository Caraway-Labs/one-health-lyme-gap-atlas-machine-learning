"""Write issue 106 county scores and experiment rows to the ML Lab.

County names stay in the score table. This module does not grant SELECT.
The shared EDA writers do not grant another role, and this role is not an owner,
so OH_LYME_PROD_READ cannot count the new table until an owner grants it.
"""

from __future__ import annotations

import json
import math
from collections.abc import Sequence

from lyme_gap_atlas_ml.class_anomaly import ExperimentRow
from lyme_gap_atlas_ml.snowflake.anomaly_scores import RunAlreadyWritten, _count, _query_params
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaSession,
    EdaWriteError,
    _require_agent_session,
    require_ml_lab_database,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import StatementError
from lyme_gap_atlas_ml.state_anomaly import ScoredCounty

SCORE_TABLE = f"{ML_LAB_DATABASE}.EDA.COUNTY_STATE_ANOMALY_106"
_SCORE_COLUMNS = (
    "RUN_ID",
    "FIPS",
    "COUNTY_NAME",
    "STATE",
    "CENSUS_REGION",
    "PEER_RULE",
    "PEER_LABEL",
    "PEER_N",
    "STATE_N",
    "POPULATION",
    "LOG_POPULATION",
    "SVI_PERCENTILE",
    "UNINSURED_PERCENTILE",
    "RUCC_2023",
    "Z_STATE_LOG_POPULATION",
    "Z_STATE_SVI",
    "Z_STATE_UNINSURED",
    "Z_STATE_RUCC",
    "Z_NATIONAL_LOG_POPULATION",
    "Z_NATIONAL_SVI",
    "Z_NATIONAL_UNINSURED",
    "Z_NATIONAL_RUCC",
    "MAX_ABS_Z_STATE",
    "MAX_ABS_Z_NATIONAL",
    "RANK_STATE",
    "RANK_NATIONAL",
    "FLAG_Z_STATE",
    "FLAG_Z_NATIONAL",
    "FLAG_PERCENTILE",
    "PERCENTILE_APPLIED",
    "FLAG_MCD",
    "MCD_APPLIED",
    "FLAG_MCD_NATIONAL",
    "MAHALANOBIS_PEER",
    "MAHALANOBIS_NATIONAL",
    "FLAG_IF_PRIMARY",
    "FLAG_IF_SEED_B",
    "FLAG_IF_C02",
    "FLAG_IF_C10",
    "FOREST_APPLIED",
    "IF_SCORE_PRIMARY",
    "FLAG_LOF",
    "FLAG_LOF_C02",
    "FLAG_LOF_C10",
    "LOF_APPLIED",
    "LOF_SCORE",
    "FLAG_SURVEILLANCE",
    "SURVEILLANCE_APPLIED",
    "SURVEILLANCE_SIGNAL",
    "FLAG_SURVEILLANCE_NATIONAL",
    "DOMINANT_FEATURE",
    "REASON",
    "METRO",
    "HUMAN_STATUS",
    "TICK_STATUS",
    "BURGDORFERI_STATUS",
)
_CREATE_SCORES = f"""
CREATE TABLE IF NOT EXISTS {SCORE_TABLE} (
    RUN_ID VARCHAR NOT NULL,
    FIPS VARCHAR NOT NULL,
    COUNTY_NAME VARCHAR,
    STATE VARCHAR,
    CENSUS_REGION VARCHAR,
    PEER_RULE VARCHAR,
    PEER_LABEL VARCHAR,
    PEER_N NUMBER,
    STATE_N NUMBER,
    POPULATION FLOAT,
    LOG_POPULATION FLOAT,
    SVI_PERCENTILE FLOAT,
    UNINSURED_PERCENTILE FLOAT,
    RUCC_2023 NUMBER,
    Z_STATE_LOG_POPULATION FLOAT,
    Z_STATE_SVI FLOAT,
    Z_STATE_UNINSURED FLOAT,
    Z_STATE_RUCC FLOAT,
    Z_NATIONAL_LOG_POPULATION FLOAT,
    Z_NATIONAL_SVI FLOAT,
    Z_NATIONAL_UNINSURED FLOAT,
    Z_NATIONAL_RUCC FLOAT,
    MAX_ABS_Z_STATE FLOAT,
    MAX_ABS_Z_NATIONAL FLOAT,
    RANK_STATE NUMBER,
    RANK_NATIONAL NUMBER,
    FLAG_Z_STATE BOOLEAN,
    FLAG_Z_NATIONAL BOOLEAN,
    FLAG_PERCENTILE BOOLEAN,
    PERCENTILE_APPLIED BOOLEAN,
    FLAG_MCD BOOLEAN,
    MCD_APPLIED BOOLEAN,
    FLAG_MCD_NATIONAL BOOLEAN,
    MAHALANOBIS_PEER FLOAT,
    MAHALANOBIS_NATIONAL FLOAT,
    FLAG_IF_PRIMARY BOOLEAN,
    FLAG_IF_SEED_B BOOLEAN,
    FLAG_IF_C02 BOOLEAN,
    FLAG_IF_C10 BOOLEAN,
    FOREST_APPLIED BOOLEAN,
    IF_SCORE_PRIMARY FLOAT,
    FLAG_LOF BOOLEAN,
    FLAG_LOF_C02 BOOLEAN,
    FLAG_LOF_C10 BOOLEAN,
    LOF_APPLIED BOOLEAN,
    LOF_SCORE FLOAT,
    FLAG_SURVEILLANCE BOOLEAN,
    SURVEILLANCE_APPLIED BOOLEAN,
    SURVEILLANCE_SIGNAL VARCHAR,
    FLAG_SURVEILLANCE_NATIONAL BOOLEAN,
    DOMINANT_FEATURE VARCHAR,
    REASON VARCHAR,
    METRO BOOLEAN,
    HUMAN_STATUS VARCHAR,
    TICK_STATUS VARCHAR,
    BURGDORFERI_STATUS VARCHAR
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
_DELETE_TARGETS = (
    SCORE_TABLE,
    f"{ML_LAB_DATABASE}.EXPERIMENTS.MODEL_METRICS",
    f"{ML_LAB_DATABASE}.EXPERIMENTS.EXPERIMENTS",
    f"{ML_LAB_DATABASE}.EDA.FINDINGS",
    f"{ML_LAB_DATABASE}.EDA.METRICS_LONG",
)


def score_table_sql() -> str:
    """Return the score-table DDL. Tests use it to reject a non-lab target."""
    if ML_LAB_DATABASE not in _CREATE_SCORES or "COUNTY_NAME" not in _CREATE_SCORES:
        raise EdaWriteError("score table SQL is not the ML Lab county table")
    if "GRANT" in _CREATE_SCORES.upper():
        raise EdaWriteError("score table SQL must not grant another role")
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
    return (
        run_id,
        county.fips,
        county.county_name,
        county.state,
        county.region,
        county.peer_rule,
        county.peer_label,
        county.peer_n,
        county.state_n,
        county.population,
        county.log_population,
        county.svi_percentile,
        county.uninsured_percentile,
        county.rucc,
        county.state_z("log_population"),
        county.state_z("svi_percentile"),
        county.state_z("uninsured_percentile"),
        county.state_z("rucc_2023"),
        county.national_z("log_population"),
        county.national_z("svi_percentile"),
        county.national_z("uninsured_percentile"),
        county.national_z("rucc_2023"),
        _finite(county.max_abs_z_state),
        _finite(county.max_abs_z_national),
        county.rank_state,
        county.rank_national,
        county.flag_z_state,
        county.flag_z_national,
        county.flag_percentile,
        county.percentile_applied,
        county.flag_mcd,
        county.mcd_applied,
        county.flag_mcd_national,
        county.mahalanobis_peer,
        county.mahalanobis_national,
        county.flag_if_primary,
        county.flag_if_seed_b,
        county.flag_if_c02,
        county.flag_if_c10,
        county.forest_applied,
        county.if_score_primary,
        county.flag_lof,
        county.flag_lof_c02,
        county.flag_lof_c10,
        county.lof_applied,
        county.lof_score,
        county.flag_surveillance,
        county.surveillance_applied,
        county.surveillance_signal,
        county.flag_surveillance_national,
        county.dominant_feature,
        county.reason,
        county.metro,
        county.human_status,
        county.tick_status,
        county.burgdorferi_status,
    )


def _finite(value: float) -> float | None:
    if not math.isfinite(value):
        return None
    return value


def _json(value: dict[str, object]) -> str:
    try:
        return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise EdaWriteError("experiment config is not JSON data") from error
