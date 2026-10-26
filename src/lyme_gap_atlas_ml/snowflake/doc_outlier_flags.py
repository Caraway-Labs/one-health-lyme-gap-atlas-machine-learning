"""Write issue 190 county flags and experiment rows to the ML Lab.

County rows stay in the lab table. Inserts are insert-only. This role cannot
DELETE, so a run id that already has rows is refused. The SELECT grant is
attempted once for the ML Lead reader role.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal

from lyme_gap_atlas_ml.doc_outliers import ExperimentRow, FlagRow
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaSession,
    EdaWriteError,
    _require_agent_session,
    require_ml_lab_database,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import StatementError

FLAG_TABLE = f"{ML_LAB_DATABASE}.EDA.COUNTY_DOC_FLAGS_190"
READER_ROLE = "OH_LYME_PROD_READ"
_COLUMNS = (
    "RUN_ID",
    "FIPS",
    "COUNTY_NAME",
    "STATE",
    "STATE_N",
    "COMPLETE_N",
    "SIZE_BAND",
    "SCORED",
    "INCOMPLETE",
    "SCORE_ROBUST_Z",
    "FLAG_ROBUST_Z",
    "SCORE_IF_PRIMARY",
    "FLAG_IF_PRIMARY",
    "SCORE_IF_SEED_B",
    "FLAG_IF_SEED_B",
    "SCORE_LOF",
    "FLAG_LOF",
    "BOOTSTRAP_RATE_IF",
    "DOMINANT_FEATURE",
    "STABLE_USEFUL",
    "SITUATION_121",
    "CLUSTER_ID_120",
)
_CREATE = f"""
CREATE TABLE IF NOT EXISTS {FLAG_TABLE} (
    RUN_ID VARCHAR NOT NULL,
    FIPS VARCHAR NOT NULL,
    COUNTY_NAME VARCHAR,
    STATE VARCHAR,
    STATE_N NUMBER,
    COMPLETE_N NUMBER,
    SIZE_BAND VARCHAR,
    SCORED BOOLEAN,
    INCOMPLETE BOOLEAN,
    SCORE_ROBUST_Z FLOAT,
    FLAG_ROBUST_Z BOOLEAN,
    SCORE_IF_PRIMARY FLOAT,
    FLAG_IF_PRIMARY BOOLEAN,
    SCORE_IF_SEED_B FLOAT,
    FLAG_IF_SEED_B BOOLEAN,
    SCORE_LOF FLOAT,
    FLAG_LOF BOOLEAN,
    BOOTSTRAP_RATE_IF FLOAT,
    DOMINANT_FEATURE VARCHAR,
    STABLE_USEFUL BOOLEAN,
    SITUATION_121 VARCHAR,
    CLUSTER_ID_120 NUMBER
)
""".strip()
_INSERT_PREFIX = f"INSERT INTO {FLAG_TABLE} ({', '.join(_COLUMNS)})"
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
_GRANT = f"GRANT SELECT ON TABLE {FLAG_TABLE} TO ROLE {READER_ROLE}"
_GRANT_LOOKUP = f"SHOW GRANTS ON TABLE {FLAG_TABLE}"
_BATCH = 80


class RunAlreadyWritten(EdaWriteError):
    """This run id already has lab rows. Do not insert them again."""


def flag_table_sql() -> str:
    """Return the flag-table DDL. Tests use it to reject a non-lab target."""
    if ML_LAB_DATABASE not in _CREATE or "DELETE" in _CREATE.upper():
        raise EdaWriteError("flag table SQL is not an insert-only ML Lab table")
    return _CREATE


def write_flag_tables(
    executor: EdaSession,
    run_id: str,
    flags: Sequence[FlagRow],
    experiments: Sequence[ExperimentRow],
) -> dict[str, int | bool | str]:
    """Insert this run's flags and experiment rows. Refuse a second write."""
    require_ml_lab_database(ML_LAB_DATABASE)
    _require_agent_session(executor)
    if _existing_rows(executor, run_id):
        raise RunAlreadyWritten("run id already has flag or experiment rows")
    granted = False
    grant_verified = "fail"
    try:
        executor.execute(_CREATE, ())
        granted = _grant(executor)
        if granted:
            grant_verified = "pass" if _grant_visible(executor) else "fail"
        _insert_flags(executor, run_id, flags)
        _insert_experiments(executor, run_id, experiments)
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    return {
        "flags": len(flags),
        "experiments": len(experiments),
        "granted": granted,
        "grant_verified": grant_verified,
    }


def _grant(executor: EdaSession) -> bool:
    try:
        executor.execute(_GRANT, ())
    except StatementError:
        return False
    return True


def _grant_visible(executor: EdaSession) -> bool:
    try:
        rows = _query(executor, _GRANT_LOOKUP, ())
    except StatementError:
        return False
    for row in rows:
        text = " ".join(str(item).upper() for item in row)
        if "SELECT" in text and READER_ROLE in text:
            return True
    return False


def _existing_rows(executor: EdaSession, run_id: str) -> bool:
    statements = (
        f"SELECT COUNT(*) FROM {FLAG_TABLE} WHERE RUN_ID = %s",
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


def _insert_flags(executor: EdaSession, run_id: str, flags: Sequence[FlagRow]) -> None:
    rows = tuple(_flag_params(run_id, row) for row in flags)
    width = len(_COLUMNS)
    for start in range(0, len(rows), _BATCH):
        batch = rows[start : start + _BATCH]
        values = ", ".join("(" + ", ".join(["%s"] * width) + ")" for _ in batch)
        flat = tuple(item for row in batch for item in row)
        executor.execute(f"{_INSERT_PREFIX} VALUES {values}", flat)


def _flag_params(run_id: str, row: FlagRow) -> tuple[object, ...]:
    return (
        run_id,
        row.fips,
        row.county_name,
        row.state,
        row.state_n,
        row.complete_n,
        row.size_band,
        row.scored,
        row.incomplete,
        row.score_robust_z,
        row.flag_robust_z,
        row.score_if_primary,
        row.flag_if_primary,
        row.score_if_seed_b,
        row.flag_if_seed_b,
        row.score_lof,
        row.flag_lof,
        row.bootstrap_rate_if,
        row.dominant_feature,
        row.stable_useful,
        row.situation_121,
        row.cluster_id_120,
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
        rows = query(sql, params) if params else query(sql)
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
