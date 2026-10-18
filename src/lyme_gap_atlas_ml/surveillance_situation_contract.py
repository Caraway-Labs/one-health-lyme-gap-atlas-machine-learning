"""Production identifiers for the two story 138 surveillance-situation models.

Fit A and fit B both used class indexes 0 through 3 in the research result.
Those indexes are not production identifiers. A production identifier belongs
to one model version and is refused by the other model.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

PROHIBITED_READINGS = (
    "disease risk",
    "incidence",
    "pathogen absence",
    "tier 1 priority",
)
FOUR_STATE_MODEL_ID = "surveillance-situation-four-state"
TICK_PATHOGEN_MODEL_ID = "surveillance-situation-tick-pathogen"
CONFIRMED_NAMES = {
    FOUR_STATE_MODEL_ID: (
        "Established blacklegged tick",
        "Unknown tick and pathogen status",
        "Western blacklegged tick recorded",
        "Pathogen not recorded",
    ),
    TICK_PATHOGEN_MODEL_ID: (
        "Established blacklegged tick",
        "Blacklegged tick not established, pathogen not recorded",
        "Western blacklegged tick established",
        "Unknown tick and pathogen status",
    ),
}
CONFIRMED_INDICATORS = {
    FOUR_STATE_MODEL_ID: (
        "HUMAN_STATUS",
        "SCAPULARIS_STATUS",
        "PACIFICUS_STATUS",
        "BURGDORFERI_STATUS",
    ),
    TICK_PATHOGEN_MODEL_ID: (
        "SCAPULARIS_STATUS",
        "PACIFICUS_STATUS",
        "BURGDORFERI_STATUS",
    ),
}
CONFIRMED_COUNTS = {
    FOUR_STATE_MODEL_ID: (801, 35, 112, 2196),
    TICK_PATHOGEN_MODEL_ID: (1325, 1687, 97, 35),
}
PINNED_RELEASE_ID = "governed-2026-10-15-january-climate-prod"
PINNED_BUNDLE_SHA256 = "53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d"
PRIMARY_SEED = 1192026
NATIONAL_COUNTY_COUNT = 3144


class SituationContractError(ValueError):
    """The surveillance-situation contract is internally inconsistent."""


@dataclass(frozen=True)
class SituationClass:
    """One named class inside one model version."""

    id: str
    fit_class_index: int
    name: str
    county_count: int
    description: str
    must_not_be_read_as: tuple[str, ...]


@dataclass(frozen=True)
class SituationModel:
    """One latent-class fit. Its class identifiers are not valid in the other fit."""

    id: str
    version: str
    role: str
    indicators: tuple[str, ...]
    classes: tuple[SituationClass, ...]

    def require(self, class_id: str) -> SituationClass:
        """Return the class when it belongs to this model."""
        for situation in self.classes:
            if situation.id == class_id:
                return situation
        raise SituationContractError(
            f"{class_id} is not a class of {self.id}; the two fits are not interchangeable"
        )


@dataclass(frozen=True)
class SituationContract:
    """The versioned production contract for both surveillance-situation fits."""

    models: tuple[SituationModel, ...]
    release_id: str
    bundle_sha256: str
    primary_seed: int
    inheritance_rule: str

    def model(self, model_id: str) -> SituationModel:
        """Return one fit by its model identifier."""
        for item in self.models:
            if item.id == model_id:
                return item
        raise SituationContractError(f"unknown surveillance-situation model: {model_id}")

    def require(self, model_id: str, class_id: str) -> SituationClass:
        """Refuse a class identifier that belongs to the other fit."""
        return self.model(model_id).require(class_id)


def default_contract_path() -> Path:
    """Return the repository path of the v1 contract."""
    return (
        Path(__file__).resolve().parents[2]
        / "config"
        / "models"
        / "138-surveillance-situation-models-v1.json"
    )


def load_contract(path: Path | None = None) -> SituationContract:
    """Load and check the production contract."""
    payload = json.loads((path or default_contract_path()).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise SituationContractError("surveillance-situation contract must be an object")
    return _contract(payload)


def _contract(payload: Mapping[str, object]) -> SituationContract:
    source = _input(payload)
    if source.get("release_id") != PINNED_RELEASE_ID:
        raise SituationContractError("contract release does not match the pinned fit")
    if source.get("bundle_sha256") != PINNED_BUNDLE_SHA256:
        raise SituationContractError("contract bundle does not match the pinned fit")
    if source.get("primary_seed") != PRIMARY_SEED:
        raise SituationContractError("contract seed does not match the pinned fit")
    if source.get("county_count") != NATIONAL_COUNTY_COUNT:
        raise SituationContractError("contract county count is not the national cohort")
    missingness = payload.get("missingness")
    if not isinstance(missingness, Mapping):
        raise SituationContractError("missingness rule is missing")
    if missingness.get("imputation") != "forbidden":
        raise SituationContractError("imputation is forbidden")
    if missingness.get("unknown") != "real_class_not_missing_assignment":
        raise SituationContractError("Unknown must remain a real class")
    if missingness.get("unavailable_is_not_zero") is not True:
        raise SituationContractError("unavailable surveillance is not zero")
    inheritance = payload.get("inheritance_rule")
    if not isinstance(inheritance, str) or "does not silently inherit" not in inheritance:
        raise SituationContractError("a later release must not silently inherit these assignments")
    if _strings(payload.get("prohibited_readings")) != PROHIBITED_READINGS:
        raise SituationContractError("prohibited readings do not match the confirmed contract")
    raw_models = payload.get("models")
    if not isinstance(raw_models, Sequence) or isinstance(raw_models, str):
        raise SituationContractError("models must be a list")
    models = tuple(_model(item) for item in raw_models)
    if tuple(model.id for model in models) != (FOUR_STATE_MODEL_ID, TICK_PATHOGEN_MODEL_ID):
        raise SituationContractError("the contract requires the two named fits in order")
    identifiers = [situation.id for model in models for situation in model.classes]
    if len(identifiers) != len(set(identifiers)):
        raise SituationContractError("class identifiers must be unique across both fits")
    return SituationContract(
        models=models,
        release_id=PINNED_RELEASE_ID,
        bundle_sha256=PINNED_BUNDLE_SHA256,
        primary_seed=PRIMARY_SEED,
        inheritance_rule=inheritance,
    )


def _strings(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list):
        return None
    items: list[str] = []
    for item in value:
        if not isinstance(item, str):
            return None
        items.append(item)
    return tuple(items)


def _input(payload: Mapping[str, object]) -> Mapping[str, object]:
    value = payload.get("input")
    if not isinstance(value, Mapping):
        raise SituationContractError("input identity is missing")
    return value


def _model(value: object) -> SituationModel:
    if not isinstance(value, Mapping):
        raise SituationContractError("model entry must be an object")
    model_id = value.get("id")
    if model_id not in CONFIRMED_NAMES:
        raise SituationContractError("unknown model identifier")
    if not isinstance(model_id, str):
        raise SituationContractError("model identifier must be text")
    if value.get("version") != "v1":
        raise SituationContractError("this contract version is v1")
    role = value.get("role")
    if not isinstance(role, str) or not role:
        raise SituationContractError("model role is missing")
    indicators = value.get("indicators")
    if not isinstance(indicators, list) or tuple(indicators) != CONFIRMED_INDICATORS[model_id]:
        raise SituationContractError(f"{model_id} indicators do not match the confirmed fit")
    raw_classes = value.get("classes")
    if not isinstance(raw_classes, Sequence) or isinstance(raw_classes, str):
        raise SituationContractError("classes must be a list")
    classes = tuple(_situation(model_id, item) for item in raw_classes)
    if tuple(item.fit_class_index for item in classes) != (0, 1, 2, 3):
        raise SituationContractError(f"{model_id} must contain fit classes 0 through 3")
    if tuple(item.name for item in classes) != CONFIRMED_NAMES[model_id]:
        raise SituationContractError(
            f"{model_id} names do not match the scientific-owner confirmation"
        )
    if tuple(item.county_count for item in classes) != CONFIRMED_COUNTS[model_id]:
        raise SituationContractError(f"{model_id} class counts do not match the pinned fit")
    if sum(item.county_count for item in classes) != NATIONAL_COUNTY_COUNT:
        raise SituationContractError(f"{model_id} class counts do not cover every county")
    return SituationModel(
        id=model_id,
        version="v1",
        role=role,
        indicators=tuple(str(item) for item in indicators),
        classes=classes,
    )


def _situation(model_id: str, value: object) -> SituationClass:
    if not isinstance(value, Mapping):
        raise SituationContractError("class entry must be an object")
    class_id = value.get("id")
    index = value.get("fit_class_index")
    name = value.get("name")
    count = value.get("county_count")
    description = value.get("description")
    prohibited = value.get("must_not_be_read_as")
    if (
        not isinstance(class_id, str)
        or not isinstance(index, int)
        or isinstance(index, bool)
        or not isinstance(name, str)
        or not isinstance(count, int)
        or isinstance(count, bool)
        or not isinstance(description, str)
        or not isinstance(prohibited, list)
    ):
        raise SituationContractError("class fields are incomplete")
    expected_id = f"{model_id}.v1.class-{index}"
    if class_id != expected_id:
        raise SituationContractError(f"{class_id} is not scoped to {model_id} v1")
    if tuple(prohibited) != PROHIBITED_READINGS:
        raise SituationContractError("each class must carry the prohibited readings")
    if not description.strip():
        raise SituationContractError("each class needs a description")
    return SituationClass(
        id=class_id,
        fit_class_index=index,
        name=name,
        county_count=count,
        description=description,
        must_not_be_read_as=PROHIBITED_READINGS,
    )
