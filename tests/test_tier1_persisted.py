"""Selected batch contract and unsupervised lineage regression checks."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import validate as validate_json_schema

from lyme_gap_atlas_ml import tier1_features, tier1_persisted, tier1_selection
from lyme_gap_atlas_ml.contracts import ContractError, validate_bundle
from lyme_gap_atlas_ml.unsupervised_lineage import SCHEMA, validate_tier1_lineage

ROOT = Path(__file__).parents[1]
COMMIT = "b94d776f8367a48153cb080027175083f5f9300b"


def test_supervised_v1_still_requires_label_fields() -> None:
    bundle = json.loads((ROOT / "config/examples/synthetic-lineage-v1.json").read_text())
    validate_bundle(bundle)
    del bundle["dataset"]["label_as_of"]
    with pytest.raises(ContractError):
        validate_bundle(bundle)


def lineage() -> dict[str, object]:
    return {
        "schema": SCHEMA,
        "supervision_mode": "unsupervised",
        "model_version": tier1_selection.SELECTED_MODEL_VERSION,
        "feature_set_version": "tier1-county-features-v1",
        "evaluation_version": tier1_persisted.EVALUATION_VERSION,
        "tier_policy_version": tier1_selection.TIER_POLICY_VERSION,
        "release_id": "governed-2026-09-17-unknown-coverage",
        "bundle_sha256": "55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233",
        "source_commit": COMMIT,
        "prediction_batch_version": tier1_persisted.batch_id(COMMIT),
        "generated_at_utc": "2026-10-06T00:00:00Z",
        "output_sha256": "a" * 64,
        "row_count": 3144,
        "intended_use_ref": tier1_persisted.LIMITATION_REF,
    }


def test_unlabeled_lineage_is_versioned_and_has_no_fabricated_label() -> None:
    value = lineage()
    assert validate_tier1_lineage(value) == value
    schema = json.loads(
        (ROOT / "docs/architecture/declarative-ml-contracts-v2.schema.json").read_text()
    )
    validate_json_schema(value, schema)
    assert not any("label" in key or "holdout" in key for key in value)
    for key, wrong in (
        ("model_version", "tier1-isolation-forest-v1"),
        ("feature_set_version", "other"),
        ("tier_policy_version", "other"),
        ("bundle_sha256", "b" * 64),
        ("source_commit", "a" * 40),
        ("prediction_batch_version", "other"),
    ):
        invalid = value | {key: wrong}
        with pytest.raises(ContractError):
            validate_tier1_lineage(invalid)


def test_prod_lineage_admits_only_pinned_versioned_snapshot() -> None:
    snapshot = tier1_features.SNAPSHOTS["prod"]
    value = lineage() | {
        "feature_set_version": snapshot.feature_version,
        "release_id": snapshot.release_id,
        "bundle_sha256": snapshot.bundle_sha256,
        "prediction_batch_version": tier1_persisted.batch_id(COMMIT, snapshot),
    }
    assert validate_tier1_lineage(value) == value
    schema = json.loads(
        (ROOT / "docs/architecture/declarative-ml-contracts-v2.schema.json").read_text()
    )
    validate_json_schema(value, schema)
    with pytest.raises(ContractError):
        validate_tier1_lineage(value | {"feature_set_version": tier1_features.VERSION})
    from jsonschema import ValidationError

    with pytest.raises(ValidationError):
        validate_json_schema(value | {"feature_set_version": tier1_features.VERSION}, schema)


def test_prod_serialization_rejects_dev_lineage_and_accepts_pinned_identity() -> None:
    snapshot = tier1_features.SNAPSHOTS["prod"]
    identity = tier1_persisted.batch_id(COMMIT, snapshot)
    rows = synthetic_complete_batch()
    for row in rows:
        row.update(
            feature_set_version=snapshot.feature_version,
            release_id=snapshot.release_id,
            bundle_sha256=snapshot.bundle_sha256,
            prediction_batch_version=identity,
            run_id=identity,
        )
    expected = synthetic_governed_fips()
    tier1_persisted.validate(rows, identity, expected_fips=expected, snapshot=snapshot)
    json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False)
    with pytest.raises(ValueError, match="lineage"):
        tier1_persisted.validate(rows, identity, expected_fips=expected)


def test_selected_policy_boundaries_and_partial_evidence() -> None:
    for percentile, expected in (
        (0, "LOW"),
        (69.999, "LOW"),
        (70, "MEDIUM"),
        (89.999, "MEDIUM"),
        (90, "HIGH"),
        (100, "HIGH"),
    ):
        row = {
            "method": tier1_selection.SELECTED_MODEL_VERSION,
            "anomaly_percentile": percentile,
            "feature_evidence_state": "PARTIAL",
        }
        result = tier1_selection.classify(row)
        assert result["priority_tier"] == expected
        assert result["evidence_sufficiency"] == "INSUFFICIENT"
    with pytest.raises(ValueError):
        tier1_selection.classify(
            {
                "method": "tier1-isolation-forest-v1",
                "anomaly_percentile": 95,
                "feature_evidence_state": "OBSERVED",
            }
        )


def test_reasons_are_bounded_and_noncausal() -> None:
    row = {
        "human_evidence_state": "no_county_linked_record",
        "pathogen_evidence_state": "No records",
        "svi_percentile_2022": 0.9,
    }
    result = tier1_persisted.reasons(row, 0.5)
    assert len(result) == 3
    text = " ".join(reason["text"].lower() for reason in result)
    assert "absence" in text and "risk" not in text and "caused" not in text


def test_incomplete_or_duplicate_batch_fails_before_publish() -> None:
    expected = synthetic_governed_fips()
    with pytest.raises(ValueError, match="Incomplete"):
        tier1_persisted.validate([], tier1_persisted.batch_id(COMMIT), expected_fips=expected)
    row = {"county_fips": "01001"}
    with pytest.raises(ValueError, match="Incomplete or duplicate"):
        tier1_persisted.validate(
            [copy.deepcopy(row)] * 3144, tier1_persisted.batch_id(COMMIT), expected_fips=expected
        )


def synthetic_governed_fips() -> set[str]:
    """Derive a test population through the same governed feature construction path."""
    source = [
        {
            "FIPS": f"{i:05d}",
            "HUMAN_STATUS": "published_count_floor" if i % 2 else "no_county_linked_record",
            "CASE_COUNT_FLOOR_2023": i + 1 if i % 2 else None,
            "SCAPULARIS_STATUS": "Unknown",
            "PACIFICUS_STATUS": "Unknown",
            "BURGDORFERI_STATUS": ("Present", "No records", "Unknown")[i % 3],
            "SVI_PERCENTILE": i / 3143,
            "RUCC_2023": i % 9 + 1,
        }
        for i in range(3144)
    ]
    matrix, _ = tier1_features.build_matrix(source)
    return {row["county_fips"] for row in matrix}


def synthetic_complete_batch() -> list[dict[str, object]]:
    """Exercise pinned publication checks without a live or stored output file."""
    identity = tier1_persisted.batch_id(COMMIT)
    rows = []
    for index in range(3144):
        tier = "HIGH" if index < 315 else "MEDIUM" if index < 943 else "LOW"
        sufficient = index < 315 or 315 <= index < 651
        rows.append(
            {
                "county_fips": f"{index:05d}",
                "model_version": tier1_selection.SELECTED_MODEL_VERSION,
                "feature_set_version": "tier1-county-features-v1",
                "evaluation_version": tier1_persisted.EVALUATION_VERSION,
                "tier_policy_version": tier1_selection.TIER_POLICY_VERSION,
                "prediction_batch_version": identity,
                "run_id": identity,
                "release_id": "governed-2026-09-17-unknown-coverage",
                "bundle_sha256": "55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233",
                "source_commit": COMMIT,
                "generated_at_utc": "2026-10-06T00:00:00Z",
                "raw_model_score": 1.0,
                "priority_percentile": {"HIGH": 90.0, "MEDIUM": 70.0, "LOW": 0.0}[tier],
                "priority_tier": tier,
                "evidence_sufficiency": "SUFFICIENT" if sufficient else "INSUFFICIENT",
                "feature_evidence_state": "OBSERVED" if sufficient else "PARTIAL",
                "human_evidence_state": "published_count_floor"
                if sufficient
                else "no_county_linked_record",
                "pathogen_evidence_state": "Present",
                "reasons": [
                    {"code": "PUBLISHED_HUMAN_FLOOR", "text": "Published signal."},
                    {"code": "PATHOGEN_PRESENT", "text": "Publisher reports Present."},
                ],
                "limitation_ref": tier1_persisted.LIMITATION_REF,
            }
        )
    return rows


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("model_version", "tier1-isolation-forest-v1"),
        ("feature_set_version", "wrong"),
        ("tier_policy_version", "wrong"),
        ("release_id", "wrong"),
        ("bundle_sha256", "b" * 64),
        ("prediction_batch_version", "changed"),
        ("priority_tier", "LOW"),
        ("evidence_sufficiency", "NOT_ESTIMABLE"),
    ],
)
def test_wrong_lineage_or_state_cannot_pass_publication(field: str, bad: str) -> None:
    rows = synthetic_complete_batch()
    expected = synthetic_governed_fips()
    tier1_persisted.validate(rows, tier1_persisted.batch_id(COMMIT), expected_fips=expected)
    rows[0][field] = bad
    with pytest.raises(ValueError):
        tier1_persisted.validate(rows, tier1_persisted.batch_id(COMMIT), expected_fips=expected)


def test_not_estimable_cannot_be_low() -> None:
    rows = synthetic_complete_batch()
    rows[0]["evidence_sufficiency"] = "NOT_ESTIMABLE"
    rows[0]["priority_tier"] = "LOW"
    with pytest.raises(ValueError, match="NOT_ESTIMABLE"):
        tier1_persisted.validate(
            rows, tier1_persisted.batch_id(COMMIT), expected_fips=synthetic_governed_fips()
        )


def test_exact_governed_population_passes() -> None:
    tier1_persisted.validate(
        synthetic_complete_batch(),
        tier1_persisted.batch_id(COMMIT),
        expected_fips=synthetic_governed_fips(),
    )


def test_same_size_valid_looking_substitute_fails() -> None:
    rows = synthetic_complete_batch()
    rows[0]["county_fips"] = "99999"
    with pytest.raises(ValueError, match="governed feature population"):
        tier1_persisted.validate(
            rows, tier1_persisted.batch_id(COMMIT), expected_fips=synthetic_governed_fips()
        )


def test_missing_and_replacement_fips_fail_at_unchanged_count() -> None:
    rows = synthetic_complete_batch()
    rows[0]["county_fips"] = "99998"
    rows[1]["county_fips"] = "99999"
    assert len(rows) == 3144 and len({row["county_fips"] for row in rows}) == 3144
    with pytest.raises(ValueError, match="governed feature population"):
        tier1_persisted.validate(
            rows, tier1_persisted.batch_id(COMMIT), expected_fips=synthetic_governed_fips()
        )
