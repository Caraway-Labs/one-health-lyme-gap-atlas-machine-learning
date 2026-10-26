#!/usr/bin/env python3
"""Fit issue 188 published-floor models and write ML Lab rows.

County rows stay in memory. A second invocation reuses an existing run id and
does not insert again. Chart registration is a separate ``--register`` pass.

    MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_188_floor_presence.py
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
from lyme_gap_atlas_ml.floor_presence import (
    BOOTSTRAP_SEED,
    ISSUE_NUMBER,
    PERMUTATION_DRAWS,
    PERMUTATION_SEED,
    RUN_PREFIX,
    SEED_PRIMARY,
    SEED_SECOND,
    SHUFFLE_SEED,
    SOURCE_OBJECTS,
    SPEC_ID,
    Analysis,
    FamilySeedResult,
    FloorPresenceError,
    lab_experiments,
    lab_findings,
    lab_metrics,
    load_floor_queries,
    parse_counties,
    release_matches,
)
from lyme_gap_atlas_ml.floor_presence import (
    analyze as fit_floor_presence,
)
from lyme_gap_atlas_ml.floor_presence_report import DOC_PATH, render_comment, render_eda_record
from lyme_gap_atlas_ml.registry.artifacts import register_artifact, save_chart
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import QueryRecord, write_findings, write_queries
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE, EdaRun, write_eda_results
from lyme_gap_atlas_ml.snowflake.floor_presence_predictions import (
    PREDICTION_TABLE,
    write_prediction_tables,
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
SQL_PATH = ROOT / "sql" / "validation" / "188_floor_presence.sql"
DOC_FILE = ROOT / DOC_PATH
CHART_DIR = ROOT / "artifacts" / "charts" / "188"
COMMENT_PATH = CHART_DIR / "comment.md"
UPLOADS_PATH = CHART_DIR / "drive_uploads.json"
_MAX_PNG_BYTES = 20_000
_CHARTS = (
    "lso-auc",
    "calibration-logistic",
    "regime-lift",
    "permutation-importance",
)
_CAPTIONS = {
    "lso-auc.png": "Leave-state-out ROC-AUC for a published floor.",
    "calibration-logistic.png": "Calibration of logistic published-floor probabilities.",
    "regime-lift.png": "Bootstrap interval for the regime ROC-AUC lift.",
    "permutation-importance.png": "Drop in published-floor ROC-AUC after a column shuffle.",
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
    except FloorPresenceError as error:
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
    queries = load_floor_queries(SQL_PATH.read_text(encoding="utf-8"))
    captured: list[tuple[str, str, int, int, str | None]] = []
    release_rows = _capture(connection, "release_identity", queries, captured)
    matched, reasons = release_matches(release_rows[0])
    if not matched:
        raise FloorPresenceError("release pin mismatch: " + ",".join(reasons))
    cohort_rows = _capture(connection, "cohort_rows", queries, captured)
    snapshot = _timestamp(connection, captured)
    release_id = str(release_rows[0]["RELEASE_ID"])
    cohort = parse_counties(cohort_rows, release_id=release_id)
    analysis = fit_floor_presence(
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
    if existing is None:
        grant = _persist(executor, run_id, branch, commit, snapshot, captured, analysis)
    counts = _row_counts(connection, run_id)
    grant_text = grant if existing is None else "reused"
    _write_docs(analysis, run_id, commit, counts, "pending upload", grant_text)
    print(f"run_id={run_id}")
    print(f"method={analysis.decision.method}")
    print(f"product={analysis.decision.product}")
    print(f"published={analysis.published_n}")
    print(f"absent={analysis.absent_n}")
    print(f"cohort_matches={analysis.cohort_matches_expected}")
    print(f"leakage_invariant={analysis.leakage_invariant}")
    print(f"shuffled_auc_lift={analysis.shuffled_auc_lift:.6f}")
    print(f"reused_run={existing is not None}")
    print(f"grant={grant_text}")
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
            purpose="Published-floor presence models for issue 188",
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
                "permutation_seed": PERMUTATION_SEED,
                "permutation_draws": PERMUTATION_DRAWS,
                "shuffle_seed": SHUFFLE_SEED,
                "sklearn": analysis.sklearn_version,
                "svi_rescaled": analysis.svi_rescaled,
                "uninsured_rescaled": analysis.uninsured_rescaled,
            },
            random_seed=SEED_PRIMARY,
            status="succeeded",
            notes="Not a production score. Published floor present versus absent. Leave-state-out.",
        ),
        lab_metrics(analysis),
    )
    return "pass" if result["granted"] else "fail"


def _save_charts(analysis: Analysis) -> dict[str, tuple[int, str]]:
    sns.set_theme(style="whitegrid", context="paper", font_scale=0.55)
    charts = {
        "lso-auc": _auc_chart(analysis),
        "calibration-logistic": _calibration_chart(analysis),
        "regime-lift": _lift_chart(analysis),
        "permutation-importance": _importance_chart(analysis),
    }
    saved: dict[str, tuple[int, str]] = {}
    for name, content in charts.items():
        chart = save_chart(188, name, content)
        saved[name] = (len(content), chart.sha256)
        if len(content) > _MAX_PNG_BYTES:
            print(f"chart over budget {name} bytes={len(content)}")
    return saved


def _auc_chart(analysis: Analysis) -> bytes:
    logistic = _primary(analysis, "logistic")
    trees = _primary(analysis, "gradient_boosting")
    labels = ["Logistic\ndemographics", "Logistic\nregime", "Tree\ndemographics", "Tree\nregime"]
    values = [
        logistic.baseline.roc_auc,
        logistic.challenger.roc_auc,
        trees.baseline.roc_auc,
        trees.challenger.roc_auc,
    ]
    fig, ax = plt.subplots()
    sns.barplot(x=labels, y=values, hue=labels, ax=ax, palette="colorblind", legend=False)
    ax.set_ylim(0.5, 1.0)
    ax.set_ylabel("ROC-AUC")
    ax.set_xlabel("")
    ax.set_title("Leave-state-out AUC for a published floor")
    return _png(fig)


def _calibration_chart(analysis: Analysis) -> bytes:
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1], color="#999999", linewidth=0.6)
    for feature, color in (("baseline", "#4C78A8"), ("challenger", "#F58518")):
        rows = [
            row
            for row in analysis.calibration
            if row.family == "logistic" and row.feature_set == feature and row.n >= 11
        ]
        ax.plot(
            [row.mean_predicted for row in rows],
            [row.observed_rate for row in rows],
            marker="o",
            markersize=2,
            linewidth=0.8,
            color=color,
            label=feature,
        )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Observed published-floor share")
    ax.set_title("Calibration of published-floor probabilities")
    ax.legend(frameon=False, fontsize=6)
    return _png(fig)


def _lift_chart(analysis: Analysis) -> bytes:
    logistic = _primary(analysis, "logistic")
    trees = _primary(analysis, "gradient_boosting")
    labels = ["Logistic", "Tree"]
    points = [
        logistic.challenger.roc_auc - logistic.baseline.roc_auc,
        trees.challenger.roc_auc - trees.baseline.roc_auc,
    ]
    lows = [logistic.auc_lift.low, trees.auc_lift.low]
    highs = [logistic.auc_lift.high, trees.auc_lift.high]
    fig, ax = plt.subplots()
    ax.axhline(0.0, color="#999999", linewidth=0.6)
    ax.axhline(0.01, color="#54A24B", linewidth=0.6, linestyle="--")
    if all(low is not None and high is not None for low, high in zip(lows, highs, strict=True)):
        yerr = [
            [max(0.0, point - float(low)) for point, low in zip(points, lows, strict=True)],
            [max(0.0, float(high) - point) for point, high in zip(points, highs, strict=True)],
        ]
        ax.errorbar(labels, points, yerr=yerr, fmt="o", color="#4C78A8", capsize=3)
    ax.set_ylabel("ROC-AUC lift")
    ax.set_title("Bootstrap interval for the regime AUC lift")
    return _png(fig)


def _importance_chart(analysis: Analysis) -> bytes:
    rows = [
        item
        for item in analysis.importance
        if item.family == "logistic" and item.feature_set == "challenger"
    ]
    fig, ax = plt.subplots()
    sns.barplot(
        x=[item.auc_drop for item in rows],
        y=[item.feature.replace("_", "\n") for item in rows],
        hue=[item.feature for item in rows],
        ax=ax,
        palette="colorblind",
        legend=False,
        orient="h",
    )
    ax.set_xlabel("Mean AUC drop")
    ax.set_ylabel("")
    ax.set_title("Permutation drop in published-floor AUC")
    return _png(fig)


def _png(fig: Figure) -> bytes:
    data = b""
    for dpi, width, height in ((64, 4.0, 2.5), (56, 3.6, 2.3), (48, 3.2, 2.0)):
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
    raise FloorPresenceError("primary fit is missing")


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
        raise FloorPresenceError("session has no cursor")
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
    raise FloorPresenceError("snapshot timestamp is missing")


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
        "EXPERIMENTS.FLOOR_PRESENCE_PREDICTIONS_188": (
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
