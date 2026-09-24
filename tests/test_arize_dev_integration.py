"""Opt-in synthetic Arize transport proof; excluded from routine network activity."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lyme_gap_atlas_ml.contracts import validate_bundle
from lyme_gap_atlas_ml.observability.arize import ArizeSink
from lyme_gap_atlas_ml.observability.models import Environment, TelemetryPolicy, TelemetryRecord


@pytest.mark.skipif(
    os.environ.get("ATLAS_RUN_ARIZE_DEV_TEST") != "1",
    reason="set ATLAS_RUN_ARIZE_DEV_TEST=1 to opt into synthetic Arize transmission",
)
def test_synthetic_arize_stream() -> None:
    if not os.environ.get("ARIZE_API_KEY") or not os.environ.get("ATLAS_ARIZE_TEST_SPACE_ID"):
        pytest.skip("configure ARIZE_API_KEY and ATLAS_ARIZE_TEST_SPACE_ID locally")
    path = Path(__file__).parents[1] / "config/examples/synthetic-lineage-v1.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["arize"]["project_ref"] = os.environ["ATLAS_ARIZE_TEST_SPACE_ID"]
    bundle = validate_bundle(raw)
    sink = ArizeSink(
        bundle,
        TelemetryPolicy(policy_ref=bundle["arize"]["feature_logging_policy_ref"]),
        model_type="numeric",
    )
    record = TelemetryRecord(
        key=sink.key,
        environment=Environment.PRODUCTION,
        prediction_id="atlas-story-42-synthetic-proof",
        timestamp=datetime.now(UTC),
        prediction=0,
    )
    result = sink.log_prediction(record)
    print(
        f"Synthetic telemetry {result.status}: model={sink.key.model_id} "
        f"version={sink.key.model_version} space={sink.key.project_ref} "
        "environment=production payload=prediction; no private Atlas data transmitted"
    )
