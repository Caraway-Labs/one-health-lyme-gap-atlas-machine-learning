"""Tier 1 selection and tier-policy guard tests."""

import pytest

from lyme_gap_atlas_ml import tier1_model, tier1_selection


def row(percentile: float, state: str = "OBSERVED") -> dict[str, object]:
    return {
        "method": tier1_selection.SELECTED_MODEL_VERSION,
        "anomaly_percentile": percentile,
        "feature_evidence_state": state,
    }


@pytest.mark.parametrize(
    ("percentile", "expected"),
    [(0, "LOW"), (69.999, "LOW"), (70, "MEDIUM"), (89.999, "MEDIUM"), (90, "HIGH"), (100, "HIGH")],
)
def test_tier_boundaries(percentile: float, expected: str) -> None:
    result = tier1_selection.classify(row(percentile))
    assert result["priority_tier"] == expected
    assert result["tier_policy_version"] == "tier1-review-percentile-v1"
    assert result["method"] == tier1_model.REFERENCE_VERSION


def test_partial_evidence_is_independent_of_priority() -> None:
    high = tier1_selection.classify(row(95, "PARTIAL"))
    low = tier1_selection.classify(row(10, "PARTIAL"))
    assert high["evidence_sufficiency"] == low["evidence_sufficiency"] == "INSUFFICIENT"
    assert high["priority_tier"] == "HIGH"
    assert low["priority_tier"] == "LOW"


def test_rejected_model_and_unscorable_state_fail_closed() -> None:
    rejected = row(95)
    rejected["method"] = tier1_model.FOREST_VERSION
    with pytest.raises(ValueError, match="selected"):
        tier1_selection.classify(rejected)
    with pytest.raises(ValueError, match="Unscorable"):
        tier1_selection.classify(row(95, "NOT_ESTIMABLE"))
    with pytest.raises(ValueError, match="Percentile"):
        tier1_selection.classify(row(float("nan")))


def test_interpretation_contract() -> None:
    assert "review" in tier1_selection.INTENDED_USE.lower()
    assert "Not disease risk" in tier1_selection.PROHIBITED_USE
