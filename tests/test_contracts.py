"""Offline Story #41 lineage and compatibility checks."""

import copy
import json
from pathlib import Path

import pytest

from lyme_gap_atlas_ml.contracts import ContractError, dump_bundle, load_bundle, validate_bundle
from lyme_gap_atlas_ml.lifecycle import validate_state

ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "config/examples/synthetic-lineage-v1.json"
SCHEMA = ROOT / "docs/architecture/declarative-ml-contracts-v1.schema.json"
LIFECYCLE = ROOT / "docs/methodology/lifecycle-state-v1.template.json"


def example() -> dict:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_complete_example_and_roundtrip() -> None:
    bundle = load_bundle(EXAMPLE)
    assert bundle["snowflake"]["registry_model_ref"] == bundle["arize"]["model_name"]
    assert json.loads(dump_bundle(bundle)) == bundle


def test_inference_code_can_differ_from_training_code() -> None:
    bundle = example()
    bundle["prediction"]["git_sha"] = "2" * 40
    validate_bundle(bundle)


def test_structural_schema_covers_example() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    bundle = example()
    assert schema["properties"]["schema"] == {"const": "atlas-ml-contracts/v1"}
    assert set(schema["required"]) == set(bundle)
    for name, value in bundle.items():
        if isinstance(value, dict):
            assert set(schema["properties"][name]["required"]) == set(value)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema",), "atlas-ml-contracts/v2"),
        (("model_spec", "schema"), "atlas-ml-model-spec/v2"),
        (("model_spec", "identity", "id"), "Bad ID"),
        (("model_spec", "identity", "version"), "latest"),
        (("dataset", "ref", "id"), "synthetic-demo-model"),
        (("feature_set", "dataset_ref", "version"), "v2"),
        (("split", "dataset_ref", "version"), "v2"),
        (("experiment", "model_ref", "version"), "v2"),
        (("experiment", "feature_ref", "version"), "v2"),
        (("snowflake", "model_ref", "version"), "v2"),
        (("snowflake", "registry_model_ref"), "other-model"),
        (("arize", "model_name"), "other-model"),
        (("arize", "model_ref", "version"), "v2"),
        (("prediction", "split_ref", "version"), "v2"),
        (("evaluation", "frozen_plan_ref"), "fixture://different-plan"),
        (("split", "holdout", "protected"), False),
        (("evidence", "inference_run_id"), "other-run"),
    ],
)
def test_rejects_invalid_or_incompatible_fields(path: tuple[str, ...], value: object) -> None:
    bundle = example()
    node = bundle
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(ContractError):
        validate_bundle(bundle)


def test_missing_identity_and_duplicate_ids() -> None:
    missing = example()
    del missing["model_spec"]["identity"]
    with pytest.raises(ContractError, match="identity"):
        validate_bundle(missing)
    duplicate = example()
    duplicate["feature_set"]["ref"] = duplicate["dataset"]["ref"]
    duplicate["experiment"]["feature_ref"] = duplicate["dataset"]["ref"]
    duplicate["prediction"]["feature_ref"] = duplicate["dataset"]["ref"]
    with pytest.raises(ContractError, match="colliding"):
        validate_bundle(duplicate)


@pytest.mark.parametrize(
    "key", ["password", "api_key", "private_key", "snowflake_connection_name", "arize_access_token"]
)
def test_secret_fields_are_rejected(key: str) -> None:
    bundle = example()
    bundle["arize"][key] = "fixture-value"
    with pytest.raises(ContractError, match="prohibited"):
        validate_bundle(bundle)


def test_evidence_state_requires_real_reference() -> None:
    bundle = example()
    bundle["evidence"]["monitoring_status"] = "available"
    with pytest.raises(ContractError, match="monitoring_evidence_ref"):
        validate_bundle(bundle)
    bundle["evidence"]["monitoring_evidence_ref"] = "fixture://monitoring-result"
    validate_bundle(bundle)
    bundle["evidence"]["monitoring_status"] = "not_collected"
    with pytest.raises(ContractError, match="unavailable evidence"):
        validate_bundle(bundle)


@pytest.mark.parametrize(
    ("strategy", "temporal", "grouping"),
    [
        ("iid", "not-applicable", "not-applicable"),
        ("stratified", "not-applicable", "fixture://strata"),
        ("temporal", "fixture://temporal-boundaries", "not-applicable"),
        ("grouped_spatial", "not-applicable", "fixture://spatial-groups"),
        ("spatiotemporal", "fixture://temporal-boundaries", "fixture://spatial-groups"),
    ],
)
def test_split_strategies(strategy: str, temporal: str, grouping: str) -> None:
    bundle = example()
    bundle["split"].update(
        strategy=strategy,
        temporal_boundaries=temporal,
        grouping_semantics=grouping,
    )
    bundle["model_spec"]["validation_strategy"] = strategy
    validate_bundle(bundle)


def test_lifecycle_references_match_bundle() -> None:
    bundle = example()
    state = validate_state(json.loads(LIFECYCLE.read_text(encoding="utf-8")))
    state["references"] = {
        "dataset": copy.deepcopy(bundle["dataset"]["ref"]),
        "feature": copy.deepcopy(bundle["feature_set"]["ref"]),
        "split": copy.deepcopy(bundle["split"]["ref"]),
        "experiment": copy.deepcopy(bundle["experiment"]["ref"]),
        "model": {key: bundle["model_spec"]["identity"][key] for key in ("id", "version")},
    }
    validate_bundle(bundle, lifecycle=state)
    state["references"]["model"]["version"] = "v2"
    with pytest.raises(ContractError, match="lifecycle"):
        validate_bundle(bundle, lifecycle=state)
