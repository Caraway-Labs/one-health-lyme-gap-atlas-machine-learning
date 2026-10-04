"""Synthetic tests only; these counts are never empirical cohort evidence."""

import math

import pytest

from lyme_gap_atlas_ml.evidence_association_65 import (
    _cluster_interval,
    analyze_counties,
    fixed_margin_exact,
    table_statistics,
    vector_state,
)


def fixture_rows():
    return [
        {
            "RELEASE_ID": "fixture-release",
            "FIPS": f"{i:05d}",
            "IN_CONTIGUOUS_TICK_SCOPE": True,
            "SCAPULARIS_STATUS": "Unknown",
            "PACIFICUS_STATUS": "Unknown",
            "BURGDORFERI_STATUS": "No records",
        }
        for i in range(3144)
    ]


def test_unknown_is_not_negative_even_with_other_species_positive():
    assert vector_state("Established", "Unknown") is None
    assert vector_state("Reported", "No records") == "Reported"
    assert vector_state("No records", "No records") == "No records"
    assert vector_state("Reported", "Established") == "Established"
    with pytest.raises(ValueError, match="unrecognized"):
        vector_state("Negative", "No records")


def test_exclusion_overlap_and_source_records_are_not_county_n():
    rows = fixture_rows()
    rows[0].update(
        SCAPULARIS_STATUS="Established", PACIFICUS_STATUS="No records", BURGDORFERI_STATUS="Present"
    )
    rows[1].update(BURGDORFERI_STATUS="Unknown")
    rows[2].update(IN_CONTIGUOUS_TICK_SCOPE=False)
    rows[3].update(IN_CONTIGUOUS_TICK_SCOPE=None)
    result = analyze_counties(rows, "fixture-release")
    assert result["unique_counties"] == 3144
    assert result["source_observation_rows"] is None
    assert result["exclusions"]["unknown_union_in_scope"] == 3141
    assert result["exclusions"]["both_unknown_in_scope"] == 1
    assert result["exclusions"]["out_of_scope"] == 1
    assert result["exclusions"]["missing_scope"] == 1
    assert result["primary"]["n"] == 1
    assert result["primary"]["v"] is None  # one occupied category is not V=0
    assert result["disposition"] == "NOT_ESTIMABLE"


@pytest.mark.parametrize(
    "field,value",
    [
        ("FIPS", "00000"),
        ("RELEASE_ID", "other"),
        ("SCAPULARIS_STATUS", "Absent"),
        ("IN_CONTIGUOUS_TICK_SCOPE", 1),
    ],
)
def test_bad_identity_or_categories_fail_closed(field, value):
    rows = fixture_rows()
    rows[1][field] = value
    with pytest.raises(ValueError):
        analyze_counties(rows, "fixture-release")


def test_all_unknown_fixture_has_zero_eligible_not_zero_effect():
    result = analyze_counties(fixture_rows(), "fixture-release")
    assert result["primary"]["n"] == 0
    assert result["primary"]["v"] is None
    assert result["sensitivity"]["v"] is None
    assert result["primary_state_robustness"]["interval"] is None


def test_fisher_known_reference_and_work_cap():
    assert fixed_margin_exact([[1, 9], [11, 3]]) == pytest.approx(0.0027594561852200836)
    assert fixed_margin_exact([[1, 9], [11, 3]], cap=1) is None
    assert fixed_margin_exact([[1, 1], [1, 1], [1, 1]]) == pytest.approx(1)
    assert fixed_margin_exact([[0, 2], [1, 1], [2, 0]]) == pytest.approx(0.6)
    stats = table_statistics([[0, 1], [1, 0], [1, 0]])
    assert stats["method"] == "fixed-margin exact IID reference"
    assert stats["iid_reference_p"] == pytest.approx(1)


def test_effect_chisquare_and_empty_margin():
    stats = table_statistics([[20, 0], [0, 20], [0, 0]])
    assert stats["active_rows"] == [0, 1]
    assert stats["v"] == pytest.approx(1)
    assert stats["chi2"] == pytest.approx(40)
    assert stats["iid_reference_p"] == pytest.approx(math.erfc(math.sqrt(20)))
    assert table_statistics([[5, 5], [5, 5]])["v"] == pytest.approx(0)
    with pytest.raises(ValueError):
        table_statistics([[-1, 2], [1, 0]])


def test_state_robustness_is_deterministic_and_rejects_degenerate_resamples():
    balanced = {str(i): [[8, 2], [2, 8]] for i in range(10)}
    result = _cluster_interval(balanced)
    assert result == _cluster_interval(balanced)
    assert result["failed_replicates"] == 0
    assert result["interval"] == pytest.approx([0.6, 0.6])
    constant = {str(i): [[10, 0], [0, 0]] for i in range(10)}
    assert _cluster_interval(constant)["interval"] is None
    assert _cluster_interval(constant)["failed_replicates"] == 2000
