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
TEMPLATE = ROOT / "docs/methodology/lifecycle-state-v2.template.json"
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
    assert decision.current_stage == "baseline"
    assert decision.current_status == "blocked"
    assert decision.next_stage == "evaluate"
    assert decision.allowed_action == "resolve_blocker"


def test_complete_state_and_roundtrip() -> None:
    state = template()
    state["references"] = {
        key: {"id": f"fixture/{key}", "version": "v1"}
        for key in ("dataset", "feature", "split", "experiment", "model")
    }
    evidence = {
        "frame": ("decision_contract",),
        "data": ("dataset_contract", "leakage_review"),
        "baseline": ("baseline_comparison", "validation_design"),
        "evaluate": ("frozen_evaluation_plan", "evaluation_result"),
        "decide": ("review_decision",),
    }
    for name in STAGES:
        state["stages"][name] = {
            "status": "complete",
            "evidence": {key: f"fixture://{key}" for key in evidence[name]},
        }
    for name in ("decide",):
        state["stages"][name]["review"] = {
            "state": "approved",
            "decision_ref": f"fixture://{name}-decision",
        }
    state["stages"]["decide"]["disposition"] = "DEFER"
    for field in ("disposition", "review"):
        invalid = copy.deepcopy(state)
        del invalid["stages"]["decide"][field]
        with pytest.raises(LifecycleError):
            validate_state(invalid)
    invalid = copy.deepcopy(state)
    invalid["stages"]["decide"]["disposition"] = "PROMOTE"
    with pytest.raises(LifecycleError, match="disposition"):
        validate_state(invalid)
    assert resume(state).current_stage is None
    assert json.loads(dump_state(state)) == state


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s.update(schema="atlas-ml-lifecycle/v1"),
        lambda s: s["stages"]["frame"].update(status="skipped"),
        lambda s: s["stages"].pop("decide"),
        lambda s: s["stages"]["evaluate"].update(status="in_progress"),
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
    state = partial()
    state["references"].update(
        {key: {"id": f"fixture/{key}", "version": "v1"} for key in ("split", "experiment")}
    )
    state["stages"]["baseline"] = {
        "status": "complete",
        "evidence": {
            "baseline_comparison": "fixture://baseline",
            "validation_design": "fixture://split-review",
        },
    }
    state["stages"]["evaluate"] = {"status": "not_applicable", "evidence": {}}
    for update in (
        {"reason": "Synthetic exception"},
        {"evidence": {"non_applicability": "fixture://reason"}},
    ):
        state["stages"]["evaluate"].update(update)
        with pytest.raises(LifecycleError):
            validate_state(state)
    state["stages"]["evaluate"]["review"] = {
        "state": "approved",
        "decision_ref": "fixture://review",
    }
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
        "frame": ("decision_contract",),
        "data": ("dataset_contract", "leakage_review"),
        "baseline": ("baseline_comparison", "validation_design"),
    }
    for name, keys in required.items():
        state["stages"][name] = {
            "status": "complete",
            "evidence": {key: f"fixture://{key}" for key in keys},
        }
    state["stages"]["evaluate"] = {
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
    assert resume(state).holdout_used is True
    premature_gate = copy.deepcopy(state)
    premature_gate["stages"]["baseline"]["status"] = "in_progress"
    premature_gate["stages"]["evaluate"]["status"] = "not_started"
    with pytest.raises(LifecycleError, match="before prerequisite gates"):
        validate_state(premature_gate)
    premature = copy.deepcopy(state)
    premature["stages"]["evaluate"]["evidence"] = {}
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


@pytest.mark.parametrize(
    "purpose",
    [
        "tuning",
        "feature_selection",
        "model_selection",
        "threshold_selection",
        "calibration_selection",
        "exploration",
        "prompt_iteration",
    ],
)
def test_holdout_selection_purposes_fail(purpose) -> None:
    state = partial()
    state["holdout_history"] = [{"event_id": "misuse", "purpose": purpose}]
    with pytest.raises(LifecycleError, match="prohibited purpose"):
        validate_state(state)


def test_missing_leakage_review_and_question_block_progress() -> None:
    state = partial()
    del state["stages"]["data"]["evidence"]["leakage_review"]
    with pytest.raises(LifecycleError, match="missing prerequisite evidence"):
        validate_state(state)
    state = template()
    state["stages"]["frame"] = {
        "status": "not_applicable",
        "reason": "No target",
        "evidence": {"non_applicability": "fixture://reason"},
        "review": {"state": "approved", "decision_ref": "fixture://review"},
    }
    with pytest.raises(LifecycleError, match="cannot be waived"):
        validate_state(state)


def test_baseline_and_validation_design_are_required() -> None:
    for missing in ("baseline_comparison", "validation_design"):
        state = partial()
        state["references"].update(
            {key: {"id": f"fixture/{key}", "version": "v1"} for key in ("split", "experiment")}
        )
        state["stages"]["baseline"] = {
            "status": "complete",
            "evidence": {
                key: "fixture://reviewed"
                for key in ("baseline_comparison", "validation_design")
                if key != missing
            },
        }
        with pytest.raises(LifecycleError, match="missing prerequisite evidence"):
            validate_state(state)


def test_resume_reports_holdout_unused() -> None:
    assert resume(partial()).holdout_used is False


def test_terminal_decide_cannot_omit_disposition_via_non_applicability() -> None:
    state = partial()
    state["references"].update(
        {key: {"id": f"fixture/{key}", "version": "v1"} for key in ("split", "experiment")}
    )
    state["stages"]["baseline"] = {
        "status": "complete",
        "evidence": {
            "baseline_comparison": "fixture://baseline",
            "validation_design": "fixture://validation",
        },
    }
    state["stages"]["evaluate"] = {
        "status": "complete",
        "evidence": {
            "frozen_evaluation_plan": "fixture://plan",
            "evaluation_result": "fixture://result",
        },
    }
    state["stages"]["decide"] = {
        "status": "not_applicable",
        "reason": "Abandoned run",
        "evidence": {"non_applicability": "fixture://reason"},
        "review": {"state": "approved", "decision_ref": "fixture://review"},
    }
    with pytest.raises(LifecycleError, match="disposition cannot be waived"):
        resume(state)
    from jsonschema import Draft202012Validator

    schema = json.loads((ROOT / "docs/methodology/lifecycle-state-v2.schema.json").read_text())
    assert not Draft202012Validator(schema).is_valid(state)


@pytest.mark.parametrize("disposition", ["PROMOTE", None, []])
@pytest.mark.parametrize("status", ["not_started", "in_progress", "blocked", "complete"])
def test_supplied_disposition_matches_schema_at_any_status(disposition, status) -> None:
    state = template()
    state["stages"]["frame"].update(
        status=status,
        disposition=disposition,
        evidence={"decision_contract": "fixture://question"},
        blocker={"dependency": "fixture://dependency", "reason": "Waiting"},
    )
    with pytest.raises(LifecycleError, match="invalid disposition"):
        validate_state(state)
    from jsonschema import Draft202012Validator

    schema = json.loads((ROOT / "docs/methodology/lifecycle-state-v2.schema.json").read_text())
    assert not Draft202012Validator(schema).is_valid(state)
