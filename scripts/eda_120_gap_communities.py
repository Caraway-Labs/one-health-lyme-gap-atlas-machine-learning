#!/usr/bin/env python3
"""Fit issue 120 community types inside the established-tick gap.

Reads the pinned PROD presentation counties into memory, writes ML Lab rows,
and saves aggregate PNG charts under artifacts/charts/120. County assignments
are inserted only into the ML Lab assignment table.

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_120_gap_communities.py
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

from lyme_gap_atlas_ml.gap_communities import (
    SEED,
    SPEC_ID,
    Analysis,
    Frequency,
    GapCommunityError,
    Gate,
    build_findings,
    evaluate_gate,
    experiment_rows,
    fit_cohort,
    lab_metrics,
    load_gap_queries,
    query_record,
    stopped_finding,
)
from lyme_gap_atlas_ml.gap_community_report import render_comment, render_eda_record
from lyme_gap_atlas_ml.registry.artifacts import save_chart
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import write_findings, write_queries
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE, EdaRun, write_eda_results
from lyme_gap_atlas_ml.snowflake.gap_community_assignments import (
    RunAlreadyWritten,
    write_assignment_tables,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    ML_AGENT_ROLE,
    CursorStatementExecutor,
    StatementError,
    load_ml_agent_request,
    open_ml_agent_connection,
    redact_text,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "120_gap_communities.sql"
DOC_PATH = ROOT / "docs" / "eda" / "120-gap-communities.md"
CHART_DIR = ROOT / "artifacts" / "charts" / "120"
RUN_PATH = CHART_DIR / "run_id.txt"
COMMENT_PATH = CHART_DIR / "comment.md"
CHART_NAMES = ("cohort-distributions", "cluster-sizes", "numeric-medians")
_MAX_PNG_BYTES = 40_000
_SMALL = 11


def main() -> int:
    settings, _config = load_ml_agent_request(os.environ)
    if settings.role.upper() != ML_AGENT_ROLE or settings.database != ML_LAB_DATABASE:
        print("stopped: ML agent context is not the lab role and database")
        return 2
    token = os.environ.get("SNOWFLAKE_PAT", "")
    connection = open_ml_agent_connection(settings)
    try:
        return _run(connection)
    except (GapCommunityError, RunAlreadyWritten) as error:
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
    executor.execute("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 600")
    queries = load_gap_queries(SQL_PATH.read_text(encoding="utf-8"))
    run_id = _run_id()
    if _run_exists(connection, run_id):
        print(f"run_id: {run_id}")
        print("reuse: lab rows already exist for this run id")
        return 0
    captured: list[tuple[str, str, int, int, str | None]] = []
    release_rows, _meta = _capture(connection, "release_identity", queries, captured)
    county_rows, _county_meta = _capture(connection, "county_rows", queries, captured)
    for row in county_rows:
        fips = row.get("FIPS")
        if isinstance(fips, int):
            row["FIPS"] = f"{fips:05d}"
    gate = evaluate_gate(release_rows[0], county_rows)
    snapshot = _timestamp(connection, captured)
    print(
        f"gate_ok: {gate.ok} counties={gate.county_n} "
        f"published={gate.published_n} unlinked={gate.unlinked_n}",
        flush=True,
    )
    if not gate.ok:
        _write_stop(executor, connection, run_id, gate, captured, snapshot)
        print(f"run_id: {run_id}")
        print("disposition: stop")
        print("reasons: " + "; ".join(gate.reasons))
        return 2
    print("fit_start", flush=True)
    fitted = fit_cohort(county_rows, gate)
    print(
        f"fit_done: method={fitted.method_disposition} product={fitted.product_disposition} "
        f"cohort={fitted.cohort_n} double_gap={fitted.double_gap_n}",
        flush=True,
    )
    charts = _render(fitted)
    for name, content in charts.items():
        saved = save_chart(120, name, content)
        print(f"chart: {saved.file_name} bytes={len(content)} sha256={saved.sha256}")
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    counts_preview = {
        "assignments": len(fitted.assignments),
        "experiments": len(fitted.candidates),
    }
    _write_narratives(
        fitted,
        run_id=run_id,
        commit=commit or "unknown",
        charts=[f"`{name}.png` saved locally; Drive link follows upload" for name in CHART_NAMES],
        row_counts=counts_preview,
        grant=False,
    )
    written = write_assignment_tables(
        executor, run_id, fitted.assignments, experiment_rows(fitted, run_id)
    )
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="K-prototypes community types inside the established-tick gap, issue 120",
            issue_number=120,
            agent_id="OH_LYME_ML_AGENT_SVC",
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=commit,
            source_environment="ONE_HEALTH_LYME_GAP_ATLAS_PROD",
            source_release_id=gate.release_id,
            source_objects=(
                "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
                "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
            ),
            input_snapshot_ts=snapshot,
            parameters={
                "spec": SPEC_ID,
                "seed": SEED,
                "alt_seed": 1202027,
                "bootstrap_seed": 1202028,
                "gamma": fitted.gamma,
                "selected_k": None if fitted.selected is None else fitted.selected.k,
                "use_as_model_feature": False,
                "method": fitted.method_disposition,
                "product": fitted.product_disposition,
            },
            random_seed=SEED,
            status="succeeded",
            notes=(
                "Cluster membership is a descriptive partition, not disease risk and not a score."
            ),
        ),
        lab_metrics(fitted),
    )
    write_findings(executor, run_id, build_findings(fitted))
    write_queries(
        executor,
        run_id,
        [
            query_record(name, sql, rows, elapsed, query_id)
            for name, sql, rows, elapsed, query_id in captured
        ],
    )
    counts = _counts(connection, run_id)
    _write_narratives(
        fitted,
        run_id=run_id,
        commit=commit or "unknown",
        charts=[f"`{name}.png` saved locally; Drive link follows upload" for name in CHART_NAMES],
        row_counts=counts,
        grant=bool(written["granted"]),
    )
    print(f"run_id: {run_id}")
    print(f"granted: {written['granted']}")
    print("row_counts: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    for profile in fitted.profiles:
        print(
            f"type {profile.cluster_id}: n={profile.n} people={profile.population_total:.0f} "
            f"double_gap={profile.double_gap_n}"
        )
    return 0


def _write_stop(
    executor: _LabExecutor,
    connection: object,
    run_id: str,
    gate: Gate,
    captured: list[tuple[str, str, int, int, str | None]],
    snapshot: datetime,
) -> None:
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="Stopped established-tick gap communities before the fit, issue 120",
            issue_number=120,
            agent_id="OH_LYME_ML_AGENT_SVC",
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=commit,
            source_environment="ONE_HEALTH_LYME_GAP_ATLAS_PROD",
            source_release_id=gate.release_id or None,
            source_objects=(
                "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
                "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
            ),
            input_snapshot_ts=snapshot,
            parameters={"spec": SPEC_ID, "seed": SEED},
            random_seed=SEED,
            status="failed",
            notes="; ".join(gate.reasons)[:500],
        ),
        (),
    )
    write_findings(executor, run_id, [stopped_finding(gate)])
    write_queries(
        executor,
        run_id,
        [
            query_record(name, sql, rows, elapsed, query_id)
            for name, sql, rows, elapsed, query_id in captured
        ],
    )
    del connection


def _write_narratives(
    fitted: Analysis,
    *,
    run_id: str,
    commit: str,
    charts: list[str],
    row_counts: dict[str, int],
    grant: bool,
) -> None:
    comment = render_comment(
        fitted,
        run_id=run_id,
        commit=commit,
        charts=charts,
        row_counts=row_counts,
        grant=grant,
    )
    record = render_eda_record(
        fitted,
        run_id=run_id,
        commit=commit,
        charts=charts,
        row_counts=row_counts,
        grant=grant,
    )
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    COMMENT_PATH.write_text(comment, encoding="utf-8")
    DOC_PATH.write_text(record, encoding="utf-8")


def _render(fitted: Analysis) -> dict[str, bytes]:
    sns.set_theme(style="whitegrid", font_scale=0.55)
    return {
        "cohort-distributions": _distributions(fitted),
        "cluster-sizes": _sizes(fitted),
        "numeric-medians": _medians(fitted),
    }


def _distributions(fitted: Analysis) -> bytes:
    fig, axes = plt.subplots(2, 2, figsize=(6.2, 4.2))
    _bars(axes[0, 0], fitted.population_bins, "Population band")
    _bars(axes[0, 1], fitted.svi_bins, "Vulnerability percentile")
    _bars(axes[1, 0], fitted.uninsured_bins, "Uninsured percentile")
    _bars(axes[1, 1], fitted.rucc_bins, "Rural-urban code")
    fig.suptitle("Established-tick gap before clustering. Not a risk score.", fontsize=8)
    fig.tight_layout()
    return _png(fig)


def _sizes(fitted: Analysis) -> bytes:
    profiles = [profile for profile in fitted.profiles if profile.n >= _SMALL]
    fig, ax = plt.subplots(figsize=(4.6, 2.8))
    labels = [str(profile.cluster_id) for profile in profiles]
    values = [profile.population_total / 1_000_000 for profile in profiles]
    sns.barplot(x=labels, y=values, color="#1b4f72", ax=ax)
    ax.set_xlabel("Community type")
    ax.set_ylabel("People, millions")
    ax.set_title("People in each type. Not a risk score.")
    fig.tight_layout()
    return _png(fig)


def _medians(fitted: Analysis) -> bytes:
    profiles = [profile for profile in fitted.profiles if profile.n >= _SMALL]
    fig, ax = plt.subplots(figsize=(4.8, 2.8))
    labels: list[str] = []
    values: list[float] = []
    hues: list[str] = []
    for profile in profiles:
        for name, value in (
            ("vulnerability", profile.median_svi),
            ("uninsured", profile.median_uninsured),
        ):
            labels.append(str(profile.cluster_id))
            values.append(value)
            hues.append(name)
    sns.barplot(x=labels, y=values, hue=hues, ax=ax)
    ax.set_xlabel("Community type")
    ax.set_ylabel("Median percentile")
    ax.set_ylim(0, 1)
    ax.legend(fontsize=6, frameon=False, title="")
    ax.set_title("Median percentiles by type. Not a risk score.")
    fig.tight_layout()
    return _png(fig)


def _bars(ax: plt.Axes, bins: Sequence[Frequency], title: str) -> None:
    kept = [item for item in bins if item.n >= _SMALL]
    sns.barplot(
        y=[item.label.replace("_", " ") for item in kept],
        x=[item.n for item in kept],
        color="#1b4f72",
        ax=ax,
    )
    ax.set_xlabel("Counties")
    ax.set_ylabel("")
    ax.set_title(title)


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
    raise GapCommunityError("a chart exceeds 40 KB")


def _run_id() -> str:
    override = os.environ.get("GAP_COMMUNITY_RUN_ID", "").strip()
    if override:
        return override
    if RUN_PATH.exists():
        existing = RUN_PATH.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    run_id = f"120-gap-communities-{stamp}"
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
    return bool(row and int(row[0]) > 0)


def _count_sql(table: str) -> str:
    return f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.{table} WHERE RUN_ID = %s"


def _counts(connection: object, run_id: str) -> dict[str, int]:
    statements = {
        "REGISTRY.RUNS": _count_sql("REGISTRY.RUNS"),
        "EDA.METRICS_LONG": _count_sql("EDA.METRICS_LONG"),
        "EDA.FINDINGS": _count_sql("EDA.FINDINGS"),
        "EDA.GAP_COMMUNITY_ASSIGNMENTS_120": _count_sql("EDA.GAP_COMMUNITY_ASSIGNMENTS_120"),
        "EXPERIMENTS.EXPERIMENTS": _count_sql("EXPERIMENTS.EXPERIMENTS"),
        "EXPERIMENTS.MODEL_METRICS": _count_sql("EXPERIMENTS.MODEL_METRICS"),
        "REGISTRY.QUERIES": _count_sql("REGISTRY.QUERIES"),
    }
    counts: dict[str, int] = {}
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        return counts
    with cursor_factory() as cursor:
        for name, sql in statements.items():
            cursor.execute(sql, (run_id,))
            row = cursor.fetchone()
            counts[name] = int(row[0]) if row and row[0] is not None else 0
    return counts


class _LabExecutor:
    def __init__(self, connection: object) -> None:
        self._inner = CursorStatementExecutor(connection)
        self._connection = connection

    def query(self, sql: str, params: tuple[object, ...] | None = None) -> list[tuple[object, ...]]:
        if params is None:
            return self._inner.query(sql)
        return self._inner.query(sql, params)

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self._inner.execute(sql, params)

    def executemany(self, sql: str, rows: Sequence[tuple[object, ...]]) -> None:
        cursor_factory = getattr(self._connection, "cursor", None)
        if not callable(cursor_factory):
            raise StatementError(permission_denied=False)
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
        raise GapCommunityError("session has no cursor")
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
    raise GapCommunityError("snapshot timestamp is missing")


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
