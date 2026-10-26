#!/usr/bin/env python3
"""Run the issue 117 visual diagnostics.

Reads the pinned presentation cohort and January climate aggregates, writes ML
Lab aggregate rows, and saves PNG charts under artifacts/charts/117. County rows
are not written to a file. A second invocation reuses an existing run id and
does not insert again.

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn \\
        python scripts/eda_117_visual_diagnostics.py
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
from matplotlib.patches import RegularPolygon
from PIL import Image

from lyme_gap_atlas_ml.cross_domain import CROSS_FEATURES, prepare_counties, release_matches
from lyme_gap_atlas_ml.registry.artifacts import save_chart
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import (
    QueryRecord,
    write_correlations,
    write_findings,
    write_missingness,
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
from lyme_gap_atlas_ml.visual_diagnostics import (
    HEX_SIZE,
    SEED,
    SOURCE_OBJECTS,
    SPEC_ID,
    TAVG_MAX,
    TAVG_MIN,
    Analysis,
    HexCell,
    VisualDiagnosticsError,
    analyze,
    lab_correlations,
    lab_findings,
    lab_metrics,
    lab_missingness,
    load_visual_queries,
)
from lyme_gap_atlas_ml.visual_diagnostics_report import render_comment, render_eda_record

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "117_visual_diagnostics.sql"
DOC_PATH = ROOT / "docs" / "eda" / "117-visual-diagnostics.md"
COMMENT_PATH = ROOT / "artifacts" / "charts" / "117" / "comment.md"
RUN_PATH = ROOT / "outputs" / "117-run-id.txt"
_MAX_PNG_BYTES = 40_000
_SHORT = {
    "log_population": "log pop",
    "svi_percentile": "SVI",
    "uninsured_percentile": "uninsured",
    "rucc_2023": "RUCC",
    "human_published": "human floor",
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
    except VisualDiagnosticsError as error:
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
    if counts.get("REGISTRY.RUNS", 0):
        print(f"run_id={run_id}")
        print("reused_run=True")
        for name, count in counts.items():
            print(f"rows {name}={count}")
        return 0
    queries = load_visual_queries(SQL_PATH.read_text(encoding="utf-8"))
    captured: list[tuple[str, str, int, int, str | None]] = []
    release_rows, _meta = _capture(connection, "release_identity", queries, captured)
    release_matches(release_rows[0])
    cohort_rows, _cohort = _capture(connection, "cohort_rows", queries, captured)
    climate_rows, _climate = _capture(connection, "climate_means", queries, captured)
    state_rows, _state = _capture(connection, "state_day_temperature", queries, captured)
    counties = prepare_counties(cohort_rows, release_id=str(release_rows[0]["RELEASE_ID"]))
    result = analyze(counties, climate_rows, state_rows)
    charts = _render(result)
    saved = {name: save_chart(117, name, content) for name, content in charts.items()}
    snapshot = _timestamp(connection, captured)
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    _persist(
        executor,
        run_id,
        branch,
        commit,
        snapshot,
        captured,
        result,
        str(release_rows[0]["RELEASE_ID"]),
    )
    counts = _row_counts(connection, run_id)
    drive_lines = "pending upload"
    _write_docs(result, run_id, commit or "unknown", counts, drive_lines)
    print(f"run_id={run_id}")
    print(f"disposition={result.disposition}")
    print("reused_run=False")
    for name, chart in saved.items():
        print(f"chart={name} bytes={chart.path.stat().st_size} sha256={chart.sha256}")
    for name, count in counts.items():
        print(f"rows {name}={count}")
    return 0


def _persist(
    executor: _LabExecutor,
    run_id: str,
    branch: str | None,
    commit: str | None,
    snapshot: datetime,
    captured: list[tuple[str, str, int, int, str | None]],
    result: Analysis,
    release_id: str,
) -> None:
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="Visual diagnostics for issue 117",
            issue_number=117,
            agent_id="OH_LYME_ML_AGENT_SVC",
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=commit,
            source_environment="ONE_HEALTH_LYME_GAP_ATLAS_PROD",
            source_release_id=release_id,
            source_objects=SOURCE_OBJECTS,
            input_snapshot_ts=snapshot,
            parameters={
                "spec": SPEC_ID,
                "seed": SEED,
                "disposition": result.disposition,
                "importance": "not_estimable",
                "linkage": "average linkage on 1 minus absolute Spearman",
            },
            random_seed=SEED,
            status="succeeded" if result.disposition != "stop" else "inconclusive",
            notes="Aggregate visuals. No new table and no GRANT. County rows stay in memory.",
        ),
        lab_metrics(result),
    )
    write_correlations(executor, run_id, lab_correlations(result))
    write_missingness(executor, run_id, lab_missingness(result))
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


def _render(result: Analysis) -> dict[str, bytes]:
    sns.set_theme(style="white", font_scale=0.55)
    charts = {
        "climate-hexbin": _hex_chart(result),
        "correlation-heatmap": _heat_chart(result),
        "state-day-temperature": _time_chart(result),
    }
    for name, content in charts.items():
        if len(content) > _MAX_PNG_BYTES:
            raise VisualDiagnosticsError(f"{name} exceeds 40 KB")
    return charts


def _hex_chart(result: Analysis) -> bytes:
    fig, axes = plt.subplots(1, 2, figsize=(6.2, 3.2))
    panels = (
        (axes[0], result.hexbin.published_cells, "Published floor"),
        (axes[1], result.hexbin.unpublished_cells, "No county-linked record"),
    )
    for axis, cells, title in panels:
        _draw_hexes(axis, cells)
        axis.set_title(title, fontsize=8)
        axis.set_xlabel("January mean temperature (C)")
        axis.set_ylabel("January mean precipitation (mm/day)")
    fig.suptitle(
        f"January 2025 county means, hex n at least 11. Cohort n={result.hexbin.n}.",
        fontsize=8,
    )
    fig.tight_layout()
    return _png(fig)


def _draw_hexes(axis: plt.Axes, cells: Sequence[HexCell]) -> None:
    shown = [cell for cell in cells if cell.n >= 11]
    if not shown:
        axis.set_axis_off()
        axis.text(0.5, 0.5, "No publishable hex", ha="center", transform=axis.transAxes)
        return
    top = max(cell.n for cell in shown)
    for cell in shown:
        color = plt.get_cmap("Blues")(0.25 + 0.75 * cell.n / top)
        axis.add_patch(
            RegularPolygon(
                (cell.center_t, cell.center_p),
                numVertices=6,
                radius=HEX_SIZE * (TAVG_MAX - TAVG_MIN) * 0.55,
                orientation=np.pi / 6,
                facecolor=color,
                edgecolor="white",
                linewidth=0.2,
            )
        )
    axis.set_xlim(TAVG_MIN, TAVG_MAX)
    axis.set_ylim(0, 12)
    axis.tick_params(labelsize=6)


def _heat_chart(result: Analysis) -> bytes:
    order = result.heatmap.order
    index = {name: position for position, name in enumerate(CROSS_FEATURES)}
    positions = [index[name] for name in order]
    rho = np.asarray(result.heatmap.rho, dtype=float)[np.ix_(positions, positions)]
    pair_n = np.asarray(result.heatmap.pair_n)[np.ix_(positions, positions)]
    labels = [_SHORT.get(name, name) for name in order]
    annot = np.empty(rho.shape, dtype=object)
    for row in range(rho.shape[0]):
        for col in range(rho.shape[1]):
            value = rho[row, col]
            count = int(pair_n[row, col])
            if row == col or not np.isfinite(value) or count < 11:
                annot[row, col] = ""
                rho[row, col] = np.nan
            else:
                annot[row, col] = f"{value:.2f}\n{count}"
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    sns.heatmap(
        rho,
        vmin=-1,
        vmax=1,
        cmap="vlag",
        annot=annot,
        fmt="",
        annot_kws={"size": 4.5},
        xticklabels=labels,
        yticklabels=labels,
        ax=ax,
        cbar=False,
        linewidths=0.2,
        linecolor="white",
    )
    ax.tick_params(axis="x", labelrotation=40, labelsize=6)
    ax.tick_params(axis="y", labelsize=6)
    ax.set_title("Spearman, average linkage. Cell is rho and pairwise n.", fontsize=8)
    fig.tight_layout()
    return _png(fig)


def _time_chart(result: Analysis) -> bytes:
    rows = [row for row in result.time.rows if row.n >= 11]
    fig, axes = plt.subplots(
        2,
        1,
        figsize=(6.4, 4.6),
        gridspec_kw={"height_ratios": [3.2, 1.1]},
    )
    if rows:
        states = sorted(
            {row.state for row in rows}, key=lambda state: (_region(result, state), state)
        )
        days = sorted({row.day for row in rows})
        grid = np.full((len(states), len(days)), np.nan)
        lookup = {(row.state, row.day): row.mean for row in rows}
        for i, state in enumerate(states):
            for j, day in enumerate(days):
                if (state, day) in lookup:
                    grid[i, j] = lookup[(state, day)]
        sns.heatmap(
            grid,
            cmap="coolwarm",
            xticklabels=[day.strftime("%d") for day in days],
            yticklabels=states,
            ax=axes[0],
            cbar=False,
        )
        axes[0].tick_params(axis="x", labelsize=5)
        axes[0].tick_params(axis="y", labelsize=4)
        axes[0].set_title("State mean January 2025 temperature (C). n<11 omitted.", fontsize=8)
        axes[0].set_xlabel("Day")
    else:
        axes[0].set_axis_off()
    if result.time.national:
        axes[1].plot(
            [day for day, _mean, _count in result.time.national],
            [mean for _day, mean, _count in result.time.national],
            color="black",
            linewidth=1,
        )
    axes[1].set_title("National mean of publishable states", fontsize=8)
    axes[1].tick_params(labelsize=6)
    axes[1].set_ylabel("C")
    fig.tight_layout()
    return _png(fig)


def _region(result: Analysis, state: str) -> str:
    for row in result.time.rows:
        if row.state == state:
            return row.region
    return state


def _png(fig: plt.Figure) -> bytes:
    content = b""
    for dpi in (72, 60, 50, 40):
        buffer = BytesIO()
        fig.savefig(buffer, format="png", dpi=dpi)
        content = _quantize(buffer.getvalue())
        if len(content) <= _MAX_PNG_BYTES:
            plt.close(fig)
            return content
    plt.close(fig)
    return content


def _quantize(content: bytes) -> bytes:
    image = Image.open(BytesIO(content)).convert("P", palette=Image.Palette.ADAPTIVE, colors=24)
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _write_docs(
    result: Analysis,
    run_id: str,
    commit: str,
    counts: Mapping[str, int],
    drive_lines: str,
) -> None:
    DOC_PATH.write_text(
        render_eda_record(
            result,
            run_id=run_id,
            git_commit=commit,
            row_counts=counts,
            drive_lines=drive_lines,
        ),
        encoding="utf-8",
    )
    COMMENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMMENT_PATH.write_text(
        render_comment(
            result,
            run_id=run_id,
            git_commit=commit,
            row_counts=counts,
            drive_lines=drive_lines,
        ),
        encoding="utf-8",
    )


def _run_id() -> str:
    if RUN_PATH.exists():
        existing = RUN_PATH.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    run_id = f"117-visual-diagnostics-{stamp}"
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
        "EDA.MISSINGNESS": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EDA.MISSINGNESS WHERE RUN_ID = %s"
        ),
        "EDA.FINDINGS": f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EDA.FINDINGS WHERE RUN_ID = %s",
        "REGISTRY.QUERIES": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.REGISTRY.QUERIES WHERE RUN_ID = %s"
        ),
        "EXPERIMENTS.EXPERIMENTS": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EXPERIMENTS.EXPERIMENTS WHERE RUN_ID = %s"
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
        raise VisualDiagnosticsError("session has no cursor")
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
    raise VisualDiagnosticsError("snapshot timestamp is missing")


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
