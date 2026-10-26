"""Offline tests for the issue 190 within-state documentation scores."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lyme_gap_atlas_ml.class_anomaly import MAD_SCALE, Z_FLAG
from lyme_gap_atlas_ml.coverage_audit import PINNED_RELEASE_ID
from lyme_gap_atlas_ml.doc_outliers import (
    MIN_STATE,
    PRIMARY_SEED,
    SECOND_SEED,
    County,
    DocOutlierError,
    _apply_cap,
    _cap,
    _capped_forest,
    _column_z,
    _spearman,
    lab_metrics,
    load_doc_queries,
    parse_counties,
    release_gate,
    score_counties,
)
from lyme_gap_atlas_ml.state_regimes import HUMAN_NONE, HUMAN_PUBLISHED

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "sql/validation/190_doc_outliers.sql").read_text(encoding="utf-8")


def _county(index: int, state: str = "TX", **overrides: object) -> County:
    values: dict[str, object] = {
        "fips": f"{index:05d}",
        "name": f"County {index}",
        "state": state,
        "population": 20_000.0 + index * 100,
        "svi": 0.2 + (index % 7) * 0.1,
        "uninsured": 0.15 + (index % 5) * 0.05,
        "rucc": (index % 9) + 1,
        "human_status": HUMAN_NONE,
        "scapularis": "No records",
        "pacificus": "No records",
        "burgdorferi": "No records",
        "tick_status": "No records",
    }
    values.update(overrides)
    return County(**values)  # type: ignore[arg-type]


def test_release_gate_accepts_the_pin() -> None:
    release_gate(
        {
            "RELEASE_ID": PINNED_RELEASE_ID,
            "SCHEMA_VERSION": "2.0.0",
            "METHODOLOGY_VERSION": "semantic-2.0.0",
            "SCOPE": "US_COUNTIES",
            "BUNDLE_SHA256": "53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d",
        }
    )


def test_sql_selects_only_the_frozen_columns() -> None:
    queries = load_doc_queries(SQL)
    county_sql = queries["county_rows"].upper()
    assert "SCAPULARIS_STATUS" in county_sql
    assert "PACIFICUS_STATUS" in county_sql
    assert "BURGDORFERI_STATUS" in county_sql
    for banned in (
        "CASE_COUNT_FLOOR_2023",
        "INCIDENCE_FLOOR_2023",
        "EVIDENCE_COMPLETENESS",
        "GEOMETRY_JSON",
        "PAYLOAD",
        "PART_TEXT",
    ):
        assert banned not in county_sql
    assert "GAP_COMMUNITY_ASSIGNMENTS_120" in queries["gap_clusters"]


def test_robust_z_matches_the_113_scale() -> None:
    values = np.array([1.0, 2.0, 3.0, 4.0, 20.0])
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    z_values = _column_z(values, fallback=False)
    assert z_values is not None
    assert z_values[-1] == pytest.approx((20.0 - median) / (MAD_SCALE * mad))
    assert Z_FLAG == 3.5


def test_even_indicator_stays_below_the_cutoff() -> None:
    values = np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0])
    z_values = _column_z(values, fallback=False)
    assert z_values is not None
    assert float(np.max(np.abs(z_values))) == pytest.approx(1.0 / MAD_SCALE)
    assert float(np.max(np.abs(z_values))) < Z_FLAG
    rare = np.array([0.0] * 11 + [1.0])
    assert _column_z(rare, fallback=False) is None
    fallback = _column_z(rare, fallback=True)
    assert fallback is not None
    assert float(np.max(fallback)) > Z_FLAG


def test_small_state_is_not_scored_and_cap_binds() -> None:
    small = [_county(index, state="DC") for index in range(5)]
    large = []
    for index in range(20):
        population = 10_000.0 + index * 500
        if index == 7:
            population = 5_000_000.0
        large.append(
            _county(
                100 + index,
                state="TX",
                population=population,
                svi=0.1 + index * 0.04,
                human_status=HUMAN_PUBLISHED if index < 3 else HUMAN_NONE,
                scapularis="Established" if index < 3 else "No records",
                tick_status="Established" if index < 3 else "No records",
                burgdorferi="Present" if index == 1 else "No records",
            )
        )
    analysis = score_counties([*small, *large])
    assert all(not row.scored for row in analysis.rows if row.state == "DC")
    assert analysis.below_11_states == 1
    texas = [row for row in analysis.rows if row.state == "TX" and row.flag_robust_z]
    assert len(texas) <= _cap(20)
    assert _cap(20) == 1
    assert analysis.rows[0].situation_121
    metrics = lab_metrics(analysis)
    assert all("auc" not in metric.metric_name.lower() for metric in metrics)


def test_cap_keeps_the_highest_score() -> None:
    scores = np.array([1.0, 9.0, 8.0, 7.0])
    eligible = np.array([True, True, True, False])
    assert _apply_cap(["00002", "00001", "00003", "00004"], scores, eligible, 1) == ["00001"]


def test_forest_seeds_change_the_scores() -> None:
    generator = np.random.default_rng(0)
    columns = {f"feature_{index}": generator.normal(size=40) for index in range(6)}
    columns["feature_0"] = columns["feature_0"].copy()
    columns["feature_0"][:4] += 4.0
    fips = [f"{index:05d}" for index in range(40)]
    left, _left_flags = _capped_forest(columns, fips, 2, PRIMARY_SEED)
    right, _right_flags = _capped_forest(columns, fips, 2, SECOND_SEED)
    assert left is not None and right is not None
    spearman = _spearman(left, right)
    assert spearman is not None
    assert spearman < 0.999


def test_unexpected_status_stops() -> None:
    row = {
        "FIPS": "01001",
        "COUNTY": "Autauga",
        "STATE": "AL",
        "RELEASE_ID": PINNED_RELEASE_ID,
        "POPULATION": 100.0,
        "SVI_PERCENTILE": 0.2,
        "UNINSURED_PERCENTILE": 0.2,
        "RUCC_2023": 2,
        "HUMAN_STATUS": "published_count_floor",
        "SCAPULARIS_STATUS": "Absent",
        "PACIFICUS_STATUS": "No records",
        "BURGDORFERI_STATUS": "No records",
        "TICK_STATUS": "No records",
    }
    with pytest.raises(DocOutlierError, match="scapularis"):
        parse_counties([row], release_id=PINNED_RELEASE_ID, enforce_gate=False)


def test_situation_predicate_matches_121() -> None:
    county = _county(
        1,
        human_status=HUMAN_NONE,
        tick_status="Established",
        burgdorferi="Present",
    )
    labels = score_counties([county] + [_county(index + 2, state="AL") for index in range(11)])
    matched = next(row for row in labels.rows if row.fips == "00001")
    assert "double_gap" in matched.situation_121
    assert "wider_gap" in matched.situation_121
    assert MIN_STATE == 11
