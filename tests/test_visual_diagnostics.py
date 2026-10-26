"""Offline checks for the issue 117 visual diagnostics. No warehouse session."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest

from lyme_gap_atlas_ml.coverage_audit import CENSUS_REGIONS
from lyme_gap_atlas_ml.cross_domain import County
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import prepare_finding
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric, prepare_eda_metric
from lyme_gap_atlas_ml.test_selection import HUMAN_NONE, HUMAN_PUBLISHED
from lyme_gap_atlas_ml.visual_diagnostics import (
    VisualDiagnosticsError,
    _climate_days,
    _heatmap,
    _hexbin,
    _new_block,
    _time,
    analyze,
    average_linkage_order,
    axial_to_pixel,
    lab_findings,
    load_visual_queries,
    outside_product_mode,
    pixel_to_axial,
)
from lyme_gap_atlas_ml.visual_diagnostics_report import render_comment

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "117_visual_diagnostics.sql"


def test_axial_round_trip_for_the_neighbor_hex() -> None:
    x, y = axial_to_pixel(1, 0)
    assert pixel_to_axial(x, y) == (1, 0)
    assert pixel_to_axial(0.0, 0.0) == (0, 0)


def test_joint_mode_rule_is_the_product_of_the_axial_margins() -> None:
    assert outside_product_mode(1, 0, 0, 0)
    assert not outside_product_mode(2, -1, 2, -1)


def test_linkage_groups_a_block_the_definition_order_splits() -> None:
    rho = np.eye(4)
    rho[0, 2] = rho[2, 0] = 0.91
    rho[0, 3] = rho[3, 0] = 0.86
    rho[2, 3] = rho[3, 2] = 0.82
    pair_n = np.full((4, 4), 40)
    distance = _distance(rho, pair_n)
    order = average_linkage_order(distance)
    block = _new_block(order, rho, pair_n)
    assert set(block) == {0, 2, 3}


def test_linkage_does_not_call_a_definition_order_block_useful() -> None:
    rho = np.eye(4)
    rho[0, 1] = rho[1, 0] = 0.9
    rho[0, 2] = rho[2, 0] = 0.88
    rho[1, 2] = rho[2, 1] = 0.84
    pair_n = np.full((4, 4), 40)
    order = average_linkage_order(_distance(rho, pair_n))
    assert _new_block(order, rho, pair_n) == ()


def test_state_day_usefulness_uses_the_frozen_thresholds() -> None:
    states = list(CENSUS_REGIONS)[:12]
    rows = []
    for day in range(1, 32):
        for index, state in enumerate(states):
            rows.append(
                {
                    "STATE": state,
                    "DAY": date(2025, 1, day),
                    "MEAN_VALUE": ((index + day) % 12) * 1.2 + day * 0.25,
                    "N": 20,
                }
            )
    found = _time(rows)
    assert found.estimable
    assert found.useful
    assert found.wide_days >= 15
    assert found.national_range is not None
    assert found.national_range > 5
    assert len(found.coldest_states) >= 3


def test_one_climate_day_is_not_a_county_time_panel() -> None:
    found = _time([{"STATE": "AL", "DAY": date(2025, 1, 1), "MEAN_VALUE": 1.0, "N": 40}])
    assert not found.estimable
    assert not found.useful
    assert "two distinct" in found.reason


def test_a_small_state_day_is_suppressed_and_a_large_zero_is_kept() -> None:
    small = prepare_eda_metric(
        EdaMetric(
            metric_name="state_day_tavg_c",
            n_underlying=4,
            metric_value=1.2,
            geography_type="state",
            geography_id="WY",
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 1),
            unit="celsius",
        )
    )
    assert small.is_suppressed
    assert small.metric_value is None
    kept = prepare_eda_metric(
        EdaMetric(
            metric_name="hex_overflow_n",
            n_underlying=3144,
            metric_value=0,
            geography_type="national",
            geography_id="US",
            unit="counties",
        )
    )
    assert not kept.is_suppressed
    assert kept.metric_value == 0


def test_sql_reuses_the_climate_helpers_and_skips_history() -> None:
    text = SQL_PATH.read_text(encoding="utf-8")
    queries = load_visual_queries(text)
    assert set(queries) == {
        "release_identity",
        "cohort_rows",
        "climate_means",
        "state_day_temperature",
    }
    upper = text.upper()
    assert "CDC_HISTORICAL" not in upper
    assert "GEOMETRY" not in upper
    assert "PART_TEXT" not in upper
    assert "DELETE" not in upper
    assert "PAYLOAD" not in upper


def test_empty_climate_cohort_stops_when_no_chart_is_estimable() -> None:
    counties = (
        _county("01001", "Autauga", "AL", HUMAN_PUBLISHED, in_scope=True),
        _county("01003", "Baldwin", "AL", HUMAN_NONE, in_scope=True),
        _county("02013", "Aleutians East", "AK", HUMAN_NONE, in_scope=False, tick="Unknown"),
    )
    result = analyze(
        counties,
        [],
        [{"STATE": "AL", "DAY": date(2025, 1, 1), "MEAN_VALUE": -1.0, "N": 20}],
    )
    assert result.disposition == "stop"
    assert not result.importance_estimable
    assert not result.hexbin.estimable
    assert not result.heatmap.estimable
    assert not result.time.estimable
    comment = render_comment(
        result,
        run_id="117-visual-diagnostics-20261026T0000Z",
        git_commit="abc1234",
        row_counts={"REGISTRY.RUNS": 0},
        drive_lines="pending",
    )
    assert "01001" not in comment
    assert "not estimable" in comment
    for finding in lab_findings(result):
        prepare_finding(finding, finding_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def test_hexbin_below_500_counties_is_not_estimable() -> None:
    counties = (
        _county("01001", "Autauga", "AL", HUMAN_PUBLISHED, in_scope=True),
        _county("01003", "Baldwin", "AL", HUMAN_NONE, in_scope=True),
        _county("02013", "Aleutians East", "AK", HUMAN_NONE, in_scope=False, tick="Unknown"),
    )
    means = []
    for county in counties[:2]:
        means.append(
            {
                "COUNTY_FIPS": county.fips,
                "MEASURE_ID": "nclimgrid_tavg_county_day",
                "MEAN_VALUE": 1.0,
                "N": 31,
            }
        )
        means.append(
            {
                "COUNTY_FIPS": county.fips,
                "MEASURE_ID": "nclimgrid_prcp_county_day",
                "MEAN_VALUE": 1.0,
                "N": 31,
            }
        )
    found = _hexbin(counties, _days(means))
    assert not found.estimable
    assert "500" in found.reason


def test_heatmap_on_a_short_cohort_has_no_publishable_pair() -> None:
    counties = (
        _county(f"{index:05d}", f"County {index}", "AL", HUMAN_PUBLISHED, in_scope=True)
        for index in range(1, 6)
    )
    found = _heatmap(tuple(counties))
    assert not found.estimable
    assert not found.useful


def test_unknown_state_stops() -> None:
    with pytest.raises(VisualDiagnosticsError, match="Census"):
        _time([{"STATE": "ZZ", "DAY": "2025-01-01", "MEAN_VALUE": 0.0, "N": 20}])


def _distance(rho: np.ndarray, pair_n: np.ndarray) -> np.ndarray:
    distance = np.ones_like(rho, dtype=float)
    np.fill_diagonal(distance, 0.0)
    width = rho.shape[0]
    for left in range(width):
        for right in range(left + 1, width):
            if pair_n[left, right] >= 11:
                distance[left, right] = distance[right, left] = 1.0 - abs(float(rho[left, right]))
    return distance


def _days(rows: list[dict[str, object]]) -> dict[str, dict[str, tuple[float, int]]]:
    return _climate_days(rows)


def _county(
    fips: str,
    name: str,
    state: str,
    human: str,
    *,
    in_scope: bool,
    tick: str = "Established",
    pathogen: str = "Present",
) -> County:
    return County(
        fips=fips,
        name=name,
        state=state,
        population=20_000.0,
        svi=0.4,
        uninsured=0.3,
        rucc=4,
        human=human,
        tick=tick,
        pathogen=pathogen if in_scope else "Unknown",
        in_scope=in_scope,
    )
