"""Optional SDK shape proof with a fake underlying ML resource."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("arize")

from arize import ArizeClient  # noqa: E402
from arize.ml.types import Environments, ModelTypes  # noqa: E402

from lyme_gap_atlas_ml.observability.arize import _SDKMLClient  # noqa: E402


class FakeResource:
    def __init__(self) -> None:
        self.stream_call: dict[str, Any] | None = None
        self.batch_call: dict[str, Any] | None = None

    def log_stream(self, **kwargs: Any) -> Any:
        self.stream_call = kwargs
        return object()

    def log(self, **kwargs: Any) -> Any:
        self.batch_call = kwargs
        return type("Response", (), {"status_code": 200})()


def test_sdk_stream_shape() -> None:
    fake = FakeResource()
    sdk = _SDKMLClient(fake)
    sdk.log_stream(model_type="numeric", environment="production")
    assert fake.stream_call is not None
    assert fake.stream_call["model_type"] is ModelTypes.NUMERIC
    assert fake.stream_call["environment"] is Environments.PRODUCTION


@pytest.mark.parametrize(
    "environment, actual, model_type, batch_id",
    [
        ("training", 0, "numeric", None),
        ("training", False, "binary_classification", None),
        ("validation", 0, "numeric", "synthetic-validation"),
        ("validation", False, "binary_classification", "synthetic-validation"),
        ("production", 0, "numeric", None),
        ("production", False, "binary_classification", None),
    ],
)
def test_falsy_actual_batch_shape(
    environment: str, actual: int | bool, model_type: str, batch_id: str | None
) -> None:
    fake = FakeResource()
    sdk = _SDKMLClient(fake)
    prediction = None if environment == "production" else 1
    result = sdk.log_batch_record(
        space_id="synthetic-space",
        model_name="synthetic-model",
        model_version="v1",
        model_type=model_type,
        environment=environment,
        prediction_id="synthetic-id",
        prediction_timestamp=1_700_000_000,
        prediction_label=prediction,
        actual_label=actual,
        features={"synthetic_feature": 2} if prediction is not None else None,
        tags={"quality_tier": "synthetic"} if prediction is not None else None,
        batch_id=batch_id,
    )
    assert result.result().status_code == 200
    assert fake.batch_call is not None
    frame = fake.batch_call["dataframe"]
    schema = fake.batch_call["schema"]
    value = frame["_atlas_actual_label"].iloc[0]
    assert value == actual
    if type(actual) is bool:
        assert frame["_atlas_actual_label"].dtype == bool
    else:
        assert frame["_atlas_actual_label"].dtype.kind in "iu"
    assert schema.actual_label_column_name == "_atlas_actual_label"
    assert schema.prediction_id_column_name == "_atlas_prediction_id"
    assert schema.timestamp_column_name == "_atlas_prediction_ts"
    assert fake.batch_call["environment"] is getattr(Environments, environment.upper())
    assert fake.batch_call["model_type"] is getattr(ModelTypes, model_type.upper())
    assert fake.batch_call["batch_id"] == (batch_id or "")
    assert fake.batch_call["space_id"] == "synthetic-space"
    assert fake.batch_call["model_name"] == "synthetic-model"
    assert fake.batch_call["model_version"] == "v1"
    if prediction is None:
        assert schema.prediction_label_column_name is None
        assert schema.feature_column_names is None
        assert schema.tag_column_names is None
        assert set(frame.columns) == {
            "_atlas_prediction_id",
            "_atlas_prediction_ts",
            "_atlas_actual_label",
        }
    else:
        assert schema.prediction_label_column_name == "_atlas_prediction_label"
        assert schema.feature_column_names == ["synthetic_feature"]
        assert schema.tag_column_names == ["quality_tier"]
        assert frame["synthetic_feature"].iloc[0] == 2
        assert frame["quality_tier"].iloc[0] == "synthetic"


@pytest.mark.parametrize(
    "environment, actual, model_type",
    [
        ("training", 0, "numeric"),
        ("training", False, "binary_classification"),
        ("validation", 0, "numeric"),
        ("validation", False, "binary_classification"),
        ("production", 0, "numeric"),
        ("production", False, "binary_classification"),
    ],
)
def test_installed_sdk_validates_and_preserves_falsy_actual(
    monkeypatch: pytest.MonkeyPatch, environment: str, actual: int | bool, model_type: str
) -> None:
    """Run the real SDK validator/Arrow encoder; intercept before HTTP upload."""
    captured: dict[str, Any] = {}

    def fake_upload(**kwargs: Any) -> Any:
        captured.update(kwargs)
        return type("Response", (), {"status_code": 200})()

    monkeypatch.setattr("arize.utils.arrow.post_arrow_table", fake_upload)
    sdk = _SDKMLClient(ArizeClient(api_key="synthetic-placeholder").ml)
    prediction = None if environment == "production" else 1
    result = sdk.log_batch_record(
        space_id="synthetic-space",
        model_name="synthetic-model",
        model_version="v1",
        model_type=model_type,
        environment=environment,
        prediction_id="synthetic-id",
        prediction_timestamp=int(datetime.now(UTC).timestamp()),
        prediction_label=prediction,
        actual_label=actual,
        features={"synthetic_feature": 2} if prediction is not None else None,
        tags={"quality_tier": "synthetic"} if prediction is not None else None,
        batch_id="synthetic-validation" if environment == "validation" else None,
    )
    assert result.result().status_code == 200
    values = captured["pa_table"].column("_atlas_actual_label").to_pylist()
    assert len(values) == 1
    assert values[0] is actual
