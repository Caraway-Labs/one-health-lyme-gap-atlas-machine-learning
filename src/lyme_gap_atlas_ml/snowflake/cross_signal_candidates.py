"""Write issue 111 candidate rows to the ML Lab.

County names stay in the candidate table. This module does not grant SELECT.
The shared EDA writers do not grant another role, and this role is not an owner,
so OH_LYME_PROD_READ cannot count the new table until an owner grants it.
"""

from __future__ import annotations

from collections.abc import Sequence

from lyme_gap_atlas_ml.cross_signal_disagreement import Candidate
from lyme_gap_atlas_ml.snowflake.anomaly_scores import RunAlreadyWritten, _query_params
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaSession,
    EdaWriteError,
    _require_agent_session,
    require_ml_lab_database,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import StatementError

CANDIDATE_TABLE = f"{ML_LAB_DATABASE}.EDA.CROSS_SIGNAL_CANDIDATES_111"
_COLUMNS = (
    "RUN_ID",
    "FIPS",
    "COUNTY_NAME",
    "STATE",
    "CENSUS_REGION",
    "DISAGREEMENT_TYPE",
    "HUMAN_STATUS",
    "TICK_STATUS",
    "BURGDORFERI_STATUS",
    "SUPPORTING_EVIDENCE",
    "CONTRADICTING_EVIDENCE",
    "ALT_ZERO_FLOOR_STATE",
    "ALT_PARTIAL_REPORTING_STATE",
    "ALT_PATHOGEN_UNOBSERVED",
    "ALT_TICK_REPORTED_NOT_ESTABLISHED",
    "ALT_NO_VECTOR_RECORD",
    "ALT_VINTAGE_MISMATCH",
    "REVIEW_READING",
    "RUCC_2023",
    "SVI_PERCENTILE",
    "POPULATION",
    "IN_CONTIGUOUS_TICK_SCOPE",
)
_CREATE = f"""
CREATE TABLE IF NOT EXISTS {CANDIDATE_TABLE} (
    RUN_ID VARCHAR NOT NULL,
    FIPS VARCHAR NOT NULL,
    COUNTY_NAME VARCHAR,
    STATE VARCHAR,
    CENSUS_REGION VARCHAR,
    DISAGREEMENT_TYPE VARCHAR,
    HUMAN_STATUS VARCHAR,
    TICK_STATUS VARCHAR,
    BURGDORFERI_STATUS VARCHAR,
    SUPPORTING_EVIDENCE VARCHAR,
    CONTRADICTING_EVIDENCE VARCHAR,
    ALT_ZERO_FLOOR_STATE BOOLEAN,
    ALT_PARTIAL_REPORTING_STATE BOOLEAN,
    ALT_PATHOGEN_UNOBSERVED BOOLEAN,
    ALT_TICK_REPORTED_NOT_ESTABLISHED BOOLEAN,
    ALT_NO_VECTOR_RECORD BOOLEAN,
    ALT_VINTAGE_MISMATCH BOOLEAN,
    REVIEW_READING VARCHAR,
    RUCC_2023 NUMBER,
    SVI_PERCENTILE FLOAT,
    POPULATION FLOAT,
    IN_CONTIGUOUS_TICK_SCOPE BOOLEAN
)
""".strip()
_RUN_COUNT = f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.REGISTRY.RUNS WHERE RUN_ID = %s"
_DELETE = f"DELETE FROM {CANDIDATE_TABLE} WHERE RUN_ID = %s"
_BATCH = 40


def candidate_table_sql() -> str:
    """Return the candidate-table DDL. Tests use it to reject a grant or a non-lab target."""
    if ML_LAB_DATABASE not in _CREATE or "COUNTY_NAME" not in _CREATE:
        raise EdaWriteError("candidate table SQL is not the ML Lab table")
    if "GRANT" in _CREATE.upper():
        raise EdaWriteError("candidate table SQL must not grant another role")
    return _CREATE


def write_candidates(
    executor: EdaSession,
    run_id: str,
    candidates: Sequence[Candidate],
) -> int:
    """Insert this run's candidate rows. Refuse a run that already has a registry row."""
    require_ml_lab_database(ML_LAB_DATABASE)
    _require_agent_session(executor)
    try:
        count_rows = _query_params(executor, _RUN_COUNT, (run_id,))
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    if _one(count_rows) > 0:
        raise RunAlreadyWritten("run id already has a registry row")
    try:
        executor.execute(_CREATE, ())
        executor.execute(_DELETE, (run_id,))
        _insert(executor, run_id, candidates)
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    return len(candidates)


def _insert(executor: EdaSession, run_id: str, candidates: Sequence[Candidate]) -> None:
    rows = tuple(_bind(run_id, candidate) for candidate in candidates)
    width = len(_COLUMNS)
    for start in range(0, len(rows), _BATCH):
        chunk = rows[start : start + _BATCH]
        values = ", ".join("(" + ", ".join("%s" for _ in range(width)) + ")" for _ in chunk)
        sql = f"INSERT INTO {CANDIDATE_TABLE} ({', '.join(_COLUMNS)}) VALUES {values}"
        if "GRANT" in sql.upper():
            raise EdaWriteError("candidate insert must not grant another role")
        params = tuple(value for row in chunk for value in row)
        executor.execute(sql, params)


def _bind(run_id: str, candidate: Candidate) -> tuple[object, ...]:
    return (
        run_id,
        candidate.fips,
        candidate.county,
        candidate.state,
        candidate.region,
        candidate.documentation_class,
        candidate.human,
        candidate.tick,
        candidate.pathogen,
        candidate.supporting,
        candidate.contradicting,
        candidate.zero_floor_state,
        candidate.partial_reporting_state,
        candidate.pathogen_unobserved,
        candidate.tick_reported_not_established,
        candidate.no_vector_record,
        candidate.vintage_mismatch,
        candidate.review_reading,
        candidate.rucc,
        candidate.svi,
        candidate.population,
        candidate.in_scope,
    )


def _one(rows: Sequence[Sequence[object]]) -> int:
    if len(rows) != 1 or isinstance(rows[0], (str, bytes)) or len(rows[0]) != 1:
        raise EdaWriteError("run count is not usable")
    value = rows[0][0]
    if isinstance(value, bool) or not isinstance(value, int):
        raise EdaWriteError("run count is not usable")
    return value
