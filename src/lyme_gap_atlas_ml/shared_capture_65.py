"""Local-only #65 shared PROD capture gates; no acquisition or authority expansion."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

PROD_RELEASE = "governed-2026-09-18-unknown-coverage"
PROD_BUNDLE = "038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026"
BUILD_HEAD = "7b80373187b8aa665891e2f39e6bf7f8c6fb35a1"
DATA_URL = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-data"
RECEIPTS = {
    "build_head": BUILD_HEAD,
    "manifest_path": "docs/contracts/semantic-release/governed-2026-09-15-manifest.json",
    "build_url": f"{DATA_URL}/actions/runs/35328355391",
    "publication_url": f"{DATA_URL}/actions/runs/35362701191",
    "build_status": "SUCCESS",
    "publication_status": "SUCCESS",
}
# Exact historical manifest anchors, not alternate source access or raw data.
SOURCE_ANCHORS = {
    "tick": {
        "dataset_id": "cdc-ixodes-county-status-2025",
        "data_source_version_id": "b81c116f-d93d-4c6b-9d11-ac2477e0e242",
        "ingestion_run_id": "ec14cc85-85d6-4064-80f1-1354238b88d6",
        "artifact_id": "e0db2aaf-7412-47d1-ac14-ba8807375549",
        "artifact_sha256": "e35a5066a7c77b2e79c50f315a18e042405ab7baa8a414a1a907792bb25d2adc",
    },
    "pathogen": {
        "dataset_id": "cdc-ixodes-pathogen-status-2025",
        "data_source_version_id": "92b22f19-0d5d-4576-a7c6-6c9af9343edf",
        "ingestion_run_id": "796731a3-cd7f-4510-aa0c-738ab74a6a76",
        "artifact_id": "d93ff6a3-4201-4a06-bfa3-da6026a706d9",
        "artifact_sha256": "68baef5f20b1e41821d0e6955cbb1809262e0f3624e387e88c04f6ddb0266f2f",
    },
}
FIELDS = (
    "RELEASE_ID",
    "FIPS",
    "IN_CONTIGUOUS_TICK_SCOPE",
    "SCAPULARIS_STATUS",
    "PACIFICUS_STATUS",
    "BURGDORFERI_STATUS",
)


class SharedInputError(ValueError):
    """Missing/invalid input evidence; scientific estimability remains unassessed."""


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SharedInputError("provenance object required")
    return value


def _digest(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch("[0-9a-f]{64}", value))


def validate_provenance(value: object, county_sha256: str) -> dict[str, Any]:
    """Validate declarations against inspected receipts before touching row statistics."""
    provenance = _object(value)
    if provenance.get("county_sha256") != county_sha256:
        raise SharedInputError("provenance does not bind county bytes")
    timestamp = provenance.get("observed_at")
    try:
        instant = datetime.fromisoformat(str(timestamp))
    except ValueError as error:
        raise SharedInputError("capture timestamp required") from error
    if instant.tzinfo is None:
        raise SharedInputError("capture timestamp must include timezone")
    release = _object(provenance.get("release"))
    expected = {
        "release_id": PROD_RELEASE,
        "bundle_sha256": PROD_BUNDLE,
        "schema_version": "1.0.0",
        "methodology_version": "semantic-1.0.0",
        "scope": "US_COUNTIES",
        "status": "PUBLISHED",
    }
    if any(release.get(key) != val for key, val in expected.items()):
        raise SharedInputError("PROD release/bundle/meaning mismatch")
    sources = provenance.get("sources")
    if not isinstance(sources, list) or len(sources) != 2:
        raise SharedInputError("two distinct source identities required")
    by_key: dict[str, dict[str, Any]] = {}
    for item in sources:
        source = _object(item)
        key = source.get("source_key")
        if not isinstance(key, str) or key not in SOURCE_ANCHORS or key in by_key:
            raise SharedInputError("distinct tick and pathogen sources required")
        by_key[key] = source
        anchor = SOURCE_ANCHORS[key] | {
            "source_id": "cdc_arbonet_tick_module",
            "vintage": "through 2025-12-31",
            "release_version": PROD_RELEASE,
        }
        if any(source.get(field) != expected for field, expected in anchor.items()):
            raise SharedInputError("source tuple or cumulative vintage mismatch")
    capture = _object(provenance.get("capture"))
    if capture.get("object") != (
        "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V"
    ):
        raise SharedInputError("approved PROD consumer object required")
    query_id = capture.get("query_id")
    if (
        not _digest(capture.get("query_sha256"))
        or not isinstance(query_id, str)
        or not re.fullmatch("[a-zA-Z0-9_-]{1,128}", query_id)
    ):
        raise SharedInputError("bounded capture query identity required")
    if capture.get("role") not in ("OH_LYME_PROD_READ", "OH_LYME_PROD_RUNTIME"):
        raise SharedInputError("existing authorized PROD read context required")
    context = {
        "user": "MATTHEWCARAWAY",
        "database": "ONE_HEALTH_LYME_GAP_ATLAS_PROD",
        "schema": "PRESENTATION",
        "warehouse": "OH_LYME_PROD_INGEST_XS_WH",
    }
    if any(capture.get(key) != expected for key, expected in context.items()):
        raise SharedInputError("captured PROD context mismatch")
    for key, maximum in (("row_limit", 3145), ("timeout_seconds", 30)):
        bound = capture.get(key)
        minimum = 3144 if key == "row_limit" else 1
        if type(bound) is not int or not minimum <= bound <= maximum:
            raise SharedInputError("capture bounds missing or excessive")
    receipts = _object(provenance.get("receipts"))
    if any(receipts.get(key) != expected for key, expected in RECEIPTS.items()):
        raise SharedInputError("reviewed build/publication receipt binding required")
    # Retain accepted provenance only, never incidental local paths/selectors/secrets.
    return {
        "county_sha256": county_sha256,
        "observed_at": timestamp,
        "release": expected_release(release),
        "sources": [
            {
                key: source[key]
                for key in (
                    "source_key",
                    "source_id",
                    "dataset_id",
                    "release_version",
                    "vintage",
                    "data_source_version_id",
                    "ingestion_run_id",
                    "artifact_id",
                    "artifact_sha256",
                )
            }
            for source in sources
        ],
        "capture": {
            key: capture[key]
            for key in (
                "object",
                "query_id",
                "query_sha256",
                "row_limit",
                "timeout_seconds",
                "user",
                "role",
                "database",
                "schema",
                "warehouse",
            )
        },
        "receipts": dict(RECEIPTS),
    }


def expected_release(release: dict[str, Any]) -> dict[str, Any]:
    return {
        key: release[key]
        for key in (
            "release_id",
            "bundle_sha256",
            "schema_version",
            "methodology_version",
            "scope",
            "status",
        )
    }


def _verified_bytes(path: Path, expected: str, maximum: int) -> bytes:
    if not _digest(expected) or path.stat().st_size > maximum:
        raise SharedInputError("invalid digest or input byte bound exceeded")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected:
        raise SharedInputError("shared input digest mismatch")
    return content


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SharedInputError("duplicate JSON key")
        result[key] = value
    return result


def load_shared_capture(
    county_path: Path,
    provenance_path: Path,
    county_sha256: str,
    provenance_sha256: str,
) -> tuple[list[dict[str, object]], dict[str, Any]]:
    """Validate sidecar first, then projection bytes; ignore unrelated context columns."""
    envelope_bytes = _verified_bytes(provenance_path, provenance_sha256, 131072)
    envelope = json.loads(envelope_bytes.decode("utf-8-sig"), object_pairs_hook=_no_duplicates)
    provenance = validate_provenance(envelope, county_sha256)
    county_bytes = _verified_bytes(county_path, county_sha256, 16 * 1024 * 1024)
    text = county_bytes.decode("utf-8-sig")
    csv_input = county_path.suffix.lower() == ".csv"
    if csv_input:
        reader = csv.DictReader(io.StringIO(text))
        names = reader.fieldnames
        if not names or len({name.upper() for name in names}) != len(names):
            raise SharedInputError("missing or duplicate CSV headers")
        if not set(FIELDS).issubset({name.upper() for name in names}):
            raise SharedInputError("six explicit consumer fields required")
        raw_rows: object = list(reader)
    else:
        raw_rows = json.loads(text, object_pairs_hook=_no_duplicates)
    if not isinstance(raw_rows, list) or len(raw_rows) != 3144:
        raise SharedInputError("exactly 3144 county projection rows required")
    rows: list[dict[str, object]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
            raise SharedInputError("county object with named columns required")
        upper = {key.upper(): val for key, val in raw.items()}
        if len(upper) != len(raw) or not set(FIELDS).issubset(upper):
            raise SharedInputError("missing or duplicate county fields")
        row = {key: upper[key] for key in FIELDS}
        if row["RELEASE_ID"] != PROD_RELEASE:
            raise SharedInputError("county release mismatch")
        if csv_input:
            scope = row["IN_CONTIGUOUS_TICK_SCOPE"]
            if not isinstance(scope, str) or scope.lower() not in ("true", "false", ""):
                raise SharedInputError("explicit CSV scope boolean required")
            row["IN_CONTIGUOUS_TICK_SCOPE"] = None if scope == "" else scope.lower() == "true"
            for key in FIELDS[3:]:
                if row[key] == "":
                    row[key] = None
        rows.append(row)
    return rows, provenance
