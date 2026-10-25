"""Write ML Lab EDA tables other than the long metric table.

Live columns were read from ``INFORMATION_SCHEMA`` on 2026-10-25, after the
artifact helper had inserted a column the table did not have. ``CREATED_AT``
and ``EXECUTED_AT`` have defaults and are omitted.

``ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`` is the only database these statements
name. A geographic denominator below 11 clears that row's statistics. A
positive count below 11 is removed. A zero on a denominator of at least 11
is kept. ``REGISTRY.QUERIES.ROWS_RETURNED`` is statement cardinality, not a
geographic cell.
"""

from __future__ import annotations

import contextlib
import hashlib
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    REFUSED_DATABASE,
    SMALL_CELL_MINIMUM,
    EdaSession,
    EdaWriteError,
    _json_object,
    _qualified_object,
    _require_agent_session,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    ML_AGENT_ROLE,
    REFUSED_ROLE,
    ConfigError,
    CursorStatementExecutor,
    MlAgentConnectionSettings,
    StatementError,
    load_ml_agent_request,
    open_ml_agent_connection,
)

_MAX_ROWS = 5000
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_LABEL = re.compile(r"^[A-Za-z][A-Za-z0-9_ .:/+-]{0,127}$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_FINDING_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_QUERY_ID = re.compile(r"^[A-Za-z0-9-]{8,128}$")
_FIPS = re.compile(r"\b\d{5}\b")
_INTEGER_TEXT = re.compile(r"^-?[0-9]+$")
_DISPOSITIONS = frozenset({"keep", "revise", "stop", "follow-up"})
_PERCENTILE_KEYS = ("p01", "p05", "p25", "p50", "p75", "p95", "p99")
_FORBIDDEN_SQL = (
    "PART_TEXT",
    "CONTEXT_LIMITATIONS",
    "PAYLOAD",
    "OBSERVATION_LIMITATIONS",
    "MEASURE_LIMITATION",
    "RELEASE_LIMITATIONS",
    "LIMITATIONS",
)
_FORBIDDEN_PROSE = (
    "PART_TEXT",
    "CONTEXT_LIMITATIONS",
    "PAYLOAD",
    "GEOMETRY_JSON",
    "OBSERVATION_LIMITATIONS",
    "MEASURE_LIMITATION",
    "RELEASE_LIMITATIONS",
    "LIMITATIONS",
)
_FORBIDDEN_EVIDENCE = frozenset(
    {
        "PART_TEXT",
        "CONTEXT_LIMITATIONS",
        "PAYLOAD",
        "GEOMETRY_JSON",
        "OBSERVATION_LIMITATIONS",
        "MEASURE_LIMITATION",
        "RELEASE_LIMITATIONS",
        "LIMITATIONS",
        "FIPS",
        "COUNTY",
        "COUNTY_NAME",
    }
)

FINDINGS_COLUMNS = (
    "FINDING_ID",
    "RUN_ID",
    "TOPIC",
    "STATEMENT",
    "EVIDENCE",
    "EFFECT_SIZE",
    "CI_LOW",
    "CI_HIGH",
    "UNCERTAINTY_NOTE",
    "DISPOSITION",
)
MISSINGNESS_COLUMNS = (
    "RUN_ID",
    "SOURCE_OBJECT",
    "COLUMN_NAME",
    "GROUP_KEY",
    "MISSING_N",
    "TOTAL_N",
    "MISSING_PCT",
)
COLUMN_PROFILE_COLUMNS = (
    "RUN_ID",
    "SOURCE_OBJECT",
    "COLUMN_NAME",
    "DATA_TYPE",
    "ROW_COUNT",
    "NULL_COUNT",
    "DISTINCT_COUNT",
    "MIN_VALUE",
    "MAX_VALUE",
    "MEAN_VALUE",
    "STDDEV_VALUE",
    "P01",
    "P05",
    "P25",
    "P50",
    "P75",
    "P95",
    "P99",
    "TOP_VALUES",
)
CORRELATION_COLUMNS = (
    "RUN_ID",
    "VAR_A",
    "VAR_B",
    "METHOD",
    "COEFFICIENT",
    "N",
    "CI_LOW",
    "CI_HIGH",
    "P_VALUE",
)
QUERY_COLUMNS = (
    "RUN_ID",
    "SNOWFLAKE_QUERY_ID",
    "SQL_SHA256",
    "SQL_TEXT",
    "ROWS_RETURNED",
    "ELAPSED_MS",
)


def _insert_sql(table: str, columns: Sequence[str], json_columns: frozenset[str]) -> str:
    expressions = ["PARSE_JSON(%s)" if column in json_columns else "%s" for column in columns]
    joined = ", ".join(columns)
    selected = ", ".join(expressions)
    return f"INSERT INTO {ML_LAB_DATABASE}.{table} ({joined}) SELECT {selected}"


FINDINGS_SQL = _insert_sql("EDA.FINDINGS", FINDINGS_COLUMNS, frozenset({"EVIDENCE"}))
MISSINGNESS_SQL = _insert_sql("EDA.MISSINGNESS", MISSINGNESS_COLUMNS, frozenset({"GROUP_KEY"}))
COLUMN_PROFILE_SQL = _insert_sql(
    "EDA.COLUMN_PROFILES",
    COLUMN_PROFILE_COLUMNS,
    frozenset({"TOP_VALUES"}),
)
CORRELATION_SQL = _insert_sql("EDA.CORRELATIONS", CORRELATION_COLUMNS, frozenset())
QUERY_SQL = _insert_sql("REGISTRY.QUERIES", QUERY_COLUMNS, frozenset())


class _BoundRow(Protocol):
    @property
    def suppressed(self) -> bool: ...

    def bind(self, run_id: str) -> tuple[object, ...]: ...


@dataclass(frozen=True)
class LabWriteReceipt:
    run_id: str
    database: str
    table: str
    rows_written: int
    rows_suppressed: int


@dataclass(frozen=True)
class MissingnessRecord:
    source_object: str
    column_name: str
    missing_n: int
    total_n: int
    group_key: Mapping[str, object] | None = None


@dataclass(frozen=True)
class PreparedMissingness:
    source_object: str
    column_name: str
    group_key_json: str | None
    missing_n: int | None
    total_n: int | None
    missing_pct: float | None
    suppressed: bool

    def bind(self, run_id: str) -> tuple[object, ...]:
        return (
            run_id,
            self.source_object,
            self.column_name,
            self.group_key_json,
            self.missing_n,
            self.total_n,
            self.missing_pct,
        )


@dataclass(frozen=True)
class ColumnProfileRecord:
    source_object: str
    column_name: str
    row_count: int
    null_count: int
    data_type: str | None = None
    distinct_count: int | None = None
    min_value: str | None = None
    max_value: str | None = None
    mean_value: float | None = None
    stddev_value: float | None = None
    percentiles: Mapping[str, float | None] | None = None
    top_values: Sequence[Mapping[str, object]] | None = None
    count_extremes: bool = False


@dataclass(frozen=True)
class PreparedColumnProfile:
    source_object: str
    column_name: str
    data_type: str | None
    row_count: int | None
    null_count: int | None
    distinct_count: int | None
    min_value: str | None
    max_value: str | None
    mean_value: float | None
    stddev_value: float | None
    percentiles: tuple[float | None, ...]
    top_values_json: str | None
    suppressed: bool

    def bind(self, run_id: str) -> tuple[object, ...]:
        return (
            run_id,
            self.source_object,
            self.column_name,
            self.data_type,
            self.row_count,
            self.null_count,
            self.distinct_count,
            self.min_value,
            self.max_value,
            self.mean_value,
            self.stddev_value,
            *self.percentiles,
            self.top_values_json,
        )


@dataclass(frozen=True)
class CorrelationRecord:
    var_a: str
    var_b: str
    method: str
    n: int
    coefficient: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    p_value: float | None = None


@dataclass(frozen=True)
class PreparedCorrelation:
    var_a: str
    var_b: str
    method: str
    coefficient: float | None
    n: int | None
    ci_low: float | None
    ci_high: float | None
    p_value: float | None
    suppressed: bool

    def bind(self, run_id: str) -> tuple[object, ...]:
        return (
            run_id,
            self.var_a,
            self.var_b,
            self.method,
            self.coefficient,
            self.n,
            self.ci_low,
            self.ci_high,
            self.p_value,
        )


@dataclass(frozen=True)
class FindingRecord:
    topic: str
    statement: str
    disposition: str
    n_underlying: int
    evidence: Mapping[str, object] | None = None
    effect_size: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    uncertainty_note: str | None = None
    finding_id: str | None = None


@dataclass(frozen=True)
class PreparedFinding:
    finding_id: str
    topic: str
    statement: str
    evidence_json: str | None
    effect_size: float | None
    ci_low: float | None
    ci_high: float | None
    uncertainty_note: str | None
    disposition: str
    suppressed: bool

    def bind(self, run_id: str) -> tuple[object, ...]:
        return (
            self.finding_id,
            run_id,
            self.topic,
            self.statement,
            self.evidence_json,
            self.effect_size,
            self.ci_low,
            self.ci_high,
            self.uncertainty_note,
            self.disposition,
        )


@dataclass(frozen=True)
class QueryRecord:
    sql_text: str
    rows_returned: int
    elapsed_ms: int
    snowflake_query_id: str | None = None
    sql_sha256: str | None = None


@dataclass(frozen=True)
class PreparedQuery:
    snowflake_query_id: str | None
    sql_sha256: str
    sql_text: str
    rows_returned: int
    elapsed_ms: int
    suppressed: bool = False

    def bind(self, run_id: str) -> tuple[object, ...]:
        return (
            run_id,
            self.snowflake_query_id,
            self.sql_sha256,
            self.sql_text,
            self.rows_returned,
            self.elapsed_ms,
        )


def prepare_missingness(record: MissingnessRecord) -> PreparedMissingness:
    """Drop a 1–10 gap or its 1–10 complement. Keep a zero gap on a large denominator."""
    source = _qualified_object(record.source_object)
    column = _ident(record.column_name, "column_name")
    missing = _count(record.missing_n, "missing_n")
    total = _count(record.total_n, "total_n")
    if missing > total:
        raise EdaWriteError("missing_n exceeds total_n")
    group_json = _json_object(record.group_key, "group_key")
    complement = total - missing
    small_piece = (0 < missing < SMALL_CELL_MINIMUM) or (0 < complement < SMALL_CELL_MINIMUM)
    if total < SMALL_CELL_MINIMUM:
        return PreparedMissingness(source, column, group_json, None, None, None, True)
    if small_piece:
        return PreparedMissingness(source, column, group_json, None, total, None, True)
    pct = None if total == 0 else missing / total
    return PreparedMissingness(source, column, group_json, missing, total, pct, False)


def prepare_column_profile(record: ColumnProfileRecord) -> PreparedColumnProfile:
    """Clear a profile whose row count is below 11, and clear small null or level counts."""
    source = _qualified_object(record.source_object)
    column = _ident(record.column_name, "column_name")
    row_count = _count(record.row_count, "row_count")
    null_count = _count(record.null_count, "null_count")
    if null_count > row_count:
        raise EdaWriteError("null_count exceeds row_count")
    distinct = _optional_count(record.distinct_count, "distinct_count")
    percentiles = _percentiles(record.percentiles)
    mean = _number(record.mean_value, "mean_value")
    stddev = _number(record.stddev_value, "stddev_value")
    minimum = _optional_text(record.min_value, "min_value", limit=80)
    maximum = _optional_text(record.max_value, "max_value", limit=80)
    data_type = _optional_text(record.data_type, "data_type", limit=64)
    if row_count < SMALL_CELL_MINIMUM:
        return PreparedColumnProfile(
            source,
            column,
            data_type,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            (None,) * len(_PERCENTILE_KEYS),
            None,
            True,
        )
    suppressed = False
    stored_null: int | None = null_count
    if 0 < null_count < SMALL_CELL_MINIMUM:
        stored_null = None
        suppressed = True
    non_null = row_count - null_count
    if 0 < non_null < SMALL_CELL_MINIMUM:
        minimum = None
        maximum = None
        mean = None
        stddev = None
        percentiles = (None,) * len(_PERCENTILE_KEYS)
        top_json = None
        suppressed = True
    else:
        if record.count_extremes:
            minimum = _suppress_count_text(minimum)
            maximum = _suppress_count_text(maximum)
            if minimum != _optional_text(record.min_value, "min_value", limit=80) or (
                maximum != _optional_text(record.max_value, "max_value", limit=80)
            ):
                suppressed = True
        top_json, top_suppressed = _top_values(record.top_values, non_null)
        suppressed = suppressed or top_suppressed
    return PreparedColumnProfile(
        source,
        column,
        data_type,
        row_count,
        stored_null,
        distinct,
        minimum,
        maximum,
        mean,
        stddev,
        percentiles,
        top_json,
        suppressed,
    )


def prepare_correlation(record: CorrelationRecord) -> PreparedCorrelation:
    """Drop a coefficient whose pair count is below 11."""
    var_a = _label(record.var_a, "var_a")
    var_b = _label(record.var_b, "var_b")
    method = _label(record.method, "method")
    n = _count(record.n, "n")
    if n < SMALL_CELL_MINIMUM:
        return PreparedCorrelation(var_a, var_b, method, None, None, None, None, None, True)
    return PreparedCorrelation(
        var_a,
        var_b,
        method,
        _number(record.coefficient, "coefficient"),
        n,
        _number(record.ci_low, "ci_low"),
        _number(record.ci_high, "ci_high"),
        _number(record.p_value, "p_value"),
        False,
    )


def prepare_finding(record: FindingRecord, *, finding_id: str) -> PreparedFinding:
    """Scrub 1–10 evidence counts. A small denominator also clears the effect and interval."""
    topic = _label(record.topic, "topic")
    statement = _prose(record.statement, "statement", limit=2000)
    disposition = record.disposition.strip().lower()
    if disposition not in _DISPOSITIONS:
        raise EdaWriteError("disposition is not keep, revise, stop, or follow-up")
    n = _count(record.n_underlying, "n_underlying")
    evidence, scrubbed = _scrub_evidence(record.evidence)
    small = n < SMALL_CELL_MINIMUM
    return PreparedFinding(
        finding_id=_finding_id(finding_id),
        topic=topic,
        statement=statement,
        evidence_json=evidence,
        effect_size=None if small else _number(record.effect_size, "effect_size"),
        ci_low=None if small else _number(record.ci_low, "ci_low"),
        ci_high=None if small else _number(record.ci_high, "ci_high"),
        uncertainty_note=_optional_text(record.uncertainty_note, "uncertainty_note", limit=500),
        disposition=disposition,
        suppressed=small or scrubbed,
    )


def prepare_query(record: QueryRecord) -> PreparedQuery:
    """Store one statement. Free-text and payload columns are rejected."""
    sql_text = _sql_text(record.sql_text)
    digest = record.sql_sha256.strip().lower() if record.sql_sha256 else _sha256(sql_text)
    if _SHA256.fullmatch(digest) is None:
        raise EdaWriteError("sql_sha256 is not usable")
    if digest != _sha256(sql_text):
        raise EdaWriteError("sql_sha256 does not match the statement")
    query_id = _optional_query_id(record.snowflake_query_id)
    return PreparedQuery(
        snowflake_query_id=query_id,
        sql_sha256=digest,
        sql_text=sql_text,
        rows_returned=_count(record.rows_returned, "rows_returned"),
        elapsed_ms=_count(record.elapsed_ms, "elapsed_ms"),
    )


def write_missingness(
    executor: EdaSession,
    run_id: str,
    records: Sequence[MissingnessRecord],
    *,
    database: str = ML_LAB_DATABASE,
) -> LabWriteReceipt:
    prepared = _bounded(tuple(prepare_missingness(record) for record in records))
    return _write(executor, run_id, "EDA.MISSINGNESS", MISSINGNESS_SQL, prepared, database)


def write_column_profiles(
    executor: EdaSession,
    run_id: str,
    records: Sequence[ColumnProfileRecord],
    *,
    database: str = ML_LAB_DATABASE,
) -> LabWriteReceipt:
    prepared = _bounded(tuple(prepare_column_profile(record) for record in records))
    return _write(executor, run_id, "EDA.COLUMN_PROFILES", COLUMN_PROFILE_SQL, prepared, database)


def write_correlations(
    executor: EdaSession,
    run_id: str,
    records: Sequence[CorrelationRecord],
    *,
    database: str = ML_LAB_DATABASE,
) -> LabWriteReceipt:
    prepared = _bounded(tuple(prepare_correlation(record) for record in records))
    return _write(executor, run_id, "EDA.CORRELATIONS", CORRELATION_SQL, prepared, database)


def write_findings(
    executor: EdaSession,
    run_id: str,
    records: Sequence[FindingRecord],
    *,
    database: str = ML_LAB_DATABASE,
    ids: Sequence[str] | None = None,
) -> LabWriteReceipt:
    prepared_ids = _finding_ids(records, ids)
    prepared = _bounded(
        tuple(
            prepare_finding(record, finding_id=finding_id)
            for record, finding_id in zip(records, prepared_ids, strict=True)
        )
    )
    return _write(executor, run_id, "EDA.FINDINGS", FINDINGS_SQL, prepared, database)


def write_queries(
    executor: EdaSession,
    run_id: str,
    records: Sequence[QueryRecord],
    *,
    database: str = ML_LAB_DATABASE,
) -> LabWriteReceipt:
    prepared = _bounded(tuple(prepare_query(record) for record in records))
    return _write(executor, run_id, "REGISTRY.QUERIES", QUERY_SQL, prepared, database)


def write_missingness_from_environment(
    environ: Mapping[str, str],
    run_id: str,
    records: Sequence[MissingnessRecord],
    *,
    opener: Callable[[MlAgentConnectionSettings], object] | None = None,
) -> LabWriteReceipt:
    return _from_environment(
        environ,
        lambda executor: write_missingness(executor, run_id, records),
        opener=opener,
    )


def write_column_profiles_from_environment(
    environ: Mapping[str, str],
    run_id: str,
    records: Sequence[ColumnProfileRecord],
    *,
    opener: Callable[[MlAgentConnectionSettings], object] | None = None,
) -> LabWriteReceipt:
    return _from_environment(
        environ,
        lambda executor: write_column_profiles(executor, run_id, records),
        opener=opener,
    )


def write_correlations_from_environment(
    environ: Mapping[str, str],
    run_id: str,
    records: Sequence[CorrelationRecord],
    *,
    opener: Callable[[MlAgentConnectionSettings], object] | None = None,
) -> LabWriteReceipt:
    return _from_environment(
        environ,
        lambda executor: write_correlations(executor, run_id, records),
        opener=opener,
    )


def write_findings_from_environment(
    environ: Mapping[str, str],
    run_id: str,
    records: Sequence[FindingRecord],
    *,
    opener: Callable[[MlAgentConnectionSettings], object] | None = None,
    ids: Sequence[str] | None = None,
) -> LabWriteReceipt:
    return _from_environment(
        environ,
        lambda executor: write_findings(executor, run_id, records, ids=ids),
        opener=opener,
    )


def write_queries_from_environment(
    environ: Mapping[str, str],
    run_id: str,
    records: Sequence[QueryRecord],
    *,
    opener: Callable[[MlAgentConnectionSettings], object] | None = None,
) -> LabWriteReceipt:
    return _from_environment(
        environ,
        lambda executor: write_queries(executor, run_id, records),
        opener=opener,
    )


def _write(
    executor: EdaSession,
    run_id: str,
    table: str,
    sql: str,
    prepared: Sequence[_BoundRow],
    database: str,
) -> LabWriteReceipt:
    target = require_lab(database)
    checked = _run_id(run_id)
    if not sql.startswith(f"INSERT INTO {target}."):
        raise EdaWriteError("statement target is not the ML Lab")
    _require_agent_session(executor)
    try:
        for row in prepared:
            executor.execute(sql, row.bind(checked))
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    return LabWriteReceipt(
        run_id=checked,
        database=target,
        table=table,
        rows_written=len(prepared),
        rows_suppressed=sum(row.suppressed for row in prepared),
    )


def require_lab(database: str) -> str:
    candidate = database.strip()
    if candidate.upper() != ML_LAB_DATABASE:
        raise EdaWriteError(REFUSED_DATABASE)
    return ML_LAB_DATABASE


def _from_environment(
    environ: Mapping[str, str],
    write: Callable[[EdaSession], LabWriteReceipt],
    *,
    opener: Callable[[MlAgentConnectionSettings], object] | None,
) -> LabWriteReceipt:
    try:
        settings, _config = load_ml_agent_request(environ)
    except ConfigError as error:
        raise EdaWriteError(str(error)) from error
    if settings.role.upper() != ML_AGENT_ROLE:
        raise EdaWriteError(REFUSED_ROLE)
    require_lab(settings.database)
    connection = (opener or open_ml_agent_connection)(settings)
    try:
        return write(CursorStatementExecutor(connection))
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            with contextlib.suppress(Exception):
                close()


def _bounded(rows: Sequence[_BoundRow]) -> tuple[_BoundRow, ...]:
    if len(rows) > _MAX_ROWS:
        raise EdaWriteError("too many rows for one run")
    return tuple(rows)


def _finding_ids(records: Sequence[FindingRecord], ids: Sequence[str] | None) -> tuple[str, ...]:
    if ids is None:
        return tuple(record.finding_id or str(uuid4()) for record in records)
    if len(ids) != len(records):
        raise EdaWriteError("finding ids do not match the findings")
    return tuple(
        record.finding_id or supplied for record, supplied in zip(records, ids, strict=True)
    )


def _run_id(value: str) -> str:
    stripped = value.strip()
    if _RUN_ID.fullmatch(stripped) is None:
        raise EdaWriteError("run_id is missing or not usable")
    return stripped


def _label(value: str, label: str) -> str:
    stripped = value.strip()
    if _LABEL.fullmatch(stripped) is None:
        raise EdaWriteError(f"{label} is missing or not usable")
    return stripped


def _ident(value: str, label: str) -> str:
    stripped = value.strip()
    if _IDENT.fullmatch(stripped) is None:
        raise EdaWriteError(f"{label} is missing or not usable")
    return stripped.upper()


def _count(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0 or value >= 2**63:
        raise EdaWriteError(f"{label} must be a non-negative integer")
    return value


def _optional_count(value: int | None, label: str) -> int | None:
    if value is None:
        return None
    return _count(value, label)


def _number(value: object, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EdaWriteError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise EdaWriteError(f"{label} must be a finite number")
    return number


def _percentiles(value: Mapping[str, float | None] | None) -> tuple[float | None, ...]:
    if value is None:
        return (None,) * len(_PERCENTILE_KEYS)
    if set(value) != set(_PERCENTILE_KEYS):
        raise EdaWriteError("percentiles must be p01, p05, p25, p50, p75, p95, and p99")
    return tuple(_number(value[key], key) for key in _PERCENTILE_KEYS)


def _optional_text(value: str | None, label: str, *, limit: int) -> str | None:
    if value is None:
        return None
    return _prose(value, label, limit=limit)


def _prose(value: str, label: str, *, limit: int) -> str:
    stripped = value.strip()
    upper = stripped.upper()
    if (
        not stripped
        or len(stripped) > limit
        or _FIPS.search(stripped) is not None
        or any(re.search(rf"\b{token}\b", upper) is not None for token in _FORBIDDEN_PROSE)
        or any(ord(char) < 32 or ord(char) == 127 for char in stripped)
    ):
        raise EdaWriteError(f"{label} is missing or not usable")
    return stripped


def _suppress_count_text(value: str | None) -> str | None:
    if value is None or _INTEGER_TEXT.fullmatch(value) is None:
        return value
    number = int(value)
    if 0 < number < SMALL_CELL_MINIMUM:
        return None
    return value


def _top_values(
    levels: Sequence[Mapping[str, object]] | None,
    non_null: int,
) -> tuple[str | None, bool]:
    if levels is None:
        return None, False
    kept: list[dict[str, object]] = []
    suppressed = False
    accounted = 0
    for item in levels:
        if set(item) != {"value", "n"}:
            raise EdaWriteError("top_values entries must be value and n")
        raw_value = item["value"]
        if not isinstance(raw_value, str):
            raise EdaWriteError("top_values value is not usable")
        text = _prose(raw_value, "top_values", limit=80)
        n = _count(item["n"], "top_values n")
        if n < SMALL_CELL_MINIMUM:
            suppressed = True
            continue
        accounted += n
        kept.append({"value": text, "n": n})
    residual = non_null - accounted
    if residual < 0:
        raise EdaWriteError("top_values exceed the non-null row count")
    if 0 < residual < SMALL_CELL_MINIMUM:
        return None, True
    if not kept:
        return None, suppressed
    payload = {"levels": sorted(kept, key=lambda item: str(item["value"]))}
    return _json_object(payload, "top_values"), suppressed


def _scrub_evidence(value: Mapping[str, object] | None) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    scrubbed = _scrub(value, depth=0)
    changed = scrubbed != value
    if not isinstance(scrubbed, dict):
        raise EdaWriteError("evidence must be a JSON object")
    return _json_object(scrubbed, "evidence"), changed


def _scrub(value: object, *, depth: int) -> object:
    if depth > 6:
        raise EdaWriteError("JSON values are nested too deeply")
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or key.strip().upper() in _FORBIDDEN_EVIDENCE:
                raise EdaWriteError("free-text fields cannot be written")
            cleaned[key] = _scrub(item, depth=depth + 1)
        return cleaned
    if isinstance(value, list):
        return [_scrub(item, depth=depth + 1) for item in value]
    if isinstance(value, str):
        if _FIPS.search(value) is not None or any(
            re.search(rf"\b{token}\b", value.upper()) is not None for token in _FORBIDDEN_PROSE
        ):
            raise EdaWriteError("evidence text is not an aggregate label")
        return value
    if isinstance(value, int) and not isinstance(value, bool) and 0 < value < SMALL_CELL_MINIMUM:
        return None
    return value


def _finding_id(value: str) -> str:
    stripped = value.strip().lower()
    if _FINDING_ID.fullmatch(stripped) is None:
        raise EdaWriteError("finding_id is not usable")
    return stripped


def _sha256(sql_text: str) -> str:
    return hashlib.sha256(sql_text.encode("utf-8")).hexdigest()


def _sql_text(value: str) -> str:
    stripped = value.strip()
    if not stripped or len(stripped) > 100_000 or "\x00" in stripped:
        raise EdaWriteError("sql_text is missing or not usable")
    body = stripped[:-1].strip() if stripped.endswith(";") else stripped
    if ";" in body:
        raise EdaWriteError("sql_text must be one statement")
    upper = body.upper()
    if any(token in upper for token in _FORBIDDEN_SQL):
        raise EdaWriteError("sql_text reads a free-text or payload column")
    if re.search(r"GEOMETRY_JSON(?!\s+IS\s+NULL\b)", upper) is not None:
        raise EdaWriteError("sql_text reads geometry")
    return body


def _optional_query_id(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    stripped = value.strip()
    if _QUERY_ID.fullmatch(stripped) is None:
        raise EdaWriteError("snowflake_query_id is not usable")
    return stripped
