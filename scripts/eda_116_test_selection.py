#!/usr/bin/env python3
"""Run the issue 116 test-selection diagnostics.

Reads the pinned PROD presentation cohort into memory, writes ML Lab aggregate
rows, and saves PNG charts under artifacts/charts/116. County rows are not
written to a file. A second invocation reuses an existing run id and does not
insert again.

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_116_test_selection.py
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

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.registry.artifacts import save_chart
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import (
    QueryRecord,
    write_correlations,
    write_findings,
    write_queries,
)
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE, EdaRun, write_eda_results
from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    ML_AGENT_ROLE,
    CursorStatementExecutor,
    StatementError,
    load_ml_agent_request,
    open_ml_agent_connection,
    redact_text,
)
from lyme_gap_atlas_ml.test_selection import (
    METHOD_DECISIONS,
    NAIVE_SEED,
    QUERY_NAMES,
    REPLICATES,
    REPRODUCTION_SEED,
    SEED,
    SOURCE_OBJECTS,
    SPEC_ID,
    SelectionError,
    SelectionResult,
    ShareCell,
    analyze,
    lab_correlations,
    lab_findings,
    lab_metrics,
    prepare_counties,
    release_gate,
)
from lyme_gap_atlas_ml.test_selection_report import render_comment, render_eda_record

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "116_test_selection.sql"
DOC_PATH = ROOT / "docs" / "eda" / "116-test-selection.md"
COMMENT_PATH = ROOT / "artifacts" / "charts" / "116" / "comment.md"
_MAX_PNG_BYTES = 40_000
_CHARTS = ("decision-matrix", "bootstrap-intervals", "group-shares")


def main() -> int:
    settings, _config = load_ml_agent_request(os.environ)
    if settings.role.upper() != ML_AGENT_ROLE or settings.database != ML_LAB_DATABASE:
        print("stopped: ML agent context is not the lab role and database")
        return 2
    token = os.environ.get("SNOWFLAKE_PAT", "")
    connection = open_ml_agent_connection(settings)
    try:
        return _run(connection)
    except SelectionError as error:
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
    cohort_rows = _capture(connection, "cohort_rows", queries, captured)
    snapshot = _timestamp(connection, captured)
    counties = prepare_counties(
        [_coerce_row(row) for row in cohort_rows],
        release_id=str(release_rows[0]["RELEASE_ID"]),
    )
    result = analyze(counties)
    charts = _render(result)
    saved = {name: save_chart(116, name, content) for name, content in charts.items()}
    existing = _existing_run(connection)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    run_id = existing or f"116-test-selection-{stamp}"
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if existing is None:
        _persist(executor, run_id, branch, commit, snapshot, captured, result)
    counts = _row_counts(connection, run_id)
    _write_docs(result, run_id, commit or "unknown", counts, _drive_lines())
    print(f"run_id={run_id}")
    print(f"disposition={result.disposition}")
    print(f"reused_run={existing is not None}")
    for name, chart in saved.items():
        print(f"chart={name} bytes={chart.path.stat().st_size} sha256={chart.sha256}")
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
    result: SelectionResult,
) -> None:
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="Statistical test selection and October 13 robustness for issue 116",
            issue_number=116,
            agent_id="OH_LYME_ML_AGENT_SVC",
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=commit,
            source_environment="ONE_HEALTH_LYME_GAP_ATLAS_PROD",
            source_release_id=result.release_id,
            source_objects=SOURCE_OBJECTS,
            input_snapshot_ts=snapshot,
            parameters={
                "spec": SPEC_ID,
                "replicates": REPLICATES,
                "seed": SEED,
                "naive_seed": NAIVE_SEED,
                "reproduction_seed": REPRODUCTION_SEED,
                "multiplicity": "holm",
                "q3": "not_estimable",
            },
            random_seed=SEED,
            status="succeeded",
            notes="Aggregate test-selection diagnostics. County rows stay in memory.",
        ),
        lab_metrics(result),
    )
    write_correlations(executor, run_id, lab_correlations(result))
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


def _write_docs(
    result: SelectionResult,
    run_id: str,
    commit: str,
    counts: Mapping[str, int],
    drive_lines: Sequence[str],
) -> None:
    kwargs = {
        "run_id": run_id,
        "git_commit": commit,
        "row_counts": counts,
        "drive_lines": drive_lines,
    }
    DOC_PATH.write_text(render_eda_record(result, **kwargs), encoding="utf-8")
    COMMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMMENT_PATH.write_text(render_comment(result, **kwargs), encoding="utf-8")


def _render(result: SelectionResult) -> dict[str, bytes]:
    sns.set_theme(style="whitegrid", font_scale=0.65)
    charts = {
        "decision-matrix": _matrix_chart(),
        "bootstrap-intervals": _interval_chart(result),
        "group-shares": _share_chart(result),
    }
    for name, content in charts.items():
        if len(content) > _MAX_PNG_BYTES:
            raise SelectionError(f"{name} is {len(content)} bytes")
    return charts


def _matrix_chart() -> bytes:
    fig, axis = plt.subplots(figsize=(7.1, 3.6))
    axis.axis("off")
    cells = [[item.method, item.decision, item.use] for item in METHOD_DECISIONS]
    table = axis.table(cellText=cells, colLabels=["Method", "Decision", "Reason"], loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(6)
    table.scale(1, 1.15)
    axis.set_title("Issue 116 test decisions", fontsize=9)
    return _png(fig)


def _interval_chart(result: SelectionResult) -> bytes:
    rows = list(result.contrasts) + list(result.reproduced)
    labels: list[str] = []
    cluster: list[tuple[float, float, float]] = []
    naive: list[tuple[float, float, float]] = []
    for item in rows:
        estimate = item.estimate if hasattr(item, "estimate") else None
        association = getattr(item, "association", None)
        point = (
            estimate if estimate is not None else (None if association is None else association.v)
        )
        if point is None or item.cluster.low is None or item.cluster.high is None:
            continue
        labels.append(item.name)
        cluster.append((point, item.cluster.low, item.cluster.high))
        if item.naive.low is not None and item.naive.high is not None:
            naive.append((point, item.naive.low, item.naive.high))
        else:
            naive.append((point, point, point))
    fig, axis = plt.subplots(figsize=(6.4, 3.5))
    positions = list(range(len(labels)))
    _errorbar(axis, positions, cluster, -0.12, "state cluster")
    _errorbar(axis, positions, naive, 0.12, "county resample")
    axis.axvline(0, color="0.5", linewidth=0.6)
    axis.set_yticks(positions, labels, fontsize=6)
    axis.set_xlabel("Estimate and percentile interval")
    axis.set_title("State-cluster intervals beside county resamples")
    axis.legend(fontsize=6, frameon=False)
    return _png(fig)


def _share_chart(result: SelectionResult) -> bytes:
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 3.2))
    _bars(
        axes[0],
        [cell for cell in result.rucc_cells if cell.publishable],
        "Rural-urban code",
    )
    _bars(
        axes[1],
        [cell for cell in result.svi_cells if cell.publishable],
        "Vulnerability bin",
    )
    fig.suptitle("Published-floor share, publishable cells only", fontsize=9)
    return _png(fig)


def _bars(axis: plt.Axes, cells: Sequence[ShareCell], title: str) -> None:
    publishable = list(cells)
    shares = [cell.published / cell.n for cell in publishable]
    sns.barplot(x=[cell.label for cell in publishable], y=shares, ax=axis, color="#4C78A8")
    axis.set_title(title, fontsize=8)
    axis.set_ylabel("Published-floor share")
    axis.tick_params(axis="x", labelrotation=45, labelsize=6)
    axis.set_ylim(0, 1)


def _errorbar(
    axis: plt.Axes,
    positions: Sequence[int],
    rows: Sequence[tuple[float, float, float]],
    offset: float,
    label: str,
) -> None:
    ys = [position + offset for position in positions]
    values = [row[0] for row in rows]
    left = [row[0] - row[1] for row in rows]
    right = [row[2] - row[0] for row in rows]
    axis.errorbar(values, ys, xerr=[left, right], fmt="o", markersize=3, capsize=2, label=label)


def _png(fig: plt.Figure) -> bytes:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=72, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    return buffer.getvalue()


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
        raise SelectionError("session has no cursor")
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
    raise SelectionError("snapshot timestamp is missing")


def _existing_run(connection: object) -> str | None:
    sql = (
        f"SELECT RUN_ID FROM {ML_LAB_DATABASE}.REGISTRY.RUNS "
        "WHERE ISSUE_NUMBER = %s AND STARTSWITH(RUN_ID, %s)"
    )
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        return None
    with cursor_factory() as cursor:
        cursor.execute(sql, (116, "116-test-selection-"))
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
        "EDA.CORRELATIONS": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EDA.CORRELATIONS WHERE RUN_ID = %s"
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


def _coerce_row(row: Mapping[str, object]) -> dict[str, object]:
    return {key: _coerce(value) for key, value in row.items()}


def _coerce(value: object) -> object:
    if isinstance(value, Decimal):
        integral = value.to_integral_value()
        if value == integral:
            return int(integral)
        return float(value)
    return value


def _drive_lines() -> tuple[str, ...]:
    path = ROOT / "artifacts" / "charts" / "116" / "drive_links.txt"
    if not path.is_file():
        return ()
    lines = path.read_text(encoding="utf-8").splitlines()
    return tuple(line.strip() for line in lines if line.strip())


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
