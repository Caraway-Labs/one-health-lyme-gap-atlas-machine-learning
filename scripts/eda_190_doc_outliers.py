#!/usr/bin/env python3
"""Fit issue 190 within-state documentation scores and write the ML Lab rows.

County rows stay in memory and in EDA.COUNTY_DOC_FLAGS_190. Charts are aggregate
PNGs under artifacts/charts/190/. A second invocation with the same run id does
not insert again.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from lyme_gap_atlas_ml.doc_outlier_report import DOC_PATH, render_eda_record
from lyme_gap_atlas_ml.doc_outliers import (
    PRIMARY_SEED,
    RUN_PREFIX,
    SOURCE_OBJECTS,
    SPEC_ID,
    Analysis,
    DocOutlierError,
    experiment_rows,
    lab_findings,
    lab_metrics,
    load_doc_queries,
    parse_counties,
    release_gate,
    score_counties,
)
from lyme_gap_atlas_ml.registry.artifacts import save_chart
from lyme_gap_atlas_ml.snowflake.doc_outlier_flags import FLAG_TABLE, write_flag_tables
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import QueryRecord, write_findings, write_queries
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE, EdaRun, write_eda_results
from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    ML_AGENT_ROLE,
    CursorStatementExecutor,
    load_ml_agent_request,
    open_ml_agent_connection,
)

ISSUE_NUMBER = 190
SQL_PATH = Path("sql/validation/190_doc_outliers.sql")
CHART_DIR = Path("artifacts/charts/190")
_MAX_PNG_BYTES = 20_000


def main() -> int:
    settings, _config = load_ml_agent_request(os.environ)
    if settings.role.upper() != ML_AGENT_ROLE or settings.database != ML_LAB_DATABASE:
        print("stopped: ML agent context is not the lab role and database")
        return 2
    connection = open_ml_agent_connection(settings)
    try:
        return _run(connection)
    except DocOutlierError as error:
        print(f"stopped: {error}")
        return 2
    finally:
        connection.close()


def _run(connection: object) -> int:
    queries = load_doc_queries(SQL_PATH.read_text(encoding="utf-8"))
    captured: list[tuple[str, str, int, int, str | None]] = []
    release_rows = _capture(connection, "release_identity", queries, captured)
    if len(release_rows) != 1:
        print("stopped: release view did not return one row")
        return 2
    release_gate(release_rows[0])
    cohort_rows = _capture(connection, "county_rows", queries, captured)
    try:
        cluster_rows = _capture(connection, "gap_clusters", queries, captured)
    except DocOutlierError as error:
        print(f"cluster read failed: {error}")
        cluster_rows = []
    release_id = str(release_rows[0]["RELEASE_ID"])
    print(f"counties={len(cohort_rows)} clusters={len(cluster_rows)}", flush=True)
    counties = parse_counties(cohort_rows, release_id=release_id)
    clusters = {
        str(row["FIPS"]): int(row["CLUSTER_ID"])
        for row in cluster_rows
        if row.get("CLUSTER_ID") is not None
    }
    print("scoring", flush=True)
    analysis = score_counties(counties, clusters=clusters)
    print("scored", flush=True)
    charts = _save_charts(analysis)
    existing = _existing_run(connection)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    run_id = existing or f"{RUN_PREFIX}{stamp}"
    commit = _git("rev-parse HEAD") or "unknown"
    grant = "not-attempted"
    if existing is None:
        grant = _persist(connection, run_id, commit, captured, analysis)
    counts = _row_counts(connection, run_id)
    text = render_eda_record(
        analysis,
        run_id=run_id,
        commit=commit,
        counts=counts,
        drive_note="Drive registration is pending for the aggregate charts.",
        grant=grant,
    )
    Path(DOC_PATH).write_text(text, encoding="utf-8")
    print(f"run_id={run_id}")
    print(f"grant={grant}")
    print(f"method_if={analysis.method_if}")
    print(f"method_z={analysis.method_z}")
    print(f"method_lof={analysis.method_lof}")
    print(f"product={analysis.product}")
    print(f"scored_n={analysis.scored_n}")
    print(f"stable_useful_n={analysis.stable_useful_n}")
    print(f"seed_jaccard={analysis.seed_jaccard}")
    print(f"seed_spearman={analysis.seed_spearman}")
    print(f"permutation_if={analysis.permutation_jaccard_if}")
    print(f"permutation_z={analysis.permutation_jaccard_z}")
    for name, count in counts.items():
        print(f"count {name} {count}")
    for name, (size, digest) in charts.items():
        print(f"chart {name} bytes={size} sha256={digest}")
    for row in analysis.examples:
        print(
            "example",
            row.state,
            row.county_name,
            row.fips,
            f"if={row.score_if_primary}",
            f"z_flag={row.flag_robust_z}",
            f"stable={row.stable_useful}",
            f"dominant={row.dominant_feature}",
        )
    return 0


def _persist(
    connection: object,
    run_id: str,
    commit: str,
    captured: Sequence[tuple[str, str, int, int, str | None]],
    analysis: Analysis,
) -> str:
    executor = CursorStatementExecutor(connection)
    branch = _git("rev-parse --abbrev-ref HEAD")
    result = write_flag_tables(executor, run_id, analysis.rows, experiment_rows(analysis, run_id))
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="Within-state documentation difference from state peers.",
            issue_number=ISSUE_NUMBER,
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=commit,
            source_environment="prod",
            source_release_id="governed-2026-10-15-january-climate-prod",
            source_objects=SOURCE_OBJECTS,
            parameters={
                "spec": SPEC_ID,
                "primary_seed": PRIMARY_SEED,
                "second_seed": 1902027,
                "sklearn": analysis.sklearn_version,
            },
            random_seed=PRIMARY_SEED,
            status="succeeded",
            notes="Not a detector. A flag is a within-state documentation difference.",
        ),
        lab_metrics(analysis),
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
    granted = result["grant_verified"]
    return "pass" if granted == "pass" else "fail"


def _save_charts(analysis: Analysis) -> dict[str, tuple[int, str]]:
    sns.set_theme(style="whitegrid", context="paper", font_scale=0.55)
    charts = {
        "band-flag-share": _band_chart(analysis),
        "method-agreement": _agreement_chart(analysis),
        "stability": _stability_chart(analysis),
        "permutation-check": _permutation_chart(analysis),
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


def _band_chart(analysis: Analysis) -> bytes | None:
    rows = [item for item in analysis.bands if item.counties >= 11 and not 0 < item.flags < 11]
    if not rows:
        return None
    return _bars(
        [item.band for item in rows],
        [item.flags / item.counties for item in rows],
        [item.method for item in rows],
        "Flagged share by state size",
    )


def _agreement_chart(analysis: Analysis) -> bytes | None:
    rows = [item for item in analysis.agreements if item.jaccard is not None]
    if not rows:
        return None
    return _bars(
        [f"{item.left}-{item.right}" for item in rows],
        [float(item.jaccard or 0.0) for item in rows],
        None,
        "Flagged-set overlap",
    )


def _stability_chart(analysis: Analysis) -> bytes | None:
    labels = ["seed", "z", "forest", "lof"]
    values = [
        analysis.seed_jaccard,
        analysis.bootstrap_z,
        analysis.bootstrap_if,
        analysis.bootstrap_lof,
    ]
    kept = _present(labels, values)
    if not kept:
        return None
    return _bars(
        [item[0] for item in kept],
        [item[1] for item in kept],
        None,
        "Seed and bootstrap overlap",
    )


def _permutation_chart(analysis: Analysis) -> bytes | None:
    labels = ["forest", "robust z", "size z", "size forest", "size lof"]
    values = [
        analysis.permutation_jaccard_if,
        analysis.permutation_jaccard_z,
        analysis.size_spearman_z,
        analysis.size_spearman_if,
        analysis.size_spearman_lof,
    ]
    kept = _present(labels, values)
    if not kept:
        return None
    return _bars(
        [item[0] for item in kept],
        [item[1] for item in kept],
        None,
        "Shuffle and size checks",
    )


def _present(
    labels: list[str],
    values: list[float | None],
) -> list[tuple[str, float]]:
    return [
        (label, float(value))
        for label, value in zip(labels, values, strict=True)
        if value is not None
    ]


def _bars(
    labels: list[str],
    values: list[float],
    hue: list[str] | None,
    title: str,
) -> bytes:
    figure, axis = plt.subplots(figsize=(3.3, 2.15))
    if hue is None:
        sns.barplot(x=labels, y=values, ax=axis, color="#4c78a8")
    else:
        sns.barplot(x=labels, y=values, hue=hue, ax=axis)
        legend = axis.get_legend()
        if legend is not None:
            legend.remove()
    axis.set_title(title)
    axis.set_xlabel("")
    axis.set_ylabel("")
    figure.tight_layout()
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=64)
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
        raise DocOutlierError("connection has no cursor")
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
        "EDA.COUNTY_DOC_FLAGS_190": f"SELECT COUNT(*) FROM {FLAG_TABLE} WHERE RUN_ID = %s",
        "REGISTRY.ARTIFACTS": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.REGISTRY.ARTIFACTS WHERE RUN_ID = %s"
        ),
    }
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
