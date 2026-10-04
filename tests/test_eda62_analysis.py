"""Fictional unit tests, never real EDA cohorts or scientific admission."""

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.eda62_analysis import (  # noqa: E402
    analyze_selected,
    category,
    clustered_interval,
    describe,
    distribution_descriptors,
    interval_category_supported,
    mann_whitney,
    screen_taxa,
    superiority,
)


def fictional_rows(per_group: int = 3) -> list[dict[str, object]]:
    rows = []
    for state in range(1, 11):
        for county in range(2 * per_group):
            established = county < per_group
            rows.append(
                {
                    "fips": f"{state:02d}{county + 1:03d}",
                    "scapularis_status": "Established" if established else "Reported",
                    "pacificus_status": "Unknown",
                    "svi_percentile": 0.8 if established else 0.2,
                }
            )
    return rows


def test_review_counterexample_rank_neutral_is_not_distribution_equivalence() -> None:
    a, b = [0.1, 0.9], [0.4, 0.6]
    assert superiority(a, b) == 0.5
    assert category(0.5) == "NO_MEANINGFUL_DIRECTIONAL_RANK_DIFFERENCE"
    assert describe(a)["iqr"] > describe(b)["iqr"]
    assert distribution_descriptors(a, b)["empirical_cdf_max_distance"] == 0.5


def test_ties_and_direction_against_explicit_pair_enumeration() -> None:
    a, b = [0.1, 0.5, 0.5, 0.9], [0.2, 0.5, 0.8]
    expected = sum(float(x > y) + 0.5 * float(x == y) for x in a for y in b) / 12
    assert superiority(a, b) == expected
    assert superiority(b, a) == pytest.approx(1 - expected)


def test_mann_whitney_normal_variance_tie_and_continuity_calculation() -> None:
    result = mann_whitney([1.0, 2.0], [2.0, 3.0])
    assert result["u_established"] == 0.5
    assert result["p_two_sided_county_independence_only"] == pytest.approx(
        math.erfc(1 / math.sqrt(3))
    )
    assert mann_whitney([0.5] * 30, [0.5] * 30)["p_two_sided_county_independence_only"] == 1


def test_screen_never_reads_svi_and_never_makes_unknown_a_negative() -> None:
    class OutcomeGuard(dict):
        def get(self, key: str, default: object = None) -> object:
            if key == "svi_percentile":
                raise AssertionError("Outcome inspected during taxon screening")
            return super().get(key, default)

    rows = [OutcomeGuard(row) for row in fictional_rows()]
    screen = screen_taxa(rows)
    assert screen["selected_taxon"] == "scapularis_status"
    assert screen["source_state_county_n"]["pacificus_status"] == {"Unknown": 60}
    assert screen["outcomes_inspected"] is False


def test_deterministic_cluster_effect_and_ancillary_p_value_labels() -> None:
    rows = fictional_rows()
    first = analyze_selected(rows, "scapularis_status")
    second = analyze_selected(rows, "scapularis_status")
    assert first == second
    assert first["superiority"] == 1
    assert first["uncertainty"]["interval"] == [1, 1]
    assert first["uncertainty"]["valid_draws"] == 2000
    assert first["category_supported_by_interval_and_sensitivity"] is True
    assert first["source_authority_verified_by_statistics"] is False
    assert "not adjusted" in first["mann_whitney"]["p_interpretation"]


def test_too_few_states_blocks_inference_even_with_large_county_n() -> None:
    assert clustered_interval({"01": ([0.8] * 30, [0.2] * 30)})["interval"] is None
    groups = {str(i): ([0.8] * 30, []) for i in range(10)}
    groups["0"] = ([0.8] * 30, [0.2] * 30)
    assert clustered_interval(groups)["status"] == "NOT_ESTIMABLE"


def test_missing_outcomes_cannot_trigger_taxon_switch() -> None:
    rows = fictional_rows()
    for row in rows:
        row["pacificus_status"] = row["scapularis_status"]
        if row["scapularis_status"] == "Established":
            row["svi_percentile"] = None
    assert screen_taxa(rows)["selected_taxon"] == "scapularis_status"
    result = analyze_selected(rows, "scapularis_status")
    assert result["status"] == "NOT_ESTIMABLE"
    assert result["complete_county_n"] == {"ESTABLISHED": 0, "REPORTED": 30}
    assert result["exclusions"]["svi_missing"] == 30
    with pytest.raises(ValueError, match="preregistered"):
        analyze_selected(rows, "pacificus_status")


def test_zero_outcome_is_retained() -> None:
    rows = fictional_rows()
    for row in rows:
        row["svi_percentile"] = 0
    result = analyze_selected(rows, "scapularis_status")
    assert result["complete_county_n"] == {"ESTABLISHED": 30, "REPORTED": 30}
    assert result["superiority"] == 0.5
    assert result["exclusions"] == {}


def test_duplicate_and_conflicting_units_rejected() -> None:
    rows = fictional_rows()
    duplicate = dict(rows[0])
    duplicate["scapularis_status"] = "Reported"
    with pytest.raises(ValueError, match="Duplicate"):
        screen_taxa([*rows, duplicate])


@pytest.mark.parametrize("invalid", [-999, 1.1, float("nan"), True, "0.5"])
def test_invalid_svi_is_excluded_not_zero(invalid: object) -> None:
    rows = fictional_rows(per_group=4)
    rows[0]["svi_percentile"] = invalid
    result = analyze_selected(rows, "scapularis_status")
    assert result["complete_county_n"]["ESTABLISHED"] == 39
    assert result["exclusions"]["svi_invalid"] == 1


def test_category_uncertainty_must_check_interval_interior() -> None:
    assert category(0.35) == category(0.65) == "MATERIAL_DIFFERENCE"
    assert interval_category_supported([0.35, 0.65], "MATERIAL_DIFFERENCE") is False
    assert interval_category_supported([0.46, 0.54], category(0.5)) is True


def test_dominance_leave_out_and_within_state_descriptors() -> None:
    rows = fictional_rows(per_group=18)
    rows = [
        row
        for row in rows
        if row["fips"].startswith("01")
        or int(row["fips"][2:]) <= 2
        or 19 <= int(row["fips"][2:]) <= 20
    ]
    result = analyze_selected(rows, "scapularis_status")
    assert result["dominant_states"] == ["01"]
    assert result["leave_dominant_state_out"]["01"]["category_retained"] is False
    assert result["category_supported_by_interval_and_sensitivity"] is False
    assert result["within_state_descriptive"]["01"]["superiority"] == 1


def test_invalid_fips_excluded_with_explicit_count() -> None:
    rows = fictional_rows()
    result = screen_taxa([*rows, {"fips": "bad", "scapularis_status": "Reported"}])
    assert result["invalid_fips_excluded"] == 1
    assert result["unique_valid_fips"] == 60


def test_release_analysis_row_bound_is_enforced() -> None:
    with pytest.raises(ValueError, match="analysis bound"):
        screen_taxa([{"fips": "fictional"}] * 3145)
