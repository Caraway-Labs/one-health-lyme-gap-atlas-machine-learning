"""Offline contract, privacy, mapping and transport tests."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from lyme_gap_atlas_ml.contracts import validate_bundle
from lyme_gap_atlas_ml.observability.arize import (
    ArizeSink,
    IntegrationUnavailable,
    TelemetryFailure,
    key_from_bundle,
)
from lyme_gap_atlas_ml.observability.models import (
    Actual,
    Environment,
    TelemetryError,
    TelemetryPolicy,
    TelemetryRecord,
)
from lyme_gap_atlas_ml.observability.protocol import ObservabilitySink

EXAMPLE = Path(__file__).parents[1] / "config/examples/synthetic-lineage-v1.json"


class Future:
    def __init__(self, status: int) -> None:
        self.status = status

    def result(self, timeout: float | None = None) -> Any:
        return type("Response", (), {"status_code": self.status})()


class FakeML:
    def __init__(self, statuses: tuple[int, ...] = (200,)) -> None:
        self.calls: list[dict[str, Any]] = []
        self.stream_calls: list[dict[str, Any]] = []
        self.batch_calls: list[dict[str, Any]] = []
        self.statuses = statuses

    def _record(self, kwargs: dict[str, Any]) -> Future:
        self.calls.append(kwargs)
        index = min(len(self.calls) - 1, len(self.statuses) - 1)
        return Future(self.statuses[index])

    def log_stream(self, **kwargs: Any) -> Future:
        self.stream_calls.append(kwargs)
        return self._record(kwargs)

    def log_batch_record(self, **kwargs: Any) -> Future:
        self.batch_calls.append(kwargs)
        return self._record(kwargs)


def bundle() -> Any:
    return validate_bundle(json.loads(EXAMPLE.read_text(encoding="utf-8")))


def setup(
    statuses: tuple[int, ...] = (200,), retries: int = 0, model_type: str = "score_categorical"
) -> tuple[ArizeSink, FakeML]:
    contract = bundle()
    fake = FakeML(statuses)
    sink = ArizeSink(
        contract,
        TelemetryPolicy(
            frozenset({"synthetic_feature"}),
            frozenset({"quality_tier"}),
            contract["arize"]["feature_logging_policy_ref"],
        ),
        model_type=model_type,
        client=fake,
        max_retries=retries,
        sleep=lambda _: None,
    )
    return sink, fake


def row(sink: ArizeSink, environment: Environment = Environment.PRODUCTION) -> TelemetryRecord:
    return TelemetryRecord(
        key=sink.key,
        environment=environment,
        prediction_id="synthetic-prediction-1",
        timestamp=datetime.now(UTC),
        prediction="positive",
        prediction_score=0.3,
        features={"synthetic_feature": 2},
        tags={"quality_tier": "synthetic"},
        actual="positive" if environment is not Environment.PRODUCTION else None,
        batch_id="synthetic-validation-1" if environment is Environment.VALIDATION else None,
    )


def test_canonical_mapping_and_environment_paths() -> None:
    sink, fake = setup()
    assert isinstance(sink, ObservabilitySink)
    assert key_from_bundle(bundle()) == sink.key
    assert sink.log_reference([row(sink, Environment.TRAINING)]).sent == 1
    assert sink.log_validation([row(sink, Environment.VALIDATION)]).sent == 1
    assert sink.log_prediction(row(sink)).sent == 1
    assert [call["environment"] for call in fake.calls] == ["training", "validation", "production"]
    assert fake.calls[2]["model_name"] == sink.key.model_id
    assert fake.calls[2]["model_version"] == sink.key.model_version
    assert fake.calls[2]["space_id"] == sink.key.project_ref


@pytest.mark.parametrize("field,value", [("model_version", "v99"), ("project_ref", "other")])
def test_identity_mismatch_rejected(field: str, value: str) -> None:
    sink, fake = setup()
    wrong = replace(sink.key, **{field: value})
    with pytest.raises(TelemetryError, match="differs"):
        sink.log_prediction(replace(row(sink), key=wrong))
    assert not fake.calls


def test_lineage_mapping_mismatch_rejected() -> None:
    raw = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    raw["arize"]["model_version"] = "v99"
    with pytest.raises(ValueError, match="arize.model_version"):
        key_from_bundle(raw)


@pytest.mark.parametrize("actual_value", [0, False], ids=["numeric-zero", "boolean-false"])
def test_delayed_actual_falsy_is_not_missing(actual_value: int | bool) -> None:
    sink, fake = setup(
        model_type="numeric" if type(actual_value) is int else "binary_classification"
    )
    prediction = replace(row(sink), prediction=1, prediction_score=None)
    actual = Actual(
        sink.key, prediction.prediction_id, prediction.timestamp, actual_value, datetime.now(UTC)
    )
    assert sink.log_actual(actual).sent == 1
    assert fake.calls[0]["prediction_id"] == prediction.prediction_id
    assert fake.calls[0]["actual_label"] is actual_value
    assert fake.calls[0]["prediction_label"] is None
    assert len(fake.batch_calls) == 1
    assert not fake.stream_calls


@pytest.mark.parametrize("environment", [Environment.TRAINING, Environment.VALIDATION])
@pytest.mark.parametrize("actual_value", [0, False], ids=["numeric-zero", "boolean-false"])
def test_reference_and_validation_falsy_actuals(
    environment: Environment, actual_value: int | bool
) -> None:
    sink, fake = setup(
        model_type="numeric" if type(actual_value) is int else "binary_classification"
    )
    record = replace(
        row(sink, environment), prediction=1, prediction_score=None, actual=actual_value
    )
    outcome = (
        sink.log_reference([record])
        if environment is Environment.TRAINING
        else sink.log_validation([record])
    )
    assert outcome.sent == 1
    assert len(fake.batch_calls) == 1
    assert not fake.stream_calls
    assert fake.batch_calls[0]["actual_label"] is actual_value
    assert fake.batch_calls[0]["environment"] == environment.value
    assert fake.batch_calls[0]["batch_id"] == record.batch_id
    assert fake.batch_calls[0]["features"] == record.features
    assert fake.batch_calls[0]["tags"] == record.tags


def test_none_is_only_unavailable_actual() -> None:
    sink, fake = setup(model_type="numeric")
    production = replace(row(sink), prediction=1, prediction_score=None)
    assert production.actual is None
    assert sink.log_prediction(production).sent == 1
    assert len(fake.stream_calls) == 1
    assert fake.stream_calls[0]["actual_label"] is None
    assert not fake.batch_calls
    with pytest.raises(TelemetryError, match="ground truth"):
        sink.log_reference([replace(row(sink, Environment.TRAINING), actual=None)])
    with pytest.raises(TelemetryError):
        Actual(sink.key, production.prediction_id, production.timestamp, None, datetime.now(UTC))  # type: ignore[arg-type]


def test_invalid_timestamp_and_missing_prediction_id() -> None:
    sink, _ = setup()
    with pytest.raises(TelemetryError):
        replace(row(sink), prediction_id="")
    with pytest.raises(TelemetryError):
        replace(row(sink), timestamp=datetime(2026, 9, 24))


def test_allowlist_rejects_unknown_and_private_fields() -> None:
    sink, fake = setup()
    with pytest.raises(TelemetryError, match="unapproved"):
        sink.log_prediction(replace(row(sink), features={"other": 1}))
    with pytest.raises(TelemetryError, match="unsafe"):
        TelemetryPolicy(frozenset({"email"}), policy_ref="reviewed")
    assert not fake.calls


def test_credentials_absent_and_not_rendered(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ARIZE_API_KEY", raising=False)
    contract = bundle()
    contract["arize"]["project_ref"] = "synthetic-test-space"
    with pytest.raises(IntegrationUnavailable, match="ARIZE_API_KEY"):
        ArizeSink(
            contract,
            TelemetryPolicy(policy_ref=contract["arize"]["feature_logging_policy_ref"]),
            model_type="numeric",
        )
    monkeypatch.setenv("ARIZE_API_KEY", "synthetic-secret-sentinel")
    sink, _ = setup()
    assert "synthetic-secret-sentinel" not in repr(sink)


def test_retry_bounds_and_payload_immutability() -> None:
    sink, fake = setup((503, 503, 200), retries=2)
    prediction = row(sink)
    before = repr(prediction)
    sink.log_prediction(prediction)
    assert len(fake.calls) == 3
    assert repr(prediction) == before
    sink, fake = setup((503,), retries=1)
    with pytest.raises(TelemetryFailure, match="retry bound exhausted"):
        sink.log_prediction(row(sink))
    assert len(fake.calls) == 2
    sink, fake = setup((400,), retries=2)
    with pytest.raises(TelemetryFailure, match="rejected"):
        sink.log_prediction(row(sink))
    assert len(fake.calls) == 1


def test_fake_receives_atlas_owned_types() -> None:
    class FakeSink:
        def log_prediction(self, value: TelemetryRecord) -> None:
            assert isinstance(value, TelemetryRecord)

    sink, _ = setup()
    FakeSink().log_prediction(row(sink))
