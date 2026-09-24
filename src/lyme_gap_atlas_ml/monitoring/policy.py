"""Vendor-neutral, versioned monitoring policy with no I/O or model mutation."""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from lyme_gap_atlas_ml.contracts import (
    ID,
    SECRET_KEY,
    VERSION,
    ContractBundle,
    ContractError,
    validate_bundle,
)

POLICY_SCHEMA = "atlas-ml-monitoring-policy/v1"
EVIDENCE_SCHEMA = "atlas-ml-monitoring-evidence/v1"
REVIEW_SCHEMA = "atlas-ml-retraining-review/v1"
CASE_SCHEMA = "atlas-ml-regression-case/v1"
PRE = frozenset(
    {
        "feature_drift",
        "prediction_drift",
        "missingness",
        "schema_quality",
        "outlier_range",
        "freshness_coverage",
        "inference_health",
        "uncertainty_distribution",
    }
)
POST = frozenset(
    {
        "predictive_performance",
        "calibration_coverage",
        "error_distribution",
        "task_errors",
        "slice_performance",
        "baseline_comparison",
    }
)
REASONS = frozenset(
    {
        "source_revision",
        "reporting_era_change",
        "pipeline_outage",
        "missing_data",
        "expected_quiet_period",
        "feature_shift",
        "prediction_shift",
        "telemetry_failure",
        "insufficient_labels",
        "predictive_degradation",
        "monitoring_recovery",
        "input_quality",
        "inference_failure",
        "evaluation_result",
    }
)
INSUFFICIENT = frozenset(
    {
        "missing_labels",
        "immature_labels",
        "small_sample",
        "incomplete_slice",
        "unavailable_baseline",
        "unavailable_telemetry",
    }
)


class MonitoringError(ValueError):
    """Monitoring declaration is invalid or exceeds its approved boundary."""


class EvidenceState(StrEnum):
    AVAILABLE = "available"
    UNKNOWN = "unknown"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    NOT_APPLICABLE = "not_applicable"


def _obj(
    value: Any, name: str, keys: set[str], optional: set[str] | frozenset[str] = frozenset()
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - keys - optional or keys - set(value):
        raise MonitoringError(f"{name}: missing, unknown, or invalid fields")
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MonitoringError(f"{name}: nonempty string required")
    return value


def _ref(value: Any, name: str) -> dict[str, str]:
    obj = _obj(value, name, {"id", "version"})
    if not isinstance(obj["id"], str) or not ID.fullmatch(obj["id"]):
        raise MonitoringError(f"{name}: invalid ID")
    if not isinstance(obj["version"], str) or not VERSION.fullmatch(obj["version"]):
        raise MonitoringError(f"{name}: invalid version")
    return obj


def _safe(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or SECRET_KEY.search(key):
                raise MonitoringError("secret-bearing or invalid key prohibited")
            _safe(child)
    elif isinstance(value, list):
        for child in value:
            _safe(child)


def _time(value: Any, name: str) -> datetime:
    try:
        result = datetime.fromisoformat(_text(value, name))
    except ValueError as exc:
        raise MonitoringError(f"{name}: invalid timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise MonitoringError(f"{name}: timezone required")
    return result


def _window(value: Any, name: str) -> dict[str, str]:
    obj = _obj(value, name, {"start", "end"})
    if _time(obj["start"], name) >= _time(obj["end"], name):
        raise MonitoringError(f"{name}: invalid window")
    return obj


def validate_policy(raw: Any, bundle: ContractBundle) -> dict[str, Any]:
    """Validate a model-specific policy against the full Story #41 lineage bundle."""
    try:
        lineage = validate_bundle(bundle)
    except ContractError as exc:
        raise MonitoringError("invalid canonical lineage bundle") from exc
    obj = _obj(
        raw,
        "policy",
        {
            "schema",
            "model_ref",
            "arize_mapping_ref",
            "policy_ref",
            "policy_version",
            "environments",
            "pre_label",
            "post_label",
            "baseline_ref",
            "observation_window",
            "reference_window",
            "slices",
            "evidence_requirements",
            "alert_semantics",
            "owner",
            "review_state",
            "delayed_ground_truth",
            "retraining_review_ref",
        },
    )
    _safe(obj)
    if obj["schema"] != POLICY_SCHEMA:
        raise MonitoringError("unsupported policy schema")
    model = lineage["model_spec"]["identity"]
    if _ref(obj["model_ref"], "model_ref") != {"id": model["id"], "version": model["version"]}:
        raise MonitoringError("canonical model/version mismatch")
    if _text(obj["arize_mapping_ref"], "arize_mapping_ref") != lineage["arize"]["project_ref"]:
        raise MonitoringError("Arize mapping mismatch")
    if _text(obj["policy_ref"], "policy_ref") != lineage["arize"]["monitoring_policy_ref"]:
        raise MonitoringError("lineage monitoring policy mismatch")
    if not VERSION.fullmatch(_text(obj["policy_version"], "policy_version")):
        raise MonitoringError("invalid policy version")
    if (
        not isinstance(obj["environments"], list)
        or not obj["environments"]
        or set(obj["environments"]) - {"training", "validation", "production"}
    ):
        raise MonitoringError("invalid environments")
    _window(obj["observation_window"], "observation_window")
    _window(obj["reference_window"], "reference_window")
    for regime, categories in (("pre_label", PRE), ("post_label", POST)):
        monitors = obj[regime]
        if not isinstance(monitors, list) or not monitors:
            raise MonitoringError(f"{regime}: explicit enabled/disabled entries required")
        ids: set[str] = set()
        for monitor in monitors:
            entry = _obj(
                monitor,
                regime,
                {"id", "category", "enabled", "rationale", "threshold", "external_ref"},
            )
            name = _text(entry["id"], "monitor.id")
            if (
                not ID.fullmatch(name)
                or name in ids
                or entry["category"] not in categories
                or type(entry["enabled"]) is not bool
            ):
                raise MonitoringError(f"{regime}: invalid/duplicate monitor")
            ids.add(name)
            _text(entry["rationale"], "monitor.rationale")
            if entry["threshold"] != "unresolved" and not isinstance(entry["threshold"], dict):
                raise MonitoringError("threshold must be unresolved or approved reference")
            if isinstance(entry["threshold"], dict):
                _obj(entry["threshold"], "threshold", {"value", "approval_ref"})
                _text(entry["threshold"]["approval_ref"], "threshold.approval_ref")
            if entry["external_ref"] is not None:
                _text(entry["external_ref"], "monitor.external_ref")
    baseline = obj["baseline_ref"]
    if baseline is not None:
        _text(baseline, "baseline_ref")
        if baseline not in lineage["evaluation"]["required_baselines"]:
            raise MonitoringError("baseline differs from frozen evaluation contract")
    if not isinstance(obj["slices"], list):
        raise MonitoringError("slices must be a list")
    ids = set()
    for item in obj["slices"]:
        slice_obj = _obj(
            item,
            "slice",
            {
                "id",
                "dimension",
                "value_ref",
                "rationale",
                "minimum_sample",
                "minimum_label_coverage",
                "review_ref",
                "interpretation",
            },
        )
        slice_id = _text(slice_obj["id"], "slice.id")
        if not ID.fullmatch(slice_id) or slice_id in ids:
            raise MonitoringError("duplicate or invalid slice ID")
        ids.add(slice_id)
        for key in ("dimension", "value_ref", "rationale", "review_ref"):
            _text(slice_obj[key], f"slice.{key}")
        if slice_obj["interpretation"] != "descriptive_only":
            raise MonitoringError("slices are descriptive, never causal")
        if type(slice_obj["minimum_sample"]) is not int or slice_obj["minimum_sample"] < 1:
            raise MonitoringError("slice minimum sample required")
        coverage = slice_obj["minimum_label_coverage"]
        if (
            not isinstance(coverage, (int, float))
            or isinstance(coverage, bool)
            or not 0 <= coverage <= 1
        ):
            raise MonitoringError("slice label coverage must be 0..1")
    requirements = _obj(
        obj["evidence_requirements"],
        "evidence_requirements",
        {"minimum_sample", "minimum_label_coverage", "baseline_required"},
    )
    if type(requirements["minimum_sample"]) is not int or requirements["minimum_sample"] < 1:
        raise MonitoringError("minimum sample required")
    if (
        not isinstance(requirements["minimum_label_coverage"], (int, float))
        or isinstance(requirements["minimum_label_coverage"], bool)
        or not 0 <= requirements["minimum_label_coverage"] <= 1
    ):
        raise MonitoringError("invalid minimum label coverage")
    if type(requirements["baseline_required"]) is not bool:
        raise MonitoringError("baseline_required must be boolean")
    alerts = _obj(
        obj["alert_semantics"],
        "alert_semantics",
        {"investigation_required", "automatic_retraining", "automatic_promotion"},
    )
    if alerts != {
        "investigation_required": True,
        "automatic_retraining": False,
        "automatic_promotion": False,
    }:
        raise MonitoringError("alerts only initiate investigation")
    if obj["review_state"] not in {"proposed", "approved", "rejected"}:
        raise MonitoringError("invalid review state")
    _text(obj["owner"], "owner")
    _text(obj["retraining_review_ref"], "retraining_review_ref")
    delayed = _obj(
        obj["delayed_ground_truth"],
        "delayed_ground_truth",
        {
            "maturity_ref",
            "revision_ref",
            "eligibility_ref",
            "late_label_action",
            "missing_label_state",
            "actual_update_action",
            "revised_label_action",
            "history",
            "evaluation_window",
        },
    )
    if (
        delayed["maturity_ref"] != lineage["model_spec"]["label_maturity"]
        or delayed["revision_ref"] != lineage["model_spec"]["label_revision"]
    ):
        raise MonitoringError("label rules differ from ModelSpec")
    if (
        delayed["missing_label_state"] != EvidenceState.UNKNOWN
        or delayed["history"] != "append_only"
        or delayed["revised_label_action"]
        not in {"review_for_reevaluation", "reevaluate_with_new_evidence"}
        or delayed["late_label_action"]
        not in {"review_for_reevaluation", "reevaluate_with_new_evidence"}
        or delayed["actual_update_action"] != "linked_by_prediction_id"
    ):
        raise MonitoringError("invalid delayed-ground-truth rule")
    _text(delayed["eligibility_ref"], "eligibility_ref")
    _window(delayed["evaluation_window"], "evaluation_window")
    return obj


def evaluate_label(
    *,
    exists: bool,
    mature: bool,
    sample_size: int,
    minimum_sample: int,
    label_coverage: float,
    minimum_coverage: float,
    baseline_available: bool,
    baseline_required: bool,
    slice_complete: bool = True,
) -> tuple[EvidenceState, str | None]:
    """Decide sufficiency only; metric computation belongs to the frozen #30 plan."""
    if not exists:
        return EvidenceState.UNKNOWN, "missing_labels"
    if not mature:
        return EvidenceState.UNKNOWN, "immature_labels"
    if not slice_complete:
        return EvidenceState.INSUFFICIENT_EVIDENCE, "incomplete_slice"
    if sample_size < minimum_sample or label_coverage < minimum_coverage:
        return EvidenceState.INSUFFICIENT_EVIDENCE, "small_sample"
    if baseline_required and not baseline_available:
        return EvidenceState.UNKNOWN, "unavailable_baseline"
    return EvidenceState.AVAILABLE, None


def validate_evidence(raw: Any, policy: dict[str, Any]) -> dict[str, Any]:
    obj = _obj(
        raw,
        "evidence",
        {
            "schema",
            "id",
            "model_ref",
            "policy_version",
            "monitor_id",
            "category",
            "reason",
            "state",
            "sufficiency_reason",
            "observation_window",
            "reference_window",
            "baseline_ref",
            "slice_id",
            "metric",
            "value",
            "threshold_ref",
            "sample_size",
            "label_coverage",
            "data_freshness",
            "source_revision_ref",
            "reporting_era_ref",
            "observed_at",
            "arize_ref",
            "evaluation_ref",
            "related_evidence_ref",
        },
    )
    _safe(obj)
    if (
        obj["schema"] != EVIDENCE_SCHEMA
        or _ref(obj["model_ref"], "evidence.model_ref") != policy["model_ref"]
        or obj["policy_version"] != policy["policy_version"]
    ):
        raise MonitoringError("evidence schema or identity mismatch")
    _text(obj["id"], "evidence.id")
    monitor = next(
        (
            m
            for m in policy["pre_label"] + policy["post_label"]
            if m["id"] == obj["monitor_id"] and m["enabled"]
        ),
        None,
    )
    if monitor is None or obj["category"] != monitor["category"] or obj["reason"] not in REASONS:
        raise MonitoringError("unknown monitor or reason")
    if obj["state"] not in EvidenceState:
        raise MonitoringError("invalid evidence state")
    if obj["state"] != EvidenceState.AVAILABLE and obj["value"] is not None:
        raise MonitoringError("unavailable evidence cannot have metric value")
    if obj["sufficiency_reason"] is not None and obj["sufficiency_reason"] not in INSUFFICIENT:
        raise MonitoringError("invalid sufficiency reason")
    if (
        obj["state"] in {EvidenceState.UNKNOWN, EvidenceState.INSUFFICIENT_EVIDENCE}
        and obj["sufficiency_reason"] is None
    ):
        raise MonitoringError("missing sufficiency reason")
    _window(obj["observation_window"], "evidence.observation_window")
    _window(obj["reference_window"], "evidence.reference_window")
    _time(obj["observed_at"], "evidence.observed_at")
    if obj["slice_id"] is not None and obj["slice_id"] not in {s["id"] for s in policy["slices"]}:
        raise MonitoringError("unapproved slice")
    if obj["baseline_ref"] != policy["baseline_ref"]:
        raise MonitoringError("baseline mismatch")
    for key in (
        "metric",
        "threshold_ref",
        "data_freshness",
        "source_revision_ref",
        "reporting_era_ref",
        "arize_ref",
        "evaluation_ref",
        "related_evidence_ref",
    ):
        if obj[key] is not None:
            _text(obj[key], f"evidence.{key}")
    if obj["reason"] == "predictive_degradation" and monitor not in policy["post_label"]:
        raise MonitoringError("pre-label signal cannot demonstrate degradation")
    if obj["sample_size"] is not None and (
        type(obj["sample_size"]) is not int or obj["sample_size"] < 0
    ):
        raise MonitoringError("invalid sample size")
    return obj


def make_evidence(policy: dict[str, Any], **fields: Any) -> dict[str, Any]:
    """Build and validate a complete appendable evidence value."""
    return validate_evidence(
        {
            "schema": EVIDENCE_SCHEMA,
            "model_ref": policy["model_ref"],
            "policy_version": policy["policy_version"],
            **fields,
        },
        policy,
    )


def recovery_evidence(
    previous: dict[str, Any], policy: dict[str, Any], *, evidence_id: str, observed_at: str
) -> dict[str, Any]:
    """Record recovery as a new event; never rewrite the failed attempt."""
    validate_evidence(previous, policy)
    if previous["reason"] != "telemetry_failure":
        raise MonitoringError("recovery must link telemetry failure")
    return validate_evidence(
        {
            **previous,
            "id": evidence_id,
            "reason": "monitoring_recovery",
            "state": EvidenceState.AVAILABLE,
            "sufficiency_reason": None,
            "observed_at": observed_at,
            "related_evidence_ref": previous["id"],
        },
        policy,
    )


def validate_retraining_review(raw: Any, policy: dict[str, Any]) -> dict[str, Any]:
    obj = _obj(
        raw,
        "review",
        {
            "schema",
            "model_ref",
            "policy_version",
            "evidence_refs",
            "affected_slices",
            "affected_windows",
            "investigation_ref",
            "data_label_sufficiency",
            "proposed_experiment_ref",
            "evaluation_plan_ref",
            "expected_data_refresh_ref",
            "cost_resource_ref",
            "reviewer",
            "decision",
            "action",
        },
    )
    if (
        obj["schema"] != REVIEW_SCHEMA
        or obj["model_ref"] != policy["model_ref"]
        or obj["policy_version"] != policy["policy_version"]
        or not isinstance(obj["evidence_refs"], list)
        or not obj["evidence_refs"]
    ):
        raise MonitoringError("retraining review requires matching model and evidence")
    for key in (
        "investigation_ref",
        "data_label_sufficiency",
        "proposed_experiment_ref",
        "evaluation_plan_ref",
        "expected_data_refresh_ref",
        "reviewer",
    ):
        _text(obj[key], key)
    if (
        obj["decision"] not in {"pending", "approved_for_experiment", "deferred", "rejected"}
        or obj["action"] != "human_review_only"
    ):
        raise MonitoringError("no automatic retraining or promotion")
    return obj


def validate_regression_case(raw: Any, policy: dict[str, Any]) -> dict[str, Any]:
    obj = _obj(
        raw,
        "case",
        {
            "schema",
            "model_ref",
            "source_evidence_ref",
            "reason_for_inclusion",
            "expected_behavior",
            "reviewer",
            "approval_state",
            "target_case_set_ref",
        },
    )
    if (
        obj["schema"] != CASE_SCHEMA
        or obj["model_ref"] != policy["model_ref"]
        or obj["approval_state"] != "approved"
    ):
        raise MonitoringError("regression case needs matching model and explicit approval")
    for key in (
        "source_evidence_ref",
        "reason_for_inclusion",
        "expected_behavior",
        "reviewer",
        "target_case_set_ref",
    ):
        _text(obj[key], key)
    return obj


def load_policy(path: Path, bundle: ContractBundle) -> dict[str, Any]:
    return validate_policy(json.loads(path.read_text(encoding="utf-8")), bundle)
