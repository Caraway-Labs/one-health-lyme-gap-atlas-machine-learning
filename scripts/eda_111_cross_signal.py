#!/usr/bin/env python3
"""Run the issue 111 cross-signal documentation review.

Reads the pinned PROD presentation cohort into memory, writes ML Lab rows, and
saves PNG charts under artifacts/charts/111. County rows are not written to a
file. A second invocation reuses an existing run id and does not insert again.

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_111_cross_signal.py
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.cross_signal_disagreement import (
    CLASSES,
    NAIVE_SEED,
    QUERY_NAMES,
    REGIONS,
    SEED,
    SOURCE_OBJECTS,
    SPEC_ID,
    Analysis,
    CrossSignalError,
    analyze,
    lab_findings,
    lab_metrics,
    matrix_cells,
    prepare_counties,
    require_live_cohort,
    state_review_bars,
)
from lyme_gap_atlas_ml.cross_signal_report import render_comment, render_eda_record
from lyme_gap_atlas_ml.registry.artifacts import save_chart
from lyme_gap_atlas_ml.snowflake.anomaly_scores import RunAlreadyWritten
from lyme_gap_atlas_ml.snowflake.cross_signal_candidates import CANDIDATE_TABLE, write_candidates
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

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "111_cross_signal_disagreement.sql"
DOC_PATH = ROOT / "docs" / "eda" / "111-cross-signal-disagreement.md"
RUN_PATH = ROOT / "artifacts" / "charts" / "111" / "run_id.txt"
_MAX_PNG_BYTES = 40_000
_SHORT = {
    "insufficient_unknown": "unknown",
    "human_without_vector_documentation": "human only",
    "double_gap": "double gap",
    "established_no_pathogen_record": "established, no pathogen record",
    "reported_pathogen_present": "reported + pathogen",
    "reported_no_pathogen_record": "reported, no pathogen record",
    "pathogen_without_tick_record": "pathogen, no tick record",
    "concordant_undocumented": "none documented",
    "concordant_documented": "documented",
}


def main() -> int:
    settings, _config = load_ml_agent_request(os.environ)
    if settings.role.upper() != ML_AGENT_ROLE or settings.database != ML_LAB_DATABASE:
        print("stopped: ML agent context is not the lab role and database")
        return 2
    token = os.environ.get("SNOWFLAKE_PAT", "")
    connection = open_ml_agent_connection(settings)
    try:
        return _run(connection)
    except CrossSignalError as error:
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
    vintage_rows = _capture(connection, "source_vintages", queries, captured)
    cohort_rows = _capture(connection, "cohort_rows", queries, captured)
    snapshot = _timestamp(connection, captured)
    release_id = str(release_rows[0]["RELEASE_ID"])
    counties = prepare_counties(
        [_coerce_row(row) for row in cohort_rows],
        release_id=release_id,
    )
    require_live_cohort(
        counties,
        release_rows[0],
        {str(row["SOURCE_KEY"]): str(row["VINTAGE"]) for row in vintage_rows},
    )
    result = analyze(counties)
    charts = _render(result)
    for name, content in charts.items():
        save_chart(111, name, content)
    existing = _existing_run(connection)
    run_id = existing or _stored_run_id() or _new_run_id()
    _store_run_id(run_id)
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if existing is None:
        _persist(executor, run_id, branch, commit, snapshot, captured, result)
    counts = _row_counts(connection, run_id)
    _write_docs(result, run_id, commit or "unknown", counts, _drive_lines())
    print(f"run_id={run_id}")
    print(f"disposition={result.disposition}")
    print(f"reused_run={existing is not None}")
    print(f"candidates={len(result.candidates)}")
    print(f"follow_up={result.follow_up_n}")
    print(f"positive={result.positive_n}")
    print(f"double_gap={result.counts['double_gap']}")
    print(f"established_gap={result.established_gap_n}")
    for name in charts:
        path = ROOT / "artifacts" / "charts" / "111" / f"{name}.png"
        print(f"chart={name} bytes={path.stat().st_size}")
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
    try:
        written = write_candidates(executor, run_id, result.candidates)
    except RunAlreadyWritten:
        print("reused existing run during candidate insert")
        return
    print(f"candidates_inserted={written}")
    # This role can insert lab evidence and cannot delete shared EDA tables.
    # A fresh run id has no findings or queries, so the inserts are the record.
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
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="Cross-signal documentation gaps for issue 111",
            issue_number=111,
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
                "seed": SEED,
                "naive_seed": NAIVE_SEED,
                "multiplicity": "holm",
                "contract_residual": "not_computed",
            },
            random_seed=SEED,
            status="succeeded",
            notes="Documentation classes. County rows stay in the candidate table.",
        ),
        lab_metrics(result),
    )


def _write_docs(
    result: Analysis,
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
    record = render_eda_record(result, **kwargs)
    comment = render_comment(result, **kwargs)
    DOC_PATH.write_text(record + "\n" + comment, encoding="utf-8")


def _render(result: Analysis) -> dict[str, bytes]:
    sns.set_theme(style="whitegrid", font_scale=0.55)
    charts = {
        "disagreement-type-matrix": _matrix_chart(result),
        "state-review-counts": _state_chart(result),
    }
    for name, content in charts.items():
        if len(content) > _MAX_PNG_BYTES:
            raise CrossSignalError(f"{name} is {len(content)} bytes")
    return charts


def _matrix_chart(result: Analysis) -> bytes:
    labels = {(region, name): text for region, name, text in matrix_cells(result)}
    values = np.zeros((len(REGIONS), len(CLASSES)))
    annotations = np.empty((len(REGIONS), len(CLASSES)), dtype=object)
    for row, region in enumerate(REGIONS):
        for column, name in enumerate(CLASSES):
            text = labels[(region, name)]
            annotations[row, column] = text
            values[row, column] = np.nan if text == "<11" else float(text)
    figure, axis = plt.subplots(figsize=(7.4, 2.6))
    sns.heatmap(
        values,
        ax=axis,
        cmap="Blues",
        cbar=False,
        linewidths=0.4,
        linecolor="white",
        xticklabels=[_SHORT[name] for name in CLASSES],
        yticklabels=list(REGIONS),
        mask=np.isnan(values),
    )
    for row in range(len(REGIONS)):
        for column in range(len(CLASSES)):
            text = str(annotations[row, column])
            axis.text(
                column + 0.5,
                row + 0.5,
                text,
                ha="center",
                va="center",
                fontsize=8,
                color="0.1",
            )
    axis.set_title("Documentation class by Census region")
    axis.tick_params(axis="x", labelrotation=40, labelsize=6)
    axis.tick_params(axis="y", labelsize=7)
    return _png(figure, 80)


def _state_chart(result: Analysis) -> bytes:
    bars = state_review_bars(result)
    labels = [state for state, _text, _height in bars]
    heights = [0.0 if height is None else height for _state, _text, height in bars]
    colors = ["#d9d9d9" if height is None else "#4C78A8" for _state, _text, height in bars]
    figure, axis = plt.subplots(figsize=(6.2, 6.4))
    palette = dict(zip(labels, colors, strict=True))
    sns.barplot(
        x=heights,
        y=labels,
        hue=labels,
        ax=axis,
        palette=palette,
        orient="h",
        legend=False,
    )
    axis.set_xlabel("Counties with positive tick or pathogen documentation and no human floor")
    axis.set_title("State counts. Gray and <11 are suppressed")
    for index, (_state, _text, height) in enumerate(bars):
        if height is None:
            axis.text(0.2, index, "<11", va="center", fontsize=5, color="0.25")
    axis.tick_params(axis="y", labelsize=5)
    return _png(figure, 60)


def _png(figure: plt.Figure, dpi: int) -> bytes:
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0.08)
    plt.close(figure)
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
        raise CrossSignalError("session has no cursor")
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
    raise CrossSignalError("snapshot timestamp is missing")


def _existing_run(connection: object) -> str | None:
    sql = (
        f"SELECT RUN_ID FROM {ML_LAB_DATABASE}.REGISTRY.RUNS "
        "WHERE ISSUE_NUMBER = %s AND STARTSWITH(RUN_ID, %s)"
    )
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        return None
    with cursor_factory() as cursor:
        cursor.execute(sql, (111, "111-cross-signal-disagreement-"))
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
        "EDA.CROSS_SIGNAL_CANDIDATES_111": (
            f"SELECT COUNT(*) FROM {CANDIDATE_TABLE} WHERE RUN_ID = %s"
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
    return (
        "Drive folder https://drive.google.com/drive/folders/191hhct-v-vch7tHVmcTO1iPO1WTDXs4_",
        "state-review-counts.png "
        "https://drive.google.com/file/d/1HmzHz-NpIFQzbJlzzqfInWRExG_92ah1/view "
        "(13093 bytes; Drive metadata size matches the local PNG)",
        "disagreement-type-matrix.png was not kept. Two uploads changed the byte size "
        "(32115 against local 27243, then 27521 against local 27434). Both files were trashed.",
    )


def _stored_run_id() -> str | None:
    if not RUN_PATH.is_file():
        return None
    text = RUN_PATH.read_text(encoding="utf-8").strip()
    return text or None


def _store_run_id(run_id: str) -> None:
    RUN_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUN_PATH.write_text(run_id + "\n", encoding="utf-8")


def _new_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    return f"111-cross-signal-disagreement-{stamp}"


def _git(*arguments: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    text = completed.stdout.strip()
    return text or None


def _coerce_row(row: Mapping[str, object]) -> dict[str, object]:
    return {key: _coerce(value) for key, value in row.items()}


def _coerce(value: object) -> object:
    if isinstance(value, Decimal):
        return int(value) if value == int(value) else float(value)
    return value


if __name__ == "__main__":
    raise SystemExit(main())
