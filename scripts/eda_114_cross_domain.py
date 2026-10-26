#!/usr/bin/env python3
"""Fit the issue 114 cross-domain associations and PCA baseline.

Reads the pinned PROD presentation atlas into memory, writes existing ML Lab
tables, and saves aggregate PNG charts. County rows are not written to a file.
Climate day values are not queried. No GRANT is issued.

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_114_cross_domain.py
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
import numpy as np
import seaborn as sns

from lyme_gap_atlas_ml.cross_domain import (
    SEED,
    SPEC_ID,
    Analysis,
    CrossDomainError,
    analyze,
    lab_correlations,
    lab_findings,
    lab_metrics,
    load_cross_domain_queries,
    pca_experiments,
    prepare_counties,
    release_matches,
)
from lyme_gap_atlas_ml.cross_domain_report import render_comment, render_eda_record
from lyme_gap_atlas_ml.registry.artifacts import save_chart
from lyme_gap_atlas_ml.snowflake.cross_domain_experiments import (
    RunAlreadyWritten,
    write_pca_experiments,
)
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

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "114_cross_domain.sql"
DOC_PATH = ROOT / "docs" / "eda" / "114-cross-domain-associations.md"
RUN_PATH = ROOT / "outputs" / "114-run-id.txt"
CHART_NAMES = ("redundancy-heatmap", "scree", "loading-plot")
_MAX_PNG_BYTES = 40_000
_SOURCE_OBJECTS = (
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
)
_FINDING_IDS = tuple(f"11411411-0000-4000-8000-{index:012d}" for index in range(1, 5))
_SHORT = {
    "log_population": "log pop",
    "svi_percentile": "SVI",
    "uninsured_percentile": "uninsured",
    "rucc_2023": "RUCC",
    "human_published": "human",
    "tick_established": "tick est.",
    "tick_reported": "tick rep.",
    "pathogen_present": "pathogen",
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
    except (CrossDomainError, RunAlreadyWritten) as error:
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
    run_id = _run_id()
    counts = _row_counts(connection, run_id)
    if _complete(counts):
        print(f"run_id: {run_id}")
        print("already written")
        return 0
    if counts.get("EXPERIMENTS.EXPERIMENTS", 0) and not counts.get("REGISTRY.RUNS", 0):
        print("stopped: experiment rows exist without a run row")
        return 2
    queries = load_cross_domain_queries(SQL_PATH.read_text(encoding="utf-8"))
    captured: list[tuple[str, str, int, int, str | None]] = []
    release_rows, _meta = _capture(connection, "release_identity", queries, captured)
    try:
        release_matches(release_rows[0])
    except CrossDomainError as error:
        snapshot = _timestamp(connection, captured)
        _write_stop(executor, run_id, str(error), captured, snapshot)
        print(f"run_id: {run_id}")
        print("disposition: stop")
        return 2
    cohort_rows, _cohort_meta = _capture(connection, "cohort_rows", queries, captured)
    release_id = str(release_rows[0]["RELEASE_ID"])
    counties = prepare_counties(cohort_rows, release_id=release_id)
    print(f"fit_start: counties={len(counties)}", flush=True)
    fitted = analyze(counties)
    print(
        f"fit_done: representation={fitted.representation} follow_up={fitted.follow_up}",
        flush=True,
    )
    charts = _render(fitted)
    for name, content in charts.items():
        save_chart(114, name, content)
    snapshot = _timestamp(connection, captured)
    _persist(executor, connection, run_id, fitted, captured, snapshot, release_id, counts)
    return 0


def _persist(
    executor: _LabExecutor,
    connection: object,
    run_id: str,
    fitted: Analysis,
    captured: list[tuple[str, str, int, int, str | None]],
    snapshot: datetime,
    release_id: str,
    prior: dict[str, int],
) -> None:
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if not prior.get("REGISTRY.RUNS", 0):
        write_eda_results(
            executor,
            EdaRun(
                run_id=run_id,
                purpose="Cross-domain associations and PCA for issue 114",
                issue_number=114,
                agent_id="OH_LYME_ML_AGENT_SVC",
                git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
                git_branch=branch,
                git_commit=commit,
                source_environment="ONE_HEALTH_LYME_GAP_ATLAS_PROD",
                source_release_id=release_id,
                source_objects=_SOURCE_OBJECTS,
                input_snapshot_ts=snapshot,
                parameters={
                    "spec": SPEC_ID,
                    "seeds": [SEED, 1142027],
                    "representation": fitted.representation,
                    "follow_up": fitted.follow_up,
                    "family_complete": fitted.family_complete,
                },
                random_seed=SEED,
                status="succeeded" if fitted.context_pca.estimable else "failed",
                notes="No new table and no GRANT. County rows were not written.",
            ),
            lab_metrics(fitted),
        )
    if not prior.get("EXPERIMENTS.EXPERIMENTS", 0):
        write_pca_experiments(executor, run_id, pca_experiments(fitted, run_id))
    if not prior.get("EDA.CORRELATIONS", 0):
        write_correlations(executor, run_id, lab_correlations(fitted))
    if not prior.get("EDA.FINDINGS", 0):
        write_findings(executor, run_id, lab_findings(fitted), ids=_FINDING_IDS)
    if not prior.get("REGISTRY.QUERIES", 0):
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
    comment = render_comment(
        fitted,
        run_id=run_id,
        git_commit=commit or "unknown",
        row_counts=counts,
        drive_links={},
    )
    DOC_PATH.write_text(
        render_eda_record(
            fitted,
            run_id=run_id,
            git_commit=commit or "unknown",
            row_counts=counts,
            drive_links={},
        ),
        encoding="utf-8",
    )
    print(f"run_id: {run_id}")
    print(f"representation: {fitted.representation}")
    print(f"follow_up: {fitted.follow_up}")
    print("row_counts: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    for name in CHART_NAMES:
        path = ROOT / "artifacts" / "charts" / "114" / f"{name}.png"
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
            purpose="Stopped issue 114 before a fit",
            issue_number=114,
            agent_id="OH_LYME_ML_AGENT_SVC",
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=commit,
            source_environment="ONE_HEALTH_LYME_GAP_ATLAS_PROD",
            source_release_id=None,
            source_objects=_SOURCE_OBJECTS,
            input_snapshot_ts=snapshot,
            parameters={"spec": SPEC_ID, "reason": reason},
            random_seed=SEED,
            status="failed",
            notes="The predeclared release gate failed. No model was fit. No GRANT.",
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


def _complete(counts: dict[str, int]) -> bool:
    needed = (
        "REGISTRY.RUNS",
        "EDA.METRICS_LONG",
        "EDA.CORRELATIONS",
        "EDA.FINDINGS",
        "REGISTRY.QUERIES",
        "EXPERIMENTS.EXPERIMENTS",
        "EXPERIMENTS.MODEL_METRICS",
    )
    return all(counts.get(name, 0) > 0 for name in needed)


def _run_id() -> str:
    if RUN_PATH.exists():
        existing = RUN_PATH.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    run_id = f"114-cross-domain-{stamp}"
    RUN_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUN_PATH.write_text(run_id + "\n", encoding="utf-8")
    return run_id


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
        "EXPERIMENTS.EXPERIMENTS": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EXPERIMENTS.EXPERIMENTS WHERE RUN_ID = %s"
        ),
        "EXPERIMENTS.MODEL_METRICS": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EXPERIMENTS.MODEL_METRICS WHERE RUN_ID = %s"
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


class _LabExecutor:
    def __init__(self, connection: object) -> None:
        self._inner = CursorStatementExecutor(connection)

    def query(self, sql: str, params: tuple[object, ...] | None = None) -> list[tuple[object, ...]]:
        if params is None:
            return self._inner.query(sql)
        return self._inner.query(sql, params)

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self._inner.execute(sql, params)


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
        raise CrossDomainError("session has no cursor")
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
    raise CrossDomainError("snapshot timestamp is missing")


def _render(result: Analysis) -> dict[str, bytes]:
    sns.set_theme(style="whitegrid", font_scale=0.65)
    return {
        "redundancy-heatmap": _heatmap(result),
        "scree": _scree(result),
        "loading-plot": _loadings(result),
    }


def _heatmap(result: Analysis) -> bytes:
    labels = [_SHORT.get(name, name) for name in result.heatmap_labels]
    values = np.asarray(
        [[np.nan if value is None else value for value in row] for row in result.heatmap],
        dtype=float,
    )
    fig, ax = plt.subplots(figsize=(6.2, 4.6))
    if values.size:
        sns.heatmap(
            values,
            vmin=-1,
            vmax=1,
            cmap="vlag",
            annot=True,
            fmt=".2f",
            annot_kws={"size": 5},
            xticklabels=labels,
            yticklabels=labels,
            ax=ax,
            cbar=False,
        )
        ax.tick_params(axis="x", labelrotation=40, labelsize=6)
        ax.tick_params(axis="y", labelsize=6)
    ax.set_title("Cross-domain Spearman redundancy")
    fig.tight_layout()
    return _png(fig)


def _scree(result: Analysis) -> bytes:
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    for fit, marker in ((result.context_pca, "o"), (result.cross_pca, "s")):
        if not fit.shares:
            continue
        xs = list(range(1, len(fit.shares) + 1))
        ax.plot(xs, [float(share) for share in fit.shares], marker=marker, label=fit.name)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Component")
    ax.set_ylabel("Variance share")
    ax.set_title("PCA scree")
    ax.legend(fontsize=6)
    fig.tight_layout()
    return _png(fig)


def _loadings(result: Analysis) -> bytes:
    features = list(result.context_pca.features)
    fig, ax = plt.subplots(figsize=(5.8, 3.2))
    if features and result.context_pca.loadings:
        width = 0.35
        positions = np.arange(len(features))
        for offset, component in ((-width / 2, 1), (width / 2, 2)):
            heights = [_loading_value(result, feature, component) for feature in features]
            ax.bar(positions + offset, heights, width=width, label=f"PC{component}")
        ax.set_xticks(positions, [_SHORT.get(name, name) for name in features])
    ax.axhline(0, color="black", linewidth=0.6)
    ax.set_ylabel("Loading")
    ax.set_title("Three-feature PCA loadings")
    ax.legend(fontsize=6)
    fig.tight_layout()
    return _png(fig)


def _loading_value(result: Analysis, feature: str, component: int) -> float:
    for loading in result.context_pca.loadings:
        if loading.feature == feature and loading.component == component:
            return loading.value
    return 0.0


def _png(fig: plt.Figure) -> bytes:
    content = b""
    for dpi in (72, 60, 48):
        buffer = BytesIO()
        fig.savefig(buffer, format="png", dpi=dpi)
        content = buffer.getvalue()
        if len(content) <= _MAX_PNG_BYTES:
            plt.close(fig)
            return content
    plt.close(fig)
    if len(content) > _MAX_PNG_BYTES:
        raise CrossDomainError("a chart exceeds 40 KB")
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
