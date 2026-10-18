import pytest

from lyme_gap_atlas_ml.latent_class_inputs import (
    BUNDLE_SHA256,
    NATIONAL_COUNTY_COUNT,
    RELEASE_ID,
    LatentClassInputError,
    build_counties,
    require_national_cohort,
)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "FIPS": "09001",
        "STATE": "CT",
        "HUMAN_STATUS": "no_county_linked_record",
        "SCAPULARIS_STATUS": "No records",
        "PACIFICUS_STATUS": "Unknown",
        "BURGDORFERI_STATUS": "No records",
        "POPULATION": 50,
    }
    row.update(overrides)
    return row


def test_blanks_stay_categories_and_population_stays_out_of_the_indicators() -> None:
    county = build_counties([_row()])[0]
    assert county.estimand_a() == (
        "no_county_linked_record",
        "No records",
        "Unknown",
        "No records",
    )
    assert county.estimand_b() == ("No records", "Unknown", "No records")
    assert "50" not in county.estimand_a()
    assert county.population == 50


def test_counties_are_sorted_and_duplicate_fips_fail() -> None:
    counties = build_counties(
        [
            _row(FIPS="09003", STATE="CT"),
            _row(
                FIPS="02013", STATE="AK", SCAPULARIS_STATUS="Unknown", BURGDORFERI_STATUS="Unknown"
            ),
        ]
    )
    assert [county.fips for county in counties] == ["02013", "09003"]
    with pytest.raises(LatentClassInputError, match="duplicate"):
        build_counties([_row(), _row()])


@pytest.mark.parametrize(
    "overrides",
    [
        {"HUMAN_STATUS": None},
        {"HUMAN_STATUS": "Unknown"},
        {"SCAPULARIS_STATUS": ""},
        {"BURGDORFERI_STATUS": "Absent"},
        {"POPULATION": 0},
        {"POPULATION": True},
        {"FIPS": "9001"},
        {"STATE": "Connecticut"},
    ],
)
def test_invalid_values_fail_closed(overrides: dict[str, object]) -> None:
    with pytest.raises(LatentClassInputError):
        build_counties([_row(**overrides)])


@pytest.mark.parametrize(
    "column",
    [
        "CASE_COUNT_FLOOR_2023",
        "INCIDENCE_FLOOR_2023",
        "EVIDENCE_COMPLETENESS",
        "REVIEW_TIER",
        "NLCD_FOREST_SHARE",
    ],
)
def test_excluded_columns_are_rejected(column: str) -> None:
    with pytest.raises(LatentClassInputError, match="not an admitted"):
        build_counties([_row(**{column: 1})])


def test_national_cohort_requires_the_pinned_release_and_full_count() -> None:
    counties = build_counties([_row(FIPS=f"{number:05d}") for number in range(3)])
    with pytest.raises(LatentClassInputError, match="3144"):
        require_national_cohort(counties, release_id=RELEASE_ID, bundle_sha256=BUNDLE_SHA256)
    with pytest.raises(LatentClassInputError, match="release identity"):
        require_national_cohort(counties, release_id=RELEASE_ID, bundle_sha256="0" * 64)
    assert NATIONAL_COUNTY_COUNT == 3144
