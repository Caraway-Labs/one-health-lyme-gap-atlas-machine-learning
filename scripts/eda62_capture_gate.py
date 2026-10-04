"""Outcome-blind validation of the parent's shared approved consumer captures."""

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

DEV_SHA = "be74f3affff2e7753f14e7b804d672fb83d21eabe8f1dc4abead873ea21e8e45"
PROD_SHA = "5dbc0e4a66e1d702b5deafc3a430d62fe317984a6ee2e5c1759b74182f06e9ed"
PROD_MANIFEST_SHA = "1691467c100965fb6d5beb413179d4769dc51451cfb9424c8cd1df97186d0315"
FIPS_SHA = "f2651ec6a9375476e3ff09efb4c2a699cd5690ffd3f0c982aeacad967c21c241"
DEV_RELEASE = "governed-2026-09-17-unknown-coverage"
DEV_BUNDLE = "55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233"
PROD_RELEASE = "governed-2026-09-18-unknown-coverage"
PROD_BUNDLE = "038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026"


def load_pinned(path: Path, expected_sha: str) -> Any:
    if path.stat().st_size > 5_000_000:
        raise ValueError("Capture exceeds 5 MB bound")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("Capture digest mismatch; do not substitute another input")
    return json.loads(raw.decode("utf-8-sig"))


def county_identity(rows: list[dict[str, Any]], key: str) -> str:
    if len(rows) != 3144:
        raise ValueError("Expected the registered 3,144 county universe")
    fips = [row[key] for row in rows]
    if len(set(fips)) != len(fips) or any(
        not isinstance(f, str) or re.fullmatch(r"[0-9]{5}", f) is None for f in fips
    ):
        raise ValueError("Invalid or duplicate county identity")
    digest = hashlib.sha256(("\n".join(sorted(fips)) + "\n").encode()).hexdigest()
    if digest != FIPS_SHA:
        raise ValueError("Canonical county set differs from registered shared identity")
    return digest


def gate_dev(payload: list[Any]) -> dict[str, Any]:
    if (
        len(payload) != 6
        or len(payload[1]) != 1
        or len(payload[5]) != 1
        or len(payload[2]) > 10
        or len(payload[3]) > 100
    ):
        raise ValueError("Invalid shared DEV capture shape")
    before, after = payload[1][0], payload[5][0]
    if (
        before != after
        or before["RELEASE_ID"] != DEV_RELEASE
        or before["BUNDLE_SHA256"] != DEV_BUNDLE
    ):
        raise ValueError("Shared DEV release identity mismatch")
    rows = payload[4]
    identity = county_identity(rows, "FIPS")
    if any(row["RELEASE_ID"] != DEV_RELEASE for row in rows):
        raise ValueError("Mixed county release membership")
    if any(row.get("RELEASE_VERSION") != DEV_RELEASE for row in payload[2] + payload[3]):
        raise ValueError("Shared metadata release mismatch")
    states = {
        key: dict(Counter(row.get(key) for row in rows))
        for key in ("SCAPULARIS_STATUS", "PACIFICUS_STATUS")
    }
    all_unknown = all(counts == {"Unknown": 3144} for counts in states.values())
    return {
        "release_id": DEV_RELEASE,
        "bundle_sha256": DEV_BUNDLE,
        "capture_sha256": DEV_SHA,
        "canonical_fips_sha256": identity,
        "county_rows": len(rows),
        "source_state_county_n": states,
        "cohort_disposition": "NOT_ESTIMABLE" if all_unknown else "SCREENING_PENDING",
        "positive_group_n_each_taxon": {"ESTABLISHED": 0, "REPORTED": 0} if all_unknown else None,
        "source_authority_verified": False,
        "outcome_statistics_inspected": False,
    }


def gate_prod_summary(payload: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    before, after = manifest["release_before"], manifest["release_after"]
    if (
        before != after
        or before["release_id"] != PROD_RELEASE
        or before["bundle_sha256"] != PROD_BUNDLE
    ):
        raise ValueError("Public shared release identity mismatch")
    if payload["release_id"] != PROD_RELEASE:
        raise ValueError("Summary release does not match stable manifest")
    rows = payload["counties"]
    identity = county_identity(rows, "fips")
    required = {"scapularis_status", "pacificus_status", "svi_percentile"}
    common_fields = set.intersection(*(set(row) for row in rows))
    missing = sorted(required - common_fields)
    return {
        "release_id": PROD_RELEASE,
        "bundle_sha256": PROD_BUNDLE,
        "capture_sha256": PROD_SHA,
        "canonical_fips_sha256": identity,
        "county_rows": len(rows),
        "missing_issue_fields": missing,
        "cohort_disposition": None,
        "execution_status": "SPECIES_OUTCOME_PROJECTION_MISSING"
        if missing
        else "SCREENING_PENDING",
        "species_group_n": None,
        "selected_taxon": None,
        "combined_tick_status_is_not_species_status": True,
        "source_authority_verified": False,
        "outcome_statistics_inspected": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--prod", type=Path, required=True)
    parser.add_argument("--prod-manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = load_pinned(args.prod_manifest, PROD_MANIFEST_SHA)
    print(
        json.dumps(
            {
                "dev": gate_dev(load_pinned(args.dev, DEV_SHA)),
                "prod": gate_prod_summary(load_pinned(args.prod, PROD_SHA), manifest),
                "prod_manifest_sha256": hashlib.sha256(args.prod_manifest.read_bytes()).hexdigest(),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
