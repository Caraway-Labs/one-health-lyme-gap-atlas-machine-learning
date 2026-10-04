"""Synthetic mathematical counterexamples only; never real cohort counts."""

import math

import pytest

from lyme_gap_atlas_ml.paired_change import (
    CountInterval,
    PairCoverage,
    identify_change,
    summarize_publisher_coverage,
)


@pytest.mark.parametrize("floors", [(0, 0), (0, 1000), (1000, 0), (5, 6)])
def test_two_unknown_upper_bounds_allow_both_directions(floors: tuple[int, int]) -> None:
    result = identify_change(CountInterval(floors[0], None), CountInterval(floors[1], None))
    assert (result.lower, result.upper) == (-math.inf, math.inf)
    assert result.direction == "NOT_IDENTIFIED"
    assert not result.exact_magnitude


def test_finite_separated_bounds_identify_sign_but_not_exact_effect() -> None:
    result = identify_change(CountInterval(1, 3), CountInterval(5, 8))
    assert (result.lower, result.upper, result.direction) == (2, 7, "INCREASE")
    assert not result.exact_magnitude
    assert identify_change(CountInterval(5, 8), CountInterval(1, 3)).direction == "DECREASE"


def test_exact_zero_and_overlapping_intervals_are_distinct() -> None:
    assert identify_change(CountInterval(0, 0), CountInterval(0, 0)).direction == "UNCHANGED"
    result = identify_change(CountInterval(1, 3), CountInterval(2, 4))
    assert result.direction == "NOT_IDENTIFIED"
    assert identify_change(CountInterval(2, 2), CountInterval(3, 3)).exact_magnitude


@pytest.mark.parametrize("lower,upper", [(-1, None), (math.nan, None), (1, 0), (1, math.inf)])
def test_invalid_source_bounds_fail_closed(lower: float, upper: float | None) -> None:
    with pytest.raises(ValueError):
        CountInterval(lower, upper)


def test_coverage_reconciles_missingness_without_zero_filling() -> None:
    assert PairCoverage(10, 2, 1, 3, 4).missing_either_year == 6
    with pytest.raises(ValueError):
        PairCoverage(10, 2, 1, 3, 5)
    with pytest.raises(ValueError):
        PairCoverage(1, -1, 0, 0, 2)


def test_publisher_coverage_separates_observation_rows_categories_and_missing_pairs() -> None:
    rows = [
        {"year": str(y), "fips": "01001", "case_status": status, "n": "3"}
        for y in range(2011, 2020)
        for status in ("Confirmed", "Probable")
    ]
    rows.extend(
        [
            {"year": "2011", "fips": "01003", "case_status": "Confirmed", "n": "2"},
            {"year": "2013", "fips": "01003", "case_status": "Probable", "n": "1"},
            {"year": "2011", "fips": "Suppressed", "case_status": "Confirmed", "n": "7"},
        ]
    )
    result = summarize_publisher_coverage(rows)
    primary, replication = result["windows"]
    assert primary["unique_counties"] == 2
    assert primary["published_county_years"] == 8
    assert primary["source_observation_rows"] == 46
    assert primary["contrasts"][0]["earlier_only"] == 1
    assert primary["contrasts"][3]["neither_year"] == 1
    assert primary["contrasts"][0]["both_categories_in_both_years"] == 1
    assert replication["unique_counties"] == 1
    assert len(primary["contrasts"]) == 5
    assert len(replication["contrasts"]) == 2
    with pytest.raises(ValueError, match="Duplicate"):
        summarize_publisher_coverage([*rows, rows[0]])


@pytest.mark.parametrize(
    "rows", [[], [{"year": "2022", "fips": "01001", "case_status": "Confirmed", "n": "1"}]]
)
def test_absent_or_out_of_era_publisher_inputs_do_not_become_zero_counts(
    rows: list[dict[str, str]],
) -> None:
    with pytest.raises(ValueError):
        summarize_publisher_coverage(rows)
