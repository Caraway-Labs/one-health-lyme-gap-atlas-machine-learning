#!/usr/bin/env python3
"""Fit the issue 106 state-relative anomaly screen.

Reads the pinned PROD presentation cohort into memory, writes ML Lab rows, and
saves aggregate PNG charts under artifacts/charts/106. County names are written
to the EDA record and to the lab score table. They are not drawn on charts.

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_106_state_anomaly.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns

from lyme_gap_atlas_ml.class_anomaly import ClassAnomalyError, load_marked_queries, sklearn_version
from lyme_gap_atlas_ml.registry.artifacts import save_chart
from lyme_gap_atlas_ml.snowflake.anomaly_scores import RunAlreadyWritten
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import QueryRecord, write_findings, write_queries
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE, EdaRun, write_eda_results
from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    ML_AGENT_ROLE,
    CursorStatementExecutor,
    StatementError,
    load_ml_agent_request,
    open_ml_agent_connection,
    redact_text,
)
from lyme_gap_atlas_ml.snowflake.state_anomaly_scores import write_score_tables
from lyme_gap_atlas_ml.state_anomaly import (
    PRIMARY_SEED,
    QUERY_NAMES,
    SPEC_ID,
    FitResult,
    GateDecision,
    StateAnomalyError,
    build_findings,
    evaluate_gate,
    fit_states,
    lab_metrics,
)
from lyme_gap_atlas_ml.state_anomaly_report import render_comment, render_eda_record

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "106_state_anomaly.sql"
DOC_PATH = ROOT / "docs" / "eda" / "106-state-relative-anomaly.md"
_MAX_PNG_BYTES = 40_000


def main() -> int:
    settings, _config = load_ml_agent_request(os.environ)
    if settings.role.upper() != ML_AGENT_ROLE or settings.database != ML_LAB_DATABASE:
        print("stopped: ML agent context is not the lab role and database")
        return 2
    token = os.environ.get("SNOWFLAKE_PAT", "")
    connection = open_ml_agent_connection(settings)
    try:
        return _run(connection)
    except (StateAnomalyError, ClassAnomalyError, RunAlreadyWritten) as error:
        print(f"stopped: {error}")
        return 2
    except StatementError as error:
        print(f"stopped: statement failed permission_denied={error.permission_denied}")
        return 2
    except Exception as error:
        print("stopped: " + redact_text(str(error), [token])[:400])
        return 2
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()


def _run(connection: object) -> int:
    executor = _LabExecutor(connection)
    executor.query("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 600")
    queries = load_marked_queries(SQL_PATH.read_text(encoding="utf-8"), QUERY_NAMES)
    captured: list[tuple[str, str, int, int, str | None]] = []
    release_rows, _release_meta = _capture(connection, "release_identity", queries, captured)
    gate_rows, _gate_meta = _capture(connection, "cohort_gate", queries, captured)
    _capture(connection, "source_vintages", queries, captured)
    gate = evaluate_gate(release_rows[0], gate_rows[0])
    snapshot = _timestamp(connection, captured)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    run_id = f"106-state-relative-anomaly-{stamp}"
    print(f"gate_ok: {gate.ok} row_n={gate.row_n}", flush=True)
    if not gate.ok:
        print(f"run_id: {run_id}")
        print("disposition: stop")
        print("reasons: " + "; ".join(gate.reasons))
        return 2
    class_rows, _class_meta = _capture(connection, "cohort_rows", queries, captured)
    if len(class_rows) != gate.row_n:
        print("stopped: cohort row count does not match the aggregate gate")
        return 2
    for row in class_rows:
        fips = row.get("FIPS")
        if isinstance(fips, int):
            row["FIPS"] = f"{fips:05d}"
    fitted = fit_states(class_rows, run_id=run_id)
    print(f"fit_done: disposition={fitted.disposition} n_fit={fitted.n_fit}", flush=True)
    charts, skipped = _render(fitted)
    for name, content in charts.items():
        save_chart(106, name, content)
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    write_score_tables(executor, run_id, fitted.counties, fitted.experiments)
    _persist(executor, run_id, gate, branch, commit, snapshot, captured, fitted)
    counts = _row_counts(connection, run_id)
    _write_docs(fitted, run_id, commit or "unknown", counts, (), tuple(skipped))
    print(f"run_id: {run_id}")
    print(f"disposition: {fitted.disposition}")
    print("row_counts: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    print("skipped_charts: " + ", ".join(skipped))
    return 0


def _write_docs(
    fitted: FitResult,
    run_id: str,
    commit: str,
    counts: dict[str, int],
    missing: tuple[str, ...],
    skipped: tuple[str, ...],
) -> None:
    kwargs = {
        "run_id": run_id,
        "git_commit": commit,
        "row_counts": counts,
        "drive_links": (),
        "missing_charts": missing,
        "skipped_charts": skipped,
    }
    DOC_PATH.write_text(render_eda_record(fitted, **kwargs), encoding="utf-8")
    comment_path = ROOT / "artifacts" / "charts" / "106" / "comment.md"
    comment_path.parent.mkdir(parents=True, exist_ok=True)
    comment_path.write_text(render_comment(fitted, **kwargs), encoding="utf-8")


class _LabExecutor:
    """Session adapter with executemany for the county score insert."""

    def __init__(self, connection: object) -> None:
        self._connection = connection
        self._inner = CursorStatementExecutor(connection)

    def query(self, sql: str, params: tuple[object, ...] | None = None) -> list[tuple[object, ...]]:
        if params is None:
            return self._inner.query(sql)
        return self._inner.query(sql, params)

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self._inner.execute(sql, params)

    def executemany(self, sql: str, rows: Sequence[tuple[object, ...]]) -> None:
        cursor_factory = getattr(self._connection, "cursor", None)
        if not callable(cursor_factory):
            raise StateAnomalyError("session has no cursor")
        with cursor_factory() as cursor:
            cursor.executemany(sql, list(rows))


def _capture(
    connection: object,
    name: str,
    queries: Mapping[str, str],
    captured: list[tuple[str, str, int, int, str | None]],
) -> tuple[list[dict[str, object]], tuple[str, str, int, int, str | None]]:
    started = time.perf_counter()
    rows, query_id = _fetch(connection, queries[name])
    elapsed = int((time.perf_counter() - started) * 1000)
    meta = (name, queries[name], len(rows), elapsed, query_id)
    captured.append(meta)
    return rows, meta


def _fetch(connection: object, sql: str) -> tuple[list[dict[str, object]], str | None]:
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        raise StateAnomalyError("session has no cursor")
    with cursor_factory() as cursor:
        cursor.execute(sql)
        description = cursor.description
        if description is None:
            return [], getattr(cursor, "sfqid", None)
        names = [str(column[0]).upper() for column in description]
        raw_rows = cursor.fetchall()
        query_id = getattr(cursor, "sfqid", None)
    rows = [
        {name: _coerce(value) for name, value in zip(names, row, strict=True)} for row in raw_rows
    ]
    return rows, query_id if isinstance(query_id, str) else None


def _timestamp(
    connection: object,
    captured: list[tuple[str, str, int, int, str | None]],
) -> datetime:
    rows, _meta = _capture(
        connection,
        "snapshot",
        {"snapshot": "SELECT CURRENT_TIMESTAMP() AS SNAPSHOT_TS"},
        captured,
    )
    value = rows[0]["SNAPSHOT_TS"]
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    raise StateAnomalyError("snapshot timestamp is missing")


def _row_counts(connection: object, run_id: str) -> dict[str, int]:
    tables = {
        "REGISTRY.RUNS": f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.REGISTRY.RUNS WHERE RUN_ID = %s",
        "EDA.METRICS_LONG": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EDA.METRICS_LONG WHERE RUN_ID = %s"
        ),
        "EDA.FINDINGS": f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EDA.FINDINGS WHERE RUN_ID = %s",
        "REGISTRY.QUERIES": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.REGISTRY.QUERIES WHERE RUN_ID = %s"
        ),
        "EXPERIMENTS.EXPERIMENTS": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EXPERIMENTS.EXPERIMENTS WHERE RUN_ID = %s"
        ),
        "EXPERIMENTS.MODEL_METRICS": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EXPERIMENTS.MODEL_METRICS WHERE RUN_ID = %s"
        ),
        "EDA.COUNTY_STATE_ANOMALY_106": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EDA.COUNTY_STATE_ANOMALY_106 WHERE RUN_ID = %s"
        ),
    }
    counts: dict[str, int] = {}
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        return counts
    with cursor_factory() as cursor:
        for name, sql in tables.items():
            cursor.execute(sql, (run_id,))
            row = cursor.fetchone()
            counts[name] = int(row[0]) if row and row[0] is not None else 0
    return counts


def _persist(
    executor: _LabExecutor,
    run_id: str,
    gate: GateDecision,
    branch: str | None,
    commit: str | None,
    snapshot: datetime,
    captured: list[tuple[str, str, int, int, str | None]],
    fitted: FitResult,
) -> None:
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="State-relative anomaly screen for surveillance review, issue 106",
            issue_number=106,
            agent_id="OH_LYME_ML_AGENT_SVC",
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=commit,
            source_environment="ONE_HEALTH_LYME_GAP_ATLAS_PROD",
            source_release_id=gate.release_id,
            source_objects=(
                "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
                "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
                "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_SOURCE_METADATA_V",
            ),
            input_snapshot_ts=snapshot,
            parameters={
                "spec": SPEC_ID,
                "seeds": [PRIMARY_SEED, 1062027],
                "sklearn": sklearn_version(),
                "disposition": fitted.disposition,
            },
            random_seed=PRIMARY_SEED,
            status="succeeded",
            notes="County scores stay in the lab score table. Charts are aggregates.",
        ),
        lab_metrics(fitted),
    )
    finding_ids = tuple(f"10610610-0000-4000-8000-{index:012d}" for index in range(1, 4))
    write_findings(executor, run_id, build_findings(fitted), ids=finding_ids)
    write_queries(
        executor,
        run_id,
        tuple(
            QueryRecord(
                sql_text=sql,
                rows_returned=row_count,
                elapsed_ms=elapsed,
                snowflake_query_id=query_id,
            )
            for _name, sql, row_count, elapsed, query_id in captured
            if _name != "snapshot"
        ),
    )


def _render(result: FitResult) -> tuple[dict[str, bytes], list[str]]:
    sns.set_theme(style="whitegrid", font_scale=0.8)
    charts: dict[str, bytes] = {}
    skipped: list[str] = []
    sample = _sample_chart(result)
    if sample is None:
        skipped.append("state-sample-size.png")
    else:
        charts["state-sample-size"] = sample
    spread = _spread_chart(result)
    if spread is None:
        skipped.append("within-state-spread.png")
    else:
        charts["within-state-spread"] = spread
    agreement = _agreement_chart(result)
    if agreement is None:
        skipped.append("flag-agreement.png")
    else:
        charts["flag-agreement"] = agreement
    stability = _stability_chart(result)
    if stability is None:
        skipped.append("seed-stability.png")
    else:
        charts["seed-stability"] = stability
    return charts, skipped


def _sample_chart(result: FitResult) -> bytes | None:
    labels = []
    values = []
    for band in ("fallback", "shrunk", "state_native"):
        count = result.band_county_counts.get(band, 0)
        if 0 < count < 11:
            return None
        if count >= 11:
            labels.append(band)
            values.append(count)
    if not labels:
        return None
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    sns.barplot(
        data={"band": labels, "counties": values}, x="band", y="counties", ax=ax, color="#4C78A8"
    )
    ax.set_title("Counties by state-size band")
    ax.set_xlabel("")
    ax.set_ylabel("Counties")
    fig.tight_layout()
    return _png(fig)


def _spread_chart(result: FitResult) -> bytes | None:
    records: list[dict[str, object]] = []
    for band, features in result.spread.items():
        for feature, value in features.items():
            if value is None:
                continue
            records.append({"band": band, "feature": feature, "mad": value})
    if not records:
        return None
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    sns.barplot(
        data={
            "band": [row["band"] for row in records],
            "feature": [row["feature"] for row in records],
            "mad": [row["mad"] for row in records],
        },
        x="band",
        y="mad",
        hue="feature",
        ax=ax,
    )
    ax.set_title("Median within-state MAD by state size")
    ax.set_xlabel("")
    ax.set_ylabel("MAD")
    fig.tight_layout()
    return _png(fig)


def _agreement_chart(result: FitResult) -> bytes | None:
    if any(value is None for value in result.agreement.values()):
        return None
    labels = [key for key, value in result.agreement.items() if value]
    values = [value for value in result.agreement.values() if value]
    if not labels:
        return None
    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    sns.barplot(
        data={"cell": labels, "counties": values}, x="cell", y="counties", ax=ax, color="#F58518"
    )
    ax.set_title("National and state-relative robust-z flags")
    ax.tick_params(axis="x", labelrotation=20, labelsize=7)
    ax.set_xlabel("")
    ax.set_ylabel("Counties")
    fig.tight_layout()
    return _png(fig)


def _stability_chart(result: FitResult) -> bytes | None:
    if not result.seed_split or any(value is None for value in result.seed_split.values()):
        return None
    labels = list(result.seed_split)
    values = [result.seed_split[label] for label in labels]
    if any(value is None or 0 < value < 11 for value in values):
        return None
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    sns.barplot(
        data={"group": labels, "states": values},
        x="group",
        y="states",
        ax=ax,
        color="#54A24B",
    )
    ax.set_title("Isolation-forest seed Jaccard by state")
    ax.set_xlabel("")
    ax.set_ylabel("States")
    fig.tight_layout()
    return _png(fig)


def _png(fig: plt.Figure) -> bytes:
    content = b""
    for dpi in (64, 52, 42):
        buffer = BytesIO()
        fig.savefig(buffer, format="png", dpi=dpi)
        content = buffer.getvalue()
        if len(content) <= _MAX_PNG_BYTES:
            plt.close(fig)
            return content
    plt.close(fig)
    if len(content) > _MAX_PNG_BYTES:
        raise StateAnomalyError("a chart exceeds 40 KB")
    return content


def _coerce(value: object) -> object:
    if isinstance(value, Decimal):
        integral = value.to_integral_value()
        if value == integral:
            return int(integral)
        return float(value)
    return value


def _git(command: str, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", command, *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


if __name__ == "__main__":
    sys.exit(main())
