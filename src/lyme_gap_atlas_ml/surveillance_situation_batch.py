"""Assemble the story 138 county handoff from the stored latent-class result.

The county file is a replay of the pinned assignments. This module does not
refit the model and does not open Snowflake.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from lyme_gap_atlas_ml.latent_class_fit import FitConfig
from lyme_gap_atlas_ml.latent_class_inputs import (
    DATASET_ID,
    DATASET_VERSION,
    FEATURE_SET_ID,
    FEATURE_SET_VERSION,
)
from lyme_gap_atlas_ml.surveillance_situation_contract import (
    FOUR_STATE_MODEL_ID,
    NATIONAL_COUNTY_COUNT,
    PRIMARY_SEED,
    PROHIBITED_READINGS,
    TICK_PATHOGEN_MODEL_ID,
    SituationClass,
    SituationContract,
    SituationContractError,
    SituationModel,
    load_contract,
)

BATCH_ID = "surveillance-situation-batch"
BATCH_VERSION = "v1"
APPROVAL_STATE = "approved_for_data_handoff"
PROBABILITY_SUM_TOLERANCE = 1e-6
NATIONAL_POPULATION = 331_097_593
FIT_RESULT_SCHEMA = "atlas-ml-latent-class-result/119-v1"
COUNTY_SCHEMA = "atlas-ml-surveillance-situation-county-batch/138-v1"
DICTIONARY_SCHEMA = "atlas-ml-surveillance-situation-class-dictionary/138-v1"
MANIFEST_SCHEMA = "atlas-ml-surveillance-situation-batch-manifest/138-v1"
UNKNOWN_CLASS_NAME = "Unknown tick and pathogen status"
UNKNOWN_STATE_COUNTS = {"AK": 30, "HI": 5}
STATE_FIPS_PREFIX = {"AK": "02", "HI": "15"}
ESTIMAND_FOR_MODEL = {
    FOUR_STATE_MODEL_ID: "four-state",
    TICK_PATHOGEN_MODEL_ID: "tick-pathogen",
}
EXPECTED_DEPENDENCIES = {"numpy": "2.2.6", "scikit-learn": "1.9.1"}
RESULT_PATH = "config/experiments/119-latent-class-v1-result.json"
CONFIG_PATH = "config/experiments/119-latent-class-v1.json"
CONTRACT_PATH = "config/models/138-surveillance-situation-models-v1.json"
DICTIONARY_PATH = "config/models/138-surveillance-situation-class-dictionary-v1.json"
MANIFEST_PATH = "config/models/138-surveillance-situation-batch-v1.json"
COUNTY_ARTIFACT = "outputs/138-surveillance-situation-batch-v1/county-assignments.json"
FEATURE_CONTRACT_PATH = "docs/contracts/119-surveillance-latent-class-dataset-v1.md"
BATCH_SCHEMA_PATH = "docs/contracts/138-surveillance-situation-batch-v1.schema.json"
HANDOFF_PATH = "docs/contracts/138-surveillance-situation-batch-v1.md"
COUNTY_ROW_COUNT = NATIONAL_COUNTY_COUNT * 2


class SituationBatchError(ValueError):
    """The stored fit does not replay into the production handoff."""


@dataclass(frozen=True)
class SituationBatch:
    """County rows, the class dictionary, and the unapproved batch manifest."""

    county_document: dict[str, object]
    dictionary_document: dict[str, object]
    manifest: dict[str, object]

    def county_bytes(self) -> bytes:
        """Canonical UTF-8 JSON for the untracked county handoff."""
        return document_bytes(self.county_document)

    def dictionary_bytes(self) -> bytes:
        """Canonical UTF-8 JSON for the class dictionary."""
        return document_bytes(self.dictionary_document)

    def write_county(self, root: Path) -> Path:
        """Write the county handoff and require its checksum to match."""
        artifact = self.manifest.get("county_artifact")
        digest = self.manifest.get("county_sha256")
        if artifact != COUNTY_ARTIFACT or not isinstance(digest, str):
            raise SituationBatchError("county artifact path is not the handoff location")
        path = root / artifact
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.county_bytes()
        path.write_bytes(payload)
        if sha256_hex(path.read_bytes()) != digest:
            raise SituationBatchError("county checksum does not match the written handoff")
        return path


def document_bytes(document: Mapping[str, object]) -> bytes:
    """Serialize JSON with stable keys and LF newlines."""
    text = json.dumps(document, indent=2, sort_keys=True, allow_nan=False)
    return (text + "\n").encode("utf-8")


def sha256_hex(payload: bytes) -> str:
    """Return the lowercase SHA-256 hex digest of file bytes."""
    return hashlib.sha256(payload).hexdigest()


def assemble_repository(root: Path | None = None) -> SituationBatch:
    """Replay the committed result against the production contract."""
    repo = root or Path(__file__).resolve().parents[2]
    contract_payload = _object_dict(_load(repo / CONTRACT_PATH), "model contract")
    result = _object_dict(_load(repo / RESULT_PATH), "latent-class result")
    config = _object_dict(_load(repo / CONFIG_PATH), "experiment config")
    _require_config(config)
    return assemble(result, load_contract(repo / CONTRACT_PATH), contract_payload)


def assemble(
    result: Mapping[str, object],
    contract: SituationContract,
    contract_payload: Mapping[str, object],
) -> SituationBatch:
    """Build the handoff from a stored result. Raise if the pinned counts drift."""
    _require_result_identity(result, contract, contract_payload)
    estimands = _object_dict(result.get("estimands"), "estimands")
    populations: dict[str, int] = {}
    county_models: list[dict[str, object]] = []
    for model in contract.models:
        estimand_name = ESTIMAND_FOR_MODEL.get(model.id)
        if estimand_name is None:
            raise SituationBatchError(f"unknown model in the production contract: {model.id}")
        rows = _rows(model, _object_dict(estimands.get(estimand_name), estimand_name), populations)
        county_models.append({"model_id": model.id, "model_version": model.version, "rows": rows})
    if len(populations) != NATIONAL_COUNTY_COUNT:
        raise SituationBatchError("the two fits do not cover the same counties")
    if sum(populations.values()) != NATIONAL_POPULATION:
        raise SituationBatchError("population scope does not match the pinned cohort")
    county_document: dict[str, object] = {
        "batch_id": BATCH_ID,
        "batch_version": BATCH_VERSION,
        "models": county_models,
        "schema": COUNTY_SCHEMA,
    }
    dictionary_document = _dictionary(contract)
    manifest = _manifest(
        contract,
        contract_payload,
        result,
        county_sha256=sha256_hex(document_bytes(county_document)),
        dictionary_sha256=sha256_hex(document_bytes(dictionary_document)),
    )
    return SituationBatch(county_document, dictionary_document, manifest)


def _rows(
    model: SituationModel,
    estimand: Mapping[str, object],
    populations: dict[str, int],
) -> list[dict[str, object]]:
    if estimand.get("selected_classes") != 4:
        raise SituationBatchError(f"{model.id} did not select four classes")
    fitted = _object_dict(estimand.get("model"), f"{model.id} model")
    if fitted.get("converged") is not True or fitted.get("seed") != PRIMARY_SEED:
        raise SituationBatchError(f"{model.id} is not the converged primary-seed fit")
    assignments = estimand.get("assignments")
    if not isinstance(assignments, list):
        raise SituationBatchError(f"{model.id} assignments are missing")
    rows = [_row(model, _object_dict(item, "assignment"), populations) for item in assignments]
    rows.sort(key=lambda item: str(item["county_fips"]))
    fips = [str(item["county_fips"]) for item in rows]
    if len(rows) != NATIONAL_COUNTY_COUNT or len(set(fips)) != NATIONAL_COUNTY_COUNT:
        raise SituationBatchError(f"{model.id} does not contain 3144 unique counties")
    _require_counts(model, rows)
    return rows


def _row(
    model: SituationModel,
    assignment: Mapping[str, object],
    populations: dict[str, int],
) -> dict[str, object]:
    fips = _fips(assignment.get("fips"))
    state = _state(assignment.get("state"))
    prefix = STATE_FIPS_PREFIX.get(state)
    if prefix is not None and not fips.startswith(prefix):
        raise SituationBatchError(f"{fips} does not match state {state}")
    if fips.startswith(tuple(STATE_FIPS_PREFIX.values())) and prefix is None:
        raise SituationBatchError(f"{fips} is Alaska or Hawaii with another state code")
    population = _population(assignment.get("population"))
    recorded = populations.setdefault(fips, population)
    if recorded != population:
        raise SituationBatchError(f"{fips} population differs between fits")
    class_index = _class_index(assignment.get("class_id"))
    raw_probability = assignment.get("probability")
    if not isinstance(raw_probability, list) or len(raw_probability) != 4:
        raise SituationBatchError(f"{fips} probability vector must have length 4")
    probabilities = [_probability(value) for value in raw_probability]
    if abs(sum(probabilities) - 1.0) > PROBABILITY_SUM_TOLERANCE:
        raise SituationBatchError(f"{fips} probabilities do not sum to 1")
    if class_index != max(range(4), key=probabilities.__getitem__):
        raise SituationBatchError(f"{fips} hard assignment does not match its probabilities")
    class_id = f"{model.id}.v1.class-{class_index}"
    try:
        model.require(class_id)
    except SituationContractError as error:
        raise SituationBatchError(str(error)) from error
    return {
        "class_id": class_id,
        "county_fips": fips,
        "population": population,
        "probabilities": [
            {"class_id": situation.id, "probability": probabilities[situation.fit_class_index]}
            for situation in model.classes
        ],
        "state": state,
    }


def _require_counts(model: SituationModel, rows: list[dict[str, object]]) -> None:
    counts = Counter(str(row["class_id"]) for row in rows)
    if tuple(counts[situation.id] for situation in model.classes) != tuple(
        situation.county_count for situation in model.classes
    ):
        raise SituationBatchError(f"{model.id} class counts do not match the pinned fit")
    unknown = _unknown_class(model)
    unknown_rows = [row for row in rows if row["class_id"] == unknown.id]
    state_counts = Counter(str(row["state"]) for row in unknown_rows)
    outside = [row for row in rows if row["state"] in UNKNOWN_STATE_COUNTS]
    if dict(state_counts) != UNKNOWN_STATE_COUNTS or len(outside) != unknown.county_count:
        raise SituationBatchError("Unknown is not exactly the 35 Alaska and Hawaii counties")
    if any(row["class_id"] != unknown.id for row in outside):
        raise SituationBatchError("an Alaska or Hawaii county is outside the Unknown class")


def _unknown_class(model: SituationModel) -> SituationClass:
    matches = [item for item in model.classes if item.name == UNKNOWN_CLASS_NAME]
    if len(matches) != 1:
        raise SituationBatchError(f"{model.id} needs one Unknown class")
    return matches[0]


def _dictionary(contract: SituationContract) -> dict[str, object]:
    return {
        "batch_id": BATCH_ID,
        "batch_version": BATCH_VERSION,
        "models": [_dictionary_model(model) for model in contract.models],
        "schema": DICTIONARY_SCHEMA,
    }


def _dictionary_model(model: SituationModel) -> dict[str, object]:
    return {
        "classes": [
            {
                "county_count": item.county_count,
                "description": item.description,
                "fit_class_index": item.fit_class_index,
                "id": item.id,
                "must_not_be_read_as": list(item.must_not_be_read_as),
                "name": item.name,
            }
            for item in model.classes
        ],
        "id": model.id,
        "indicators": list(model.indicators),
        "role": model.role,
        "version": model.version,
    }


def _manifest(
    contract: SituationContract,
    contract_payload: Mapping[str, object],
    result: Mapping[str, object],
    *,
    county_sha256: str,
    dictionary_sha256: str,
) -> dict[str, object]:
    research = _object_dict(contract_payload.get("research"), "research lineage")
    missingness = _object_dict(contract_payload.get("missingness"), "missingness")
    fit = FitConfig()
    return {
        "algorithm": "in-repository categorical latent class EM",
        "approval_state": APPROVAL_STATE,
        "batch_id": BATCH_ID,
        "batch_schema": BATCH_SCHEMA_PATH,
        "batch_version": BATCH_VERSION,
        "bundle_sha256": contract.bundle_sha256,
        "class_dictionary": DICTIONARY_PATH,
        "class_dictionary_sha256": dictionary_sha256,
        "config": CONFIG_PATH,
        "county_artifact": COUNTY_ARTIFACT,
        "county_row_count": COUNTY_ROW_COUNT,
        "county_sha256": county_sha256,
        "dependencies": dict(EXPECTED_DEPENDENCIES),
        "feature_contract": {
            "dataset_id": DATASET_ID,
            "dataset_version": DATASET_VERSION,
            "document": FEATURE_CONTRACT_PATH,
            "feature_set_id": FEATURE_SET_ID,
            "feature_set_version": FEATURE_SET_VERSION,
        },
        "git_sha": research.get("fit_code_revision"),
        "handoff_document": HANDOFF_PATH,
        "inheritance_rule": contract.inheritance_rule,
        "missingness_contract": {
            "document": CONTRACT_PATH,
            "imputation": missingness.get("imputation"),
            "no_records": missingness.get("no_records"),
            "unavailable_is_not_zero": missingness.get("unavailable_is_not_zero"),
            "unknown": missingness.get("unknown"),
        },
        "model_contract": CONTRACT_PATH,
        "models": [
            {"class_count": 4, "id": model.id, "role": model.role, "version": model.version}
            for model in contract.models
        ],
        "population_scope": {
            "county_count": NATIONAL_COUNTY_COUNT,
            "geography": "US counties and county equivalents, including Alaska and Hawaii",
            "population": NATIONAL_POPULATION,
            "population_role": "reporting denominator",
        },
        "primary_seed": contract.primary_seed,
        "probability_sum_tolerance": PROBABILITY_SUM_TOLERANCE,
        "prohibited_readings": list(PROHIBITED_READINGS),
        "release_id": contract.release_id,
        "result": RESULT_PATH,
        "result_commit": research.get("merged_commit"),
        "run": {
            "log_likelihood_tolerance": fit.tolerance,
            "max_em_iterations": fit.max_iterations,
            "random_starts_per_seed": fit.random_starts,
            "training_location": "local machine",
            "wall_clock_seconds_recorded": False,
        },
        "schema": MANIFEST_SCHEMA,
        "snowflake_objects_written": [],
        "stored_estimator": result.get("estimator"),
    }


def _require_result_identity(
    result: Mapping[str, object],
    contract: SituationContract,
    contract_payload: Mapping[str, object],
) -> None:
    research = _object_dict(contract_payload.get("research"), "research lineage")
    dataset = _object_dict(result.get("dataset"), "dataset")
    feature_set = _object_dict(result.get("feature_set"), "feature set")
    if (
        result.get("schema") != FIT_RESULT_SCHEMA
        or result.get("release_id") != contract.release_id
        or result.get("bundle_sha256") != contract.bundle_sha256
        or result.get("county_count") != NATIONAL_COUNTY_COUNT
        or result.get("code_revision") != research.get("fit_code_revision")
        or result.get("snowflake_objects_written") != []
        or result.get("estimator") != "in-repository categorical latent class EM"
        or result.get("dependencies") != EXPECTED_DEPENDENCIES
        or dataset.get("id") != DATASET_ID
        or dataset.get("version") != DATASET_VERSION
        or feature_set.get("id") != FEATURE_SET_ID
        or feature_set.get("version") != FEATURE_SET_VERSION
    ):
        raise SituationBatchError("stored result does not match the pinned production contract")
    missingness = _object_dict(contract_payload.get("missingness"), "missingness")
    if (
        missingness.get("no_records") != "category"
        or missingness.get("unknown") != "real_class_not_missing_assignment"
        or missingness.get("imputation") != "forbidden"
        or missingness.get("unavailable_is_not_zero") is not True
        or "does not silently inherit" not in contract.inheritance_rule
    ):
        raise SituationBatchError("missingness contract is not the confirmed rule")


def _require_config(config: Mapping[str, object]) -> None:
    if (
        config.get("id") != "surveillance-latent-class-experiment"
        or config.get("version") != "v1"
        or config.get("primary_seed") != PRIMARY_SEED
        or config.get("fit_status") != "selected"
        or config.get("result") != RESULT_PATH
        or config.get("estimands") != ["four-state", "tick-pathogen"]
    ):
        raise SituationBatchError("experiment config is not the selected pinned fit")


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _object_dict(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SituationBatchError(f"{label} is missing")
    mapped: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise SituationBatchError(f"{label} has a non-text key")
        mapped[key] = item
    return mapped


def _fips(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{5}", value) is None:
        raise SituationBatchError("county FIPS must be five digits")
    return value


def _state(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[A-Z]{2}", value) is None:
        raise SituationBatchError("state must be a two-letter code")
    return value


def _population(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SituationBatchError("population must be a positive integer")
    return value


def _class_index(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in range(4):
        raise SituationBatchError("fit class index must be 0, 1, 2, or 3")
    return value


def _probability(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SituationBatchError("probability must be a finite number")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise SituationBatchError("probability must be finite and between 0 and 1")
    return number
