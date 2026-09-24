"""Validated, immutable Atlas telemetry values; no Arize SDK imports."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal, TypeAlias

Scalar: TypeAlias = str | bool | int | float
Label: TypeAlias = str | bool | int | float
_SAFE_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_FORBIDDEN = re.compile(
    r"password|passwd|token|secret|credential|api_key|private|email|phone|address|"
    r"contact|authorization|header|name|free_text|notes|comment|description",
    re.I,
)


class TelemetryError(ValueError):
    """Atlas payload or policy is unsafe or incompatible."""


class Environment(StrEnum):
    TRAINING = "training"
    VALIDATION = "validation"
    PRODUCTION = "production"


@dataclass(frozen=True)
class ModelKey:
    model_id: str
    model_version: str
    project_ref: str

    def __post_init__(self) -> None:
        if not self.model_id or not self.model_version or not self.project_ref:
            raise TelemetryError("model ID, version, and Arize project reference are required")


@dataclass(frozen=True)
class TelemetryPolicy:
    """Explicitly reviewed scalar field names; empty allowlists send no fields."""

    feature_names: frozenset[str] = frozenset()
    tag_names: frozenset[str] = frozenset()
    policy_ref: str = ""

    def __post_init__(self) -> None:
        if not self.policy_ref:
            raise TelemetryError("approved telemetry policy reference is required")
        for name in self.feature_names | self.tag_names:
            if not _SAFE_NAME.fullmatch(name) or _FORBIDDEN.search(name):
                raise TelemetryError("unsafe or non-scalar telemetry field name")


@dataclass(frozen=True)
class TelemetryRecord:
    key: ModelKey
    environment: Environment
    prediction_id: str
    timestamp: datetime
    prediction: Label
    features: dict[str, Scalar] = field(default_factory=dict)
    tags: dict[str, Scalar] = field(default_factory=dict)
    prediction_score: float | None = None
    actual: Label | None = None
    batch_id: str | None = None
    # Model uncertainty and source quality remain separate Atlas concepts. The
    # current Arize scalar adapter deliberately does not serialize either.
    uncertainty_interval: tuple[float, float] | None = None
    data_quality_state: str | None = None

    def __post_init__(self) -> None:
        _validate_common(self.prediction_id, self.timestamp)
        _validate_label(self.prediction)
        if self.actual is not None:
            _validate_label(self.actual)
        if self.prediction_score is not None and (
            isinstance(self.prediction_score, bool)
            or not math.isfinite(self.prediction_score)
            or not 0 <= self.prediction_score <= 1
        ):
            raise TelemetryError("prediction score must be a finite probability")
        if self.environment is Environment.VALIDATION and not self.batch_id:
            raise TelemetryError("validation batch ID is required")
        if self.uncertainty_interval is not None:
            low, high = self.uncertainty_interval
            if not all(math.isfinite(v) for v in (low, high)) or low > high:
                raise TelemetryError("invalid model uncertainty interval")
        if self.data_quality_state is not None and not self.data_quality_state:
            raise TelemetryError("invalid data quality state")


@dataclass(frozen=True)
class Actual:
    key: ModelKey
    prediction_id: str
    prediction_timestamp: datetime
    actual: Label
    observed_at: datetime
    environment: Literal[Environment.PRODUCTION] = Environment.PRODUCTION

    def __post_init__(self) -> None:
        _validate_common(self.prediction_id, self.prediction_timestamp)
        _validate_label(self.actual)
        if self.observed_at.tzinfo is None or self.observed_at < self.prediction_timestamp:
            raise TelemetryError("actual timestamp must follow prediction timestamp")
        if self.environment is not Environment.PRODUCTION:
            raise TelemetryError("delayed actuals require production environment")


def _validate_common(prediction_id: str, timestamp: datetime) -> None:
    if not prediction_id or len(prediction_id) > 128:
        raise TelemetryError("stable prediction ID is required")
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise TelemetryError("timezone-aware timestamp is required")
    # Arize accepts at most two years past and one year future; fail early so
    # events are never silently timestamped at ingestion time instead.
    now = datetime.now(UTC)
    if not now - timedelta(days=730) <= timestamp <= now + timedelta(days=365):
        raise TelemetryError("prediction timestamp outside Arize supported window")


def _validate_label(value: Label) -> None:
    if (
        not isinstance(value, (str, bool, int, float))
        or (isinstance(value, str) and (not value or len(value) > 100))
        or (isinstance(value, float) and not math.isfinite(value))
    ):
        raise TelemetryError("unsupported prediction or actual label")


def validate_fields(record: TelemetryRecord, policy: TelemetryPolicy) -> None:
    for values, allowed in (
        (record.features, policy.feature_names),
        (record.tags, policy.tag_names),
    ):
        if values.keys() - allowed:
            raise TelemetryError("unapproved telemetry field")
        for name, value in values.items():
            if not _SAFE_NAME.fullmatch(name) or _FORBIDDEN.search(name):
                raise TelemetryError("unsafe telemetry field name")
            if (
                not isinstance(value, (str, bool, int, float))
                or (isinstance(value, str) and len(value) > 100)
                or (isinstance(value, float) and not math.isfinite(value))
            ):
                raise TelemetryError("unsupported telemetry field value")
