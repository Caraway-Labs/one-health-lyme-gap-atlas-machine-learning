"""Verify retained #63 public responses and one detail probe before aggregate EDA."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .evidence_association_65 import PATHOGEN, VECTOR, vector_state
from .shared_capture_65 import (
    BUILD_HEAD,
    PROD_BUNDLE,
    PROD_RELEASE,
    RECEIPTS,
    SOURCE_ANCHORS,
    SharedInputError,
    _no_duplicates,
    _verified_bytes,
)

PUBLIC_BASE = "https://api.carawaylabs.com"
PUBLIC_FILES = {
    "prod-api-metadata-before.json": ("/v1/atlas/metadata", 1_000_000),
    "prod-api-scores.json": (f"/v1/atlas/scores?dataset_version={PROD_RELEASE}", 5_000_000),
    "prod-api-sources.json": ("/v1/sources?page_size=100", 1_000_000),
    "prod-api-measures.json": ("/v1/measures?page_size=100", 1_000_000),
    "prod-api-metadata-after.json": ("/v1/atlas/metadata", 1_000_000),
}
EXPECTED_IDENTITY = {
    "release_id": PROD_RELEASE,
    "bundle_sha256": PROD_BUNDLE,
    "schema_version": "1.0.0",
    "methodology_version": "semantic-1.0.0",
}
CANONICAL_FIPS_SHA256 = "f2651ec6a9375476e3ff09efb4c2a699cd5690ffd3f0c982aeacad967c21c241"


def _identity(value: Any) -> None:
    if not isinstance(value, dict) or any(value.get(k) != v for k, v in EXPECTED_IDENTITY.items()):
        raise SharedInputError("public immutable release identity mismatch")


def load_public_capture(
    directory: Path,
    manifest_path: Path,
    manifest_sha256: str,
    scores_sha256: str,
    detail_path: Path,
    detail_sha256: str,
) -> tuple[list[dict[str, object]], dict[str, Any]]:
    """No network; verify raw response bytes, meaning, identity and bounded detail compatibility."""
    manifest = json.loads(
        _verified_bytes(manifest_path, manifest_sha256, 131072).decode("utf-8-sig"),
        object_pairs_hook=_no_duplicates,
    )
    if manifest.get("schema") != "ml63-shared-public-consumer-capture/v1":
        raise SharedInputError("shared public manifest version mismatch")
    _identity(manifest.get("release_before"))
    _identity(manifest.get("release_after"))
    if manifest.get("served_identity_unchanged") is not True:
        raise SharedInputError("unstable shared capture")
    records = manifest.get("files")
    if not isinstance(records, dict) or set(records) != set(PUBLIC_FILES):
        raise SharedInputError("five documented retained public responses required")
    payloads: dict[str, Any] = {}
    evidence: dict[str, Any] = {}
    for name, (route, maximum) in PUBLIC_FILES.items():
        record = records[name]
        if (
            record.get("url") != PUBLIC_BASE + route
            or record.get("timeout_seconds") != 30
            or record.get("max_bytes") != maximum
        ):
            raise SharedInputError("public route or bounds mismatch")
        expected = scores_sha256 if name == "prod-api-scores.json" else record.get("sha256")
        if record.get("sha256") != expected:
            raise SharedInputError("scores digest not bound to manifest")
        content = _verified_bytes(directory / name, expected, maximum)
        if record.get("bytes") != len(content):
            raise SharedInputError("retained public byte count mismatch")
        payloads[name] = json.loads(content.decode("utf-8-sig"), object_pairs_hook=_no_duplicates)
        evidence[name] = {"url": record["url"], "sha256": expected, "bytes": len(content)}
    for name in ("prod-api-metadata-before.json", "prod-api-metadata-after.json"):
        metadata = payloads[name]
        _identity(metadata)
        if metadata.get("scope") != "US_COUNTIES":
            raise SharedInputError("public geography scope mismatch")
        source_rows = metadata.get("sources")
        if not isinstance(source_rows, list):
            raise SharedInputError("public source vintage metadata missing")
        for key in SOURCE_ANCHORS:
            selected = [row for row in source_rows if row.get("key") == key]
            if len(selected) != 1 or selected[0].get("vintage") != "through 2025-12-31":
                raise SharedInputError("public cumulative vintage mismatch")
    sources = payloads["prod-api-sources.json"]
    measures = payloads["prod-api-measures.json"]
    for collection in (sources, measures):
        if (
            not isinstance(collection.get("data"), list)
            or len(collection["data"]) > 100
            or collection.get("meta", {}).get("next_page_token", "MISSING") is not None
            or any(row.get("release_version") != PROD_RELEASE for row in collection["data"])
        ):
            raise SharedInputError("incomplete or mismatched public metadata collection")
    for key, anchor in SOURCE_ANCHORS.items():
        selected = [row for row in sources["data"] if row.get("source_id") == key]
        if len(selected) != 1:
            raise SharedInputError("distinct public source identities required")
        source = selected[0]
        if (
            source.get("lineage_source_id") != "cdc_arbonet_tick_module"
            or source.get("dataset_id") != anchor["dataset_id"]
            or source.get("source_vintage") != "through 2025-12-31"
        ):
            raise SharedInputError("public source identity or period mismatch")
    scores = payloads["prod-api-scores.json"]
    if (
        scores.get("release_id") != PROD_RELEASE
        or scores.get("methodology_version") != "semantic-1.0.0"
    ):
        raise SharedInputError("public scores release or method mismatch")
    counties = scores.get("counties")
    if not isinstance(counties, list) or len(counties) != 3144:
        raise SharedInputError("public county array must contain 3144 rows")
    seen: set[str] = set()
    rows: list[dict[str, object]] = []
    for county in counties:
        required = {"fips", "in_contiguous_tick_scope", "tick_status", "burgdorferi_status"}
        if not isinstance(county, dict) or not required.issubset(county):
            raise SharedInputError("four explicit public evidence fields required")
        fips = county["fips"]
        if not isinstance(fips, str) or not re.fullmatch("[0-9]{5}", fips) or fips in seen:
            raise SharedInputError("invalid or duplicate public county identity")
        if type(county["in_contiguous_tick_scope"]) is not bool:
            raise SharedInputError("explicit public scope boolean required")
        if county["tick_status"] not in (*VECTOR, "Unknown") or county[
            "burgdorferi_status"
        ] not in (*PATHOGEN, "Unknown"):
            raise SharedInputError("unrecognized public documentation state")
        seen.add(fips)
        rows.append(
            {
                "RELEASE_ID": scores["release_id"],
                "FIPS": fips,
                "IN_CONTIGUOUS_TICK_SCOPE": county["in_contiguous_tick_scope"],
                "VECTOR_STATUS": county["tick_status"],
                "BURGDORFERI_STATUS": county["burgdorferi_status"],
            }
        )
    fips_digest = hashlib.sha256(("\n".join(sorted(seen)) + "\n").encode()).hexdigest()
    if (
        fips_digest != CANONICAL_FIPS_SHA256
        or manifest.get("canonical_fips_normalized_sha256") != fips_digest
    ):
        raise SharedInputError("canonical public county set mismatch")
    detail_bytes = _verified_bytes(detail_path, detail_sha256, 262144)
    detail = json.loads(detail_bytes.decode("utf-8-sig"), object_pairs_hook=_no_duplicates)
    _identity(detail.get("release"))
    if detail.get("fips") != "01001":
        raise SharedInputError("registered fixed detail identity mismatch")
    s, p = detail.get("scapularis_status"), detail.get("pacificus_status")
    if not ((s in VECTOR and p in VECTOR) or s == p == "Unknown"):
        raise SharedInputError("detail violates closed source species domain")
    union = vector_state(s, p) or "Unknown"
    if union != detail.get("tick_status"):
        raise SharedInputError("governed aggregate rollup mismatch")
    bulk_row = next((row for row in rows if row["FIPS"] == "01001"), None)
    if bulk_row is None or any(
        bulk_row[field] != detail.get(key)
        for field, key in (
            ("VECTOR_STATUS", "tick_status"),
            ("BURGDORFERI_STATUS", "burgdorferi_status"),
            ("IN_CONTIGUOUS_TICK_SCOPE", "in_contiguous_tick_scope"),
        )
    ):
        raise SharedInputError("fixed detail and bulk evidence disagree")
    return rows, {
        "representation": "public_governed_aggregate_no_species_reconstruction",
        "manifest_sha256": manifest_sha256,
        "scores_sha256": scores_sha256,
        "detail_sha256": detail_sha256,
        "canonical_fips_sha256": fips_digest,
        "files": evidence,
        "release": EXPECTED_IDENTITY,
        "historical_receipts": RECEIPTS,
        "manifest_source_anchors": SOURCE_ANCHORS,
        "producer_contract_head": BUILD_HEAD,
        "detail_projection_check": "fixed 01001 release/scope/source-domain/rollup/bulk match",
        "private_row_lineage_independently_verified": False,
        "reviewed_metadata_admission_established": False,
        "limit": "documentation association only; no species-specific inference or ML admission",
    }
