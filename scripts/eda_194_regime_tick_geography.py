#!/usr/bin/env python3
"""Fit issue 194 tick-geography models and write ML Lab rows.

County rows stay in memory. A second invocation reuses an existing run id and
does not insert again. Chart registration is a separate ``--register`` pass.

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn \\
        python scripts/eda_194_regime_tick_geography.py
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
import seaborn as sns
from matplotlib.figure import Figure

from lyme_gap_atlas_ml.coverage_audit import PINNED_RELEASE_ID
from lyme_gap_atlas_ml.floor_presence import release_matches
from lyme_gap_atlas_ml.regime_tick_geography import (
    BOOTSTRAP_SEED,
    FAMILY_GBT,
    FAMILY_LOGISTIC,
    FEATURE_BASELINE,
    FEATURE_CHALLENGER,
    ISSUE_NUMBER,
    NUMERIC_FEATURES,
    RUN_PREFIX,
    SEED_PRIMARY,
    SEED_SECOND,
    SHUFFLE_SEED,
    SOURCE_OBJECTS,
    SPEC_ID,
    Analysis,
    FamilySeedResult,
    RegimeTickError,
    histogram_bins,
    lab_experiments,
    lab_findings,
    lab_metrics,
    load_regime_queries,
    parse_geography,
)
from lyme_gap_atlas_ml.regime_tick_geography import (
    analyze as fit_regime_tick,
)
from lyme_gap_atlas_ml.regime_tick_report import DOC_PATH, render_comment, render_eda_record
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
from lyme_gap_atlas_ml.snowflake.regime_tick_predictions import (
    PREDICTION_TABLE,
    mark_run_finished,
    write_prediction_tables,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "194_regime_tick_geography.sql"
DOC_FILE = ROOT / DOC_PATH
CHART_DIR = ROOT / "artifacts" / "charts" / "194"
COMMENT_PATH = CHART_DIR / "comment.md"
UPLOADS_PATH = CHART_DIR / "drive_uploads.json"
_MAX_PNG_BYTES = 20_000
_CHARTS = (
    "auc-comparison",
    "regime-lift",
    "calibration-logistic",
    "state-lift-hist",
)
_CAPTIONS = {
    "auc-comparison.png": "Leave-state-out ROC-AUC for tick geography and the regime.",
    "regime-lift.png": "Bootstrap interval for the regime ROC-AUC lift over tick geography.",
    "calibration-logistic.png": "Calibration of logistic published-floor probabilities.",
    "state-lift-hist.png": (
        "Per-state logistic ROC-AUC lift for states with n at least 11. "
        "Bins of 1 to 10 states are omitted."
    ),
}


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
    except RegimeTickError as error:
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
    queries = load_regime_queries(SQL_PATH.read_text(encoding="utf-8"))
    captured: list[tuple[str, str, int, int, str | None]] = []
    release_rows = _capture(connection, "release_identity", queries, captured)
    matched, reasons = release_matches(release_rows[0])
    if not matched:
        raise RegimeTickError("release pin mismatch: " + ",".join(reasons))
    cohort_rows = _capture(connection, "cohort_rows", queries, captured)
    snapshot = _timestamp(connection, captured)
    release_id = str(release_rows[0]["RELEASE_ID"])
    cohort = parse_geography(cohort_rows, release_id=release_id)
    analysis = fit_regime_tick(
        cohort.counties,
        svi_rescaled=cohort.svi_rescaled,
        uninsured_rescaled=cohort.uninsured_rescaled,
    )
    saved = _save_charts(analysis)
    existing = _existing_run(connection)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%MZ")
    run_id = existing or f"{RUN_PREFIX}{stamp}"
    commit = _git("rev-parse", "HEAD") or "unknown"
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    grant = "not-attempted"
    finished = "not-attempted"
    if existing is None:
        grant = _persist(executor, run_id, branch, commit, snapshot, captured, analysis)
        finished = mark_run_finished(executor, run_id)
    counts = _row_counts(connection, run_id)
    grant_text = grant if existing is None else "reused"
    _write_docs(analysis, run_id, commit, counts, "Drive upload pending.", grant_text)
    print(f"run_id={run_id}")
    print(f"method={analysis.decision.method}")
    print(f"product={analysis.decision.product}")
    print(f"published={analysis.published_n}")
    print(f"absent={analysis.absent_n}")
    print(f"cohort_matches={analysis.cohort_matches_expected}")
    print(f"leakage_invariant={analysis.leakage_invariant}")
    print(f"shuffled_auc_lift={analysis.shuffled_auc_lift:.6f}")
    print(f"shuffle_baseline_gap={analysis.shuffle_baseline_gap:.6f}")
    print(f"logistic_pass={analysis.decision.logistic_real_lift}")
    print(f"tree_positive={analysis.decision.tree_auc_positive}")
    print(f"reasons={','.join(analysis.decision.reasons) or 'none'}")
    print(f"reused_run={existing is not None}")
    print(f"grant={grant_text}")
    print(f"finished={finished if existing is None else 'reused'}")
    _print_scores(analysis)
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
    result = write_prediction_tables(
        executor,
        run_id,
        analysis.predictions,
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
            purpose="Regime signal beyond tick geography for issue 194",
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
                "seed_primary": SEED_PRIMARY,
                "seed_second": SEED_SECOND,
                "bootstrap_seed": BOOTSTRAP_SEED,
                "shuffle_seed": SHUFFLE_SEED,
                "numeric_features": list(NUMERIC_FEATURES),
                "sklearn": analysis.sklearn_version,
                "svi_rescaled": analysis.svi_rescaled,
                "uninsured_rescaled": analysis.uninsured_rescaled,
            },
            random_seed=SEED_PRIMARY,
            status="succeeded",
            notes=(
                "Not a production score. Published floor present versus absent. "
                "Leave-state-out. Tick geography versus regime."
            ),
        ),
        lab_metrics(analysis),
    )
    grants = result["grants"]
    return grants if isinstance(grants, str) else "fail"


def _save_charts(analysis: Analysis) -> dict[str, tuple[int, str]]:
    sns.set_theme(style="whitegrid", context="paper", font_scale=0.55)
    charts = {
        "auc-comparison": _auc_chart(analysis),
        "regime-lift": _lift_chart(analysis),
        "calibration-logistic": _calibration_chart(analysis),
        "state-lift-hist": _hist_chart(analysis),
    }
    saved: dict[str, tuple[int, str]] = {}
    for name, content in charts.items():
        chart = save_chart(194, name, content)
        saved[name] = (len(content), chart.sha256)
        if len(content) > _MAX_PNG_BYTES:
            print(f"chart over budget {name} bytes={len(content)}")
    return saved


def _auc_chart(analysis: Analysis) -> bytes:
    logistic = _primary(analysis, FAMILY_LOGISTIC)
    trees = _primary(analysis, FAMILY_GBT)
    frame = {
        "model": ["Logistic", "Logistic", "Tree", "Tree"],
        "features": ["Tick geography", "Plus regime", "Tick geography", "Plus regime"],
        "auc": [
            logistic.baseline.roc_auc,
            logistic.challenger.roc_auc,
            trees.baseline.roc_auc,
            trees.challenger.roc_auc,
        ],
    }
    fig, ax = plt.subplots()
    sns.barplot(
        data=frame,
        x="model",
        y="auc",
        hue="features",
        ax=ax,
        palette="colorblind",
    )
    ax.set_ylim(0.5, 1.0)
    ax.set_ylabel("ROC-AUC")
    ax.set_xlabel("")
    ax.set_title("Leave-state-out AUC for a published floor")
    ax.legend(frameon=False, fontsize=6, title="")
    return _png(fig)


def _lift_chart(analysis: Analysis) -> bytes:
    logistic = _primary(analysis, FAMILY_LOGISTIC)
    trees = _primary(analysis, FAMILY_GBT)
    labels = ["Logistic", "Tree"]
    points = [
        logistic.challenger.roc_auc - logistic.baseline.roc_auc,
        trees.challenger.roc_auc - trees.baseline.roc_auc,
    ]
    lows = [logistic.auc_lift.low, trees.auc_lift.low]
    highs = [logistic.auc_lift.high, trees.auc_lift.high]
    fig, ax = plt.subplots()
    ax.axhline(0.0, color="#999999", linewidth=0.6, label="No lift")
    ax.axhline(0.01, color="#54A24B", linewidth=0.6, linestyle="--", label="Pass bar")
    if all(low is not None and high is not None for low, high in zip(lows, highs, strict=True)):
        yerr = [
            [max(0.0, point - float(low)) for point, low in zip(points, lows, strict=True)],
            [max(0.0, float(high) - point) for point, high in zip(points, highs, strict=True)],
        ]
        ax.errorbar(labels, points, yerr=yerr, fmt="o", color="#4C78A8", capsize=3, label="Lift")
    ax.set_ylabel("ROC-AUC lift")
    ax.set_title("Bootstrap interval for the regime AUC lift")
    ax.legend(frameon=False, fontsize=6)
    return _png(fig)


def _calibration_chart(analysis: Analysis) -> bytes:
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], color="#999999", linewidth=0.6, label="Matched share")
    for feature, color, label in (
        (FEATURE_BASELINE, "#4C78A8", "Tick geography"),
        (FEATURE_CHALLENGER, "#F58518", "Plus regime"),
    ):
        rows = [
            row
            for row in analysis.calibration
            if row.family == FAMILY_LOGISTIC and row.feature_set == feature and row.n >= 11
        ]
        ax.plot(
            [row.mean_predicted for row in rows],
            [row.observed_rate for row in rows],
            marker="o",
            markersize=2,
            linewidth=0.8,
            color=color,
            label=label,
        )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Observed published-floor share")
    ax.set_title("Calibration of published-floor probabilities")
    ax.legend(frameon=False, fontsize=6)
    return _png(fig)


def _hist_chart(analysis: Analysis) -> bytes:
    lifts = [
        item.lift
        for item in analysis.state_lifts
        if item.family == FAMILY_LOGISTIC and item.county_n >= 11 and item.lift is not None
    ]
    bins = histogram_bins([float(item) for item in lifts])
    short = {
        "<= -0.20": "<=-0.2",
        "-0.20 to -0.10": "-0.2 to -0.1",
        "-0.10 to 0.00": "-0.1 to 0",
        "0.00 to 0.10": "0 to 0.1",
        "0.10 to 0.20": "0.1 to 0.2",
        "> 0.20": ">0.2",
    }
    labels = [short[label] for label, _count in bins]
    fig, ax = plt.subplots()
    if bins:
        sns.barplot(
            x=labels,
            y=[count for _label, count in bins],
            hue=labels,
            ax=ax,
            palette="colorblind",
            legend=False,
        )
    ax.set_ylabel("States")
    ax.set_xlabel("ROC-AUC lift")
    ax.set_title("State logistic lift, n>=11; bins of 1-10 omitted")
    ax.tick_params(axis="x", labelsize=7)
    return _png(fig)


def _png(fig: Figure) -> bytes:
    data = b""
    for dpi, width, height in ((64, 4.2, 2.6), (56, 3.8, 2.4), (48, 3.4, 2.2)):
        fig.set_size_inches(width, height)
        buffer = BytesIO()
        fig.savefig(buffer, format="png", dpi=dpi)
        data = buffer.getvalue()
        if len(data) <= _MAX_PNG_BYTES:
            break
    plt.close(fig)
    return data


def _primary(analysis: Analysis, family: str) -> FamilySeedResult:
    for fit in analysis.fits:
        if fit.family == family and fit.seed == SEED_PRIMARY:
            return fit
    raise RegimeTickError("primary fit is missing")


def _print_scores(analysis: Analysis) -> None:
    for fit in analysis.fits:
        if fit.seed != SEED_PRIMARY:
            continue
        lift = fit.challenger.roc_auc - fit.baseline.roc_auc
        low = "na" if fit.auc_lift.low is None else f"{fit.auc_lift.low:.4f}"
        high = "na" if fit.auc_lift.high is None else f"{fit.auc_lift.high:.4f}"
        print(
            f"score {fit.family} base={fit.baseline.roc_auc:.4f} "
            f"chal={fit.challenger.roc_auc:.4f} lift={lift:.4f} "
            f"interval={low},{high} pr={fit.baseline.pr_auc:.4f},{fit.challenger.pr_auc:.4f} "
            f"brier={fit.baseline.brier:.4f},{fit.challenger.brier:.4f}"
        )


def _write_docs(
    analysis: Analysis,
    run_id: str,
    commit: str,
    counts: Mapping[str, int],
    drive_note: str,
    grant: str,
) -> None:
    comment = render_comment(
        analysis,
        run_id=run_id,
        commit=commit,
        counts=counts,
        drive_note=drive_note,
        grant=grant,
    )
    record = render_eda_record(
        analysis,
        run_id=run_id,
        commit=commit,
        counts=counts,
        drive_note=drive_note,
        grant=grant,
    )
    DOC_FILE.write_text(record, encoding="utf-8")
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    COMMENT_PATH.write_text(comment, encoding="utf-8")


def _register() -> int:
    payload = json.loads(UPLOADS_PATH.read_text(encoding="utf-8"))
    run_id = str(payload["run_id"])
    index = json.loads((CHART_DIR / "index.json").read_text(encoding="utf-8"))
    known = {entry["file_name"]: entry["sha256"] for entry in index["files"]}
    for item in payload["files"]:
        file_name = str(item["file_name"])
        content = (CHART_DIR / file_name).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != known.get(file_name) or digest != str(item["sha256"]):
            print(f"sha mismatch {file_name}")
            return 2
        register_artifact(
            run_id,
            ISSUE_NUMBER,
            file_name,
            str(item["drive_file_id"]),
            str(item["drive_link"]),
            digest,
            caption=_CAPTIONS[file_name],
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
        raise RegimeTickError("session has no cursor")
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
    raise RegimeTickError("snapshot timestamp is missing")


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
        "EDA.REGIME_VS_TICK_GEOGRAPHY_194": (
            f"SELECT COUNT(*) FROM {PREDICTION_TABLE} WHERE RUN_ID = %s"
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
