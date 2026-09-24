"""Version 1 of the offline Atlas ML lifecycle gate contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_ID = "atlas-ml-lifecycle/v1"
STAGES = ("frame", "data", "explore", "prepare", "candidates", "validate", "communicate", "operate")
STATUSES = {"not_started", "in_progress", "blocked", "complete", "not_applicable"}
REQUIRED_EVIDENCE = {
    "frame": ("decision_contract",),
    "data": ("dataset_contract",),
    "explore": ("profile",),
    "prepare": ("feature_implementation",),
    "candidates": ("baseline_comparison",),
    "validate": ("frozen_evaluation_plan", "evaluation_result"),
    "communicate": ("model_card", "review_decision"),
    "operate": ("release_decision", "monitoring_plan"),
}
REFERENCE_KEYS = {"dataset", "feature", "split", "experiment", "model"}
HOLDOUT_PURPOSES = {"final_evaluation", "independent_audit"}


class LifecycleError(ValueError):
    """A state cannot be trusted for lifecycle decisions."""


def _object(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise LifecycleError(f"{where} must be an object with string keys")
    return value


def _text(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LifecycleError(f"{where} must be nonempty text")
    return value


@dataclass(frozen=True)
class ResumeDecision:
    completed: tuple[str, ...]
    current_stage: str | None
    current_status: str | None
    next_stage: str | None
    allowed_action: str
    evidence: dict[str, dict[str, str]]


def validate_state(raw: Any) -> dict[str, Any]:
    """Validate a JSON state and return it; reject incomplete or unsafe gates."""
    state = _object(raw, "state")
    if not {"schema", "project_id", "stages", "references", "holdout_history"} <= set(state):
        raise LifecycleError("missing required lifecycle state field")
    if set(state) - {
        "schema",
        "project_id",
        "stages",
        "references",
        "holdout_history",
        "assumptions",
        "limitations",
    }:
        raise LifecycleError("unknown state field")
    if state.get("schema") != SCHEMA_ID:
        raise LifecycleError("unsupported lifecycle schema")
    _text(state.get("project_id"), "project_id")
    stages = _object(state.get("stages"), "stages")
    if set(stages) != set(STAGES):
        raise LifecycleError("stages must contain every v1 stage exactly once")
    refs = _object(state.get("references", {}), "references")
    if set(refs) - REFERENCE_KEYS:
        raise LifecycleError("unknown reference kind")
    for key, value in refs.items():
        ref = _object(value, f"references.{key}")
        if set(ref) != {"id", "version"}:
            raise LifecycleError(f"references.{key}: expected id and version")
        _text(ref.get("id"), f"references.{key}.id")
        _text(ref.get("version"), f"references.{key}.version")
    seen_open = False
    active = 0
    for name in STAGES:
        stage = _object(stages[name], name)
        if set(stage) - {"status", "evidence", "reason", "blocker", "review"}:
            raise LifecycleError(f"{name}: unknown stage field")
        status = stage.get("status")
        if status not in STATUSES:
            raise LifecycleError(f"{name}: invalid status")
        evidence = _object(stage.get("evidence"), f"{name}.evidence")
        for key, value in evidence.items():
            _text(value, f"{name}.evidence.{key}")
        review = _object(stage.get("review", {}), f"{name}.review")
        if set(review) - {"state", "decision_ref"}:
            raise LifecycleError(f"{name}: unknown review field")
        if review.get("state", "pending") not in {"pending", "approved", "rejected"}:
            raise LifecycleError(f"{name}: invalid review state")
        if review.get("state") in {"approved", "rejected"}:
            _text(review.get("decision_ref"), f"{name}.review.decision_ref")
        if status in {"complete", "not_applicable"}:
            if seen_open:
                raise LifecycleError(f"{name}: previous stage is not terminal")
            required = REQUIRED_EVIDENCE[name] if status == "complete" else ("non_applicability",)
            if any(key not in evidence for key in required):
                raise LifecycleError(f"{name}: missing prerequisite evidence")
            if status == "not_applicable":
                _text(stage.get("reason"), f"{name}.reason")
                if review.get("state") != "approved":
                    raise LifecycleError(f"{name}: non-applicability needs approved review")
            if (
                name in {"communicate", "operate"}
                and status == "complete"
                and review.get("state") != "approved"
            ):
                raise LifecycleError(f"{name}: human decision remains required")
        else:
            was_open = seen_open
            seen_open = True
            if status in {"in_progress", "blocked"}:
                if was_open:
                    raise LifecycleError(f"{name}: skipped earlier open stage")
                active += 1
                if active > 1:
                    raise LifecycleError("only one stage may be active")
            if status == "blocked":
                blocker = _object(stage.get("blocker"), f"{name}.blocker")
                if set(blocker) != {"dependency", "reason"}:
                    raise LifecycleError(f"{name}: blocker needs dependency and reason")
                _text(blocker.get("dependency"), f"{name}.blocker.dependency")
                _text(blocker.get("reason"), f"{name}.blocker.reason")
        required_refs = {
            "data": ("dataset",),
            "prepare": ("feature",),
            "candidates": ("split", "experiment"),
            "validate": ("model",),
        }
        if status == "complete" and any(key not in refs for key in required_refs.get(name, ())):
            raise LifecycleError(f"{name}: missing versioned reference")
    history = state.get("holdout_history", [])
    if not isinstance(history, list):
        raise LifecycleError("holdout_history must be a list")
    event_ids: set[str] = set()
    prior_access = False
    for event in history:
        item = _object(event, "holdout event")
        if set(item) - {
            "event_id",
            "timestamp",
            "actor",
            "purpose",
            "split_ref",
            "evaluation_plan_ref",
            "result_ref",
            "repeat_reason",
            "review_decision_ref",
        }:
            raise LifecycleError("unknown holdout event field")
        event_id = _text(item.get("event_id"), "holdout event_id")
        if event_id in event_ids:
            raise LifecycleError("duplicate holdout event_id")
        event_ids.add(event_id)
        if item.get("purpose") not in HOLDOUT_PURPOSES:
            raise LifecycleError("holdout used for prohibited purpose")
        for key in ("timestamp", "actor", "split_ref", "evaluation_plan_ref", "result_ref"):
            _text(item.get(key), f"holdout.{key}")
        split = refs.get("split")
        if split is None or item["split_ref"] != f"{split['id']}@{split['version']}":
            raise LifecycleError("holdout event split does not match versioned split")
        if prior_access:
            _text(item.get("repeat_reason"), "holdout.repeat_reason")
            _text(item.get("review_decision_ref"), "holdout.review_decision_ref")
        prior_access = True
    if history and "split" not in refs:
        raise LifecycleError("holdout access requires versioned split reference")
    if history:
        if any(stages[name]["status"] not in {"complete", "not_applicable"} for name in STAGES[:5]):
            raise LifecycleError("holdout access before prerequisite gates")
        plan_ref = stages["validate"]["evidence"].get("frozen_evaluation_plan")
        if not plan_ref or any(event["evaluation_plan_ref"] != plan_ref for event in history):
            raise LifecycleError("holdout access without matching frozen evaluation plan")
    return state


def load_state(path: Path) -> dict[str, Any]:
    return validate_state(json.loads(path.read_text(encoding="utf-8")))


def dump_state(state: dict[str, Any]) -> str:
    validate_state(state)
    return json.dumps(state, indent=2, sort_keys=True) + "\n"


def resume(state: dict[str, Any]) -> ResumeDecision:
    """Return the next safe action without rerunning terminal stages."""
    state = validate_state(state)
    stages = state["stages"]
    completed = tuple(s for s in STAGES if stages[s]["status"] in {"complete", "not_applicable"})
    evidence = {s: stages[s]["evidence"] for s in completed}
    current = next(
        (s for s in STAGES if stages[s]["status"] not in {"complete", "not_applicable"}), None
    )
    if current is None:
        return ResumeDecision(completed, None, None, None, "await_new_reviewed_scope", evidence)
    status = stages[current]["status"]
    action = "resolve_blocker" if status == "blocked" else "inspect_evidence_then_work"
    next_index = STAGES.index(current) + 1
    next_stage = STAGES[next_index] if next_index < len(STAGES) else None
    return ResumeDecision(completed, current, status, next_stage, action, evidence)
