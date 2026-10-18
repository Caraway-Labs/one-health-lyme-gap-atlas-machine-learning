import json
from copy import deepcopy
from pathlib import Path

import pytest

from lyme_gap_atlas_ml.surveillance_situation_batch import (
    SituationBatchError,
    assemble,
)
from lyme_gap_atlas_ml.surveillance_situation_contract import load_contract

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / "config/experiments/119-latent-class-v1-result.json"
CONTRACT = ROOT / "config/models/138-surveillance-situation-models-v1.json"
APPROVAL = ROOT / "config/models/138-surveillance-situation-batch-v1-approval.json"
MANIFEST = ROOT / "config/models/138-surveillance-situation-batch-v1.json"
HANDOFF = ROOT / "docs/contracts/138-surveillance-situation-data-handoff-v1.md"


def _inputs() -> tuple[dict[str, object], object, dict[str, object]]:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    contract_payload = json.loads(CONTRACT.read_text(encoding="utf-8"))
    return result, load_contract(CONTRACT), contract_payload


def test_approval_matches_the_immutable_batch() -> None:
    approval = json.loads(APPROVAL.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    handoff = HANDOFF.read_text(encoding="utf-8")
    assert approval["approver"] == "Matthew Caraway"
    assert approval["approved_at"] == "2026-10-18T11:37:14-06:00"
    assert approval["approval_state"] == "approved_for_data_handoff"
    assert approval["batch_id"] == "surveillance-situation-batch"
    assert approval["batch_version"] == "v1"
    assert approval["git_sha"] == manifest["git_sha"]
    assert approval["release_id"] == manifest["release_id"]
    assert approval["bundle_sha256"] == manifest["bundle_sha256"]
    assert approval["county_sha256"] == manifest["county_sha256"]
    assert approval["class_dictionary_sha256"] == manifest["class_dictionary_sha256"]
    assert approval["compatibility_disposition"] == "carry forward"
    assert approval["compatibility_dated"] == "2026-10-18"
    assert approval["snowflake_objects_written"] == []
    assert (
        approval["production_mutation"] == "This repository does not mutate production Snowflake."
    )
    assert approval["publisher"] == {
        "repository": "Caraway-Labs/one-health-lyme-gap-atlas-data",
        "issue": 702,
    }
    assert [item["issue"] for item in approval["downstream"]] == [253, 650]
    assert "Matthew Caraway" in handoff
    assert "2026-10-18T11:37:14-06:00" in handoff
    assert "Data #702" in handoff
    assert "API #253" in handoff
    assert "web #650" in handoff
    assert "does not mutate production Snowflake" in handoff


def test_a_missing_or_repeated_county_stops_the_handoff() -> None:
    result, contract, payload = _inputs()
    missing = deepcopy(result)
    missing["estimands"]["four-state"]["assignments"].pop()
    with pytest.raises(SituationBatchError, match="3144 unique counties"):
        assemble(missing, contract, payload)
    repeated = deepcopy(result)
    rows = repeated["estimands"]["tick-pathogen"]["assignments"]
    rows.append(deepcopy(rows[0]))
    with pytest.raises(SituationBatchError, match="3144 unique counties"):
        assemble(repeated, contract, payload)


def test_count_and_unknown_drift_stop_without_a_new_version() -> None:
    result, contract, payload = _inputs()
    changed = deepcopy(result)
    row = next(
        item
        for item in changed["estimands"]["four-state"]["assignments"]
        if item["class_id"] == 0 and item["state"] not in {"AK", "HI"}
    )
    row["class_id"] = 3
    row["probability"] = [0.0, 0.0, 0.0, 1.0]
    with pytest.raises(SituationBatchError, match="class counts do not match"):
        assemble(changed, contract, payload)
    relocated = deepcopy(result)
    assignments = relocated["estimands"]["four-state"]["assignments"]
    alaska = next(item for item in assignments if item["state"] == "AK")
    continental = next(
        item for item in assignments if item["class_id"] == 0 and item["state"] not in {"AK", "HI"}
    )
    alaska["class_id"] = 0
    alaska["probability"] = [1.0, 0.0, 0.0, 0.0]
    continental["class_id"] = 1
    continental["probability"] = [0.0, 1.0, 0.0, 0.0]
    with pytest.raises(SituationBatchError, match="Alaska and Hawaii"):
        assemble(relocated, contract, payload)
