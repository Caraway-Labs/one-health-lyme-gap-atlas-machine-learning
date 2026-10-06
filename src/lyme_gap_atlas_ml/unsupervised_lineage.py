"""Versioned unlabeled lineage companion to supervised declarative v1."""

from __future__ import annotations

import re
from typing import Any

from lyme_gap_atlas_ml.contracts import ContractError

SCHEMA = "atlas-ml-contracts/v2"
SHA = re.compile(r"[0-9a-f]{40}")


def validate_tier1_lineage(value: Any) -> dict[str, Any]:
    """Validate only the identities required for the approved unsupervised run.

    Supervised v1 keeps its required label and holdout fields in contracts.py.
    This v2 shape has no label, target, split or holdout fields to populate.
    """
    if not isinstance(value, dict) or set(value) != {
        "schema",
        "supervision_mode",
        "model_version",
        "feature_set_version",
        "evaluation_version",
        "tier_policy_version",
        "release_id",
        "bundle_sha256",
        "source_commit",
        "prediction_batch_version",
        "generated_at_utc",
        "output_sha256",
        "row_count",
        "intended_use_ref",
    }:
        raise ContractError("unsupervised lineage: missing or unknown fields")
    if value["schema"] != SCHEMA or value["supervision_mode"] != "unsupervised":
        raise ContractError("unsupervised lineage: schema or mode mismatch")
    from lyme_gap_atlas_ml import tier1_features, tier1_selection
    from lyme_gap_atlas_ml.tier1_persisted import EVALUATION_VERSION, LIMITATION_REF, batch_id

    expected = {
        "model_version": tier1_selection.SELECTED_MODEL_VERSION,
        "feature_set_version": tier1_features.VERSION,
        "evaluation_version": EVALUATION_VERSION,
        "tier_policy_version": tier1_selection.TIER_POLICY_VERSION,
        "release_id": tier1_features.RELEASE_ID,
        "bundle_sha256": tier1_features.BUNDLE_SHA256,
        "intended_use_ref": LIMITATION_REF,
        "row_count": 3144,
    }
    if any(value[key] != expected_value for key, expected_value in expected.items()):
        raise ContractError("unsupervised lineage: incompatible selected identity")
    if not isinstance(value["source_commit"], str) or not SHA.fullmatch(value["source_commit"]):
        raise ContractError("unsupervised lineage: invalid source commit")
    if value["prediction_batch_version"] != batch_id(value["source_commit"]):
        raise ContractError("unsupervised lineage: batch identity mismatch")
    if not isinstance(value["output_sha256"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", value["output_sha256"]
    ):
        raise ContractError("unsupervised lineage: invalid output digest")
    if not isinstance(value["generated_at_utc"], str) or not value["generated_at_utc"].endswith(
        "Z"
    ):
        raise ContractError("unsupervised lineage: UTC timestamp required")
    return value
