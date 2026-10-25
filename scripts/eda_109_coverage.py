#!/usr/bin/env python3
"""Run the issue 109 county coverage audit.

Reads pinned PROD presentation aggregates, writes ML Lab rows, and saves three
PNG charts under artifacts/charts/109. Charts are git-ignored. Drive upload is
a separate step. The command is:

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_109_coverage.py

``--redraw-charts`` rebuilds the three PNGs from ML Lab metrics for the
existing run. It does not read PROD or insert another run.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

from lyme_gap_atlas_ml.coverage_audit import (
    HEATMAP_REGIONS,
    HEATMAP_SIGNALS,
    PINNED_RELEASE_ID,
    REFERENCE_COUNTIES,
    REFERENCE_NO_COUNTY_LINKED_RECORD,
    REFERENCE_PUBLISHED_HUMAN_FLOOR,
    REFERENCE_RELEASE_ID,
    SEED,
    SOURCE_OBJECTS,
    ChartFrames,
    CoverageAuditError,
    FetchedCoverage,
    RegionRow,
    assemble_coverage,
    check_integrity,
    heatmap_cell_label,
    load_queries,
)
from lyme_gap_atlas_ml.registry.artifacts import save_chart
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import (
    QueryRecord as LabQuery,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import (
    write_column_profiles,
    write_correlations,
    write_findings,
    write_missingness,
    write_queries,
)
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE, EdaRun, write_eda_results
from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    ML_AGENT_ROLE,
    CursorStatementExecutor,
    load_ml_agent_request,
    open_ml_agent_connection,
    redact_text,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "109_county_signal_coverage.sql"
HEATMAP_KEYS = (
    "HUMAN_UNDOC_N",
    "CASE_NULL_N",
    "INCIDENCE_NULL_N",
    "TICK_UNDOC_N",
    "SCAPULARIS_UNDOC_N",
    "PACIFICUS_UNDOC_N",
    "PATHOGEN_UNDOC_N",
    "SVI_NULL_N",
    "UNINSURED_PERCENT_NULL_N",
    "UNINSURED_PERCENTILE_NULL_N",
    "POPULATION_NULL_N",
    "RUCC_NULL_N",
)


CHART_RUN_ID = "109-coverage-missingness-20261025T2105Z"
_BAR_SIGNALS = ("HUMAN_STATUS", "TICK_STATUS", "BURGDORFERI_STATUS")
_BAR_STATUS_ORDER = (
    "published_count_floor",
    "no_county_linked_record",
    "Established",
    "Reported",
    "Present",
    "No records",
    "Unknown",
)


def main() -> int:
    if "--redraw-charts" in sys.argv:
        return redraw_charts()
    settings, _config = load_ml_agent_request(os.environ)
    if settings.role.upper() != ML_AGENT_ROLE or settings.database != ML_LAB_DATABASE:
        print("stopped: ML agent context is not the lab role and database")
        return 2
    token = os.environ.get("SNOWFLAKE_PAT", "")
    connection = open_ml_agent_connection(settings)
    try:
        return _run(connection)
    except CoverageAuditError as error:
        print(f"stopped: {error}")
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
    queries = load_queries(SQL_PATH.read_text(encoding="utf-8"))
    captured: list[tuple[str, str, int, int, str | None]] = []
    frames: dict[str, list[dict[str, object]]] = {}
    for name in queries:
        started = time.perf_counter()
        rows, query_id = _fetch(connection, queries[name])
        elapsed = int((time.perf_counter() - started) * 1000)
        captured.append((name, queries[name], len(rows), elapsed, query_id))
        frames[name] = rows
    snapshot = _timestamp(connection)
    fetched = _fetched(frames)
    check_integrity(fetched)
    assembled = assemble_coverage(fetched)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    run_id = f"109-coverage-missingness-{stamp}"
    charts = _render(assembled.charts)
    saved = {name: save_chart(109, name, content) for name, content in charts.items()}
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="County evidence coverage, comparability, and missingness for issue 109",
            issue_number=109,
            agent_id="OH_LYME_ML_AGENT_SVC",
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=commit,
            source_environment="ONE_HEALTH_LYME_GAP_ATLAS_PROD",
            source_release_id=PINNED_RELEASE_ID,
            source_objects=SOURCE_OBJECTS,
            input_snapshot_ts=snapshot,
            parameters={
                "spec": "109-county-evidence-coverage/v1.1",
                "reference_release": REFERENCE_RELEASE_ID,
                "reference_counties": REFERENCE_COUNTIES,
                "reference_published_human_floor": REFERENCE_PUBLISHED_HUMAN_FLOOR,
                "reference_no_county_record": REFERENCE_NO_COUNTY_LINKED_RECORD,
                "percentile_edges": [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99],
                "small_cell_minimum": 11,
                "seed_used": False,
            },
            random_seed=SEED,
            status="succeeded",
            notes="Aggregate coverage audit. County lists stay in Snowflake.",
        ),
        assembled.metrics,
    )
    missing = write_missingness(executor, run_id, assembled.missingness)
    profiles = write_column_profiles(executor, run_id, assembled.profiles)
    findings = write_findings(
        executor,
        run_id,
        assembled.findings,
        ids=tuple(f"10910910-0000-4000-8000-{index:012d}" for index in range(1, 6)),
    )
    queries_written = write_queries(
        executor,
        run_id,
        tuple(
            LabQuery(
                sql_text=sql,
                rows_returned=row_count,
                elapsed_ms=elapsed,
                snowflake_query_id=query_id,
            )
            for _name, sql, row_count, elapsed, query_id in captured
        ),
    )
    correlations = write_correlations(executor, run_id, ())
    print(f"run_id: {run_id}")
    print(f"disposition: {assembled.disposition}")
    print(f"git_commit: {commit}")
    print(f"metrics: {len(assembled.metrics)}")
    print(f"missingness: {missing.rows_written} suppressed {missing.rows_suppressed}")
    print(f"profiles: {profiles.rows_written} suppressed {profiles.rows_suppressed}")
    print(f"findings: {findings.rows_written}")
    print(f"queries: {queries_written.rows_written}")
    print(f"correlations: {correlations.rows_written}")
    for name, chart in saved.items():
        content = charts[name]
        print(f"chart: {name} bytes {len(content)} sha256 {chart.sha256}")
    for finding in assembled.findings:
        print(f"finding {finding.topic}: {finding.statement}")
    return 0


def _fetch(connection: object, sql: str) -> tuple[list[dict[str, object]], str | None]:
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        raise CoverageAuditError("session has no cursor")
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


def _timestamp(connection: object) -> datetime:
    rows, _query_id = _fetch(connection, "SELECT CURRENT_TIMESTAMP() AS SNAPSHOT_TS")
    value = rows[0]["SNAPSHOT_TS"]
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value
    raise CoverageAuditError("snapshot timestamp is missing")


def _fetched(frames: dict[str, list[dict[str, object]]]) -> FetchedCoverage:
    integrity = _one(frames, "atlas_integrity")
    release = _one(frames, "release_identity")
    numeric = _one(frames, "numeric_profile")
    unallocated = _one(frames, "state_unallocated_profile")
    geometry = _one(frames, "geometry_null")
    nlcd_total = _one(frames, "nlcd_county_total")
    climate = _one(frames, "climate_coverage")
    sources = tuple(_source(row) for row in frames["source_vintages"])
    levels = tuple(
        (_text(row["COLUMN_NAME"]), _optional_text(row.get("LEVEL")), _int(row["N"]))
        for row in frames["categorical_levels"]
    )
    regions = tuple(_region(row) for row in frames["region_undocumented"])
    states = tuple(
        (
            _text(row["STATE"]),
            _text(row["SIGNAL"]),
            _optional_text(row.get("STATUS")),
            _int(row["N"]),
        )
        for row in frames["state_status"]
    )
    joints = tuple(
        (
            _text(row["HUMAN_STATUS"]),
            _text(row["TICK_STATUS"]),
            _text(row["BURGDORFERI_STATUS"]),
            _int(row["N"]),
        )
        for row in frames["joint_partition"]
    )
    nlcd = tuple(
        (_text(row["MEASURE_ID"]), _int(row["ROW_N"]), _int(row["COUNTY_N"]))
        for row in frames["nlcd_coverage"]
    )
    climate_status = tuple(
        (
            _optional_text(row.get("COVERAGE_STATUS")),
            _optional_text(row.get("VALUE_STATE")),
            _int(row["ROW_N"]),
            _int(row["COUNTY_N"]),
        )
        for row in frames["climate_status"]
    )
    return FetchedCoverage(
        row_n=_int(integrity["ROW_N"]),
        fips_n=_int(integrity["FIPS_N"]),
        fips_pattern_n=_int(integrity["FIPS_PATTERN_N"]),
        release_n=_int(integrity["RELEASE_N"]),
        release_min=_text(integrity["RELEASE_MIN"]),
        release_max=_text(integrity["RELEASE_MAX"]),
        release_id=_text(release["RELEASE_ID"]),
        bundle_sha256=_text(release["BUNDLE_SHA256"]),
        schema_version=_text(release["SCHEMA_VERSION"]),
        methodology_version=_text(release["METHODOLOGY_VERSION"]),
        scope=_text(release["SCOPE"]),
        sources=sources,
        levels=levels,
        regions=regions,
        states=states,
        joints=joints,
        numeric={key: _number(value) for key, value in numeric.items()},
        unallocated={key: _number(value) for key, value in unallocated.items()},
        geometry_null_n=_int(geometry["GEOMETRY_NULL_N"]),
        nlcd_measures=nlcd,
        nlcd_counties=_int(nlcd_total["COUNTY_N"]),
        climate_row_n=_int(climate["ROW_N"]),
        climate_county_n=_int(climate["COUNTY_N"]),
        climate_measure_n=_int(climate["MEASURE_N"]),
        climate_day_n=_int(climate["DAY_N"]),
        climate_min=_day(climate.get("MIN_START")),
        climate_max=_day(climate.get("MAX_END")),
        climate_status=climate_status,
    )


def _source(row: Mapping[str, object]) -> tuple[str, str]:
    vintage = row.get("VINTAGE")
    label = "unspecified" if vintage is None else _text(vintage)
    return _text(row["SOURCE_KEY"]), label


def _region(row: Mapping[str, object]) -> RegionRow:
    return RegionRow(
        region=_text(row["REGION"]),
        total_n=_int(row["TOTAL_N"]),
        counts={key: _int(row[key]) for key in HEATMAP_KEYS},
    )


def _render(charts: ChartFrames) -> dict[str, bytes]:
    sns.set_theme(style="whitegrid", context="talk")
    return {
        "missingness-heatmap-signal-by-region": _heatmap(charts),
        "vintage-timeline": _vintage(charts),
        "coverage-bar": _bars(charts),
    }


def _heatmap(charts: ChartFrames) -> bytes:
    matrix = np.array(
        [[np.nan if value is None else value for value in row] for row in charts.heatmap_shares],
        dtype=float,
    )
    annot = np.array(
        [
            ["" if value is None else heatmap_cell_label(value) for value in row]
            for row in charts.heatmap_shares
        ]
    )
    fig, ax = plt.subplots(figsize=(5.6, 4.0))
    sns.heatmap(
        matrix,
        ax=ax,
        cmap="viridis",
        vmin=0,
        vmax=1,
        mask=np.isnan(matrix),
        annot=annot,
        fmt="",
        annot_kws={"size": 7},
        xticklabels=list(charts.heatmap_regions),
        yticklabels=[signal.replace("_", " ") for signal in charts.heatmap_signals],
        cbar_kws={"label": "Share", "shrink": 0.7},
        linewidths=0.3,
        linecolor="white",
    )
    for row_index, row in enumerate(charts.heatmap_shares):
        for column_index, value in enumerate(row):
            if value is not None:
                continue
            ax.add_patch(
                plt.Rectangle(
                    (column_index, row_index),
                    1,
                    1,
                    facecolor="#d9d9d9",
                    edgecolor="white",
                    linewidth=0.4,
                    zorder=2,
                )
            )
            ax.text(
                column_index + 0.5,
                row_index + 0.5,
                heatmap_cell_label(None),
                ha="center",
                va="center",
                color="#222222",
                fontsize=7,
                zorder=3,
            )
    ax.set_title("Counties without a positive documented signal")
    ax.set_xlabel("Census region")
    ax.set_ylabel("Signal")
    fig.text(
        0.01,
        0.01,
        "Cells marked <11 are suppressed. Unknown and No records are not negatives. "
        "A high western-blacklegged share is the species range.",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    return _png(fig, dpi=52)


def _vintage(charts: ChartFrames) -> bytes:
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    for index, (_label, start, end) in enumerate(charts.vintages):
        end_day = date.fromisoformat(end)
        start_day = end_day if start is None else date.fromisoformat(start)
        left = mdates.date2num(start_day)
        width = max(mdates.date2num(end_day) - left, 30)
        ax.barh(index, width, left=left, height=0.6, color="#1b9e77")
    ax.set_yticks(range(len(charts.vintages)))
    ax.set_yticklabels([label for label, _start, _end in charts.vintages])
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_title("Source vintage windows on the pinned release")
    ax.set_xlabel("Year")
    fig.tight_layout()
    return _png(fig)


def _bars(charts: ChartFrames) -> bytes:
    signals = [_signal_caption(signal) for signal, _status, _count in charts.bars]
    statuses = [_status_caption(status) for _signal, status, _count in charts.bars]
    counts = [count for _signal, _status, count in charts.bars]
    fig, ax = plt.subplots(figsize=(6.6, 3.8))
    sns.barplot(x=signals, y=counts, hue=statuses, ax=ax)
    ax.legend(
        title="Status",
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        borderaxespad=0,
        fontsize=7,
        title_fontsize=8,
        frameon=False,
    )
    ax.set_title("National county counts by surveillance status")
    ax.set_xlabel("Signal")
    ax.set_ylabel("Counties")
    fig.text(
        0.01,
        0.01,
        "Levels below 11 counties are omitted. Human floors are lower bounds.",
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.05, 0.74, 1))
    return _png(fig)


def _signal_caption(signal: str) -> str:
    captions = {
        "HUMAN_STATUS": "Human",
        "TICK_STATUS": "Tick",
        "BURGDORFERI_STATUS": "Pathogen",
    }
    return captions.get(signal, signal.replace("_", " "))


def _status_caption(status: str) -> str:
    captions = {
        "published_count_floor": "published floor",
        "no_county_linked_record": "no county-linked record",
    }
    return captions.get(status, status)


def redraw_charts() -> int:
    """Rebuild the three PNGs from lab metrics. Does not query PROD."""
    settings, _config = load_ml_agent_request(os.environ)
    if settings.role.upper() != ML_AGENT_ROLE or settings.database != ML_LAB_DATABASE:
        print("stopped: ML agent context is not the lab role and database")
        return 2
    token = os.environ.get("SNOWFLAKE_PAT", "")
    connection = open_ml_agent_connection(settings)
    try:
        charts = _charts_from_lab(connection)
        rendered = _render(charts)
        for name, content in rendered.items():
            saved = save_chart(109, name, content)
            print(f"chart: {name} bytes {len(content)} sha256 {saved.sha256}")
    except CoverageAuditError as error:
        print(f"stopped: {error}")
        return 2
    except Exception as error:
        print("stopped: " + redact_text(str(error), [token])[:400])
        return 2
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()
    return 0


def _charts_from_lab(connection: object) -> ChartFrames:
    rows, _query_id = _fetch(
        connection,
        f"""
        SELECT METRIC_NAME, GEOGRAPHY_ID, DIMENSIONS::VARCHAR AS DIMENSIONS,
               METRIC_VALUE, IS_SUPPRESSED
        FROM {ML_LAB_DATABASE}.EDA.METRICS_LONG
        WHERE RUN_ID = '{CHART_RUN_ID}'
          AND (
            (METRIC_NAME = 'undocumented_share' AND GEOGRAPHY_TYPE = 'census_region')
            OR (
              METRIC_NAME = 'status_county_count'
              AND GEOGRAPHY_TYPE = 'national'
              AND GEOGRAPHY_ID = 'US'
            )
          )
        """,
    )
    shares: dict[tuple[str, str], float | None] = {}
    bars: list[tuple[str, str, int]] = []
    for row in rows:
        dimensions = _dimensions(row["DIMENSIONS"])
        if row["METRIC_NAME"] == "undocumented_share":
            signal = _text(dimensions["signal"])
            region = _text(row["GEOGRAPHY_ID"])
            value = row["METRIC_VALUE"]
            shares[(signal, region)] = (
                None if _flag(row["IS_SUPPRESSED"]) or value is None else float(value)
            )
            continue
        if _flag(row["IS_SUPPRESSED"]):
            continue
        signal = _text(dimensions["signal"])
        status = _text(dimensions["status"])
        count = _metric_count(row["METRIC_VALUE"])
        if signal in _BAR_SIGNALS and (count == 0 or count >= 11):
            bars.append((signal, status, count))
    try:
        heatmap = tuple(
            tuple(shares[(signal, region)] for region in HEATMAP_REGIONS)
            for signal, _key in HEATMAP_SIGNALS
        )
    except KeyError as error:
        raise CoverageAuditError("heatmap metrics are incomplete") from error
    if any(len(row) != len(HEATMAP_REGIONS) for row in heatmap):
        raise CoverageAuditError("heatmap metrics are incomplete")
    if len(shares) != len(HEATMAP_SIGNALS) * len(HEATMAP_REGIONS):
        raise CoverageAuditError("heatmap metrics are incomplete")
    ordered = tuple(
        sorted(
            bars,
            key=lambda item: (
                _BAR_SIGNALS.index(item[0]),
                _BAR_STATUS_ORDER.index(item[1])
                if item[1] in _BAR_STATUS_ORDER
                else len(_BAR_STATUS_ORDER),
            ),
        )
    )
    return ChartFrames(
        heatmap_signals=tuple(signal for signal, _key in HEATMAP_SIGNALS),
        heatmap_regions=HEATMAP_REGIONS,
        heatmap_shares=heatmap,
        bars=ordered,
        vintages=_vintages(),
    )


def _vintages() -> tuple[tuple[str, str | None, str], ...]:
    return (
        ("Human surveillance", "2023-01-01", "2023-12-31"),
        ("Population, 2022 county layer", "2018-01-01", "2022-12-31"),
        ("Social vulnerability", "2018-01-01", "2022-12-31"),
        ("Rural-urban code", "2023-01-01", "2023-12-31"),
        ("Tick status, cumulative", None, "2025-12-31"),
        ("Pathogen status, cumulative", None, "2025-12-31"),
        ("Land cover vintage", "2025-01-01", "2025-12-31"),
        ("Climate county-day window", "2025-01-01", "2025-01-31"),
    )


def _dimensions(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return parsed
    raise CoverageAuditError("metric dimensions are missing")


def _flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise CoverageAuditError("suppression flag is missing")


def _metric_count(value: object) -> int:
    if isinstance(value, bool) or value is None:
        raise CoverageAuditError("metric count is missing")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)
    raise CoverageAuditError("metric count is missing")


def _png(fig: plt.Figure, *, dpi: int = 80) -> bytes:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi, pil_kwargs={"optimize": True})
    plt.close(fig)
    return buffer.getvalue()


def _one(frames: dict[str, list[dict[str, object]]], name: str) -> dict[str, object]:
    rows = frames[name]
    if len(rows) != 1:
        raise CoverageAuditError(f"{name} did not return one aggregate row")
    return rows[0]


def _coerce(value: object) -> object:
    if isinstance(value, Decimal):
        integral = value.to_integral_value()
        if value == integral:
            return int(integral)
        return float(value)
    return value


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CoverageAuditError("aggregate is not an integer")
    return value


def _number(value: object) -> object:
    if value is None or isinstance(value, (int, float)):
        return value
    raise CoverageAuditError("aggregate is not a number")


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CoverageAuditError("aggregate label is missing")
    return value.strip()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _text(value)


def _day(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise CoverageAuditError("period bound is not a date")


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


if __name__ == "__main__":
    raise SystemExit(main())
