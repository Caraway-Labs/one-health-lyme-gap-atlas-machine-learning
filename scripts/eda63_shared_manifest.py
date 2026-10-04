"""Validate a shared DEV consumer capture without inspecting outcome statistics."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lyme_gap_atlas_ml.eda63 import BUNDLE_SHA256, RELEASE


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_capture(payload: list[Any]) -> dict[str, Any]:
    if (
        len(payload) != 6
        or len(payload[1]) != 1
        or len(payload[5]) != 1
        or len(payload[2]) > 10
        or len(payload[3]) > 100
        or len(payload[4]) != 3144
    ):
        raise ValueError("capture shape/row bounds mismatch")
    before, after = payload[1][0], payload[5][0]
    if (
        before != after
        or before["RELEASE_ID"] != RELEASE
        or before["BUNDLE_SHA256"] != BUNDLE_SHA256
    ):
        raise ValueError("release pointer/identity changed or wrong release")
    rows = payload[4]
    if any(row.get("RELEASE_VERSION") != RELEASE for row in payload[2] + payload[3]):
        raise ValueError("source/measure metadata release mismatch")
    fips = [row["FIPS"] for row in rows]
    if (
        len(set(fips)) != len(fips)
        or fips != sorted(fips)
        or any(row["RELEASE_ID"] != RELEASE for row in rows)
    ):
        raise ValueError("county identity/order mismatch")
    identity_digest = hashlib.sha256(("\n".join(fips) + "\n").encode()).hexdigest()
    if identity_digest != "f2651ec6a9375476e3ff09efb4c2a699cd5690ffd3f0c982aeacad967c21c241":
        raise ValueError("canonical FIPS digest mismatch")
    old_projection = [
        {key: row[key] for key in ["RELEASE_ID", "FIPS", "STATE", "SVI_PERCENTILE", "RUCC_2023"]}
        for row in rows
    ]
    if digest(old_projection) != "011bab4449c3a0bd2ea2dda10c68aa76033b0ae910a954a54221f30c99ac9b6c":
        raise ValueError("SVI/RUCC values differ from retained ML63 snapshot")
    return {
        "schema": "ml63-shared-consumer-capture/v1",
        "release_before": before,
        "release_after": after,
        "pointer_unchanged": True,
        "projection_rows": len(rows),
        "unique_counties": len(set(fips)),
        "source_metadata_rows": len(payload[2]),
        "measure_metadata_rows": len(payload[3]),
        "canonical_fips_normalized_sha256": identity_digest,
        "county_projection_normalized_sha256": digest(rows),
        "source_metadata_normalized_sha256": digest(sorted(payload[2], key=digest)),
        "measure_metadata_normalized_sha256": digest(sorted(payload[3], key=digest)),
        "county_fields": sorted(rows[0]),
        "sql": "sql/datasets/eda63_shared_consumer_capture.sql",
        "context": {
            "user": "MATTHEWCARAWAY",
            "role": "OH_LYME_DEV_READ",
            "database": "ONE_HEALTH_LYME_GAP_ATLAS_DEV",
            "schema": "PRESENTATION",
            "warehouse": "OH_LYME_DEV_INGEST_XS_WH",
        },
        "bounds": {
            "statement_timeout_seconds": 30,
            "select_count": 5,
            "row_limits": [1, 10, 100, 3145, 1],
        },
        "scope": (
            "Existing public DEV presentation views only; no writes or private authority reads"
        ),
        "limits": [
            "Source-record lineage and authoritative REVIEWED envelopes not captured",
            "SVI/RUCC already analyzed in ML63; added fields not statistically inspected",
            "Human numerator is 2023 only; not ML61's required 2022 numerator",
            "Native source row counts and publication/retrieval authority not inferred",
            "Capture conveys no new source acceptance or ML feature admission",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    args = parser.parse_args()
    raw = args.snapshot.read_bytes()
    if len(raw) > 5_000_000:
        raise ValueError("snapshot exceeds 5 MB")
    result = validate_capture(json.loads(raw.decode("utf-8-sig")))
    context_raw = args.context.read_bytes()
    context_row = json.loads(context_raw.decode("utf-8-sig"))[0][0]
    actual_context = {
        key: context_row[column]
        for key, column in {
            "user": "CURRENT_USER()",
            "role": "CURRENT_ROLE()",
            "database": "CURRENT_DATABASE()",
            "schema": "CURRENT_SCHEMA()",
            "warehouse": "CURRENT_WAREHOUSE()",
        }.items()
    }
    if actual_context != result["context"]:
        raise ValueError("captured context does not match authorized DEV scope")
    result["context_sha256"] = hashlib.sha256(context_raw).hexdigest()
    result["snapshot_sha256"] = hashlib.sha256(raw).hexdigest()
    result["manifest_generated_at"] = datetime.now(UTC).isoformat()
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
