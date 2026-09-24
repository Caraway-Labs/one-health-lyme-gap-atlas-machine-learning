"""Strict, offline validation of the Atlas ML lineage bundle v1."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, TypedDict, cast

SCHEMA = "atlas-ml-contracts/v1"
ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
VERSION = re.compile(r"^v[1-9][0-9]*(?:\.[0-9]+){0,2}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
SECRET_KEY = re.compile(
    r"(^|_)(?:password|passwd|pat|api_key|private_key|secret|credential|"
    r"connection_name|connection_selector|access_token)(?:_|$)",
    re.I,
)


class ContractError(ValueError):
    """A declaration is incomplete, incompatible, or unsafe."""


class Reference(TypedDict):
    id: str
    version: str


class ModelIdentity(TypedDict):
    id: str
    version: str
    family: str
    issue: str
    git_sha: str


class ContractBundle(TypedDict):
    schema: str
    model_spec: dict[str, Any]
    dataset: dict[str, Any]
    feature_set: dict[str, Any]
    split: dict[str, Any]
    evaluation: dict[str, Any]
    experiment: dict[str, Any]
    snowflake: dict[str, Any]
    arize: dict[str, Any]
    prediction: dict[str, Any]
    evidence: dict[str, Any]


def _object(
    value: Any, where: str, required: set[str], optional: set[str] | None = None
) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise ContractError(f"{where}: expected object")
    missing = required - value.keys()
    unknown = value.keys() - required - (optional or set())
    if missing or unknown:
        raise ContractError(f"{where}: missing {sorted(missing)}; unknown {sorted(unknown)}")
    return value


def _str(value: Any, where: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{where}: expected nonempty string")
    if pattern and not pattern.fullmatch(value):
        raise ContractError(f"{where}: invalid format")
    return value


def _strings(value: Any, where: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ContractError(f"{where}: expected {'nonempty ' if nonempty else ''}list")
    for i, item in enumerate(value):
        _str(item, f"{where}[{i}]")
    if len(value) != len(set(value)):
        raise ContractError(f"{where}: duplicate entry")
    return value


def _ref(value: Any, where: str) -> Reference:
    obj = _object(value, where, {"id", "version"})
    _str(obj["id"], f"{where}.id", ID)
    _str(obj["version"], f"{where}.version", VERSION)
    return cast(Reference, obj)


def _same(actual: Any, expected: Any, where: str) -> None:
    if actual != expected:
        raise ContractError(f"{where}: incompatible reference")


def _secret_keys(value: Any, where: str = "bundle") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if SECRET_KEY.search(key):
                raise ContractError(f"{where}.{key}: prohibited secret or local connection field")
            _secret_keys(child, f"{where}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _secret_keys(child, f"{where}[{index}]")


def _identity(value: Any, where: str) -> ModelIdentity:
    obj = _object(value, where, {"id", "version", "family", "issue", "git_sha"})
    _str(obj["id"], f"{where}.id", ID)
    _str(obj["version"], f"{where}.version", VERSION)
    _str(obj["family"], f"{where}.family", ID)
    if not re.fullmatch(
        r"https://github\.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/[1-9][0-9]*",
        _str(obj["issue"], f"{where}.issue"),
    ):
        raise ContractError(f"{where}.issue: expected owning repository issue URL")
    _str(obj["git_sha"], f"{where}.git_sha", SHA)
    return cast(ModelIdentity, obj)


def _model_spec(value: Any) -> dict[str, Any]:
    keys = {
        "schema",
        "identity",
        "objective",
        "intended_decision",
        "intended_uses",
        "prohibited_uses",
        "prediction_unit",
        "geography_grain",
        "time_grain",
        "target_description",
        "target_type",
        "prediction_horizon",
        "data_cutoff",
        "label_source",
        "label_maturity",
        "label_revision",
        "baseline_policy",
        "primary_metric",
        "secondary_metrics",
        "validation_strategy",
        "calibration_requirement",
        "explainability_requirement",
        "uncertainty_requirement",
        "monitoring_requirement",
        "retraining_review_policy",
    }
    obj = _object(value, "model_spec", keys)
    _same(obj["schema"], "atlas-ml-model-spec/v1", "model_spec.schema")
    _identity(obj["identity"], "model_spec.identity")
    for key in keys - {
        "schema",
        "identity",
        "intended_uses",
        "prohibited_uses",
        "secondary_metrics",
    }:
        _str(obj[key], f"model_spec.{key}")
    for key in ("intended_uses", "prohibited_uses"):
        _strings(obj[key], f"model_spec.{key}", nonempty=True)
    _strings(obj["secondary_metrics"], "model_spec.secondary_metrics")
    return obj


def _dataset(value: Any) -> dict[str, Any]:
    keys = {
        "schema",
        "ref",
        "provenance_ref",
        "geography_grain",
        "time_start",
        "time_end",
        "data_cutoff",
        "label_as_of",
        "governed_source_refs",
        "snapshot_ref",
        "quality_refs",
        "limitation_refs",
    }
    obj = _object(value, "dataset", keys)
    _same(obj["schema"], "atlas-ml-dataset/v1", "dataset.schema")
    _ref(obj["ref"], "dataset.ref")
    for key in keys - {"schema", "ref", "governed_source_refs", "quality_refs", "limitation_refs"}:
        _str(
            obj[key],
            f"dataset.{key}",
            DATE if key in {"time_start", "time_end", "data_cutoff", "label_as_of"} else None,
        )
    if obj["time_start"] > obj["time_end"] or obj["time_end"] > obj["data_cutoff"]:
        raise ContractError("dataset: invalid time range or cutoff")
    _strings(obj["governed_source_refs"], "dataset.governed_source_refs", nonempty=True)
    _strings(obj["quality_refs"], "dataset.quality_refs")
    _strings(obj["limitation_refs"], "dataset.limitation_refs")
    return obj


def _feature(value: Any) -> dict[str, Any]:
    keys = {
        "schema",
        "ref",
        "dataset_ref",
        "implementation_ref",
        "config_ref",
        "point_in_time_availability",
        "transformation_ref",
        "quality_ref",
        "coverage_ref",
    }
    obj = _object(value, "feature_set", keys)
    _same(obj["schema"], "atlas-ml-feature-set/v1", "feature_set.schema")
    _ref(obj["ref"], "feature_set.ref")
    _ref(obj["dataset_ref"], "feature_set.dataset_ref")
    for key in keys - {"schema", "ref", "dataset_ref"}:
        _str(obj[key], f"feature_set.{key}")
    return obj


def _split(value: Any) -> dict[str, Any]:
    keys = {
        "schema",
        "ref",
        "dataset_ref",
        "strategy",
        "temporal_boundaries",
        "grouping_semantics",
        "embargo",
        "label_maturity_cutoff",
        "holdout",
        "frozen_plan_ref",
    }
    obj = _object(value, "split", keys)
    _same(obj["schema"], "atlas-ml-split/v1", "split.schema")
    _ref(obj["ref"], "split.ref")
    _ref(obj["dataset_ref"], "split.dataset_ref")
    if obj["strategy"] not in {
        "iid",
        "stratified",
        "temporal",
        "grouped_spatial",
        "spatiotemporal",
    }:
        raise ContractError("split.strategy: unsupported strategy")
    for key in (
        "temporal_boundaries",
        "grouping_semantics",
        "embargo",
        "label_maturity_cutoff",
        "frozen_plan_ref",
    ):
        _str(obj[key], f"split.{key}")
    holdout = _object(obj["holdout"], "split.holdout", {"id", "protected", "plan_ref"})
    _str(holdout["id"], "split.holdout.id", ID)
    if holdout["protected"] is not True:
        raise ContractError("split.holdout.protected: must be true")
    _str(holdout["plan_ref"], "split.holdout.plan_ref")
    _same(holdout["plan_ref"], obj["frozen_plan_ref"], "split.holdout.plan_ref")
    if (
        obj["strategy"] in {"temporal", "spatiotemporal"}
        and obj["temporal_boundaries"] == "not-applicable"
    ):
        raise ContractError("split: temporal boundaries required")
    if (
        obj["strategy"] in {"grouped_spatial", "spatiotemporal"}
        and obj["grouping_semantics"] == "not-applicable"
    ):
        raise ContractError("split: grouping semantics required")
    return obj


def _evaluation(value: Any) -> dict[str, Any]:
    keys = {
        "schema",
        "ref",
        "primary_metric",
        "secondary_metrics",
        "calibration_measures",
        "coverage_measures",
        "required_baselines",
        "approved_slices",
        "minimum_evidence",
        "abstention_behavior",
        "error_cost_policy_ref",
        "frozen_plan_ref",
        "holdout_id",
    }
    obj = _object(value, "evaluation", keys)
    _same(obj["schema"], "atlas-ml-evaluation/v1", "evaluation.schema")
    _ref(obj["ref"], "evaluation.ref")
    for key in keys - {
        "schema",
        "ref",
        "secondary_metrics",
        "calibration_measures",
        "coverage_measures",
        "required_baselines",
        "approved_slices",
    }:
        _str(obj[key], f"evaluation.{key}", ID if key == "holdout_id" else None)
    for key in (
        "secondary_metrics",
        "calibration_measures",
        "coverage_measures",
        "approved_slices",
    ):
        _strings(obj[key], f"evaluation.{key}")
    _strings(obj["required_baselines"], "evaluation.required_baselines", nonempty=True)
    return obj


def _experiment(value: Any) -> dict[str, Any]:
    keys = {
        "schema",
        "ref",
        "run_id",
        "model_ref",
        "dataset_ref",
        "feature_ref",
        "split_ref",
        "evaluation_ref",
        "model_config_ref",
        "preprocessing_ref",
        "seeds",
        "runtime_ref",
        "dependency_ref",
        "git_sha",
    }
    obj = _object(value, "experiment", keys, {"parent_run_ref"})
    _same(obj["schema"], "atlas-ml-experiment/v1", "experiment.schema")
    for key in ("ref", "model_ref", "dataset_ref", "feature_ref", "split_ref", "evaluation_ref"):
        _ref(obj[key], f"experiment.{key}")
    for key in ("run_id", "model_config_ref", "preprocessing_ref", "runtime_ref", "dependency_ref"):
        _str(obj[key], f"experiment.{key}", ID if key == "run_id" else None)
    _str(obj["git_sha"], "experiment.git_sha", SHA)
    if (
        not isinstance(obj["seeds"], list)
        or not obj["seeds"]
        or any(type(seed) is not int or seed < 0 for seed in obj["seeds"])
    ):
        raise ContractError("experiment.seeds: expected nonempty list of nonnegative integers")
    if "parent_run_ref" in obj:
        _str(obj["parent_run_ref"], "experiment.parent_run_ref")
    return obj


def _snowflake(value: Any) -> dict[str, Any]:
    keys = {
        "schema",
        "model_ref",
        "dataset_ref",
        "experiment_ref",
        "run_id",
        "dataset_object_ref",
        "experiment_object_ref",
        "experiment_run_ref",
        "ml_job_ref",
        "registry_model_ref",
        "registry_version_ref",
    }
    obj = _object(value, "snowflake", keys, {"feature_store_ref"})
    _same(obj["schema"], "atlas-ml-snowflake-map/v1", "snowflake.schema")
    for key in ("model_ref", "dataset_ref", "experiment_ref"):
        _ref(obj[key], f"snowflake.{key}")
    for key in keys - {"schema", "model_ref", "dataset_ref", "experiment_ref"}:
        _str(obj[key], f"snowflake.{key}")
    if "feature_store_ref" in obj:
        _str(obj["feature_store_ref"], "snowflake.feature_store_ref")
    return obj


def _arize(value: Any) -> dict[str, Any]:
    keys = {
        "schema",
        "model_ref",
        "project_ref",
        "model_name",
        "model_version",
        "environment",
        "feature_logging_policy_ref",
        "prediction_logging_policy_ref",
        "actual_logging_policy_ref",
        "monitoring_policy_ref",
    }
    obj = _object(value, "arize", keys)
    _same(obj["schema"], "atlas-ml-arize-map/v1", "arize.schema")
    _ref(obj["model_ref"], "arize.model_ref")
    for key in keys - {"schema", "model_ref"}:
        _str(obj[key], f"arize.{key}")
    if obj["environment"] not in {"training", "validation", "production"}:
        raise ContractError("arize.environment: unsupported environment")
    return obj


def _prediction(value: Any) -> dict[str, Any]:
    keys = {
        "schema",
        "model_ref",
        "experiment_ref",
        "run_id",
        "dataset_ref",
        "feature_ref",
        "split_ref",
        "prediction_cutoff",
        "prediction_horizon",
        "inference_run_id",
        "git_sha",
        "output_contract_version",
    }
    obj = _object(value, "prediction", keys)
    _same(obj["schema"], "atlas-ml-prediction-identity/v1", "prediction.schema")
    for key in ("model_ref", "experiment_ref", "dataset_ref", "feature_ref", "split_ref"):
        _ref(obj[key], f"prediction.{key}")
    for key in (
        "run_id",
        "prediction_cutoff",
        "prediction_horizon",
        "inference_run_id",
        "git_sha",
        "output_contract_version",
    ):
        pattern = {
            "run_id": ID,
            "prediction_cutoff": DATE,
            "inference_run_id": ID,
            "git_sha": SHA,
            "output_contract_version": VERSION,
        }.get(key)
        _str(obj[key], f"prediction.{key}", pattern)
    return obj


def _evidence(value: Any) -> dict[str, Any]:
    obj = _object(
        value,
        "evidence",
        {
            "schema",
            "model_ref",
            "inference_run_id",
            "evaluation_ref",
            "monitoring_policy_ref",
            "monitoring_status",
            "evaluation_status",
        },
        {"monitoring_evidence_ref", "evaluation_evidence_ref"},
    )
    _same(obj["schema"], "atlas-ml-evidence/v1", "evidence.schema")
    _ref(obj["model_ref"], "evidence.model_ref")
    _ref(obj["evaluation_ref"], "evidence.evaluation_ref")
    _str(obj["inference_run_id"], "evidence.inference_run_id", ID)
    _str(obj["monitoring_policy_ref"], "evidence.monitoring_policy_ref")
    for kind in ("monitoring", "evaluation"):
        status = obj[f"{kind}_status"]
        ref = obj.get(f"{kind}_evidence_ref")
        if status not in {"not_collected", "available"}:
            raise ContractError(f"evidence.{kind}_status: unsupported status")
        if status == "available":
            _str(ref, f"evidence.{kind}_evidence_ref")
        elif ref is not None:
            raise ContractError(
                f"evidence.{kind}_evidence_ref: unavailable evidence cannot have ref"
            )
    return obj


def validate_bundle(raw: Any, *, lifecycle: Any | None = None) -> ContractBundle:
    """Validate every declaration and relationship; no network or credential lookup."""
    bundle = _object(
        raw,
        "bundle",
        {
            "schema",
            "model_spec",
            "dataset",
            "feature_set",
            "split",
            "evaluation",
            "experiment",
            "snowflake",
            "arize",
            "prediction",
            "evidence",
        },
    )
    _secret_keys(bundle)
    _same(bundle["schema"], SCHEMA, "bundle.schema")
    model = _model_spec(bundle["model_spec"])
    dataset = _dataset(bundle["dataset"])
    feature = _feature(bundle["feature_set"])
    split = _split(bundle["split"])
    evaluation = _evaluation(bundle["evaluation"])
    experiment = _experiment(bundle["experiment"])
    snowflake = _snowflake(bundle["snowflake"])
    arize = _arize(bundle["arize"])
    prediction = _prediction(bundle["prediction"])
    evidence = _evidence(bundle["evidence"])
    model_ref = {k: model["identity"][k] for k in ("id", "version")}
    refs = {
        "model": model_ref,
        "dataset": dataset["ref"],
        "feature": feature["ref"],
        "split": split["ref"],
        "evaluation": evaluation["ref"],
        "experiment": experiment["ref"],
    }
    if len({(ref["id"], ref["version"]) for ref in refs.values()}) != len(refs):
        raise ContractError("bundle: duplicate or colliding identity")
    for where, actual, expected in (
        ("feature_set.dataset_ref", feature["dataset_ref"], refs["dataset"]),
        ("split.dataset_ref", split["dataset_ref"], refs["dataset"]),
        ("experiment.model_ref", experiment["model_ref"], refs["model"]),
        ("experiment.dataset_ref", experiment["dataset_ref"], refs["dataset"]),
        ("experiment.feature_ref", experiment["feature_ref"], refs["feature"]),
        ("experiment.split_ref", experiment["split_ref"], refs["split"]),
        ("experiment.evaluation_ref", experiment["evaluation_ref"], refs["evaluation"]),
        ("snowflake.model_ref", snowflake["model_ref"], refs["model"]),
        ("snowflake.dataset_ref", snowflake["dataset_ref"], refs["dataset"]),
        ("snowflake.experiment_ref", snowflake["experiment_ref"], refs["experiment"]),
        ("arize.model_ref", arize["model_ref"], refs["model"]),
        ("prediction.model_ref", prediction["model_ref"], refs["model"]),
        ("prediction.experiment_ref", prediction["experiment_ref"], refs["experiment"]),
        ("prediction.dataset_ref", prediction["dataset_ref"], refs["dataset"]),
        ("prediction.feature_ref", prediction["feature_ref"], refs["feature"]),
        ("prediction.split_ref", prediction["split_ref"], refs["split"]),
        ("evidence.model_ref", evidence["model_ref"], refs["model"]),
        ("evidence.evaluation_ref", evidence["evaluation_ref"], refs["evaluation"]),
    ):
        _same(actual, expected, where)
    for where, actual, expected in (
        ("experiment.git_sha", experiment["git_sha"], model["identity"]["git_sha"]),
        ("snowflake.run_id", snowflake["run_id"], experiment["run_id"]),
        ("snowflake.registry_model_ref", snowflake["registry_model_ref"], model_ref["id"]),
        ("snowflake.registry_version_ref", snowflake["registry_version_ref"], model_ref["version"]),
        ("arize.model_name", arize["model_name"], model_ref["id"]),
        ("arize.model_version", arize["model_version"], model_ref["version"]),
        ("prediction.run_id", prediction["run_id"], experiment["run_id"]),
        (
            "prediction.prediction_horizon",
            prediction["prediction_horizon"],
            model["prediction_horizon"],
        ),
        ("evaluation.primary_metric", evaluation["primary_metric"], model["primary_metric"]),
        ("evaluation.frozen_plan_ref", evaluation["frozen_plan_ref"], split["frozen_plan_ref"]),
        ("evaluation.holdout_id", evaluation["holdout_id"], split["holdout"]["id"]),
        ("dataset.geography_grain", dataset["geography_grain"], model["geography_grain"]),
        ("model_spec.validation_strategy", model["validation_strategy"], split["strategy"]),
        (
            "evidence.inference_run_id",
            evidence["inference_run_id"],
            prediction["inference_run_id"],
        ),
        (
            "evidence.monitoring_policy_ref",
            evidence["monitoring_policy_ref"],
            arize["monitoring_policy_ref"],
        ),
    ):
        _same(actual, expected, where)
    if lifecycle is not None:
        from lyme_gap_atlas_ml.lifecycle import validate_state

        state = validate_state(lifecycle)
        for key in ("model", "dataset", "feature", "split", "experiment"):
            if key in state["references"]:
                _same(state["references"][key], refs[key], f"lifecycle.references.{key}")
        for event in state["holdout_history"]:
            _same(
                event["evaluation_plan_ref"],
                split["frozen_plan_ref"],
                "lifecycle.holdout_history.evaluation_plan_ref",
            )
    return cast(ContractBundle, bundle)


def load_bundle(path: Path, *, lifecycle: Any | None = None) -> ContractBundle:
    return validate_bundle(json.loads(path.read_text(encoding="utf-8")), lifecycle=lifecycle)


def dump_bundle(bundle: ContractBundle) -> str:
    validate_bundle(bundle)
    return json.dumps(bundle, indent=2, sort_keys=True) + "\n"
