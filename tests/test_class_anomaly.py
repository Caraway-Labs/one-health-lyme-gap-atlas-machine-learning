"""Issue 122 class screen with synthetic rows. No live Snowflake connection."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest

from lyme_gap_atlas_ml.class_anomaly import (
    EXPECTED_CLASS_N,
    ClassAnomalyError,
    build_findings,
    decide_disposition,
    dominant_label,
    evaluate_gate,
    fit_class,
    lab_metrics,
    load_class_queries,
)
from lyme_gap_atlas_ml.class_anomaly_report import render_comment, render_eda_record
from lyme_gap_atlas_ml.coverage_audit import PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.snowflake.anomaly_scores import score_table_sql, write_score_tables
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import prepare_finding
from lyme_gap_atlas_ml.snowflake.eda_writer import (
    ML_LAB_DATABASE,
    EdaWriteError,
    prepare_eda_metric,
)
from lyme_gap_atlas_ml.snowflake.ml_agent_access import IDENTITY_SQL, ML_AGENT_ROLE

ROOT = Path(__file__).resolve().parents[1]
STATES = ("ME", "NY", "PA", "OH", "IL", "VA", "NC", "GA", "IA", "CA")


def _rows(
    n: int = 80,
    *,
    huge: int = 6,
    rucc: int | None = None,
    svi_scale: float = 1.0,
) -> list[dict[str, object]]:
    rng = np.random.default_rng(122)
    rows: list[dict[str, object]] = []
    for index in range(n):
        population = float(rng.lognormal(mean=10.2, sigma=0.35))
        if index < huge:
            population = 5_000_000.0
        svi = float(rng.uniform(0.05, 0.95)) * svi_scale
        rows.append(
            {
                "FIPS": f"{index:05d}",
                "COUNTY": f"Example {index} County",
                "STATE": STATES[index % len(STATES)],
                "POPULATION": population,
                "SVI_PERCENTILE": svi,
                "UNINSURED_PERCENTILE": float(rng.uniform(0.05, 0.95)),
                "RUCC_2023": 4 if rucc is None else rucc,
                "HUMAN_STATUS": "published_count_floor",
                "BURGDORFERI_STATUS": "No records",
                "TICK_STATUS": "Established",
            }
        )
    return rows


def _release() -> dict[str, object]:
    return {
        "RELEASE_ID": PINNED_RELEASE_ID,
        "SCHEMA_VERSION": "2.0.0",
        "BUNDLE_SHA256": PINNED_BUNDLE_SHA256,
        "METHODOLOGY_VERSION": "semantic-2.0.0",
        "SCOPE": "US_COUNTIES",
    }


def _gate(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "CLASS_N": EXPECTED_CLASS_N,
        "FIPS_N": EXPECTED_CLASS_N,
        "FIPS_PATTERN_N": EXPECTED_CLASS_N,
        "RELEASE_N": 1,
        "RELEASE_MIN": PINNED_RELEASE_ID,
        "RELEASE_MAX": PINNED_RELEASE_ID,
        "DOUBLE_GAP_N": 228,
        "GAP_810_N": 810,
    }
    base.update(overrides)
    return base


def test_queries_match_the_registered_file() -> None:
    text = (ROOT / "sql" / "validation" / "122_established_class.sql").read_text(encoding="utf-8")
    queries = load_class_queries(text)
    assert set(queries) == {"release_identity", "class_gate", "class_rows"}
    assert "TICK_STATUS = 'Established'" in queries["class_rows"]
    assert "COUNTY" in queries["class_rows"]


def test_gate_accepts_the_pin_and_rejects_a_different_class_size() -> None:
    assert evaluate_gate(_release(), _gate()).ok
    blocked = evaluate_gate(_release(), _gate(CLASS_N=1400, FIPS_N=1400, FIPS_PATTERN_N=1400))
    assert not blocked.ok
    assert blocked.class_n == 1400


def test_fit_flags_large_counties_and_repeats() -> None:
    rows = _rows()
    rows[0]["COUNTY"] = "Zebulon County"
    first = fit_class(rows, reference_double_gap=None, run_id="122-test")
    second = fit_class(rows, reference_double_gap=None, run_id="122-test")
    assert first.features_dropped == ("rucc_2023",)
    assert first.n_fit == 80
    assert first.flag_counts["robust_z"] >= 6
    assert any(row.county_name == "Zebulon County" and row.flag_robust_z for row in first.counties)
    assert first.flag_counts == second.flag_counts
    assert np.allclose(
        [row.if_score_primary for row in first.counties],
        [row.if_score_primary for row in second.counties],
    )
    labels = [item.label for item in first.population_bins]
    assert "Zebulon County" not in labels
    comment = render_comment(
        first,
        run_id="122-test",
        git_commit="abc1234",
        row_counts={"scores": 80},
        drive_links=(),
        missing_charts=(),
        prior_artifact_note="",
    )
    assert "Zebulon County" in comment
    assert "Zebulon County" not in " ".join(finding.statement for finding in build_findings(first))
    for finding in build_findings(first):
        prepare_finding(finding, finding_id="12212210-0000-4000-8000-000000000001")


def test_percentile_unit_rule_divides_by_100() -> None:
    fitted = fit_class(_rows(svi_scale=100.0), reference_double_gap=None)
    assert "svi_percentile" in fitted.scaled_columns
    assert max(row.svi_percentile for row in fitted.counties) <= 1


def test_duplicate_fips_stops() -> None:
    rows = _rows()
    rows[1]["FIPS"] = rows[0]["FIPS"]
    with pytest.raises(ClassAnomalyError, match="duplicated"):
        fit_class(rows, reference_double_gap=None)


def test_disposition_rule() -> None:
    assert (
        decide_disposition(
            exclusions=0,
            double_gap_reproduced=True,
            mcd_ok=True,
            seed_jaccard=0.95,
            forest_adds=False,
            max_driver_share=0.4,
        )
        == "keep"
    )
    assert (
        decide_disposition(
            exclusions=0,
            double_gap_reproduced=False,
            mcd_ok=True,
            seed_jaccard=0.95,
            forest_adds=False,
            max_driver_share=0.2,
        )
        == "revise"
    )
    assert (
        decide_disposition(
            exclusions=0,
            double_gap_reproduced=True,
            mcd_ok=True,
            seed_jaccard=0.95,
            forest_adds=True,
            max_driver_share=0.2,
        )
        == "follow-up"
    )
    assert dominant_label({"log_population": 1.0, "svi_percentile": 0.2}) == "joint"
    assert dominant_label({"log_population": 4.0, "svi_percentile": 2.6}) == "log_population"


def test_small_bin_is_not_a_chart_count() -> None:
    rows = _rows(rucc=None)
    for index, row in enumerate(rows):
        row["RUCC_2023"] = 9 if index < 5 else 1
    fitted = fit_class(rows, reference_double_gap=None)
    assert fitted.features_kept
    assert all(
        item.count is None or item.count >= 11 or item.count == 0 for item in fitted.rucc_bins
    )
    metrics = [prepare_eda_metric(metric) for metric in lab_metrics(fitted)]
    for metric in metrics:
        if metric.metric_name == "feature_bin_count" and metric.n_underlying is not None:
            assert metric.n_underlying == 0 or metric.n_underlying >= 11


def test_score_sql_stays_in_the_lab() -> None:
    sql = score_table_sql()
    assert ML_LAB_DATABASE in sql
    assert "COUNTY_NAME" in sql
    assert "GEOMETRY" not in sql


class _Fake:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []

    def query(self, sql: str, params: Sequence[object] | None = None) -> list[tuple[object, ...]]:
        self.calls.append((sql, None if params is None else tuple(params)))
        if sql == IDENTITY_SQL:
            return [(ML_AGENT_ROLE, "OH_LYME_ML_LAB_XS_WH", ML_LAB_DATABASE)]
        if "REGISTRY.RUNS" in sql:
            return [(0,)]
        raise AssertionError(sql)

    def execute(self, sql: str, params: Sequence[object] = ()) -> None:
        self.calls.append((sql, tuple(params)))


def test_writer_inserts_scores_without_a_second_run() -> None:
    fitted = fit_class(_rows(), reference_double_gap=None, run_id="122-test")
    session = _Fake()
    receipt = write_score_tables(session, "122-test", fitted.counties, fitted.experiments)
    assert receipt["scores"] == 80
    inserts = [sql for sql, _params in session.calls if sql.startswith("INSERT INTO")]
    assert any("COUNTY_ANOMALY_SCORES_122" in sql for sql in inserts)
    assert any("EXPERIMENTS.EXPERIMENTS" in sql for sql in inserts)
    session.calls.clear()

    def query(sql: str, params: Sequence[object] | None = None) -> list[tuple[object, ...]]:
        if sql == IDENTITY_SQL:
            return [(ML_AGENT_ROLE, "OH_LYME_ML_LAB_XS_WH", ML_LAB_DATABASE)]
        return [(1,)]

    session.query = query  # type: ignore[method-assign]
    with pytest.raises(EdaWriteError, match="already"):
        write_score_tables(session, "122-test", fitted.counties, fitted.experiments)
    record = render_eda_record(
        fitted,
        run_id="122-test",
        git_commit="abc1234",
        row_counts={"scores": 80},
        drive_links=(),
        missing_charts=("feature-distributions.png",),
    )
    assert "Example 0 County" in record
