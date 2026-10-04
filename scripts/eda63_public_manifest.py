"""Validate retained anonymous public API responses without outcome statistics."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RELEASE = "governed-2026-09-18-unknown-coverage"
BUNDLE = "038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026"
REQUESTS = {
    "prod-api-metadata-before.json": ("/v1/atlas/metadata", 1_000_000),
    "prod-api-scores.json": (f"/v1/atlas/scores?dataset_version={RELEASE}", 5_000_000),
    "prod-api-sources.json": ("/v1/sources?page_size=100", 1_000_000),
    "prod-api-measures.json": ("/v1/measures?page_size=100", 1_000_000),
    "prod-api-metadata-after.json": ("/v1/atlas/metadata", 1_000_000),
}


def validate_public(payloads: dict[str, Any]) -> dict[str, Any]:
    before = payloads["prod-api-metadata-before.json"]
    after = payloads["prod-api-metadata-after.json"]
    keys = ["release_id", "bundle_sha256", "schema_version", "methodology_version"]
    if (
        any(before[key] != after[key] for key in keys)
        or before["release_id"] != RELEASE
        or before["bundle_sha256"] != BUNDLE
    ):
        raise ValueError("served release changed or identity mismatch")
    scores = payloads["prod-api-scores.json"]
    counties = scores["counties"]
    if scores["release_id"] != RELEASE or len(counties) != 3144:
        raise ValueError("public county count/release mismatch")
    fips = sorted(county["fips"] for county in counties)
    if len(set(fips)) != 3144:
        raise ValueError("duplicate public FIPS")
    identity_digest = hashlib.sha256(("\n".join(fips) + "\n").encode()).hexdigest()
    if identity_digest != "f2651ec6a9375476e3ff09efb4c2a699cd5690ffd3f0c982aeacad967c21c241":
        raise ValueError("public canonical county identity mismatch")
    metadata_counts = {}
    for filename in ["prod-api-sources.json", "prod-api-measures.json"]:
        response = payloads[filename]
        if (
            len(response["data"]) > 100
            or response["meta"]["next_page_token"] is not None
            or any(row["release_version"] != RELEASE for row in response["data"])
        ):
            raise ValueError("metadata incomplete or release mismatch")
        metadata_counts[filename] = len(response["data"])
    return {
        "schema": "ml63-shared-public-consumer-capture/v1",
        "release_before": {key: before[key] for key in keys},
        "release_after": {key: after[key] for key in keys},
        "served_identity_unchanged": True,
        "county_rows": len(counties),
        "unique_canonical_counties": len(set(fips)),
        "metadata_counts": metadata_counts,
        "canonical_fips_normalized_sha256": identity_digest,
        "county_summary_fields": sorted(counties[0]),
        "limits": [
            "Anonymous documented public API only; no warehouse identity or private authority",
            "New status outcomes captured without statistical profiling",
            "Summary has tick_status, burgdorferi_status and contiguous scope",
            "Summary lacks species statuses, population, SVI/RUCC and human floors",
            "Derived score components must never be substituted for source measures",
            "Public responses may be cached; consistency is not a warehouse transaction proof",
            "No private record/hash authority or REVIEWED metadata admission established",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    payloads = {}
    files = {}
    for filename, (route, size_limit) in REQUESTS.items():
        raw = (args.directory / filename).read_bytes()
        if len(raw) > size_limit:
            raise ValueError("public response exceeds byte bound")
        payloads[filename] = json.loads(raw.decode("utf-8-sig"))
        files[filename] = {
            "url": "https://api.carawaylabs.com" + route,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "timeout_seconds": 30,
            "max_bytes": size_limit,
        }
    result = validate_public(payloads)
    result["files"] = files
    result["manifest_generated_at"] = datetime.now(UTC).isoformat()
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
