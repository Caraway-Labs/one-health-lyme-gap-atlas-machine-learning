#!/usr/bin/env python3
"""Run the issue 113 within-state contrast.

Reads the pinned PROD presentation cohort into memory, writes ML Lab aggregate
rows, and saves one PNG when the chart gate opens. County rows are not written
to a file. A second invocation reuses an existing run id and does not insert
the metrics again.

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn \\
        python scripts/eda_113_spatial_neighbors.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.registry.artifacts import register_artifact, save_chart
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
from lyme_gap_atlas_ml.spatial_neighbor_report import render_eda_record
from lyme_gap_atlas_ml.spatial_neighbors import (
    QUERY_NAMES,
    SEED,
    SPEC_ID,
    STATE_DRAWS,
    Analysis,
    SpatialNeighborError,
    assert_catalog_clear,
    assert_lab_edges,
    assert_measures,
    fit_within_state,
    lab_findings,
    lab_metrics,
    parse_counties,
    release_gate,
    require_reference,
    vintage_gate,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "113_spatial_neighbors.sql"
DOC_PATH = ROOT / "docs" / "eda" / "113-spatial-neighbor-outliers.md"
CHART_DIR = ROOT / "artifacts" / "charts" / "113"
CHART_NAME = "state-median-incidence"
DRIVE_LINKS = CHART_DIR / "drive_links.txt"
_MAX_PNG_BYTES = 40_000
_SOURCE_OBJECTS = (
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_SOURCE_METADATA_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_MEASURE_METADATA_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.INFORMATION_SCHEMA.COLUMNS",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
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
    except SpatialNeighborError as error:
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
    executor = CursorStatementExecutor(connection)
    executor.query("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 600")
    queries = load_marked_queries(SQL_PATH.read_text(encoding="utf-8"), QUERY_NAMES)
    captured: list[tuple[str, str, int, int, str | None]] = []
    release_rows = _capture(connection, "release_identity", queries, captured)
    release_gate(release_rows[0])
    vintage_gate(_capture(connection, "source_vintages", queries, captured))
    assert_catalog_clear(_capture(connection, "adjacency_columns", queries, captured))
    assert_measures(_capture(connection, "spatial_measures", queries, captured))
    edge_rows = _capture(connection, "adjacency_lab_rows", queries, captured)
    assert_lab_edges(_int(edge_rows[0].get("EDGE_N")))
    cohort_rows = _capture(connection, "cohort_rows", queries, captured)
    snapshot = _timestamp(connection, captured)
    release_id = str(release_rows[0]["RELEASE_ID"])
    counties = parse_counties(
        [_pad_fips(_coerce_row(row)) for row in cohort_rows],
        release_id=release_id,
    )
    require_reference(counties)
    result = fit_within_state(counties)
    chart = _chart(result)
    saved = None
    if chart is not None:
        saved = save_chart(113, CHART_NAME, chart)
    existing = _existing_run(connection)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    run_id = existing or f"113-spatial-neighbors-{stamp}"
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if existing is None:
        _persist(executor, run_id, branch, commit, snapshot, captured, result)
    counts = _row_counts(connection, run_id)
    _register_chart(connection, run_id, saved)
    counts = _row_counts(connection, run_id)
    _write_doc(result, run_id, commit or "unknown", counts, _drive_lines())
    print(f"run_id={run_id}")
    print(f"within_state={result.within_state_disposition}")
    print(f"neighbor={result.neighbor_disposition}")
    print(f"product={result.product_disposition}")
    print(f"reused_run={existing is not None}")
    if saved is not None:
        print(f"chart={saved.file_name} bytes={saved.path.stat().st_size} sha256={saved.sha256}")
    else:
        print("chart=none")
    for name, count in counts.items():
        print(f"rows {name}={count}")
    return 0


def _persist(
    executor: CursorStatementExecutor,
    run_id: str,
    branch: str | None,
    commit: str | None,
    snapshot: datetime,
    captured: list[tuple[str, str, int, int, str | None]],
    result: Analysis,
) -> None:
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="Within-state incidence contrast for issue 113",
            issue_number=113,
            agent_id="OH_LYME_ML_AGENT_SVC",
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=commit,
            source_environment="ONE_HEALTH_LYME_GAP_ATLAS_PROD",
            source_release_id="governed-2026-10-15-january-climate-prod",
            source_objects=_SOURCE_OBJECTS,
            input_snapshot_ts=snapshot,
            parameters={
                "spec": SPEC_ID,
                "seed": SEED,
                "state_draws": STATE_DRAWS,
                "adjacency_sources": 0,
                "neighbor_estimable": 0,
            },
            random_seed=SEED,
            status="succeeded",
            notes="Aggregate within-state incidence contrast. County rows stay in memory.",
        ),
        lab_metrics(result),
    )
    write_findings(executor, run_id, lab_findings(result))
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


def _chart(result: Analysis) -> bytes | None:
    if not result.chart_bins:
        return None
    labels = [label for label, _count in result.chart_bins]
    heights = [count for _label, count in result.chart_bins]
    for dpi, width in ((72, 4.4), (60, 4.0), (48, 3.6)):
        fig, axis = plt.subplots(figsize=(width, 2.4))
        sns.barplot(x=labels, y=heights, ax=axis, color="#4C78A8")
        axis.set_title("States by median published incidence floor", fontsize=8)
        axis.set_xlabel("Median incidence floor per 100,000", fontsize=7)
        axis.set_ylabel("States", fontsize=7)
        axis.tick_params(axis="x", labelrotation=45, labelsize=6)
        axis.tick_params(axis="y", labelsize=6)
        content = _png(fig, dpi)
        if len(content) <= _MAX_PNG_BYTES:
            return content
    return None


def _png(fig: plt.Figure, dpi: int) -> bytes:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return buffer.getvalue()


def _register_chart(connection: object, run_id: str, saved: object) -> None:
    lines = _drive_lines()
    if saved is None or not lines or _row_counts(connection, run_id).get("REGISTRY.ARTIFACTS", 0):
        return
    first = lines[0].split()
    if len(first) < 3:
        return
    file_name, file_id, link = first[0], first[1], first[2]
    path = getattr(saved, "path", None)
    digest = getattr(saved, "sha256", None)
    if not isinstance(path, Path) or not isinstance(digest, str):
        return
    register_artifact(
        run_id,
        113,
        file_name,
        file_id,
        link,
        digest,
        byte_size=path.stat().st_size,
        caption="States by median published incidence floor",
        connection=connection,
    )


def _write_doc(
    result: Analysis,
    run_id: str,
    commit: str,
    counts: dict[str, int],
    drive_lines: tuple[str, ...],
) -> None:
    DOC_PATH.write_text(
        render_eda_record(
            result,
            run_id=run_id,
            commit=commit,
            counts=counts,
            drive_lines=drive_lines,
        ),
        encoding="utf-8",
    )


def _capture(
    connection: object,
    name: str,
    queries: Mapping[str, str],
    captured: list[tuple[str, str, int, int, str | None]],
) -> list[dict[str, object]]:
    started = time.perf_counter()
    rows, query_id = _fetch(connection, queries[name])
    elapsed = int((time.perf_counter() - started) * 1000)
    captured.append((name, queries[name], len(rows), elapsed, query_id))
    return rows


def _fetch(connection: object, sql: str) -> tuple[list[dict[str, object]], str | None]:
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        raise SpatialNeighborError("session has no cursor")
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
    rows = _capture(
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
    raise SpatialNeighborError("snapshot timestamp is missing")


def _existing_run(connection: object) -> str | None:
    sql = (
        f"SELECT RUN_ID FROM {ML_LAB_DATABASE}.REGISTRY.RUNS "
        "WHERE ISSUE_NUMBER = %s AND STARTSWITH(RUN_ID, %s)"
    )
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        return None
    with cursor_factory() as cursor:
        cursor.execute(sql, (113, "113-spatial-neighbors-"))
        found = [str(row[0]) for row in cursor.fetchall() if row and row[0]]
    if not found:
        return None
    return max(found)


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
        "REGISTRY.ARTIFACTS": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.REGISTRY.ARTIFACTS WHERE RUN_ID = %s"
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


def _drive_lines() -> tuple[str, ...]:
    if not DRIVE_LINKS.is_file():
        return ()
    return tuple(line for line in DRIVE_LINKS.read_text(encoding="utf-8").splitlines() if line)


def _coerce_row(row: Mapping[str, object]) -> dict[str, object]:
    return {key: _coerce(value) for key, value in row.items()}


def _pad_fips(row: dict[str, object]) -> dict[str, object]:
    fips = row.get("FIPS")
    if isinstance(fips, int) and not isinstance(fips, bool):
        row["FIPS"] = f"{fips:05d}"
    elif isinstance(fips, str) and fips.strip().isdigit() and len(fips.strip()) <= 5:
        row["FIPS"] = fips.strip().zfill(5)
    return row


def _coerce(value: object) -> object:
    if isinstance(value, Decimal):
        integral = value.to_integral_value()
        if value == integral:
            return int(integral)
        return float(value)
    return value


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SpatialNeighborError("edge count is not an integer")
    return value


def _git(*arguments: str) -> str | None:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    text = completed.stdout.strip()
    return text or None


if __name__ == "__main__":
    sys.exit(main())
