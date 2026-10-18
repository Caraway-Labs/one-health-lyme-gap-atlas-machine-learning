from pathlib import Path

import pytest

from lyme_gap_atlas_ml.surveillance_situation_contract import (
    FOUR_STATE_MODEL_ID,
    TICK_PATHOGEN_MODEL_ID,
    SituationContractError,
    default_contract_path,
    load_contract,
)

ROOT = Path(__file__).resolve().parents[1]


def test_confirmed_names_are_scoped_to_one_model_version() -> None:
    contract = load_contract()
    four_state = contract.model(FOUR_STATE_MODEL_ID)
    tick = contract.model(TICK_PATHOGEN_MODEL_ID)
    assert [item.name for item in four_state.classes] == [
        "Established blacklegged tick",
        "Unknown tick and pathogen status",
        "Western blacklegged tick recorded",
        "Pathogen not recorded",
    ]
    assert [item.name for item in tick.classes] == [
        "Established blacklegged tick",
        "Blacklegged tick not established, pathogen not recorded",
        "Western blacklegged tick established",
        "Unknown tick and pathogen status",
    ]
    assert four_state.classes[0].id != tick.classes[0].id
    assert four_state.require(four_state.classes[0].id).county_count == 801
    assert tick.require(tick.classes[0].id).county_count == 1325


def test_a_class_from_one_fit_is_refused_by_the_other() -> None:
    contract = load_contract()
    foreign = contract.model(FOUR_STATE_MODEL_ID).classes[0].id
    with pytest.raises(SituationContractError, match="not interchangeable"):
        contract.require(TICK_PATHOGEN_MODEL_ID, foreign)


def test_contract_text_names_both_models_and_the_prohibited_readings() -> None:
    text = (ROOT / "docs/contracts/138-surveillance-situation-models-v1.md").read_text(
        encoding="utf-8"
    )
    contract = load_contract()
    for model in contract.models:
        assert model.id in text
        for situation in model.classes:
            assert situation.id in text
            assert situation.name in text
    for reading in ("disease risk", "incidence", "pathogen absence", "Tier 1 priority"):
        assert reading in text
    assert "does not silently inherit" in text
    assert default_contract_path().is_file()
