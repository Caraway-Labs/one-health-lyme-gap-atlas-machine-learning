#!/usr/bin/env python3
"""Fit issue 123 state reporting regimes and write ML Lab rows.

County rows stay in memory. A second invocation reuses an existing run id and
does not insert again. Chart registration is a separate ``--register`` pass.

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_123_state_regimes.py
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Mapping
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from matplotlib.figure import Figure

from lyme_gap_atlas_ml.coverage_audit import PINNED_RELEASE_ID
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
from lyme_gap_atlas_ml.snowflake.state_regime_groups import write_group_tables
from lyme_gap_atlas_ml.state_regime_report import DOC_PATH, render_comment, render_eda_record
from lyme_gap_atlas_ml.state_regimes import (
    ISSUE_NUMBER,
    REPLICATES,
    RUN_PREFIX,
    SEED_DESCRIPTIVE,
    SEED_PUBLICATION_FREE,
    SOURCE_OBJECTS,
    SPEC_ID,
    Analysis,
    ProfileFit,
    StateRegimeError,
    aggregate_states,
    analyze,
    assignment_rows,
    lab_experiments,
    lab_findings,
    lab_metrics,
    load_state_queries,
    release_matches,
    require_cohort,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "123_state_regimes.sql"
CHART_DIR = ROOT / "artifacts" / "charts" / "123"
COMMENT_PATH = CHART_DIR / "comment.md"
UPLOADS_PATH = CHART_DIR / "drive_uploads.json"
_MAX_PNG_BYTES = 40_000
_CHARTS = ("descriptive-dendrogram", "publication-free-dendrogram", "group-contingency")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--register":
        return _register()
    settings, _config = load_ml_agent_request(os.environ)
    if settings.role.upper() != ML_AGENT_ROLE or settings.database != ML_LAB_DATABASE:
        print("stopped: ML agent context is not the lab role and database")
        return 2
    token = os.environ.get("SNOWFLAKE_PAT", "")
    connection = open_ml_agent_connection(settings)
    try:
        return _run(connection)
    except StateRegimeError as error:
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
    queries = load_state_queries(SQL_PATH.read_text(encoding="utf-8"))
    captured: list[tuple[str, str, int, int, str | None]] = []
    release_rows = _capture(connection, "release_identity", queries, captured)
    matched, reasons = release_matches(release_rows[0])
    if not matched:
        raise StateRegimeError("release pin mismatch: " + ",".join(reasons))
    cohort_rows = _capture(connection, "state_rows", queries, captured)
    snapshot = _timestamp(connection, captured)
    release_id = str(release_rows[0]["RELEASE_ID"])
    states = aggregate_states(cohort_rows, release_id=release_id)
    require_cohort(states)
    analysis = analyze(states)
    saved = _save_charts(analysis)
    existing = _existing_run(connection)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    run_id = existing or f"{RUN_PREFIX}{stamp}"
    commit = _git("rev-parse", "HEAD") or "unknown"
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    grant = "not-attempted"
    if existing is None:
        grant = _persist(executor, run_id, branch, commit, snapshot, captured, analysis)
    counts = _row_counts(connection, run_id)
    grant_text = grant if existing is None else "reused"
    _write_docs(analysis, run_id, commit, counts, "pending upload", grant_text)
    print(f"run_id={run_id}")
    print(f"method={analysis.decision.method}")
    print(f"product={analysis.decision.product}")
    print(f"reused_run={existing is not None}")
    print(f"grant={grant}")
    for name, chart in saved.items():
        print(f"chart={name} bytes={chart[0]} sha256={chart[1]}")
    for name, count in counts.items():
        print(f"rows {name}={count}")
    return 0


def _persist(
    executor: CursorStatementExecutor,
    run_id: str,
    branch: str | None,
    commit: str,
    snapshot: datetime,
    captured: list[tuple[str, str, int, int, str | None]],
    analysis: Analysis,
) -> str:
    result = write_group_tables(
        executor,
        run_id,
        assignment_rows(analysis),
        lab_experiments(analysis, run_id),
    )
    write_findings(executor, run_id, lab_findings(analysis))
    write_queries(
        executor,
        run_id,
        tuple(
            QueryRecord(
                sql_text=sql,
                rows_returned=rows,
                elapsed_ms=elapsed,
                snowflake_query_id=query_id,
            )
            for _name, sql, rows, elapsed, query_id in captured
        ),
    )
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="State reporting regime groups for issue 123",
            issue_number=ISSUE_NUMBER,
            agent_id="OH_LYME_ML_AGENT_SVC",
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=None if commit == "unknown" else commit,
            source_environment="ONE_HEALTH_LYME_GAP_ATLAS_PROD",
            source_release_id=PINNED_RELEASE_ID,
            source_objects=SOURCE_OBJECTS,
            input_snapshot_ts=snapshot,
            parameters={
                "spec": SPEC_ID,
                "linkage": "ward",
                "distance": "euclidean",
                "descriptive_seed": SEED_DESCRIPTIVE,
                "publication_free_seed": SEED_PUBLICATION_FREE,
                "replicates": REPLICATES,
                "k_grid": "2-6",
                "rural": "rucc_4_to_9",
                "sklearn": analysis.sklearn_version,
            },
            random_seed=SEED_DESCRIPTIVE,
            status="succeeded",
            notes="State aggregates only. A missing median is not stored as zero.",
        ),
        lab_metrics(analysis),
    )
    return "pass" if result["granted"] else "fail"


def _save_charts(analysis: Analysis) -> dict[str, tuple[int, str]]:
    sns.set_theme(style="white", context="paper")
    charts = {
        "descriptive-dendrogram": _dendrogram(
            analysis.descriptive,
            analysis,
            "Descriptive reporting profile",
        ),
        "publication-free-dendrogram": _dendrogram(
            analysis.publication_free,
            analysis,
            "Publication-free profile",
        ),
        "group-contingency": _contingency(analysis),
    }
    saved: dict[str, tuple[int, str]] = {}
    for name, content in charts.items():
        if len(content) > _MAX_PNG_BYTES:
            raise StateRegimeError(f"{name} exceeds 40000 bytes")
        chart = save_chart(ISSUE_NUMBER, name, content)
        saved[name] = (len(content), chart.sha256)
    return saved


def _dendrogram(profile: ProfileFit, analysis: Analysis, title: str) -> bytes:
    states = analysis.states
    total = len(states)
    coords = _layout(profile, total)
    figure, axis = plt.subplots(figsize=(7.0, 6.6))
    for merge_index, pair in enumerate(profile.children):
        left, right = pair
        left_x, left_y = coords[left]
        right_x, right_y = coords[right]
        height = profile.distances[merge_index]
        axis.plot(
            [left_x, height, height, right_x],
            [left_y, left_y, right_y, right_y],
            color="#4c4c4c",
            linewidth=0.6,
        )
    axis.axvline(profile.cut_height, color="#888888", linestyle="--", linewidth=0.8)
    axis.set_yticks(range(total))
    axis.set_yticklabels([states[leaf].state for leaf in profile.leaf_order], fontsize=6)
    palette = sns.color_palette("colorblind", n_colors=profile.chosen.k)
    for tick, leaf in zip(axis.get_yticklabels(), profile.leaf_order, strict=True):
        tick.set_color(palette[profile.labels[leaf] - 1])
    axis.set_xlabel("Ward merge height")
    axis.set_title(f"{title}, Ward cut at {profile.chosen.k} groups")
    axis.set_ylim(-1, total)
    figure.text(
        0.01,
        0.005,
        "Postal codes only. The dashed line is the chosen cut. Share values are not printed.",
        fontsize=6,
    )
    sns.despine(ax=axis, left=True)
    return _png(figure)


def _layout(profile: ProfileFit, total: int) -> dict[int, tuple[float, float]]:
    coords: dict[int, tuple[float, float]] = {}
    y_of = {leaf: float(index) for index, leaf in enumerate(profile.leaf_order)}
    for leaf in range(total):
        coords[leaf] = (0.0, y_of[leaf])
    for merge_index, pair in enumerate(profile.children):
        left, right = pair
        height = profile.distances[merge_index]
        center_y = (coords[left][1] + coords[right][1]) / 2.0
        coords[total + merge_index] = (height, center_y)
    return coords


def _contingency(analysis: Analysis) -> bytes:
    data = np.array(analysis.contingency, dtype=float)
    annot = np.empty(data.shape, dtype=object)
    for row in range(data.shape[0]):
        for column in range(data.shape[1]):
            count = int(analysis.contingency[row][column])
            if 0 < count < 11:
                data[row, column] = np.nan
                annot[row, column] = ""
            else:
                annot[row, column] = str(count)
    figure, axis = plt.subplots(figsize=(6.0, 3.8))
    sns.heatmap(
        data,
        annot=annot,
        fmt="",
        cmap="Blues",
        mask=np.isnan(data),
        linewidths=0.4,
        linecolor="#dddddd",
        cbar=False,
        xticklabels=[f"group {group}" for group in analysis.publication_free_ids],
        yticklabels=[f"group {group}" for group in analysis.descriptive_ids],
        ax=axis,
    )
    axis.set_xlabel("Publication-free group")
    axis.set_ylabel("Descriptive group")
    axis.set_title(f"State groups, adjusted Rand {analysis.cross_ari:.2f}")
    figure.text(0.01, 0.005, "Cells of 1 to 10 states are blank.", fontsize=6)
    return _png(figure)


def _png(figure: Figure) -> bytes:
    data = b""
    for dpi in (72, 60, 50, 42):
        buffer = BytesIO()
        figure.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
        data = buffer.getvalue()
        if len(data) <= _MAX_PNG_BYTES:
            plt.close(figure)
            return data
    plt.close(figure)
    raise StateRegimeError(f"png is {len(data)} bytes")


def _write_docs(
    analysis: Analysis,
    run_id: str,
    commit: str,
    counts: Mapping[str, int],
    drive_lines: str,
    grant: str,
) -> None:
    comment = render_comment(
        analysis,
        run_id=run_id,
        commit=commit,
        counts=counts,
        drive_lines=drive_lines,
        grant=grant,
    )
    record = render_eda_record(
        analysis,
        run_id=run_id,
        commit=commit,
        counts=counts,
        drive_lines=drive_lines,
        grant=grant,
    )
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    COMMENT_PATH.write_text(comment, encoding="utf-8")
    (ROOT / DOC_PATH).write_text(record, encoding="utf-8")


def _register() -> int:
    payload = json.loads(UPLOADS_PATH.read_text(encoding="utf-8"))
    run_id = str(payload["run_id"])
    index = json.loads((CHART_DIR / "index.json").read_text(encoding="utf-8"))
    known = {entry["file_name"]: entry["sha256"] for entry in index["files"]}
    for item in payload["files"]:
        file_name = str(item["file_name"])
        content = (CHART_DIR / file_name).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != known.get(file_name):
            print(f"sha mismatch {file_name}")
            return 2
        register_artifact(
            run_id,
            ISSUE_NUMBER,
            file_name,
            str(item["drive_file_id"]),
            str(item["drive_link"]),
            digest,
            caption=str(item["caption"]),
            byte_size=len(content),
        )
        print(f"registered {file_name} bytes={len(content)}")
    return 0


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
        raise StateRegimeError("session has no cursor")
    with cursor_factory() as cursor:
        cursor.execute(sql)
        description = cursor.description
        if description is None:
            return [], _query_id(cursor)
        names = [str(column[0]).upper() for column in description]
        raw_rows = cursor.fetchall()
        query_id = _query_id(cursor)
    rows = [{name: row[index] for index, name in enumerate(names)} for row in raw_rows]
    return rows, query_id


def _query_id(cursor: object) -> str | None:
    query_id = getattr(cursor, "sfqid", None)
    if not isinstance(query_id, str) or len(query_id) < 8:
        return None
    return query_id


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
    raise StateRegimeError("snapshot timestamp is missing")


def _existing_run(connection: object) -> str | None:
    sql = (
        f"SELECT RUN_ID FROM {ML_LAB_DATABASE}.REGISTRY.RUNS "
        "WHERE ISSUE_NUMBER = %s AND STARTSWITH(RUN_ID, %s)"
    )
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        return None
    with cursor_factory() as cursor:
        cursor.execute(sql, (ISSUE_NUMBER, RUN_PREFIX))
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
        "EXPERIMENTS.EXPERIMENTS": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EXPERIMENTS.EXPERIMENTS WHERE RUN_ID = %s"
        ),
        "EXPERIMENTS.MODEL_METRICS": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EXPERIMENTS.MODEL_METRICS WHERE RUN_ID = %s"
        ),
        "EDA.STATE_REGIME_GROUPS_123": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EDA.STATE_REGIME_GROUPS_123 WHERE RUN_ID = %s"
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
            try:
                cursor.execute(sql, (run_id,))
                row = cursor.fetchone()
            except Exception:
                counts[name] = 0
                continue
            counts[name] = int(row[0]) if row and row[0] is not None else 0
    return counts


def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return value or None


if __name__ == "__main__":
    sys.exit(main())
