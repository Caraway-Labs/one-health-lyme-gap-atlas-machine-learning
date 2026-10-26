"""Issue 106 state-relative screen with synthetic rows. No live Snowflake connection."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from lyme_gap_atlas_ml.class_anomaly import ClassAnomalyError
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE, prepare_eda_metric
from lyme_gap_atlas_ml.snowflake.ml_agent_access import IDENTITY_SQL, ML_AGENT_ROLE
from lyme_gap_atlas_ml.snowflake.state_anomaly_scores import score_table_sql, write_score_tables
from lyme_gap_atlas_ml.state_anomaly import (
    build_findings,
    decide_state_disposition,
    fit_states,
    lab_metrics,
    percentile_flags,
    shrunk_mad,
    surveillance_flags,
)
from lyme_gap_atlas_ml.state_anomaly_report import render_comment, render_eda_record


def test_shrunk_scale_moves_toward_the_region() -> None:
    blended = shrunk_mad(state_mad=0.1, state_n=20, loo_mad=1.0, loo_n=100, full_mad=1.0)
    assert abs(blended - (20 / 60) * 0.1 - (40 / 60) * 1.0) < 1e-12
    assert shrunk_mad(0.0, 20, 1.0, 100, 9.0) == 1.0
    assert shrunk_mad(0.0, 20, 0.0, 10, 2.0) == 2.0


def test_percentile_and_surveillance_rules() -> None:
    values = np.arange(40, dtype=float)
    flags = percentile_flags(values)
    assert bool(flags[0])
    assert bool(flags[-1])
    assert not bool(flags[20])
    rare = np.zeros(60)
    rare[:12] = 1
    chosen, applied = surveillance_flags(rare)
    assert applied
    assert int(chosen.sum()) == 12
    common = np.zeros(60)
    common[:24] = 1
    chosen, applied = surveillance_flags(common)
    assert applied
    assert int(chosen.sum()) == 0
    tiny = np.zeros(30)
    tiny[:5] = 1
    _chosen, applied = surveillance_flags(tiny)
    assert not applied


def test_disposition_order() -> None:
    assert (
        decide_state_disposition(
            exclusions=0,
            state_flags=0,
            jaccard_national=0.1,
            median_abs_rank_shift=500,
            small_share=None,
            urban_gap=None,
            urban_comparable=False,
            native_feature_failure=False,
            mcd_failure_share=0.0,
        )
        == "defer"
    )
    assert (
        decide_state_disposition(
            exclusions=1,
            state_flags=0,
            jaccard_national=0.1,
            median_abs_rank_shift=None,
            small_share=None,
            urban_gap=None,
            urban_comparable=False,
            native_feature_failure=False,
            mcd_failure_share=None,
        )
        == "revise"
    )
    assert (
        decide_state_disposition(
            exclusions=0,
            state_flags=40,
            jaccard_national=0.2,
            median_abs_rank_shift=200,
            small_share=0.05,
            urban_gap=0.05,
            urban_comparable=True,
            native_feature_failure=False,
            mcd_failure_share=0.0,
        )
        == "proceed"
    )
    assert (
        decide_state_disposition(
            exclusions=0,
            state_flags=40,
            jaccard_national=0.2,
            median_abs_rank_shift=200,
            small_share=0.2,
            urban_gap=0.0,
            urban_comparable=True,
            native_feature_failure=False,
            mcd_failure_share=0.0,
        )
        == "revise"
    )


def test_small_state_does_not_use_a_within_state_peer() -> None:
    rows = _panel()
    fitted = fit_states(rows, run_id="106-test")
    by_state = {row.state: row.peer_rule for row in fitted.counties}
    assert by_state["DE"] == "class_peer"
    assert by_state["MD"] == "state_shrunk"
    assert by_state["TX"] == "state_native"
    assert all(not row.forest_applied for row in fitted.counties)
    assert all(not row.percentile_applied for row in fitted.counties if row.state == "MD")
    assert any(row.percentile_applied for row in fitted.counties if row.state == "DE")
    de = next(row for row in fitted.counties if row.state == "DE")
    assert "Census region South" in de.peer_label
    assert de.state_n == 10


def test_state_outlier_is_not_forced_onto_the_national_list() -> None:
    rows = _panel(seed=7)
    rows.append(_county("99999", "TX", "Outlier County", population=2_000_000, draw=0))
    fitted = fit_states(rows, run_id="106-outlier")
    outlier = next(row for row in fitted.counties if row.fips == "99999")
    assert outlier.flag_z_state
    assert outlier.dominant_feature == "log_population"
    assert "Outlier County" in render_eda_record(
        fitted,
        run_id="106-outlier",
        git_commit="abc1234",
        row_counts={"scores": fitted.n_fit},
        drive_links=(),
        missing_charts=(),
        skipped_charts=(),
    )


def test_null_population_is_excluded_and_not_zero() -> None:
    rows = _panel()
    rows.append(_county("01001", "TX", "Missing Pop", population=None, draw=1))
    fitted = fit_states(rows, run_id="106-missing")
    assert fitted.exclusions == 1
    assert fitted.disposition == "revise"
    assert all(row.fips != "01001" for row in fitted.counties)


def test_duplicate_fips_stops() -> None:
    rows = _panel()
    rows.append(dict(rows[-1]))
    try:
        fit_states(rows, run_id="106-dup")
    except ClassAnomalyError as error:
        assert "duplicated" in str(error)
    else:
        raise AssertionError("duplicate FIPS should stop")


def test_findings_and_score_sql_stay_aggregate_and_in_the_lab() -> None:
    fitted = fit_states(_panel(), run_id="106-lab")
    findings = build_findings(fitted)
    assert len(findings) == 3
    for finding in findings:
        assert "01000" not in finding.statement
    metrics = [prepare_eda_metric(metric) for metric in lab_metrics(fitted)]
    for metric in metrics:
        if metric.n_underlying is not None:
            assert metric.n_underlying == 0 or metric.n_underlying >= 11
    sql = score_table_sql()
    assert ML_LAB_DATABASE in sql
    assert "COUNTY_STATE_ANOMALY_106" in sql
    assert "GRANT" not in sql.upper()
    assert "GEOMETRY" not in sql
    session = _Fake()
    receipt = write_score_tables(session, "106-lab", fitted.counties, fitted.experiments)
    assert receipt["scores"] == fitted.n_fit
    comment = render_comment(
        fitted,
        run_id="106-lab",
        git_commit="abc1234",
        row_counts={"EDA.COUNTY_STATE_ANOMALY_106": fitted.n_fit},
        drive_links=(),
        missing_charts=(),
        skipped_charts=("seed-stability.png",),
    )
    assert "not incidence" in comment
    assert "Part of" not in comment


def _panel(seed: int = 5) -> list[dict[str, object]]:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, object]] = []
    specs = (
        ("DE", 10, 10.0),
        ("MD", 20, 10.5),
        ("TX", 50, 10.2),
        ("CA", 50, 13.5),
    )
    serial = 0
    for state, count, center in specs:
        for draw in range(count):
            serial += 1
            rows.append(
                _county(
                    f"{serial:05d}",
                    state,
                    f"County {serial}",
                    population=float(np.exp(center + float(rng.normal(0, 0.25)))),
                    draw=draw,
                )
            )
    return rows


def _county(
    fips: str,
    state: str,
    name: str,
    population: float | None,
    draw: int,
) -> dict[str, object]:
    return {
        "FIPS": fips,
        "COUNTY": name,
        "STATE": state,
        "POPULATION": population,
        "SVI_PERCENTILE": 0.4 + (draw % 5) * 0.02,
        "UNINSURED_PERCENTILE": 0.3 + (draw % 4) * 0.02,
        "RUCC_2023": (draw % 9) + 1,
        "HUMAN_STATUS": "published_count_floor",
        "TICK_STATUS": "Established",
        "BURGDORFERI_STATUS": "No records",
    }


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

    def executemany(self, sql: str, rows: Sequence[tuple[object, ...]]) -> None:
        self.calls.append((sql, rows[0] if rows else None))
