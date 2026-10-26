#!/usr/bin/env python3
"""Fit the issue 121 county correspondence map.

Reads the pinned PROD presentation counties into memory, writes ML Lab rows,
and saves aggregate PNG charts under artifacts/charts/121. County coordinates
are inserted only into the ML Lab coordinate table.

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_121_county_mca.py
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
from matplotlib.patches import Ellipse

from lyme_gap_atlas_ml.county_mca import (
    CHI2_95_DF2,
    SEED,
    SPEC_ID,
    Analysis,
    CountyMcaError,
    Gate,
    build_findings,
    chart_contributions,
    evaluate_gate,
    experiment_rows,
    fit_counties,
    lab_metrics,
    load_mca_queries,
    query_record,
    stopped_finding,
)
from lyme_gap_atlas_ml.county_mca_report import render_eda_record
from lyme_gap_atlas_ml.registry.artifacts import save_chart
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import write_findings, write_queries
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE, EdaRun, write_eda_results
from lyme_gap_atlas_ml.snowflake.mca_coordinates import RunAlreadyWritten, write_mca_tables
from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    ML_AGENT_ROLE,
    CursorStatementExecutor,
    StatementError,
    load_ml_agent_request,
    open_ml_agent_connection,
    redact_text,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "121_county_mca.sql"
DOC_PATH = ROOT / "docs" / "eda" / "121-county-contrasts.md"
RUN_PATH = ROOT / "artifacts" / "charts" / "121" / "run_id.txt"
CHART_NAMES = ("greenacre-scree", "category-pulls", "axis-map")
_MAX_PNG_BYTES = 40_000
_GROUP_COLORS = {
    "aligned": "#1b4f72",
    "double_gap": "#b9770e",
    "wider_gap": "#196f3d",
    "human_ahead": "#6c3483",
    "undocumented": "#7b241c",
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
    except (CountyMcaError, RunAlreadyWritten) as error:
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
    queries = load_mca_queries(SQL_PATH.read_text(encoding="utf-8"))
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
    fitted = fit_counties(county_rows, gate)
    print(
        f"fit_done: method={fitted.method_disposition} product={fitted.product_disposition}",
        flush=True,
    )
    for contrast in fitted.contrasts:
        print(contrast.sentence, flush=True)
    charts = _render(fitted)
    for name, content in charts.items():
        saved = save_chart(121, name, content)
        print(f"chart: {saved.file_name} bytes={len(content)} sha256={saved.sha256}")
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    written = write_mca_tables(
        executor, run_id, fitted.coordinates, experiment_rows(fitted, run_id)
    )
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose=(
                "Exploratory multiple correspondence map of county "
                "surveillance categories, issue 121"
            ),
            issue_number=121,
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
                "use_as_model_feature": False,
                "svi_scaled": gate.svi_scaled,
                "method": fitted.method_disposition,
                "product": fitted.product_disposition,
            },
            random_seed=SEED,
            status="succeeded",
            notes="Axes are an exploratory exhibit, not a risk surface and not a model feature.",
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
    DOC_PATH.write_text(
        render_eda_record(
            fitted,
            run_id=run_id,
            commit=commit or "unknown",
            charts=[
                f"`{name}.png` saved locally; Drive link follows upload" for name in CHART_NAMES
            ],
            row_counts=counts,
        ),
        encoding="utf-8",
    )
    print(f"run_id: {run_id}")
    print(f"granted: {written['granted']}")
    print("row_counts: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    for group in fitted.groups:
        print(
            f"group {group.name}: n={group.count} reference={group.reference} "
            f"centroid=({group.centroid_1:.4f}, {group.centroid_2:.4f})"
        )
    if fitted.stability is not None:
        stability = fitted.stability
        print(
            "stability: "
            f"spearman=({stability.spearman_1:.4f}, {stability.spearman_2:.4f}, "
            f"{stability.spearman_3:.4f}) "
            f"procrustes={stability.procrustes:.4f} stable={stability.stable}"
        )
    print(f"separation: {fitted.separation_ratio}")
    print("shares: " + ", ".join(f"{share:.4f}" for share in fitted.greenacre_shares[:3]))
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
            purpose="Stopped county correspondence map before the fit, issue 121",
            issue_number=121,
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
        [],
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


def _render(fitted: Analysis) -> dict[str, bytes]:
    sns.set_theme(style="whitegrid", font_scale=0.6)
    return {
        "greenacre-scree": _scree(fitted),
        "category-pulls": _pulls(fitted),
        "axis-map": _map(fitted),
    }


def _scree(fitted: Analysis) -> bytes:
    shares = [float(share) for share in fitted.greenacre_shares[:8]]
    fig, ax = plt.subplots(figsize=(4.4, 2.8))
    sns.barplot(x=list(range(1, len(shares) + 1)), y=shares, color="#1b4f72", ax=ax)
    ax.set_xlabel("Axis")
    ax.set_ylabel("Greenacre share")
    ax.set_title("Exploratory MCA inertia. Not a risk surface.")
    fig.tight_layout()
    return _png(fig)


def _pulls(fitted: Analysis) -> bytes:
    fig, axes = plt.subplots(1, 2, figsize=(6.4, 3.2))
    for axis, panel in zip((1, 2), axes, strict=True):
        rows = list(chart_contributions(fitted.contributions, axis))[:6]
        labels = [row.category_id.replace("_", " ") for row in rows]
        values = [row.contribution for row in rows]
        sns.barplot(y=labels, x=values, color="#1b4f72", ax=panel)
        panel.set_xlabel("Contribution")
        panel.set_ylabel("")
        panel.set_title(f"Axis {axis}")
    fig.suptitle("Categories that pull the first two axes", fontsize=8)
    fig.tight_layout()
    return _png(fig)


def _map(fitted: Analysis) -> bytes:
    coords = fitted.row_coordinates
    fig, ax = plt.subplots(figsize=(4.8, 3.6))
    hexbin = ax.hexbin(
        coords[:, 0],
        coords[:, 1],
        gridsize=10,
        mincnt=11,
        cmap="Blues",
        linewidths=0.2,
    )
    for count, (x_pos, y_pos) in zip(hexbin.get_array(), hexbin.get_offsets(), strict=False):
        if float(count) >= 11:
            ax.text(
                x_pos, y_pos, f"{int(count)}", ha="center", va="center", fontsize=4, color="#1c2833"
            )
    flags = _flags(fitted)
    for group in fitted.groups:
        mask = flags[group.name]
        _ellipse(ax, coords[mask, :2], _GROUP_COLORS[group.name])
        ax.scatter(
            [group.centroid_1],
            [group.centroid_2],
            s=28,
            color=_GROUP_COLORS[group.name],
            label=f"{group.name} n={group.count}",
            zorder=3,
        )
    ax.legend(fontsize=5, frameon=False, loc="best")
    ax.set_xlabel("Axis 1")
    ax.set_ylabel("Axis 2")
    ax.set_title("Group centroids on the MCA plane. Not a risk surface.")
    fig.tight_layout()
    return _png(fig)


def _flags(fitted: Analysis) -> dict[str, np.ndarray]:
    return {
        "aligned": np.array([row.in_aligned for row in fitted.coordinates]),
        "double_gap": np.array([row.in_double_gap for row in fitted.coordinates]),
        "wider_gap": np.array([row.in_wider_gap for row in fitted.coordinates]),
        "human_ahead": np.array([row.in_human_ahead for row in fitted.coordinates]),
        "undocumented": np.array([row.in_undocumented for row in fitted.coordinates]),
    }


def _ellipse(ax: plt.Axes, points: np.ndarray, color: str) -> None:
    if len(points) < 11:
        return
    center = points.mean(axis=0)
    covariance = np.cov(points, rowvar=False, ddof=1) / len(points)
    values, vectors = np.linalg.eigh(covariance)
    if np.any(values <= 1e-12):
        return
    order = np.argsort(values)[::-1]
    values = values[order]
    vectors = vectors[:, order]
    angle = float(np.degrees(np.arctan2(vectors[1, 0], vectors[0, 0])))
    width, height = 2.0 * np.sqrt(values * CHI2_95_DF2)
    ax.add_patch(
        Ellipse(
            xy=center,
            width=float(width),
            height=float(height),
            angle=angle,
            facecolor="none",
            edgecolor=color,
            linewidth=0.8,
        )
    )


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
    raise CountyMcaError("a chart exceeds 40 KB")


def _run_id() -> str:
    override = os.environ.get("MCA_RUN_ID", "").strip()
    if override:
        return override
    if RUN_PATH.exists():
        existing = RUN_PATH.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    run_id = f"121-county-contrasts-{stamp}"
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
        "EDA.COUNTY_MCA_COORDINATES_121": _count_sql("EDA.COUNTY_MCA_COORDINATES_121"),
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
        raise CountyMcaError("session has no cursor")
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
    raise CountyMcaError("snapshot timestamp is missing")


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
