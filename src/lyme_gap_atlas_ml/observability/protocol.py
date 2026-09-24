"""The interface model and evaluation code may depend on."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .models import Actual, TelemetryRecord


@dataclass(frozen=True)
class TelemetryOutcome:
    sent: int
    status: str


@runtime_checkable
class ObservabilitySink(Protocol):
    def log_reference(self, rows: Sequence[TelemetryRecord]) -> TelemetryOutcome: ...

    def log_validation(self, rows: Sequence[TelemetryRecord]) -> TelemetryOutcome: ...

    def log_prediction(self, row: TelemetryRecord) -> TelemetryOutcome: ...

    def log_actual(self, actual: Actual) -> TelemetryOutcome: ...
