"""Synthetic publication profiles exercise safety, never supply real cohort N."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.eda62_availability import audit_profile  # noqa: E402


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
    assert result["execution_status"] == "ACCESS_BLOCKED"
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
