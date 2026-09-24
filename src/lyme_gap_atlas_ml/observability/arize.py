"""The only Arize SDK integration for traditional ML telemetry."""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from importlib import import_module
from typing import Any, Protocol

from lyme_gap_atlas_ml.contracts import ContractBundle, validate_bundle

from .models import (
    Actual,
    Environment,
    ModelKey,
    TelemetryError,
    TelemetryPolicy,
    TelemetryRecord,
    validate_fields,
)
from .protocol import TelemetryOutcome


class IntegrationUnavailable(RuntimeError):
    """Local Arize configuration or optional SDK is unavailable."""


class TelemetryFailure(RuntimeError):
    """Submission failed; caller must record the missing telemetry evidence."""


class _Future(Protocol):
    def result(self, timeout: float | None = None) -> Any: ...


class _MLClient(Protocol):
    def log_stream(self, **kwargs: Any) -> _Future: ...

    def log_actual_batch(self, **kwargs: Any) -> _Future: ...


class _Immediate:
    def __init__(self, response: Any) -> None:
        self.response = response

    def result(self, timeout: float | None = None) -> Any:
        return self.response


class _SDKMLClient:
    def __init__(self, ml: Any) -> None:
        self.ml = ml

    def log_stream(self, **kwargs: Any) -> _Future:
        types = import_module("arize.ml.types")
        kwargs["model_type"] = getattr(types.ModelTypes, kwargs["model_type"].upper())
        kwargs["environment"] = getattr(types.Environments, kwargs["environment"].upper())
        return self.ml.log_stream(**kwargs)  # type: ignore[no-any-return]

    def log_actual_batch(self, **kwargs: Any) -> _Future:
        # The v8.55 stream implementation checks `if actual_label`, dropping
        # numeric 0 and False. An explicit one-row batch preserves them.
        pandas = import_module("pandas")
        types = import_module("arize.ml.types")
        frame = pandas.DataFrame(
            [
                {
                    "prediction_id": kwargs["prediction_id"],
                    "prediction_ts": kwargs["prediction_timestamp"],
                    "actual_label": kwargs["actual_label"],
                }
            ]
        )
        schema = types.Schema(
            prediction_id_column_name="prediction_id",
            timestamp_column_name="prediction_ts",
            actual_label_column_name="actual_label",
        )
        response = self.ml.log(
            space_id=kwargs["space_id"],
            model_name=kwargs["model_name"],
            model_type=getattr(types.ModelTypes, kwargs["model_type"].upper()),
            dataframe=frame,
            schema=schema,
            environment=types.Environments.PRODUCTION,
            model_version=kwargs["model_version"],
            timeout=30.0,
        )
        return _Immediate(response)


def key_from_bundle(bundle: ContractBundle) -> ModelKey:
    """Revalidate Story #41 lineage, then resolve exact Arize identity."""
    validated = validate_bundle(bundle)
    identity = validated["model_spec"]["identity"]
    mapping = validated["arize"]
    return ModelKey(identity["id"], identity["version"], mapping["project_ref"])


def _configured_ml_client() -> _MLClient:
    api_key = os.environ.get("ARIZE_API_KEY")
    if not api_key:
        raise IntegrationUnavailable("ARIZE_API_KEY is required for Arize telemetry")
    try:
        client_type = import_module("arize").ArizeClient
    except ImportError as exc:
        raise IntegrationUnavailable("install the optional arize dependency") from exc
    return _SDKMLClient(client_type(api_key=api_key).ml)


class ArizeSink:
    """Strict Atlas-to-Arize mapper with synchronous, visible delivery result.

    Retries are opt-in and restricted to explicit HTTP 429/5xx responses. An
    ambiguous exception may have transmitted data, so it is never retried.
    """

    def __init__(
        self,
        bundle: ContractBundle,
        policy: TelemetryPolicy,
        *,
        model_type: str,
        client: _MLClient | None = None,
        max_retries: int = 0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.key = key_from_bundle(bundle)
        mapping = bundle["arize"]
        if any(
            policy.policy_ref != mapping[name]
            for name in (
                "feature_logging_policy_ref",
                "prediction_logging_policy_ref",
                "actual_logging_policy_ref",
            )
        ):
            raise TelemetryError("telemetry policy reference differs from lineage")
        if max_retries < 0 or max_retries > 3:
            raise TelemetryError("retry count must be between zero and three")
        if model_type not in {
            "numeric",
            "score_categorical",
            "binary_classification",
            "regression",
        }:
            raise TelemetryError("model type is unsupported by the Atlas scalar adapter")
        self.policy = policy
        self.model_type = model_type
        if client is None and self.key.project_ref.startswith("fixture://"):
            raise IntegrationUnavailable(
                "replace synthetic project reference with approved space ID"
            )
        self.client = client if client is not None else _configured_ml_client()
        self.max_retries = max_retries
        self.sleep = sleep

    def _send(
        self,
        *,
        prediction_id: str,
        timestamp: int,
        environment: Environment,
        prediction: Any = None,
        actual: Any = None,
        features: dict[str, Any] | None = None,
        tags: dict[str, Any] | None = None,
        batch_id: str | None = None,
        actual_only: bool = False,
    ) -> None:
        kwargs = {
            "space_id": self.key.project_ref,
            "model_name": self.key.model_id,
            "model_version": self.key.model_version,
            "model_type": self.model_type,
            "environment": environment.value,
            "prediction_id": prediction_id,
            "prediction_timestamp": timestamp,
            "prediction_label": prediction,
            "actual_label": actual,
            "features": features or None,
            "tags": tags or None,
            "batch_id": batch_id,
            "timeout": 30.0,
        }
        for attempt in range(self.max_retries + 1):
            try:
                operation = self.client.log_actual_batch if actual_only else self.client.log_stream
                response = operation(**kwargs).result(timeout=35.0)
            except Exception:
                # SDK exception strings may include request details or secrets.
                raise TelemetryFailure(
                    "Arize telemetry submission failed; delivery uncertain"
                ) from None
            status = getattr(response, "status_code", None)
            if status is not None and 200 <= status < 300:
                return
            if status in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                self.sleep(min(2**attempt, 4))
                continue
            if status in {401, 403}:
                raise TelemetryFailure("Arize authentication or authorization failed")
            if status in {429, 500, 502, 503, 504}:
                raise TelemetryFailure("Arize transient failure; retry bound exhausted")
            raise TelemetryFailure("Arize rejected telemetry")

    def _check_key(self, key: ModelKey) -> None:
        if key != self.key:
            raise TelemetryError("telemetry model, version, or project differs from lineage")

    def _send_row(self, row: TelemetryRecord, required: Environment) -> None:
        self._check_key(row.key)
        if row.environment is not required:
            raise TelemetryError("telemetry environment mismatch")
        validate_fields(row, self.policy)
        if row.environment in {Environment.TRAINING, Environment.VALIDATION} and row.actual is None:
            raise TelemetryError("training and validation require ground truth")
        if row.actual is not None and not bool(row.actual):
            raise TelemetryError("send zero or false actual through log_actual")
        prediction: Any = row.prediction
        actual: Any = row.actual
        if self.model_type == "score_categorical":
            if not isinstance(prediction, str) or row.prediction_score is None:
                raise TelemetryError("score categorical needs a class and probability")
            prediction = (prediction, row.prediction_score)
            if actual is not None:
                if not isinstance(actual, str):
                    raise TelemetryError("score categorical actual must be a class label")
                actual = (actual, 1.0)
        elif row.prediction_score is not None:
            raise TelemetryError("score is unsupported for this model type")
        self._send(
            prediction_id=row.prediction_id,
            timestamp=int(row.timestamp.timestamp()),
            environment=row.environment,
            prediction=prediction,
            actual=actual,
            features=dict(row.features),
            tags=dict(row.tags),
            batch_id=row.batch_id,
        )

    def _send_rows(
        self, rows: Sequence[TelemetryRecord], environment: Environment
    ) -> TelemetryOutcome:
        if not rows or len(rows) > 1000:
            raise TelemetryError("telemetry batch must contain 1 to 1000 rows")
        if len({row.prediction_id for row in rows}) != len(rows):
            raise TelemetryError("duplicate prediction ID in batch")
        for row in rows:
            self._send_row(row, environment)
        return TelemetryOutcome(len(rows), "sent")

    def log_reference(self, rows: Sequence[TelemetryRecord]) -> TelemetryOutcome:
        return self._send_rows(rows, Environment.TRAINING)

    def log_validation(self, rows: Sequence[TelemetryRecord]) -> TelemetryOutcome:
        return self._send_rows(rows, Environment.VALIDATION)

    def log_prediction(self, row: TelemetryRecord) -> TelemetryOutcome:
        self._send_row(row, Environment.PRODUCTION)
        return TelemetryOutcome(1, "sent")

    def log_actual(self, actual: Actual) -> TelemetryOutcome:
        self._check_key(actual.key)
        value: Any = actual.actual
        if self.model_type == "score_categorical":
            if not isinstance(value, str):
                raise TelemetryError("score categorical actual must be a class label")
            value = (value, 1.0)
        self._send(
            prediction_id=actual.prediction_id,
            timestamp=int(actual.prediction_timestamp.timestamp()),
            environment=Environment.PRODUCTION,
            actual=value,
            actual_only=True,
        )
        return TelemetryOutcome(1, "sent")
