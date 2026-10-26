#!/usr/bin/env python3
"""Rerun the issue 192 lookup under the issue 196 bootstrap gate.

The issue 192 run is not updated. Charts are aggregate PNGs under
artifacts/charts/196/. A second invocation with the same run id does not insert
again.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from lyme_gap_atlas_ml.peer_lookup import (
    PRIMARY_SEED,
    SECOND_SEED,
    SOURCE_OBJECTS,
    Analysis,
    PeerLookupError,
    load_peer_queries,
    parse_clusters,
    parse_counties,
    release_gate,
    score_counties,
)
from lyme_gap_atlas_ml.peer_lookup_rerun import (
    CEILING_EXPECTATION,
    CEILING_K15_EXPECTATION,
    CONDITIONAL_MEDIAN_MIN,
    ISSUE_NUMBER,
    NEIGHBOR_READ_SQL,
    PRIOR_RUN_ID,
    RUN_PREFIX,
    SPEC_ID_196,
    decide_rerun,
    experiment_rows_196,
    lab_findings_196,
    lab_metrics_196,
    lists_match,
)
from lyme_gap_atlas_ml.peer_lookup_rerun_report import DOC_PATH, render_eda_record
from lyme_gap_atlas_ml.registry.artifacts import save_chart
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import QueryRecord, write_findings, write_queries
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaRun,
    EdaWriteError,
    write_eda_results,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    ML_AGENT_ROLE,
    CursorStatementExecutor,
    load_ml_agent_request,
    open_ml_agent_connection,
)
from lyme_gap_atlas_ml.snowflake.peer_lookup_rerun import (
    write_differing_neighbors,
    write_rerun_experiments,
)
from lyme_gap_atlas_ml.snowflake.peer_neighbors import mark_run_finished

SQL_PATH = Path("sql/validation/192_peer_lookup.sql")
_MAX_PNG_BYTES = 20_000
_TIMEOUT_SECONDS = 600


def main() -> int:
    settings, _config = load_ml_agent_request(os.environ)
    if settings.role.upper() != ML_AGENT_ROLE or settings.database != ML_LAB_DATABASE:
        print("stopped: ML agent context is not the lab role and database")
        return 2
    connection = open_ml_agent_connection(settings)
    try:
        return _run(connection)
    except (PeerLookupError, EdaWriteError) as error:
        print(f"stopped: {error}")
        return 2
    finally:
        connection.close()


def _run(connection: object) -> int:
    _session_timeout(connection)
    queries = load_peer_queries(SQL_PATH.read_text(encoding="utf-8"))
    captured: list[tuple[str, str, int, int, str | None]] = []
    release_rows = _capture(connection, "release_identity", queries["release_identity"], captured)
    if len(release_rows) != 1:
        print("stopped: release view did not return one row")
        return 2
    release_gate(release_rows[0])
    cohort_rows = _capture(connection, "county_rows", queries["county_rows"], captured)
    cluster_rows = _capture(connection, "gap_clusters", queries["gap_clusters"], captured)
    stored_rows = _capture(connection, "prior_neighbors", NEIGHBOR_READ_SQL, captured)
    release_id = str(release_rows[0]["RELEASE_ID"])
    print(f"counties={len(cohort_rows)} clusters={len(cluster_rows)}", flush=True)
    counties = parse_counties(cohort_rows, release_id=release_id)
    clusters = parse_clusters(cluster_rows)
    print("scoring", flush=True)
    analysis = score_counties(counties, clusters)
    decision = decide_rerun(analysis)
    print("scored", flush=True)
    stored = {
        str(row["FIPS"]): (str(row["EUCLIDEAN_NEIGHBORS"]), str(row["COSINE_NEIGHBORS"]))
        for row in stored_rows
    }
    unchanged = lists_match(stored, analysis.rows)
    charts = _save_charts(analysis)
    existing = _existing_run(connection)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    run_id = existing or f"{RUN_PREFIX}{stamp}"
    commit = _git("rev-parse HEAD") or "unknown"
    grant = "referenced-192-table"
    finished = "not-attempted"
    if existing is None:
        grant = _persist(connection, run_id, commit, captured, analysis, unchanged)
        finished = mark_run_finished(CursorStatementExecutor(connection), run_id)
    counts = _row_counts(connection, run_id, unchanged)
    text = render_eda_record(
        analysis,
        decision,
        run_id=run_id,
        commit=commit,
        counts=counts,
        drive_note="Drive registration is pending for the aggregate charts.",
        grant=grant,
        lists_unchanged=unchanged,
    )
    Path(DOC_PATH).write_text(text, encoding="utf-8")
    print(f"run_id={run_id}")
    print(f"prior_run_id={PRIOR_RUN_ID}")
    print(f"lists_unchanged={unchanged}")
    print(f"grant={grant}")
    print(f"finished_at={finished}")
    print(f"method={decision.method}")
    print(f"product={decision.product}")
    print(f"failures={','.join(decision.failures) if decision.failures else 'none'}")
    print(f"conditional_median={analysis.conditional_median}")
    print(f"conditional_low={analysis.conditional_low}")
    print(f"conditional_high={analysis.conditional_high}")
    print(f"conditional_seed_b={analysis.conditional_median_b}")
    print(f"conditional_k15={analysis.conditional_k15_median}")
    print(f"raw_median={analysis.bootstrap_median}")
    print(f"cosine_n={analysis.type_agreement_cosine_n}")
    print(f"euclidean_n={analysis.type_agreement_euclidean_n}")
    for name, count in counts.items():
        print(f"count {name} {count}")
    for name, (size, digest) in charts.items():
        print(f"chart {name} bytes={size} sha256={digest}")
    return 0


def _persist(
    connection: object,
    run_id: str,
    commit: str,
    captured: Sequence[tuple[str, str, int, int, str | None]],
    analysis: Analysis,
    unchanged: bool,
) -> str:
    executor = CursorStatementExecutor(connection)
    branch = _git("rev-parse --abbrev-ref HEAD")
    decision = decide_rerun(analysis)
    experiments = experiment_rows_196(analysis, run_id)
    write_rerun_experiments(executor, run_id, experiments)
    grant = "referenced-192-table"
    if not unchanged:
        grant = write_differing_neighbors(executor, run_id, analysis.rows)
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="Peer-county lookup rerun with a conditional bootstrap gate.",
            issue_number=ISSUE_NUMBER,
            agent_id="OH_LYME_ML_AGENT_SVC",
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=commit,
            source_environment="prod",
            source_release_id="governed-2026-10-15-january-climate-prod",
            source_objects=SOURCE_OBJECTS,
            parameters={
                "spec": SPEC_ID_196,
                "primary_seed": PRIMARY_SEED,
                "second_seed": SECOND_SEED,
                "conditional_median_min": CONDITIONAL_MEDIAN_MIN,
                "stable_ceiling": CEILING_EXPECTATION,
                "prior_run_id": PRIOR_RUN_ID,
                "sklearn": analysis.sklearn_version,
            },
            random_seed=PRIMARY_SEED,
            status="succeeded",
            notes="Lookup aid only. No ground truth. Not a disease similarity.",
        ),
        lab_metrics_196(analysis),
    )
    write_findings(executor, run_id, lab_findings_196(analysis, decision))
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
    return grant


def _save_charts(analysis: Analysis) -> dict[str, tuple[int, str]]:
    sns.set_theme(style="whitegrid", context="paper")
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 11, "legend.fontsize": 8})
    charts = {
        "method-agreement": _agreement_chart(analysis),
        "stability": _stability_chart(analysis),
        "ablation": _ablation_chart(analysis),
        "neighbor-distance": _distance_chart(analysis),
    }
    saved: dict[str, tuple[int, str]] = {}
    for name, content in charts.items():
        if content is None:
            print(f"chart omitted {name}")
            continue
        chart = save_chart(ISSUE_NUMBER, name, content)
        saved[name] = (len(content), chart.sha256)
        if len(content) > _MAX_PNG_BYTES:
            print(f"chart over budget {name} bytes={len(content)}")
    return saved


def _agreement_chart(analysis: Analysis) -> bytes | None:
    frame = _long(
        (
            ("In sample", "Euclidean", analysis.type_agreement_euclidean),
            ("In sample", "Cosine", analysis.type_agreement_cosine),
            ("In sample", "Same RUCC", analysis.type_agreement_baseline),
            ("State held out", "Euclidean", analysis.type_agreement_lso),
            ("State held out", "Cosine", analysis.type_agreement_lso_cosine),
            ("State held out", "Same RUCC", analysis.type_agreement_lso_baseline),
        )
    )
    if frame is None:
        return None
    return _grouped(frame, "Type agreement", "Share of typed neighbors", log=False)


def _stability_chart(analysis: Analysis) -> bytes | None:
    frame = _long(
        (
            ("k=5", "Conditional", analysis.conditional_median),
            ("k=5", "Raw Jaccard", analysis.bootstrap_median),
            ("k=5", "Stable ceiling", CEILING_EXPECTATION),
            ("k=15", "Conditional", analysis.conditional_k15_median),
            ("k=15", "Raw Jaccard", analysis.k15_bootstrap_median),
            ("k=15", "Stable ceiling", CEILING_K15_EXPECTATION),
        )
    )
    if frame is None:
        return None
    return _grouped(frame, "Neighbor-list stability", "Jaccard", log=False)


def _ablation_chart(analysis: Analysis) -> bytes | None:
    rows: list[tuple[str, str, float]] = []
    labels = {
        "svi_percentile": "SVI",
        "uninsured_percentile": "Uninsured",
        "log_population": "Log population",
        "rucc": "RUCC",
        "scapularis_status": "Blacklegged",
        "pacificus_status": "Western",
        "burgdorferi_status": "Pathogen",
    }
    for row in analysis.ablations:
        if row.dropped_jaccard > 0:
            rows.append((labels[row.block], "Dropped", row.dropped_jaccard))
        if row.alone_jaccard > 0:
            rows.append((labels[row.block], "Alone", row.alone_jaccard))
    if not rows:
        return None
    return _grouped(rows, "Feature-block overlap", "Jaccard with the full list", log=True)


def _distance_chart(analysis: Analysis) -> bytes | None:
    values = np.array([value for value in analysis.distance_values if np.isfinite(value)])
    if values.size < 11:
        return None
    counts, edges = np.histogram(values, bins=8)
    labels: list[str] = []
    heights: list[float] = []
    for count, left, right in zip(counts, edges[:-1], edges[1:], strict=True):
        if count < 11:
            continue
        labels.append(f"{left:.2f}-{right:.2f}")
        heights.append(float(count))
    if not labels:
        return None
    figure, axis = plt.subplots(figsize=(6.4, 3.8))
    sns.barplot(x=labels, y=heights, hue=["Euclidean k=5"] * len(labels), ax=axis, legend=True)
    axis.set_title("Distance to the 5th neighbor")
    axis.set_xlabel("Euclidean distance")
    axis.set_ylabel("Counties")
    axis.tick_params(axis="x", labelrotation=30)
    figure.tight_layout()
    return _png(figure)


def _long(
    rows: Sequence[tuple[str, str, float | None]],
) -> list[tuple[str, str, float]] | None:
    kept = [(slot, method, value) for slot, method, value in rows if value is not None]
    if not kept:
        return None
    return kept


def _grouped(
    rows: Sequence[tuple[str, str, float]],
    title: str,
    ylabel: str,
    *,
    log: bool,
) -> bytes:
    figure, axis = plt.subplots(figsize=(6.4, 3.8))
    sns.barplot(
        x=[row[0] for row in rows],
        y=[row[2] for row in rows],
        hue=[row[1] for row in rows],
        ax=axis,
    )
    axis.set_title(title)
    axis.set_xlabel("")
    axis.set_ylabel(ylabel)
    axis.tick_params(axis="x", labelrotation=15)
    if log:
        axis.set_yscale("log")
        axis.set_ylim(min(row[2] for row in rows) * 0.7, 1.2)
    figure.tight_layout()
    return _png(figure)


def _png(figure: plt.Figure) -> bytes:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=64)
    plt.close(figure)
    return buffer.getvalue()


def _session_timeout(connection: object) -> None:
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        return
    cursor = cursor_factory()
    try:
        cursor.execute(f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {_TIMEOUT_SECONDS}")
    except Exception:
        print("statement timeout was not set")
    finally:
        cursor.close()


def _capture(
    connection: object,
    name: str,
    sql: str,
    captured: list[tuple[str, str, int, int, str | None]],
) -> list[dict[str, object]]:
    started = time.perf_counter()
    rows, query_id = _fetch(connection, sql)
    elapsed = int((time.perf_counter() - started) * 1000)
    if elapsed > _TIMEOUT_SECONDS * 1000:
        raise PeerLookupError("query exceeded 10 minutes")
    captured.append((name, sql, len(rows), elapsed, query_id))
    return rows


def _fetch(connection: object, sql: str) -> tuple[list[dict[str, object]], str | None]:
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        raise PeerLookupError("connection has no cursor")
    cursor = cursor_factory()
    try:
        cursor.execute(sql)
        description = cursor.description
        if description is None:
            return [], getattr(cursor, "sfqid", None)
        names = [str(column[0]) for column in description]
        fetched = cursor.fetchall()
        query_id = getattr(cursor, "sfqid", None)
    finally:
        cursor.close()
    rows = [dict(zip(names, row, strict=True)) for row in fetched]
    return rows, query_id if isinstance(query_id, str) else None


def _existing_run(connection: object) -> str | None:
    sql = (
        f"SELECT RUN_ID FROM {ML_LAB_DATABASE}.REGISTRY.RUNS "
        "WHERE ISSUE_NUMBER = %s AND STARTSWITH(RUN_ID, %s)"
    )
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        return None
    cursor = cursor_factory()
    try:
        cursor.execute(sql, (ISSUE_NUMBER, RUN_PREFIX))
        rows = cursor.fetchall()
    finally:
        cursor.close()
    if not rows:
        return None
    return str(sorted(str(row[0]) for row in rows)[-1])


def _row_counts(connection: object, run_id: str, unchanged: bool) -> dict[str, int]:
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
        "REGISTRY.ARTIFACTS": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.REGISTRY.ARTIFACTS WHERE RUN_ID = %s"
        ),
    }
    if not unchanged:
        tables["EDA.PEER_COUNTY_NEIGHBORS_196"] = (
            "SELECT COUNT(*) FROM "
            f"{ML_LAB_DATABASE}.EDA.PEER_COUNTY_NEIGHBORS_196 WHERE RUN_ID = %s"
        )
    counts: dict[str, int] = {}
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        return counts
    cursor = cursor_factory()
    try:
        for name, sql in tables.items():
            cursor.execute(sql, (run_id,))
            row = cursor.fetchone()
            counts[name] = int(row[0]) if row else 0
        cursor.execute(
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EDA.PEER_COUNTY_NEIGHBORS_192 "
            "WHERE RUN_ID = %s",
            (PRIOR_RUN_ID,),
        )
        referenced = cursor.fetchone()
        counts["EDA.PEER_COUNTY_NEIGHBORS_192_referenced"] = int(referenced[0]) if referenced else 0
    finally:
        cursor.close()
    return counts


def _git(command: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *command.split()],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    text = completed.stdout.strip()
    return text or None


if __name__ == "__main__":
    sys.exit(main())
