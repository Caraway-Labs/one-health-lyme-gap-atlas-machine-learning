"""Insert the issue 196 experiment rows. Neighbor lists stay in the issue 192 table.

A new neighbor table is created only when the recomputed lists differ. Inserts
are insert-only. A second write of the same run id is refused. SELECT on a new
table is granted to the two reader roles.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal

from lyme_gap_atlas_ml.peer_lookup import ExperimentRow, NeighborRow
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaSession,
    EdaWriteError,
    _require_agent_session,
    require_ml_lab_database,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import StatementError
from lyme_gap_atlas_ml.snowflake.peer_neighbors import READER_ROLES, RunAlreadyWritten

NEIGHBOR_TABLE = f"{ML_LAB_DATABASE}.EDA.PEER_COUNTY_NEIGHBORS_196"
_COLUMNS = (
    "RUN_ID",
    "FIPS",
    "COUNTY_NAME",
    "STATE",
    "CLUSTER_ID",
    "SITUATION",
    "PROTOTYPE_CLUSTER_ID",
    "EUCLIDEAN_NEIGHBORS",
    "COSINE_NEIGHBORS",
    "EUCLIDEAN_DISTANCE_K",
    "BASELINE_PEER_N",
    "LEAVE_STATE_TYPE_AGREEMENT",
)
_CREATE = f"""
CREATE TABLE IF NOT EXISTS {NEIGHBOR_TABLE} (
    RUN_ID VARCHAR NOT NULL,
    FIPS VARCHAR NOT NULL,
    COUNTY_NAME VARCHAR,
    STATE VARCHAR,
    CLUSTER_ID NUMBER,
    SITUATION VARCHAR,
    PROTOTYPE_CLUSTER_ID NUMBER,
    EUCLIDEAN_NEIGHBORS VARCHAR,
    COSINE_NEIGHBORS VARCHAR,
    EUCLIDEAN_DISTANCE_K FLOAT,
    BASELINE_PEER_N NUMBER,
    LEAVE_STATE_TYPE_AGREEMENT FLOAT
)
""".strip()
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
_BATCH = 80


def write_rerun_experiments(
    executor: EdaSession,
    run_id: str,
    experiments: Sequence[ExperimentRow],
) -> None:
    """Insert experiment rows for this run. Refuse a run id that already has rows."""
    require_ml_lab_database(ML_LAB_DATABASE)
    _require_agent_session(executor)
    if _run_exists(executor, run_id):
        raise RunAlreadyWritten("run id already has experiment or registry rows")
    try:
        _insert_experiments(executor, run_id, experiments)
    except StatementError as error:
        raise EdaWriteError("statement failed") from error


def write_differing_neighbors(
    executor: EdaSession,
    run_id: str,
    neighbors: Sequence[NeighborRow],
) -> str:
    """Create the issue 196 neighbor table, grant SELECT, and insert one run."""
    require_ml_lab_database(ML_LAB_DATABASE)
    _require_agent_session(executor)
    if ML_LAB_DATABASE not in _CREATE:
        raise EdaWriteError("neighbor table SQL is not an ML Lab table")
    try:
        executor.execute(_CREATE, ())
        granted = _grant_all(executor)
        _insert_neighbors(executor, run_id, neighbors)
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    return granted


def _run_exists(executor: EdaSession, run_id: str) -> bool:
    statements = (
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


def _grant_all(executor: EdaSession) -> str:
    for role in READER_ROLES:
        try:
            executor.execute(f"GRANT SELECT ON TABLE {NEIGHBOR_TABLE} TO ROLE {role}", ())
        except StatementError:
            continue
    try:
        rows = _query(executor, f"SHOW GRANTS ON TABLE {NEIGHBOR_TABLE}", ())
    except StatementError:
        return ",".join(f"{role}=fail" for role in READER_ROLES)
    found = {role: False for role in READER_ROLES}
    for row in rows:
        text = " ".join(str(item).upper() for item in row)
        if "SELECT" not in text:
            continue
        for role in READER_ROLES:
            if role in text:
                found[role] = True
    return ",".join(f"{role}={'pass' if found[role] else 'fail'}" for role in READER_ROLES)


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
                json.dumps(experiment.config, sort_keys=True, separators=(",", ":")),
                json.dumps(experiment.split_definition, sort_keys=True, separators=(",", ":")),
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


def _insert_neighbors(
    executor: EdaSession,
    run_id: str,
    neighbors: Sequence[NeighborRow],
) -> None:
    rows = tuple(_neighbor_params(run_id, row) for row in neighbors)
    prefix = f"INSERT INTO {NEIGHBOR_TABLE} ({', '.join(_COLUMNS)})"
    width = len(_COLUMNS)
    for start in range(0, len(rows), _BATCH):
        batch = rows[start : start + _BATCH]
        values = ", ".join("(" + ", ".join(["%s"] * width) + ")" for _ in batch)
        flat = tuple(item for row in batch for item in row)
        executor.execute(f"{prefix} VALUES {values}", flat)


def _neighbor_params(run_id: str, row: NeighborRow) -> tuple[object, ...]:
    return (
        run_id,
        row.fips,
        row.county_name,
        row.state,
        row.cluster_id,
        row.situation,
        row.prototype_cluster_id,
        row.euclidean_neighbors,
        row.cosine_neighbors,
        row.euclidean_distance_k,
        row.baseline_peer_n,
        row.leave_state_type_agreement,
    )


def _query(executor: EdaSession, sql: str, params: tuple[object, ...]) -> list[tuple[object, ...]]:
    query = getattr(executor, "query", None)
    if not callable(query):
        raise EdaWriteError("session cannot query")
    rows = query(sql, params)
    return [tuple(row) for row in rows]


def _count(rows: Sequence[Sequence[object]]) -> int:
    if len(rows) != 1 or isinstance(rows[0], (str, bytes)) or len(rows[0]) != 1:
        raise EdaWriteError("lookup did not return one count")
    value = rows[0][0]
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise EdaWriteError("lookup did not return one count")
    return int(value)
