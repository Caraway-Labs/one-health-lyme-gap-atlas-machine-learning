"""Story #43 contracts run without Arize, Snowflake, or network access."""

import copy
import json
from pathlib import Path

import pytest

from lyme_gap_atlas_ml.monitoring import (
    EvidenceState,
    MonitoringError,
    evaluate_label,
    make_evidence,
    recovery_evidence,
    validate_evidence,
    validate_policy,
    validate_regression_case,
    validate_retraining_review,
)

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = json.loads((ROOT / "config/examples/synthetic-lineage-v1.json").read_text())
EXAMPLES = ROOT / "config/examples/monitoring"


@pytest.fixture
def policy():  # type: ignore[no-untyped-def]
    return json.loads((EXAMPLES / "synthetic-pre-label-v1.json").read_text())


def test_examples_validate() -> None:
    for path in EXAMPLES.glob("*.json"):
        assert validate_policy(json.loads(path.read_text()), BUNDLE)


def test_identity_schema_and_causal_slice(policy: dict) -> None:  # type: ignore[type-arg]
    for mutation in (
        lambda p: p.update(schema="atlas-ml-monitoring-policy/v2"),
        lambda p: p["model_ref"].update(version="v99"),
        lambda p: p["slices"][0].update(interpretation="causal"),
        lambda p: p["alert_semantics"].update(automatic_retraining=True),
    ):
        candidate = copy.deepcopy(policy)
        mutation(candidate)
        with pytest.raises(MonitoringError):
            validate_policy(candidate, BUNDLE)


def test_label_states() -> None:
    common = dict(
        sample_size=20,
        minimum_sample=10,
        label_coverage=0.9,
        minimum_coverage=0.8,
        baseline_available=True,
        baseline_required=True,
    )
    assert evaluate_label(exists=False, mature=False, **common) == (
        EvidenceState.UNKNOWN,
        "missing_labels",
    )
    assert evaluate_label(exists=True, mature=False, **common) == (
        EvidenceState.UNKNOWN,
        "immature_labels",
    )
    assert evaluate_label(exists=True, mature=True, **{**common, "sample_size": 3}) == (
        EvidenceState.INSUFFICIENT_EVIDENCE,
        "small_sample",
    )
    assert evaluate_label(exists=True, mature=True, **{**common, "slice_complete": False}) == (
        EvidenceState.INSUFFICIENT_EVIDENCE,
        "incomplete_slice",
    )
    assert evaluate_label(exists=True, mature=True, **{**common, "baseline_available": False}) == (
        EvidenceState.UNKNOWN,
        "unavailable_baseline",
    )
    assert evaluate_label(exists=True, mature=True, **common) == (EvidenceState.AVAILABLE, None)


def _evidence(policy: dict, **changes: object) -> dict:  # type: ignore[type-arg]
    fields = dict(
        id="event-1",
        monitor_id="feature-drift",
        category="feature_drift",
        reason="telemetry_failure",
        state="unknown",
        sufficiency_reason="unavailable_telemetry",
        observation_window=policy["observation_window"],
        reference_window=policy["reference_window"],
        baseline_ref=policy["baseline_ref"],
        slice_id=None,
        metric=None,
        value=None,
        threshold_ref=None,
        sample_size=None,
        label_coverage=None,
        data_freshness=None,
        source_revision_ref=None,
        reporting_era_ref=None,
        observed_at="2026-09-24T00:00:00+00:00",
        arize_ref=None,
        evaluation_ref=None,
        related_evidence_ref=None,
    )
    fields.update(changes)
    return make_evidence(policy, **fields)


def test_telemetry_failure_and_recovery_preserve_prediction(policy: dict) -> None:  # type: ignore[type-arg]
    approved_prediction = {"id": "prediction-1", "value": 0.4}
    original = copy.deepcopy(approved_prediction)
    failed = _evidence(policy)
    recovered = recovery_evidence(
        failed, policy, evidence_id="event-2", observed_at="2026-09-25T00:00:00+00:00"
    )
    assert failed["reason"] == "telemetry_failure"
    assert recovered["related_evidence_ref"] == failed["id"]
    assert recovered["reason"] == "monitoring_recovery"
    assert approved_prediction == original
    assert json.loads(json.dumps(recovered)) == recovered


def test_revision_is_not_drift_or_degradation(policy: dict) -> None:  # type: ignore[type-arg]
    revision = _evidence(
        policy,
        reason="source_revision",
        state="available",
        sufficiency_reason=None,
        source_revision_ref="fixture://revision",
    )
    assert revision["reason"] == "source_revision"
    with pytest.raises(MonitoringError):
        _evidence(
            policy, reason="predictive_degradation", state="available", sufficiency_reason=None
        )
    with pytest.raises(MonitoringError):
        validate_evidence({**revision, "schema": "unknown"}, policy)


def test_retraining_and_regression_require_review(policy: dict) -> None:  # type: ignore[type-arg]
    review = dict(
        schema="atlas-ml-retraining-review/v1",
        model_ref=policy["model_ref"],
        policy_version=policy["policy_version"],
        evidence_refs=["event-1"],
        affected_slices=["state"],
        affected_windows=[policy["observation_window"]],
        investigation_ref="fixture://investigation",
        data_label_sufficiency="unknown",
        proposed_experiment_ref="fixture://experiment-26",
        evaluation_plan_ref="fixture://evaluation-30",
        expected_data_refresh_ref="fixture://refresh",
        cost_resource_ref=None,
        reviewer="synthetic-reviewer",
        decision="pending",
        action="human_review_only",
    )
    assert validate_retraining_review(review, policy)
    for change in (
        {"evidence_refs": []},
        {"action": "automatic_retraining"},
        {"action": "automatic_promotion"},
    ):
        with pytest.raises(MonitoringError):
            validate_retraining_review({**review, **change}, policy)
    case = dict(
        schema="atlas-ml-regression-case/v1",
        model_ref=policy["model_ref"],
        source_evidence_ref="event-1",
        reason_for_inclusion="confirmed failure",
        expected_behavior="detect missing input",
        reviewer="synthetic-reviewer",
        approval_state="proposed",
        target_case_set_ref="fixture://cases-v1",
    )
    with pytest.raises(MonitoringError):
        validate_regression_case(case, policy)
    assert validate_regression_case({**case, "approval_state": "approved"}, policy)
