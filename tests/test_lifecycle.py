"""Offline contract and gate tests for Story #39."""

import copy
import json
from pathlib import Path

import pytest

from lyme_gap_atlas_ml.lifecycle import (
    STAGES,
    LifecycleError,
    dump_state,
    load_state,
    resume,
    validate_state,
)

ROOT = Path(__file__).parents[1]
TEMPLATE = ROOT / "docs/methodology/lifecycle-state-v1.template.json"
PARTIAL = ROOT / "tests/fixtures/partial_lifecycle.json"


def template() -> dict:
    return json.loads(TEMPLATE.read_text(encoding="utf-8"))


def partial() -> dict:
    return json.loads(PARTIAL.read_text(encoding="utf-8"))


def test_template_and_partial_resume() -> None:
    assert resume(load_state(TEMPLATE)).current_stage == "frame"
    decision = resume(load_state(PARTIAL))
    assert decision.completed == ("frame", "data")
    assert decision.evidence["data"]["dataset_contract"] == "fixture://reviewed-dataset"
    assert decision.current_stage == "explore"
    assert decision.current_status == "blocked"
    assert decision.next_stage == "prepare"
    assert decision.allowed_action == "resolve_blocker"


def test_complete_state_and_roundtrip() -> None:
    state = template()
    state["references"] = {
        key: {"id": f"fixture/{key}", "version": "v1"}
        for key in ("dataset", "feature", "split", "experiment", "model")
    }
    evidence = {
        "frame": ("decision_contract",),
        "data": ("dataset_contract",),
        "explore": ("profile",),
        "prepare": ("feature_implementation",),
        "candidates": ("baseline_comparison",),
        "validate": ("frozen_evaluation_plan", "evaluation_result"),
        "communicate": ("model_card", "review_decision"),
        "operate": ("release_decision", "monitoring_plan"),
    }
    for name in STAGES:
        state["stages"][name] = {
            "status": "complete",
            "evidence": {key: f"fixture://{key}" for key in evidence[name]},
        }
    for name in ("communicate", "operate"):
        state["stages"][name]["review"] = {
            "state": "approved",
            "decision_ref": f"fixture://{name}-decision",
        }
    assert resume(state).current_stage is None
    assert json.loads(dump_state(state)) == state


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s.update(schema="atlas-ml-lifecycle/v2"),
        lambda s: s["stages"]["frame"].update(status="skipped"),
        lambda s: s["stages"].pop("operate"),
        lambda s: s["stages"]["prepare"].update(status="in_progress"),
        lambda s: s["stages"]["frame"].update(status="complete"),
        lambda s: s["stages"]["frame"].update(status="blocked"),
        lambda s: s.pop("holdout_history"),
    ],
)
def test_invalid_states(change) -> None:
    state = template()
    change(state)
    with pytest.raises(LifecycleError):
        validate_state(state)


def test_not_applicable_requires_reason_evidence_and_review() -> None:
    state = template()
    state["stages"]["frame"] = {"status": "not_applicable", "evidence": {}}
    for update in (
        {"reason": "Synthetic exception"},
        {"evidence": {"non_applicability": "fixture://reason"}},
    ):
        state["stages"]["frame"].update(update)
        with pytest.raises(LifecycleError):
            validate_state(state)
    state["stages"]["frame"]["review"] = {"state": "approved", "decision_ref": "fixture://review"}
    validate_state(state)


def test_missing_prior_evidence_is_not_resumable() -> None:
    state = partial()
    del state["stages"]["frame"]["evidence"]["decision_contract"]
    with pytest.raises(LifecycleError):
        resume(state)


def test_holdout_policy_and_auditable_repeat() -> None:
    state = template()
    state["references"] = {
        key: {"id": f"fixture/{key}", "version": "v1"}
        for key in ("dataset", "feature", "split", "experiment")
    }
    required = {
        "frame": "decision_contract",
        "data": "dataset_contract",
        "explore": "profile",
        "prepare": "feature_implementation",
        "candidates": "baseline_comparison",
    }
    for name, key in required.items():
        state["stages"][name] = {"status": "complete", "evidence": {key: f"fixture://{key}"}}
    state["stages"]["validate"] = {
        "status": "in_progress",
        "evidence": {"frozen_evaluation_plan": "fixture://frozen-plan"},
    }
    event = {
        "event_id": "fixture-1",
        "timestamp": "2026-01-01T00:00:00Z",
        "actor": "fixture-agent",
        "purpose": "final_evaluation",
        "split_ref": "fixture/split@v1",
        "evaluation_plan_ref": "fixture://frozen-plan",
        "result_ref": "fixture://result-1",
    }
    state["holdout_history"] = [event]
    validate_state(state)
    premature = copy.deepcopy(state)
    premature["stages"]["validate"]["evidence"] = {}
    with pytest.raises(LifecycleError):
        validate_state(premature)
    misuse = copy.deepcopy(state)
    misuse["holdout_history"][0]["purpose"] = "feature_selection"
    with pytest.raises(LifecycleError):
        validate_state(misuse)
    repeat = copy.deepcopy(event)
    repeat.update(event_id="fixture-2", result_ref="fixture://result-2")
    state["holdout_history"].append(repeat)
    with pytest.raises(LifecycleError):
        validate_state(state)
    repeat.update(repeat_reason="Audited re-evaluation", review_decision_ref="fixture://review")
    validate_state(state)
    repeat["event_id"] = "fixture-1"
    with pytest.raises(LifecycleError):
        validate_state(state)
