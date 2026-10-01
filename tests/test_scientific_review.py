"""Offline structural checks and representative scientific-review failure packets."""

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[1]
PACKET = json.loads((ROOT / "tests/fixtures/scientific_review_cases.json").read_text())
SCHEMA = json.loads((ROOT / "docs/methodology/scientific-review-v1.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA)
RESULTS = ROOT / "config/examples/reviews"


def result(name: str) -> dict:
    return json.loads((RESULTS / f"{name}.json").read_text())


def test_all_example_results_validate() -> None:
    Draft202012Validator.check_schema(SCHEMA)
    for path in RESULTS.glob("*.json"):
        VALIDATOR.validate(json.loads(path.read_text()))


def test_representative_comparison_replays_without_model_training() -> None:
    packet = copy.deepcopy(PACKET)
    assert packet["fixture_only"]
    base = packet["base"]
    for name in ("baseline", "candidate"):
        accuracy = sum(
            actual == predicted
            for actual, predicted in zip(base["labels"], base[name]["predictions"], strict=True)
        ) / len(base["labels"])
        assert accuracy == base[name]["accuracy"]
    assert base["available_at"] <= base["cutoff"]
    assert not base["holdout_history"]
    review = result("representative-blocked")
    assert review["disposition"] == "BLOCKED"
    assert review["checks"]["reproducibility"] == "BLOCKED"
    assert base["reproduction"]["git_sha"] == "1" * 40
    assert "illustrative" in review["findings"][0]
    assert packet == PACKET  # Review/replay did not rewrite source evidence.


@pytest.mark.parametrize("name", list(PACKET["cases"]))
def test_review_fixtures_expose_their_material_failures(name: str) -> None:
    case = PACKET["cases"][name]
    experiment = copy.deepcopy(PACKET["base"])
    experiment.update(case["overrides"])
    if name == "leakage":
        assert experiment["available_at"] > experiment["cutoff"]
    elif name == "holdout_reuse":
        assert len(experiment["holdout_history"]) == 2
        assert experiment["holdout_history"][1]["purpose"] == "hyperparameter_tuning"
    elif name == "missing_baseline":
        assert experiment["baseline"] is None
    elif name == "irreproducible_identity":
        assert not experiment["reproduction"]["git_sha"]
        assert not experiment["reproduction"]["run_id"]
    elif name == "misleading_interpretation":
        assert "diagnoses" in experiment["interpretation"]
        assert "causal" in experiment["interpretation"]
    elif name == "undecided_target":
        assert experiment["question"] is None
    review = result(name)
    assert review["disposition"] == case["disposition"]
    assert review["checks"][case["check"]] == case["disposition"]
    assert case["finding"] in review["findings"]
    assert review["remediation"] == case["remediation"]
    VALIDATOR.validate(review)
    falsely_passing = copy.deepcopy(review)
    falsely_passing["disposition"] = "PASS"
    assert not VALIDATOR.is_valid(falsely_passing)


@pytest.mark.parametrize("check", list(SCHEMA["properties"]["checks"]["properties"]))
def test_missing_check_cannot_validate(check: str) -> None:
    review = result("representative-blocked")
    del review["checks"][check]
    assert not VALIDATOR.is_valid(review)


@pytest.mark.parametrize("field,value", [("findings", []), ("remediation", ""), ("evidence", [])])
def test_nonpassing_review_needs_evidence_findings_and_remediation(field: str, value) -> None:
    review = result("representative-blocked")
    review[field] = value
    assert not VALIDATOR.is_valid(review)


def test_passing_structure_grants_no_release_permission() -> None:
    review = result("representative-blocked")
    review["disposition"] = "PASS"
    review["checks"] = dict.fromkeys(review["checks"], "PASS")
    review["findings"] = []
    review["remediation"] = ""
    VALIDATOR.validate(review)  # Structural example only; not a scientific pass.
    review["release_approved"] = True
    assert not VALIDATOR.is_valid(review)
    del review["release_approved"]
    review["checks"]["holdout"] = "PROMOTE"
    assert not VALIDATOR.is_valid(review)


@pytest.mark.parametrize("disposition", ["FAIL", "BLOCKED", "NEEDS_DECISION"])
def test_overall_nonpass_must_be_supported_by_a_check(disposition: str) -> None:
    review = result("representative-blocked")
    review["checks"] = dict.fromkeys(review["checks"], "PASS")
    review["disposition"] = disposition
    assert not VALIDATOR.is_valid(review)
