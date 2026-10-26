#!/usr/bin/env python3
"""Fit the issue 110 peer-county cluster baselines.

Reads the pinned PROD presentation tables into memory, writes ML Lab rows, and
saves aggregate PNG charts under artifacts/charts/110. County names are written
to the EDA record and to the lab cluster table. They are not drawn on charts.

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_110_peer_clusters.py
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
import numpy as np
import seaborn as sns

from lyme_gap_atlas_ml.peer_cluster_report import (
    build_findings,
    profile_frame,
    render_comment,
    render_eda_record,
    stability_frame,
)
from lyme_gap_atlas_ml.peer_clusters import (
    PRIMARY_SEED,
    SPEC_ID,
    Analysis,
    PeerClusterError,
    analyze,
    build_counties,
    lab_metrics,
    load_peer_queries,
    release_matches,
    sklearn_version,
)
from lyme_gap_atlas_ml.registry.artifacts import save_chart
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
from lyme_gap_atlas_ml.snowflake.peer_cluster_scores import (
    READER_ROLE,
    RunAlreadyWritten,
    write_cluster_tables,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "110_peer_clusters.sql"
DOC_PATH = ROOT / "docs" / "eda" / "110-peer-county-clusters.md"
RUN_PATH = ROOT / "outputs" / "110-run-id.txt"
CHART_NAMES = ("cluster-profile", "stability-heatmap")
_MAX_PNG_BYTES = 40_000
_SOURCE_OBJECTS = (
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V",
)


def main() -> int:
    settings, _config = load_ml_agent_request(os.environ)
    if settings.role.upper() != ML_AGENT_ROLE or settings.database != ML_LAB_DATABASE:
        print("stopped: ML agent context is not the lab role and database")
        return 2
    token = os.environ.get("SNOWFLAKE_PAT", "")
    connection = open_ml_agent_connection(settings)
    try:
        return _run(connection)
    except (PeerClusterError, RunAlreadyWritten) as error:
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
    executor.query("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 540")
    run_id = _run_id()
    if _run_exists(connection, run_id):
        print(f"run_id: {run_id}")
        print("already written")
        return 0
    queries = load_peer_queries(SQL_PATH.read_text(encoding="utf-8"))
    captured: list[tuple[str, str, int, int, str | None]] = []
    release_rows, _meta = _capture(connection, "release_identity", queries, captured)
    matched, reasons = release_matches(release_rows[0])
    snapshot = _timestamp(connection, captured)
    if not matched:
        reason = "release pin mismatch: " + ",".join(reasons)
        _write_stop(executor, run_id, reason, captured, snapshot)
        print(f"run_id: {run_id}")
        print("disposition: stop")
        return 2
    atlas_rows, _atlas_meta = _capture(connection, "atlas_rows", queries, captured)
    nlcd_rows, _nlcd_meta = _capture(connection, "nlcd_county_total", queries, captured)
    climate_rows, climate_loaded = _climate(connection, queries, captured)
    nlcd_count = _int_cell(nlcd_rows, "COUNTY_N")
    counties = build_counties(atlas_rows, climate_rows)
    fitted = analyze(
        counties,
        nlcd_counties=nlcd_count,
        climate_loaded=climate_loaded,
        bootstrap=True,
        log=lambda message: print(message, flush=True),
    )
    print(
        f"fit_done: cluster={fitted.decision.cluster} product={fitted.decision.product}",
        flush=True,
    )
    charts = _render(fitted)
    for name, content in charts.items():
        save_chart(110, name, content)
    _persist(executor, connection, run_id, fitted, captured, snapshot, release_rows[0])
    return 0


def _persist(
    executor: _LabExecutor,
    connection: object,
    run_id: str,
    fitted: Analysis,
    captured: list[tuple[str, str, int, int, str | None]],
    snapshot: datetime,
    release_row: Mapping[str, object],
) -> None:
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    written = write_cluster_tables(executor, run_id, fitted)
    granted = bool(written["granted"])
    grant_note = (
        f"SELECT on EDA.COUNTY_CLUSTERS_110 was granted to {READER_ROLE}."
        if granted
        else (
            f"SELECT on EDA.COUNTY_CLUSTERS_110 was not granted. "
            f"The ML agent role cannot grant to {READER_ROLE}; the ML Lead grants it."
        )
    )
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="Peer-county cluster baselines for issue 110",
            issue_number=110,
            agent_id="OH_LYME_ML_AGENT_SVC",
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=commit,
            source_environment="ONE_HEALTH_LYME_GAP_ATLAS_PROD",
            source_release_id=str(release_row.get("RELEASE_ID", "")),
            source_objects=_SOURCE_OBJECTS,
            input_snapshot_ts=snapshot,
            parameters={
                "spec": SPEC_ID,
                "seeds": [PRIMARY_SEED, 1102027],
                "sklearn": sklearn_version(),
                "cluster_decision": fitted.decision.cluster,
                "product_call": fitted.decision.product,
                "climate_loaded": fitted.climate_loaded,
            },
            random_seed=PRIMARY_SEED,
            status="succeeded",
            notes="County assignments stay in the lab cluster table. Charts are aggregates.",
        ),
        lab_metrics(fitted),
    )
    finding_ids = tuple(f"11011010-0000-4000-8000-{index:012d}" for index in range(1, 4))
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
        ),
    )
    counts = _row_counts(connection, run_id)
    missing = tuple(f"{name}.png" for name in CHART_NAMES)
    comment = render_comment(
        fitted,
        run_id=run_id,
        git_commit=commit or "unknown",
        row_counts=counts,
        drive_links=(),
        missing_charts=missing,
        grant_note=grant_note,
    )
    DOC_PATH.write_text(
        render_eda_record(
            fitted,
            run_id=run_id,
            git_commit=commit or "unknown",
            row_counts=counts,
            drive_links=(),
            missing_charts=missing,
            grant_note=grant_note,
        ),
        encoding="utf-8",
    )
    print(f"run_id: {run_id}")
    print(f"cluster_decision: {fitted.decision.cluster}")
    print(f"product_call: {fitted.decision.product}")
    print("row_counts: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    for name in CHART_NAMES:
        path = ROOT / "artifacts" / "charts" / "110" / f"{name}.png"
        print(f"chart: {name}.png bytes={path.stat().st_size}")
    print("COMMENT_BEGIN")
    print(comment)
    print("COMMENT_END")


def _write_stop(
    executor: _LabExecutor,
    run_id: str,
    reason: str,
    captured: list[tuple[str, str, int, int, str | None]],
    snapshot: datetime,
) -> None:
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="Stopped issue 110 peer clusters before a fit",
            issue_number=110,
            agent_id="OH_LYME_ML_AGENT_SVC",
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=commit,
            source_environment="ONE_HEALTH_LYME_GAP_ATLAS_PROD",
            source_release_id=None,
            source_objects=_SOURCE_OBJECTS[:2],
            input_snapshot_ts=snapshot,
            parameters={"spec": SPEC_ID, "reason": reason},
            random_seed=PRIMARY_SEED,
            status="failed",
            notes="The predeclared release gate failed. No model was fit.",
        ),
        [],
    )
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
        ),
    )


def _climate(
    connection: object,
    queries: Mapping[str, str],
    captured: list[tuple[str, str, int, int, str | None]],
) -> tuple[list[dict[str, object]] | None, bool]:
    try:
        rows, _meta = _capture(connection, "climate_county", queries, captured)
    except StatementError:
        print("climate aggregate failed; climate and multi-domain are not estimable", flush=True)
        return None, False
    return rows, True


def _run_id() -> str:
    if RUN_PATH.exists():
        existing = RUN_PATH.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    run_id = f"110-peer-county-clusters-{stamp}"
    RUN_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUN_PATH.write_text(run_id + "\n", encoding="utf-8")
    return run_id


def _run_exists(connection: object, run_id: str) -> bool:
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        return False
    with cursor_factory() as cursor:
        cursor.execute(
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.REGISTRY.RUNS WHERE RUN_ID = %s",
            (run_id,),
        )
        row = cursor.fetchone()
    return bool(row and row[0] and int(row[0]) > 0)


class _LabExecutor:
    """Session adapter with executemany for the county insert."""

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
            raise PeerClusterError("session has no cursor")
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
    print(f"query {name}: rows={len(rows)} ms={elapsed}", flush=True)
    return rows, meta


def _fetch(connection: object, sql: str) -> tuple[list[dict[str, object]], str | None]:
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        raise PeerClusterError("session has no cursor")
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
    raise PeerClusterError("snapshot timestamp is missing")


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
        "EDA.COUNTY_CLUSTERS_110": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EDA.COUNTY_CLUSTERS_110 WHERE RUN_ID = %s"
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


def _render(result: Analysis) -> dict[str, bytes]:
    sns.set_theme(style="whitegrid", font_scale=0.65)
    return {
        "cluster-profile": _profile_chart(result),
        "stability-heatmap": _stability_chart(result),
    }


def _profile_chart(result: Analysis) -> bytes:
    rows = [row for row in profile_frame(result) if row["slice"] == "context"]
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    if rows:
        sns.barplot(
            data={
                "feature": [str(row["feature"]) for row in rows],
                "mean": [float(row["mean"]) for row in rows],
                "cluster": [str(row["cluster"]) for row in rows],
            },
            x="feature",
            y="mean",
            hue="cluster",
            ax=ax,
        )
        ax.legend(fontsize=6, title="")
    ax.set_title("Context-only standardized cluster means")
    ax.set_xlabel("")
    ax.set_ylabel("Standardized mean")
    fig.tight_layout()
    return _png(fig)


def _stability_chart(result: Analysis) -> bytes:
    names, columns, matrix = stability_frame(result)
    fig, ax = plt.subplots(figsize=(6.6, 3.2))
    if names:
        values = np.asarray(
            [[np.nan if value is None else value for value in row] for row in matrix],
            dtype=float,
        )
        sns.heatmap(
            values,
            vmin=0,
            vmax=1,
            cmap="Blues",
            annot=True,
            fmt=".2f",
            annot_kws={"size": 6},
            xticklabels=list(columns),
            yticklabels=list(names),
            ax=ax,
            cbar=False,
        )
        ax.tick_params(axis="x", labelrotation=40, labelsize=6)
    ax.set_title("Cluster stability")
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
        raise PeerClusterError("a chart exceeds 40 KB")
    return content


def _int_cell(rows: Sequence[Mapping[str, object]], key: str) -> int | None:
    if not rows:
        return None
    value = rows[0].get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


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
