"""Synthetic publication profiles exercise safety, never supply real cohort N."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.eda62_availability import audit_atlas_screen, audit_profile  # noqa: E402


def profile(measure: str) -> dict[str, object]:
    return {
        "RELEASE_VERSION": "fictional-test-only",
        "MEASURE_ID": measure,
        "SOURCE_KEY": "fictional",
        "OBSERVATION_ROWS": 2,
        "UNIQUE_COUNTIES": 2,
    }


def test_unpublished_is_access_blocker_not_negative_or_scientific_stop() -> None:
    result = audit_profile([profile("human_status")])
    assert result["execution_status"] == "VIEW_EXCLUDES_INPUTS"
    assert result["scientific_disposition"] is None
    assert result["group_n"] == {"ESTABLISHED": None, "REPORTED": None}
    assert result["effect"] is None
    assert result["selected_taxon"] is None


def test_publication_never_substitutes_for_eligibility() -> None:
    result = audit_profile(
        [profile("scapularis_status"), profile("pacificus_status"), profile("svi_percentile_2022")]
    )
    assert result["execution_status"] == "ELIGIBILITY_NOT_SCREENED"
    assert result["outcome_statistics_inspected"] is False
    assert result["group_n"]["ESTABLISHED"] is None


def test_one_taxon_is_enough_to_propose_screening() -> None:
    result = audit_profile([profile("scapularis_status"), profile("svi_percentile_2022")])
    assert result["execution_status"] == "ELIGIBILITY_NOT_SCREENED"


@pytest.mark.parametrize("rows", [[], [profile("human_status")] * 10])
def test_ambiguous_shape_rejected(rows: list[dict[str, object]]) -> None:
    with pytest.raises(ValueError):
        audit_profile(rows)


def test_mixed_release_and_duplicates_rejected() -> None:
    a, b = profile("human_status"), profile("other")
    b["RELEASE_VERSION"] = "another-release"
    with pytest.raises(ValueError, match="one immutable"):
        audit_profile([a, b])
    with pytest.raises(ValueError, match="Duplicate"):
        audit_profile([a, a])


@pytest.mark.parametrize("count", [-1, 3, True, "2"])
def test_invalid_count_rejected(count: object) -> None:
    row = profile("human_status")
    row["UNIQUE_COUNTIES"] = count
    with pytest.raises(ValueError, match="counts"):
        audit_profile([row])


def atlas_row(taxon: str, status: str = "Unknown") -> dict[str, object]:
    return {
        "RELEASE_ID": "fictional-test-only",
        "TAXON_FIELD": taxon,
        "SOURCE_STATUS": status,
        "COUNTY_ROWS": 2,
        "UNIQUE_COUNTIES": 2,
        "UNIQUE_STATES": 1,
        "INVALID_FIPS": 0,
        "SVI_NULL": 0,
        "SVI_INVALID_DOMAIN": 0,
    }


def test_complete_unknown_is_no_positive_contrast_in_this_release_only() -> None:
    result = audit_atlas_screen([atlas_row("SCAPULARIS_STATUS"), atlas_row("PACIFICUS_STATUS")])
    assert result["execution_status"] == "NO_POSITIVE_CONTRAST"
    assert result["positive_group_n_by_taxon"]["SCAPULARIS_STATUS"] == {
        "ESTABLISHED": 0,
        "REPORTED": 0,
    }
    assert result["source_authority_verified"] is False
    assert result["selected_taxon"] is None


def test_partial_unknown_does_not_establish_all_taxa_ineligible() -> None:
    result = audit_atlas_screen([atlas_row("SCAPULARIS_STATUS")])
    assert result["execution_status"] == "SCREENING_PENDING"
    assert result["positive_group_n_by_taxon"] is None


def test_positive_visibility_does_not_grant_scientific_admission() -> None:
    result = audit_atlas_screen(
        [
            atlas_row("SCAPULARIS_STATUS", "Established"),
            atlas_row("PACIFICUS_STATUS"),
        ]
    )
    assert result["execution_status"] == "SCREENING_PENDING"
    assert result["scientific_disposition_for_this_release"] is None
    assert result["source_authority_verified"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("UNIQUE_COUNTIES", 1),
        ("INVALID_FIPS", 1),
        ("SVI_NULL", -1),
        ("UNIQUE_STATES", 3),
    ],
)
def test_atlas_invalid_aggregate_rejected(field: str, value: int) -> None:
    row = atlas_row("SCAPULARIS_STATUS")
    row[field] = value
    with pytest.raises(ValueError):
        audit_atlas_screen([row])


def test_atlas_mixed_releases_rejected() -> None:
    a, b = atlas_row("SCAPULARIS_STATUS"), atlas_row("PACIFICUS_STATUS")
    b["RELEASE_ID"] = "another"
    with pytest.raises(ValueError):
        audit_atlas_screen([a, b])


def test_atlas_duplicate_status_rejected() -> None:
    row = atlas_row("SCAPULARIS_STATUS")
    with pytest.raises(ValueError):
        audit_atlas_screen([row, row])
