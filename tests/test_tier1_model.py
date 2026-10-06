"""Contract and deterministic checks for the bounded Tier 1 candidates."""

from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from lyme_gap_atlas_ml import tier1_features as features
from lyme_gap_atlas_ml import tier1_model as model


def rows() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for index in range(9):
        human = int(index % 3 != 0)
        pathogen = index % 3
        result.append(
            {
                "county_fips": f"{index:05d}",
                "human_published_floor": human,
                "human_case_count_floor_log1p": float(index + 1) if human else 0.0,
                "pathogen_present": int(pathogen == 0),
                "pathogen_no_records": int(pathogen == 1),
                "pathogen_unknown": int(pathogen == 2),
                "svi_percentile_2022": index / 8,
                "human_evidence_state": (
                    "published_count_floor" if human else "no_county_linked_record"
                ),
                "pathogen_evidence_state": ("Present", "No records", "Unknown")[pathogen],
                "vector_evidence_state": "Unknown",
                "rucc_2023_context": index % 9 + 1,
                "feature_evidence_state": "PARTIAL" if not human or pathogen == 2 else "OBSERVED",
                "feature_set_version": features.VERSION,
                "release_id": features.RELEASE_ID,
                "bundle_sha256": features.BUNDLE_SHA256,
                "priority_tier": "HIGH",
                "county_review_priority": 999,
                "supervised_label": 1,
            }
        )
    return result


def test_models_are_deterministic_and_context_cannot_train() -> None:
    source = rows()
    first, forest = model.score(source, "run")
    second, _ = model.score(source, "run")
    assert first == second
    assert forest.n_features_in_ == len(features.FEATURE_COLUMNS) == 6
    assert model._validated_matrix(source).shape == (9, 6)
    assert all(0 <= item["anomaly_percentile"] <= 100 for item in first)
    assert all(item["model_config_version"] == item["method"] for item in first)
    assert (
        max(item["raw_anomaly_score"] for item in first if item["method"] == model.FOREST_VERSION)
        > 0
    )
    changed = deepcopy(source)
    for item in changed:
        item["priority_tier"] = "LOW"
        item["county_review_priority"] = -1
        item["supervised_label"] = 0
        item["rucc_2023_context"] = 99
    assert model.score(changed, "run")[0] == [{**item, "rucc_2023_context": 99} for item in first]


@pytest.mark.parametrize("mutation", ["duplicate", "release", "feature", "placeholder"])
def test_invalid_matrix_fails_closed(mutation: str) -> None:
    source = rows()
    if mutation == "duplicate":
        source[1]["county_fips"] = source[0]["county_fips"]
    elif mutation == "release":
        source[0]["bundle_sha256"] = "wrong"
    elif mutation == "feature":
        source[0]["feature_set_version"] = "wrong"
    else:
        source[0]["human_case_count_floor_log1p"] = 1.0
    with pytest.raises(ValueError):
        model.score(source, "run")


def test_reference_and_percentiles() -> None:
    matrix = model._validated_matrix(rows())
    assert np.array_equal(model._reference(matrix), model._reference(matrix))
    assert model._percentiles(np.array([2.0, 1.0, 2.0])).tolist() == [75.0, 0.0, 75.0]
