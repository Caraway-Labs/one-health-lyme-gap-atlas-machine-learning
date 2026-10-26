"""Write issue 110 cluster assignments and experiment rows to the ML Lab.

County names stay in the cluster table. Inserts are insert-only. This role
cannot DELETE, so a run id that already has rows is refused. The optional
SELECT grant is attempted once for the reader role the ML Lead uses.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from lyme_gap_atlas_ml.peer_clusters import SLICE_FEATURES, Analysis, ExperimentRow
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaSession,
    EdaWriteError,
    _require_agent_session,
    require_ml_lab_database,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import StatementError

CLUSTER_TABLE = f"{ML_LAB_DATABASE}.EDA.COUNTY_CLUSTERS_110"
READER_ROLE = "OH_LYME_PROD_READ"
_CLUSTER_COLUMNS = (
    "RUN_ID",
    "FIPS",
    "COUNTY_NAME",
    "STATE",
    "CENSUS_REGION",
    "CLUSTER_CONTEXT",
    "CLUSTER_EXTENDED",
    "CLUSTER_CLIMATE",
    "CLUSTER_COVERAGE",
    "CLUSTER_MULTIDOMAIN",
)
_CREATE_CLUSTERS = f"""
CREATE TABLE IF NOT EXISTS {CLUSTER_TABLE} (
    RUN_ID VARCHAR NOT NULL,
    FIPS VARCHAR NOT NULL,
    COUNTY_NAME VARCHAR,
    STATE VARCHAR,
    CENSUS_REGION VARCHAR,
    CLUSTER_CONTEXT NUMBER,
    CLUSTER_EXTENDED NUMBER,
    CLUSTER_CLIMATE NUMBER,
    CLUSTER_COVERAGE NUMBER,
    CLUSTER_MULTIDOMAIN NUMBER
)
""".strip()
_INSERT_CLUSTERS = (
    f"INSERT INTO {CLUSTER_TABLE} ({', '.join(_CLUSTER_COLUMNS)}) "
    f"VALUES ({', '.join('%s' for _ in _CLUSTER_COLUMNS)})"
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
_GRANT = f"GRANT SELECT ON TABLE {CLUSTER_TABLE} TO ROLE {READER_ROLE}"


class RunAlreadyWritten(EdaWriteError):
    """This run id already has lab rows. Do not insert them again."""


def cluster_table_sql() -> str:
    """Return the cluster-table DDL. Tests use it to reject a non-lab target."""
    if ML_LAB_DATABASE not in _CREATE_CLUSTERS or "DELETE" in _CREATE_CLUSTERS.upper():
        raise EdaWriteError("cluster table SQL is not an insert-only ML Lab table")
    return _CREATE_CLUSTERS


def write_cluster_tables(
    executor: EdaSession,
    run_id: str,
    analysis: Analysis,
) -> dict[str, int | bool]:
    """Insert this run's assignments and experiment rows. Refuse a run that already has rows."""
    require_ml_lab_database(ML_LAB_DATABASE)
    _require_agent_session(executor)
    if _existing_rows(executor, run_id):
        raise RunAlreadyWritten("run id already has cluster or experiment rows")
    granted = False
    try:
        executor.execute(_CREATE_CLUSTERS, ())
        granted = _grant(executor)
        _insert_counties(executor, run_id, analysis)
        _insert_experiments(executor, run_id, analysis.experiments)
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    return {
        "clusters": len(analysis.counties),
        "experiments": len(analysis.experiments),
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
        f"SELECT COUNT(*) FROM {CLUSTER_TABLE} WHERE RUN_ID = %s",
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


def _insert_counties(executor: EdaSession, run_id: str, analysis: Analysis) -> None:
    labels = {name: analysis.slice(name).labels for name in SLICE_FEATURES}
    rows = []
    for index, county in enumerate(analysis.counties):
        rows.append(
            (
                run_id,
                county.fips,
                county.name,
                county.state,
                county.region,
                labels["context"][index],
                labels["extended"][index],
                labels["climate"][index],
                labels["coverage"][index],
                labels["multidomain"][index],
            )
        )
    many = getattr(executor, "executemany", None)
    if callable(many):
        many(_INSERT_CLUSTERS, rows)
        return
    for params in rows:
        executor.execute(_INSERT_CLUSTERS, params)


def _insert_experiments(
    executor: EdaSession, run_id: str, experiments: Sequence[ExperimentRow]
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
