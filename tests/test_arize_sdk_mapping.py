"""Optional SDK shape proof with a fake underlying ML resource."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("arize")

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


def test_sdk_stream_and_zero_actual_batch_shape() -> None:
    fake = FakeResource()
    sdk = _SDKMLClient(fake)
    sdk.log_stream(model_type="numeric", environment="production")
    assert fake.stream_call is not None
    assert fake.stream_call["model_type"] is ModelTypes.NUMERIC
    assert fake.stream_call["environment"] is Environments.PRODUCTION

    result = sdk.log_actual_batch(
        space_id="synthetic-space",
        model_name="synthetic-model",
        model_version="v1",
        model_type="numeric",
        prediction_id="synthetic-id",
        prediction_timestamp=1_700_000_000,
        actual_label=0,
    )
    assert result.result().status_code == 200
    assert fake.batch_call is not None
    assert fake.batch_call["dataframe"].iloc[0]["actual_label"] == 0
    assert fake.batch_call["schema"].actual_label_column_name == "actual_label"
    assert fake.batch_call["environment"] is Environments.PRODUCTION
