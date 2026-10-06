"""Versioned Tier 1 surveillance-review selection and batch-relative tier policy."""

from __future__ import annotations

from typing import Any

from lyme_gap_atlas_ml import tier1_model

SELECTED_MODEL_VERSION = tier1_model.REFERENCE_VERSION
REJECTED_MODEL_VERSION = tier1_model.FOREST_VERSION
TIER_POLICY_VERSION = "tier1-review-percentile-v1"
HIGH_PERCENTILE = 90.0
MEDIUM_PERCENTILE = 70.0
INTENDED_USE = "Unusual county surveillance/evidence profile for epidemiologist review"
PROHIBITED_USE = "Not disease risk, incidence, diagnosis, or a calibrated probability"


def classify(row: dict[str, Any]) -> dict[str, Any]:
    """Attach independent review tier and evidence sufficiency to a selected score."""
    if row["method"] != SELECTED_MODEL_VERSION:
        raise ValueError("Only the selected Tier 1 model can receive this tier policy")
    percentile = float(row["anomaly_percentile"])
    if not 0 <= percentile <= 100:
        raise ValueError("Percentile must be within [0, 100]")
    state = row["feature_evidence_state"]
    if state not in ("OBSERVED", "PARTIAL"):
        raise ValueError("Unscorable evidence state cannot receive a tier")
    tier = (
        "HIGH"
        if percentile >= HIGH_PERCENTILE
        else ("MEDIUM" if percentile >= MEDIUM_PERCENTILE else "LOW")
    )
    return {
        **row,
        "priority_tier": tier,
        "tier_policy_version": TIER_POLICY_VERSION,
        "evidence_sufficiency": "SUFFICIENT" if state == "OBSERVED" else "INSUFFICIENT",
    }
