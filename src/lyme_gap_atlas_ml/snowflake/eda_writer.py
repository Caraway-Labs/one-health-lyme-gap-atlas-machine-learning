"""Write aggregate EDA results to the ML Lab. Live sessions stay behind an injected opener.

Run metadata goes to ``REGISTRY.RUNS`` and metrics go to ``EDA.METRICS_LONG`` in
``ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB``. Any cell whose underlying count is below 11
is stored suppressed: the count and metric value are removed before the write.
No other database is a valid target.
"""

from __future__ import annotations

import contextlib
import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    IDENTITY_SQL,
    ML_AGENT_ROLE,
    REFUSED_INCOMPLETE,
    REFUSED_ROLE,
    ConfigError,
    CursorStatementExecutor,
    MlAgentConnectionSettings,
    StatementError,
    load_ml_agent_request,
    open_ml_agent_connection,
)

ML_LAB_DATABASE = "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB"
SMALL_CELL_MINIMUM = 11
REFUSED_DATABASE = "writes are allowed only to ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB"
_MAX_METRICS = 5000
_MAX_SOURCE_OBJECTS = 32
_JSON_OBJECT_LIMIT = 4000
_JSON_DEPTH_LIMIT = 6
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_LABEL = re.compile(r"^[A-Za-z][A-Za-z0-9_ .:/+-]{0,127}$")
_GEOID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
_COMMIT = re.compile(r"^[0-9a-fA-F]{7,64}$")
_STATUSES = frozenset({"running", "succeeded", "failed", "inconclusive"})
_FORBIDDEN_KEYS = frozenset({"PART_TEXT", "CONTEXT_LIMITATIONS"})
_RUNS_TABLE = f"{ML_LAB_DATABASE}.REGISTRY.RUNS"
_METRICS_TABLE = f"{ML_LAB_DATABASE}.EDA.METRICS_LONG"
_RUN_INSERT = f"""
INSERT INTO {_RUNS_TABLE} (
    RUN_ID, ISSUE_NUMBER, AGENT_ID, PURPOSE,
    GIT_REPO, GIT_BRANCH, GIT_COMMIT,
    SOURCE_ENVIRONMENT, SOURCE_RELEASE_ID, SOURCE_OBJECTS,
    INPUT_SNAPSHOT_TS, PARAMETERS, RANDOM_SEED, STATUS, NOTES
)
SELECT
    %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, PARSE_JSON(%s),
    %s, PARSE_JSON(%s), %s, %s, %s
""".strip()
_METRIC_INSERT = f"""
INSERT INTO {_METRICS_TABLE} (
    RUN_ID, METRIC_NAME, GEOGRAPHY_TYPE, GEOGRAPHY_ID,
    PERIOD_START, PERIOD_END, DIMENSIONS, METRIC_VALUE, UNIT,
    N_UNDERLYING, IS_SUPPRESSED
)
SELECT
    %s, %s, %s, %s,
    %s, %s, PARSE_JSON(%s), %s, %s,
    %s, %s
""".strip()


class EdaWriteError(ValueError):
    """The EDA write was rejected before or during a lab-only insert."""


class EdaSession(Protocol):
    def query(self, sql: str) -> Sequence[Sequence[object]]: ...

    def execute(self, sql: str, params: Sequence[object]) -> None: ...


@dataclass(frozen=True)
class EdaRun:
    run_id: str
    purpose: str
    issue_number: int | None = None
    agent_id: str | None = None
    git_repo: str | None = None
    git_branch: str | None = None
    git_commit: str | None = None
    source_environment: str | None = None
    source_release_id: str | None = None
    source_objects: tuple[str, ...] = ()
    input_snapshot_ts: datetime | None = None
    parameters: Mapping[str, object] | None = None
    random_seed: int | None = None
    status: str = "running"
    notes: str | None = None


@dataclass(frozen=True)
class EdaMetric:
    metric_name: str
    n_underlying: int
    metric_value: float | int | None = None
    geography_type: str | None = None
    geography_id: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    dimensions: Mapping[str, object] | None = None
    unit: str | None = None


@dataclass(frozen=True)
class PreparedMetric:
    """Metric row after small-cell suppression. Suppressed cells carry no count or value."""

    metric_name: str
    geography_type: str | None
    geography_id: str | None
    period_start: date | None
    period_end: date | None
    dimensions_json: str | None
    metric_value: float | None
    unit: str | None
    n_underlying: int | None
    is_suppressed: bool

    def bind(self, run_id: str) -> tuple[object, ...]:
        return (
            run_id,
            self.metric_name,
            self.geography_type,
            self.geography_id,
            self.period_start,
            self.period_end,
            self.dimensions_json,
            self.metric_value,
            self.unit,
            self.n_underlying,
            self.is_suppressed,
        )


@dataclass(frozen=True)
class EdaWriteReceipt:
    run_id: str
    database: str
    metrics_written: int
    metrics_suppressed: int


def require_ml_lab_database(database: str) -> str:
    """Return the canonical lab database, or reject every other target."""
    candidate = database.strip()
    if _IDENT.fullmatch(candidate) is None or candidate.upper() != ML_LAB_DATABASE:
        raise EdaWriteError(REFUSED_DATABASE)
    return ML_LAB_DATABASE


def prepare_eda_metric(metric: EdaMetric) -> PreparedMetric:
    """Validate one aggregate metric and remove counts below the small-cell minimum."""
    name = _label(metric.metric_name, "metric_name")
    count = _count(metric.n_underlying)
    value = _number(metric.metric_value, "metric_value")
    start = _day(metric.period_start, "period_start")
    end = _day(metric.period_end, "period_end")
    if start is not None and end is not None and end < start:
        raise EdaWriteError("period_end is before period_start")
    suppressed = count < SMALL_CELL_MINIMUM
    return PreparedMetric(
        metric_name=name,
        geography_type=_optional_label(metric.geography_type, "geography_type"),
        geography_id=_optional_geoid(metric.geography_id),
        period_start=start,
        period_end=end,
        dimensions_json=_json_object(metric.dimensions, "dimensions"),
        metric_value=None if suppressed else value,
        unit=_optional_label(metric.unit, "unit"),
        n_underlying=None if suppressed else count,
        is_suppressed=suppressed,
    )


def write_eda_results(
    executor: EdaSession,
    run: EdaRun,
    metrics: Sequence[EdaMetric],
    *,
    database: str = ML_LAB_DATABASE,
) -> EdaWriteReceipt:
    """Insert one run row and its metrics. The target database must be the ML Lab."""
    target = require_ml_lab_database(database)
    prepared_run = _prepare_run(run)
    prepared_metrics = _prepare_metrics(metrics)
    run_id = prepared_run[0]
    if not isinstance(run_id, str):
        raise EdaWriteError("run_id is missing or not usable")
    _require_agent_session(executor)
    try:
        executor.execute(_RUN_INSERT, prepared_run)
        for metric in prepared_metrics:
            executor.execute(_METRIC_INSERT, metric.bind(run_id))
    except StatementError as error:
        raise EdaWriteError("statement failed") from error
    return EdaWriteReceipt(
        run_id=run_id,
        database=target,
        metrics_written=len(prepared_metrics),
        metrics_suppressed=sum(metric.is_suppressed for metric in prepared_metrics),
    )


def write_eda_results_from_environment(
    environ: Mapping[str, str],
    run: EdaRun,
    metrics: Sequence[EdaMetric],
    *,
    opener: Callable[[MlAgentConnectionSettings], object] | None = None,
) -> EdaWriteReceipt:
    """Open the ML agent connection and write. The opener is not called for a refused target."""
    try:
        settings, _config = load_ml_agent_request(environ)
    except ConfigError as error:
        raise EdaWriteError(str(error)) from error
    if settings.role.upper() != ML_AGENT_ROLE:
        raise EdaWriteError(REFUSED_ROLE)
    require_ml_lab_database(settings.database)
    connection = (opener or open_ml_agent_connection)(settings)
    try:
        return write_eda_results(
            CursorStatementExecutor(connection),
            run,
            metrics,
            database=ML_LAB_DATABASE,
        )
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            with contextlib.suppress(Exception):
                close()


def _prepare_metrics(metrics: Sequence[EdaMetric]) -> tuple[PreparedMetric, ...]:
    rows = tuple(metrics)
    if len(rows) > _MAX_METRICS:
        raise EdaWriteError("too many metric rows for one run")
    return tuple(prepare_eda_metric(metric) for metric in rows)


def _prepare_run(run: EdaRun) -> tuple[object, ...]:
    run_id = run.run_id.strip()
    if _RUN_ID.fullmatch(run_id) is None:
        raise EdaWriteError("run_id is missing or not usable")
    status = run.status.strip().lower()
    if status not in _STATUSES:
        raise EdaWriteError("status is not a recognized run status")
    if len(run.source_objects) > _MAX_SOURCE_OBJECTS:
        raise EdaWriteError("too many source objects")
    sources = [_qualified_object(item) for item in run.source_objects]
    source_json = json.dumps(sources, separators=(",", ":")) if sources else None
    return (
        run_id,
        _optional_int(run.issue_number, "issue_number"),
        _optional_text(run.agent_id, "agent_id", limit=128),
        _text(run.purpose, "purpose", limit=500),
        _optional_text(run.git_repo, "git_repo", limit=200),
        _optional_text(run.git_branch, "git_branch", limit=200),
        _commit(run.git_commit),
        _optional_text(run.source_environment, "source_environment", limit=64),
        _optional_text(run.source_release_id, "source_release_id", limit=128),
        source_json,
        _timestamp(run.input_snapshot_ts),
        _json_object(run.parameters, "parameters"),
        _optional_int(run.random_seed, "random_seed"),
        status,
        _optional_text(run.notes, "notes", limit=2000),
    )


def _require_agent_session(executor: EdaSession) -> None:
    try:
        rows = executor.query(IDENTITY_SQL)
    except StatementError as error:
        raise EdaWriteError(REFUSED_INCOMPLETE) from error
    if len(rows) != 1:
        raise EdaWriteError(REFUSED_INCOMPLETE)
    row = rows[0]
    if isinstance(row, (str, bytes)) or len(row) != 3:
        raise EdaWriteError(REFUSED_INCOMPLETE)
    role, warehouse, database = row
    if not isinstance(role, str) or not isinstance(warehouse, str) or not isinstance(database, str):
        raise EdaWriteError(REFUSED_INCOMPLETE)
    if not role.strip() or not warehouse.strip() or not database.strip():
        raise EdaWriteError(REFUSED_INCOMPLETE)
    if role.strip().upper() != ML_AGENT_ROLE:
        raise EdaWriteError(REFUSED_ROLE)


def _label(value: str, label: str) -> str:
    stripped = value.strip()
    if _LABEL.fullmatch(stripped) is None:
        raise EdaWriteError(f"{label} is missing or not usable")
    return stripped


def _optional_label(value: str | None, label: str) -> str | None:
    if value is None or not value.strip():
        return None
    return _label(value, label)


def _optional_geoid(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    stripped = value.strip()
    if _GEOID.fullmatch(stripped) is None:
        raise EdaWriteError("geography_id is missing or not usable")
    return stripped


def _text(value: str, label: str, *, limit: int) -> str:
    stripped = value.strip()
    if not stripped or len(stripped) > limit or _unsupported(stripped):
        raise EdaWriteError(f"{label} is missing or not usable")
    return stripped


def _optional_text(value: str | None, label: str, *, limit: int) -> str | None:
    if value is None or not value.strip():
        return None
    return _text(value, label, limit=limit)


def _commit(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    stripped = value.strip()
    if _COMMIT.fullmatch(stripped) is None:
        raise EdaWriteError("git_commit is not usable")
    return stripped.lower()


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EdaWriteError("n_underlying must be a non-negative integer")
    return value


def _optional_int(value: int | None, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or abs(value) >= 2**63:
        raise EdaWriteError(f"{label} is not usable")
    if label == "issue_number" and value < 1:
        raise EdaWriteError("issue_number is not usable")
    return value


def _number(value: object, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EdaWriteError(f"{label} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise EdaWriteError(f"{label} must be a finite number")
    return number


def _day(value: date | None, label: str) -> date | None:
    if value is None:
        return None
    if type(value) is not date:
        raise EdaWriteError(f"{label} must be a calendar date")
    return value


def _timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise EdaWriteError("input_snapshot_ts requires a timezone")
    return value


def _qualified_object(value: str) -> str:
    parts = value.split(".")
    if len(parts) != 3 or any(_IDENT.fullmatch(part) is None for part in parts):
        raise EdaWriteError("source_objects entries must be database.schema.object identifiers")
    return ".".join(part.upper() for part in parts)


def _json_object(value: Mapping[str, object] | None, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise EdaWriteError(f"{label} must be a JSON object")
    _reject_forbidden(value, depth=0)
    try:
        encoded = json.dumps(value, allow_nan=False, separators=(",", ":"), sort_keys=True)
    except (TypeError, ValueError) as error:
        raise EdaWriteError(f"{label} must be JSON data") from error
    if not encoded.startswith("{"):
        raise EdaWriteError(f"{label} must be a JSON object")
    if len(encoded) > _JSON_OBJECT_LIMIT:
        raise EdaWriteError(f"{label} is too long")
    return encoded


def _reject_forbidden(value: object, *, depth: int) -> None:
    if depth > _JSON_DEPTH_LIMIT:
        raise EdaWriteError("JSON values are nested too deeply")
    if isinstance(value, dict):
        if len(value) > 30:
            raise EdaWriteError("JSON objects have too many fields")
        for key, item in value.items():
            if not isinstance(key, str) or key.strip().upper() in _FORBIDDEN_KEYS:
                raise EdaWriteError("free-text fields cannot be written")
            _reject_forbidden(item, depth=depth + 1)
        return
    if isinstance(value, list):
        if len(value) > 50:
            raise EdaWriteError("JSON arrays are too long")
        for item in value:
            _reject_forbidden(item, depth=depth + 1)
        return
    if isinstance(value, str):
        if len(value) > 200 or _unsupported(value):
            raise EdaWriteError("text values are limited to aggregate labels")
        return
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if abs(value) >= 2**63:
            raise EdaWriteError("JSON integers are out of range")
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise EdaWriteError("JSON numbers must be finite")
        return
    raise EdaWriteError("JSON values must be plain data")


def _unsupported(value: str) -> bool:
    return any(ord(char) < 32 or ord(char) == 127 for char in value)
