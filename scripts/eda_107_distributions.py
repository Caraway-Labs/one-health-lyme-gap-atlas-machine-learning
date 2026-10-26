#!/usr/bin/env python3
"""Run the issue 107 county distribution profile.

Reads the pinned PROD presentation cohort into memory, writes ML Lab rows, and
saves PNG charts under artifacts/charts/107. County rows are not written to a
file. A second invocation reuses an existing run id and does not insert again.

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_107_distributions.py
"""

from __future__ import annotations

import hashlib
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
from lyme_gap_atlas_ml.county_distribution_report import render_comment, render_eda_record
from lyme_gap_atlas_ml.county_distributions import (
    HUMAN_PUBLISHED,
    SEED,
    SOURCE_OBJECTS,
    SPEC_ID,
    Analysis,
    AtlasCounty,
    DistributionError,
    SignalGroup,
    TierCounty,
    analyze,
    box_groups,
    chart_bins,
    climate_groups_from_profile,
    climate_mean_groups,
    climate_means_sql,
    climate_profile_sql,
    column_profiles,
    findings,
    lab_metrics,
    release_matches,
)
from lyme_gap_atlas_ml.registry.artifacts import save_chart
from lyme_gap_atlas_ml.snowflake.county_adjacency import (
    ADJACENCY_TABLE,
    COUNT_ADJACENCY_SQL,
    CREATE_ADJACENCY_SQL,
    GRANT_ADJACENCY_SQL,
    INSERT_ADJACENCY_SQL,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import (
    ColumnProfileRecord,
    FindingRecord,
    QueryRecord,
    write_column_profiles,
    write_findings,
    write_queries,
)
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaMetric,
    EdaRun,
    write_eda_results,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import (
    ML_AGENT_ROLE,
    CursorStatementExecutor,
    load_ml_agent_request,
    open_ml_agent_connection,
    redact_text,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "107_county_distributions.sql"
DOC_PATH = ROOT / "docs" / "eda" / "107-county-distributions.md"
RUN_PATH = ROOT / "outputs" / "107-run-id.txt"
_MAX_PNG_BYTES = 40_000
QUERY_NAMES = (
    "release_identity",
    "source_vintages",
    "atlas_rows",
    "tier_rows",
    "climate_status",
    "nlcd_counties",
)


def main() -> int:
    settings, _config = load_ml_agent_request(os.environ)
    if settings.role.upper() != ML_AGENT_ROLE or settings.database != ML_LAB_DATABASE:
        print("stopped: ML agent context is not the lab role and database")
        return 2
    token = os.environ.get("SNOWFLAKE_PAT", "")
    connection = open_ml_agent_connection(settings)
    try:
        return _run(connection)
    except DistributionError as error:
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
    queries = load_marked_queries(SQL_PATH.read_text(encoding="utf-8"), QUERY_NAMES)
    captured: list[tuple[str, str, int, int, str | None]] = []
    release_rows = _capture(connection, "release_identity", queries, captured)
    if len(release_rows) != 1 or not release_matches(release_rows[0]):
        print("stopped: release pin does not match the frozen specification")
        return 2
    _capture(connection, "source_vintages", queries, captured)
    atlas_rows = _capture(connection, "atlas_rows", queries, captured)
    tier_rows = _capture(connection, "tier_rows", queries, captured)
    _capture(connection, "climate_status", queries, captured)
    profile_rows, mean_rows, climate_note = _climate_frames(connection, captured)
    nlcd_rows = _capture(connection, "nlcd_counties", queries, captured)
    nlcd_counties = int(nlcd_rows[0]["COUNTY_N"]) if nlcd_rows else 0
    counties = tuple(_county(row) for row in atlas_rows)
    tiers = tuple(_tier(row) for row in tier_rows)
    day_groups = climate_groups_from_profile(profile_rows)
    mean_groups = climate_mean_groups(mean_rows, counties)
    result = analyze(
        counties,
        tiers,
        (),
        nlcd_counties=nlcd_counties,
        climate_day_groups=day_groups,
        climate_mean_groups=mean_groups,
        climate_row_count=sum(group.summary.n for group in day_groups),
    )
    if len({county.fips for county in counties}) != 3144 or len(counties) != 3144:
        print("stopped: FIPS gate failed")
        return 2
    metrics = lab_metrics(result)
    profiles = column_profiles(result)
    found = findings(result)
    charts = _render(result, counties)
    for name, content in charts.items():
        save_chart(107, name, content)
    existing = _existing_run(connection)
    run_id = existing or _stored_run_id() or _new_run_id()
    _store_run_id(run_id)
    commit = _git("rev-parse", "HEAD")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if existing is None:
        _persist(executor, run_id, branch, commit, captured, result, metrics, profiles, found)
    adjacency_note = _adjacency(connection, run_id)
    if climate_note:
        adjacency_note = f"{adjacency_note}. {climate_note}"
    counts = _row_counts(connection, run_id)
    _write_docs(result, run_id, commit or "unknown", counts, adjacency_note)
    print(f"run_id={run_id}")
    print(f"disposition={result.disposition}")
    print(f"reused_run={existing is not None}")
    print(f"metrics={len(metrics)}")
    print(f"published={result.published}")
    print(f"tiers={result.tier.high},{result.tier.medium},{result.tier.low}")
    print(f"adjacency={adjacency_note}")
    for name in charts:
        path = ROOT / "artifacts" / "charts" / "107" / f"{name}.png"
        print(f"chart={name} bytes={path.stat().st_size} sha256={_sha(path)}")
    for name, count in counts.items():
        print(f"rows {name}={count}")
    return 0


def _persist(
    executor: CursorStatementExecutor,
    run_id: str,
    branch: str | None,
    commit: str | None,
    captured: list[tuple[str, str, int, int, str | None]],
    result: Analysis,
    metrics: Sequence[EdaMetric],
    profiles: Sequence[ColumnProfileRecord],
    found: Sequence[FindingRecord],
) -> None:
    write_eda_results(
        executor,
        EdaRun(
            run_id=run_id,
            purpose="County distributions, variability, and tier boundaries for issue 107",
            issue_number=107,
            agent_id="OH_LYME_ML_AGENT_SVC",
            git_repo="Caraway-Labs/one-health-lyme-gap-atlas-machine-learning",
            git_branch=branch,
            git_commit=commit,
            source_environment="ONE_HEALTH_LYME_GAP_ATLAS_PROD",
            source_release_id="governed-2026-10-15-january-climate-prod",
            source_objects=SOURCE_OBJECTS,
            input_snapshot_ts=datetime.now(UTC),
            parameters={
                "spec": SPEC_ID,
                "seed": SEED,
                "tier_release": "governed-2026-09-18-unknown-coverage",
                "weighting": "county_and_population",
                "published": result.published,
                "high": result.tier.high,
                "medium": result.tier.medium,
                "low": result.tier.low,
            },
            random_seed=SEED,
            status="succeeded" if result.disposition != "stop" else "inconclusive",
            notes="Descriptive distributions. County rows stay in memory.",
        ),
        metrics,
    )
    write_column_profiles(executor, run_id, profiles)
    write_findings(executor, run_id, found)
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


def _adjacency(connection: object, run_id: str) -> str:
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        return "skipped: session has no cursor"
    try:
        with cursor_factory() as cursor:
            cursor.execute("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 540")
            cursor.execute(CREATE_ADJACENCY_SQL)
            cursor.execute(COUNT_ADJACENCY_SQL, (run_id,))
            existing = cursor.fetchone()
            if not existing or int(existing[0]) == 0:
                cursor.execute(INSERT_ADJACENCY_SQL, (run_id,))
            cursor.execute(COUNT_ADJACENCY_SQL, (run_id,))
            edges_row = cursor.fetchone()
            edges = int(edges_row[0]) if edges_row and edges_row[0] is not None else 0
            cursor.execute(
                f"SELECT COUNT(*) FROM ("
                f"SELECT FIPS_A AS FIPS FROM {ADJACENCY_TABLE} WHERE RUN_ID = %s "
                f"UNION SELECT FIPS_B FROM {ADJACENCY_TABLE} WHERE RUN_ID = %s)",
                (run_id, run_id),
            )
            touched_row = cursor.fetchone()
            touched = int(touched_row[0]) if touched_row and touched_row[0] is not None else 0
            granted = "no"
            try:
                cursor.execute(GRANT_ADJACENCY_SQL)
                granted = "yes"
            except Exception:
                granted = "no"
            cursor.execute("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = 600")
        return (
            f"{ADJACENCY_TABLE} edges {edges}, counties with a shared border {touched}, "
            f"SELECT grant to OH_LYME_PROD_READ {granted}"
        )
    except Exception:
        return "skipped: the spatial join did not finish inside the warehouse limit"


def _render(result: Analysis, counties: Sequence[AtlasCounty]) -> dict[str, bytes]:
    sns.set_theme(style="whitegrid", font_scale=0.7)
    incidence = _national(result.signals, "incidence_floor_2023")
    temperature = _national(result.climate_days, "nclimgrid_tavg_county_day")
    charts = {
        "incidence-histogram": _hist(incidence, "Published incidence floor per 100,000"),
        "incidence-by-rucc": _boxes(counties),
        "floor-ecdf": _ecdf(counties),
    }
    if temperature is not None and temperature.summary.n >= 11:
        charts["tavg-histogram"] = _hist(temperature, "Daily average temperature, degrees Celsius")
    for name, content in charts.items():
        if len(content) > _MAX_PNG_BYTES:
            raise DistributionError(f"{name} is {len(content)} bytes")
    return charts


def _hist(group: SignalGroup | None, title: str) -> bytes:
    if group is None:
        raise DistributionError("histogram group is missing")
    bins = chart_bins(group.summary.histogram)
    labels = [label for label, _count in bins]
    heights = [0.0 if count is None else float(count) for _label, count in bins]
    figure, axis = plt.subplots(figsize=(5.4, 3.0))
    sns.barplot(x=labels, y=heights, ax=axis, color="#4C78A8")
    axis.set_title(title)
    axis.set_ylabel("Count")
    axis.tick_params(axis="x", labelrotation=60, labelsize=6)
    for index, (_label, count) in enumerate(bins):
        if count is None:
            axis.text(index, 0.2, "<11", ha="center", va="bottom", fontsize=6, color="0.25")
    return _png(figure, 70)


def _boxes(counties: Sequence[AtlasCounty]) -> bytes:
    groups = box_groups(counties)
    codes: list[str] = []
    observations: list[float] = []
    for code, series in groups:
        codes.extend([code] * len(series))
        observations.extend(series)
    figure, axis = plt.subplots(figsize=(5.4, 3.0))
    sns.boxplot(
        x=codes,
        y=observations,
        hue=codes,
        ax=axis,
        color="#4C78A8",
        fliersize=2,
        legend=False,
    )
    axis.set_xlabel("RUCC 2023")
    axis.set_ylabel("Incidence floor per 100,000")
    axis.set_title("Published incidence floor by rural-urban code")
    return _png(figure, 70)


def _ecdf(counties: Sequence[AtlasCounty]) -> bytes:
    case = sorted(
        county.case_floor
        for county in counties
        if county.human_status == HUMAN_PUBLISHED and county.case_floor is not None
    )
    incidence = sorted(
        county.incidence_floor
        for county in counties
        if county.human_status == HUMAN_PUBLISHED and county.incidence_floor is not None
    )
    figure, axes = plt.subplots(1, 2, figsize=(5.8, 2.8))
    _draw_ecdf(axes[0], case, "Case floor")
    _draw_ecdf(axes[1], incidence, "Incidence floor per 100,000")
    return _png(figure, 70)


def _draw_ecdf(axis: plt.Axes, values: list[float], title: str) -> None:
    if len(values) < 11:
        axis.set_title(title)
        axis.text(0.5, 0.5, "not shown", ha="center", transform=axis.transAxes)
        return
    ranks = (np.arange(1, len(values) + 1)) / len(values)
    axis.plot(values, ranks, color="#4C78A8", linewidth=1.2)
    axis.set_title(title)
    axis.set_ylabel("ECDF")
    axis.tick_params(labelsize=7)


def _png(figure: plt.Figure, dpi: int) -> bytes:
    content = _save(figure, dpi)
    if len(content) > _MAX_PNG_BYTES:
        content = _save(figure, 48)
    plt.close(figure)
    return content


def _save(figure: plt.Figure, dpi: int) -> bytes:
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0.05)
    return buffer.getvalue()


def _national(groups: Sequence[SignalGroup], signal: str) -> SignalGroup | None:
    for group in groups:
        if group.signal == signal and group.geography_type == "national":
            return group
    return None


def _climate_frames(
    connection: object,
    captured: list[tuple[str, str, int, int, str | None]],
) -> tuple[list[dict[str, object]], list[dict[str, object]], str]:
    try:
        profile = _capture_sql(connection, "climate_profile", climate_profile_sql(), captured)
        means = _capture_sql(connection, "climate_means", climate_means_sql(), captured)
    except Exception:
        note = (
            "Climate values were not aggregated. That distribution is not estimable from this run."
        )
        return [], [], note
    return profile, means, ""


def _write_docs(
    result: Analysis,
    run_id: str,
    commit: str,
    counts: Mapping[str, int],
    adjacency_note: str,
) -> None:
    kwargs = {
        "run_id": run_id,
        "git_commit": commit,
        "row_counts": counts,
        "drive_lines": ("Drive upload pending",),
        "adjacency_note": adjacency_note,
    }
    record = render_eda_record(result, **kwargs)
    comment = render_comment(result, **kwargs)
    DOC_PATH.write_text(record + "\n" + comment, encoding="utf-8")


def _row_counts(connection: object, run_id: str) -> dict[str, int]:
    tables = {
        "REGISTRY.RUNS": f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.REGISTRY.RUNS WHERE RUN_ID = %s",
        "EDA.METRICS_LONG": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EDA.METRICS_LONG WHERE RUN_ID = %s"
        ),
        "EDA.COLUMN_PROFILES": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EDA.COLUMN_PROFILES WHERE RUN_ID = %s"
        ),
        "EDA.FINDINGS": f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.EDA.FINDINGS WHERE RUN_ID = %s",
        "REGISTRY.QUERIES": (
            f"SELECT COUNT(*) FROM {ML_LAB_DATABASE}.REGISTRY.QUERIES WHERE RUN_ID = %s"
        ),
        "EDA.COUNTY_ADJACENCY_107": COUNT_ADJACENCY_SQL,
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


def _capture(
    connection: object,
    name: str,
    queries: Mapping[str, str],
    captured: list[tuple[str, str, int, int, str | None]],
) -> list[dict[str, object]]:
    return _capture_sql(connection, name, queries[name], captured)


def _capture_sql(
    connection: object,
    name: str,
    sql: str,
    captured: list[tuple[str, str, int, int, str | None]],
) -> list[dict[str, object]]:
    started = time.perf_counter()
    rows, query_id = _fetch(connection, sql)
    elapsed = int((time.perf_counter() - started) * 1000)
    captured.append((name, sql, len(rows), elapsed, query_id))
    return rows


def _fetch(connection: object, sql: str) -> tuple[list[dict[str, object]], str | None]:
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        raise DistributionError("session has no cursor")
    with cursor_factory() as cursor:
        cursor.execute(sql)
        description = cursor.description
        if description is None:
            return [], getattr(cursor, "sfqid", None)
        names = [str(column[0]).upper() for column in description]
        raw_rows = cursor.fetchall()
        query_id = getattr(cursor, "sfqid", None)
    return [
        {name: _coerce(value) for name, value in zip(names, row, strict=True)} for row in raw_rows
    ], query_id if isinstance(query_id, str) else None


def _county(row: Mapping[str, object]) -> AtlasCounty:
    return AtlasCounty(
        fips=_text(row, "FIPS"),
        county=_text(row, "COUNTY"),
        state=_text(row, "STATE"),
        population=_float(row.get("POPULATION")),
        human_status=_text(row, "HUMAN_STATUS"),
        case_floor=_float(row.get("CASE_COUNT_FLOOR_2023")),
        incidence_floor=_float(row.get("INCIDENCE_FLOOR_2023")),
        svi_percentile=_float(row.get("SVI_PERCENTILE")),
        uninsured_percentile=_float(row.get("UNINSURED_PERCENTILE")),
        rucc=_int(row.get("RUCC_2023")),
    )


def _tier(row: Mapping[str, object]) -> TierCounty:
    return TierCounty(
        fips=_text(row, "COUNTY_FIPS"),
        tier=_text(row, "PRIORITY_TIER"),
        percentile=_float(row.get("PRIORITY_PERCENTILE")),
        score=_float(row.get("RAW_MODEL_SCORE")),
        sufficiency=_text(row, "EVIDENCE_SUFFICIENCY"),
        human_evidence_state=_text(row, "HUMAN_EVIDENCE_STATE"),
    )


def _text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise DistributionError(f"{key} is missing")
    return value


def _float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DistributionError("numeric field is not a number")
    return float(value)


def _int(value: object) -> int | None:
    number = _float(value)
    if number is None:
        return None
    return int(number)


def _coerce(value: object) -> object:
    if isinstance(value, Decimal):
        return int(value) if value == int(value) else float(value)
    return value


def _existing_run(connection: object) -> str | None:
    sql = (
        f"SELECT RUN_ID FROM {ML_LAB_DATABASE}.REGISTRY.RUNS "
        "WHERE ISSUE_NUMBER = %s AND STARTSWITH(RUN_ID, %s)"
    )
    cursor_factory = getattr(connection, "cursor", None)
    if not callable(cursor_factory):
        return None
    with cursor_factory() as cursor:
        cursor.execute(sql, (107, "107-county-distributions-"))
        found = [str(row[0]) for row in cursor.fetchall() if row and row[0]]
    if not found:
        return None
    return max(found)


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
    return f"107-county-distributions-{stamp}"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    text = completed.stdout.strip()
    return text or None


if __name__ == "__main__":
    raise SystemExit(main())
