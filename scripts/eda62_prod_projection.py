"""Replay the admitted published PROD projection; screen before frozen selection."""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.eda62_analysis import analyze_selected, screen_taxa  # noqa: E402
from scripts.eda62_capture_gate import (  # noqa: E402
    PROD_BUNDLE,
    PROD_RELEASE,
    county_identity,
    load_pinned,
)

CAPTURE_SHA = "a62e522c2da8482a20fd1ad055fe280acd15c60e49f63d6b2d331f9fef50395e"
SELECTION_RECORD = "docs/methodology/62-prod-selection.md"


def validate_capture(payload: list[Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(payload) != 5 or len(payload[1]) != 1 or len(payload[3]) != 1 or len(payload[4]) != 1:
        raise ValueError("Invalid bounded capture shape")
    before, after = payload[1][0], payload[4][0]
    if (
        before != after
        or before["RELEASE_ID"] != PROD_RELEASE
        or before["BUNDLE_SHA256"] != PROD_BUNDLE
    ):
        raise ValueError("Release changed or differs from admitted projection")
    raw_rows = payload[2]
    identity_digest = county_identity(raw_rows, "FIPS")
    if [row["FIPS"] for row in raw_rows] != sorted(row["FIPS"] for row in raw_rows):
        raise ValueError("Capture ordering differs from registered query")
    rows = []
    for row in raw_rows:
        if row["RELEASE_ID"] != PROD_RELEASE or row["BUNDLE_SHA256"] != PROD_BUNDLE:
            raise ValueError("Mixed row release/bundle membership")
        if not isinstance(row["STATE"], str) or re.fullmatch(r"[A-Z]{2}", row["STATE"]) is None:
            raise ValueError("Invalid published state identity")
        for field in ("SCAPULARIS_STATUS", "PACIFICUS_STATUS"):
            if row[field] not in {"Established", "Reported", "No records", "Unknown", None}:
                raise ValueError("Unrecognized source-defined species state; no guessed mapping")
        rows.append({key.lower(): value for key, value in row.items()})
    state_by_prefix: dict[str, str] = {}
    for row in rows:
        previous = state_by_prefix.setdefault(row["fips"][:2], row["state"])
        if previous != row["state"]:
            raise ValueError("FIPS/state projection inconsistency")
    metadata = {
        "capture_sha256": CAPTURE_SHA,
        "release_id": PROD_RELEASE,
        "bundle_sha256": PROD_BUNDLE,
        "canonical_fips_sha256": identity_digest,
        "county_rows": len(rows),
        "capture_query_id": payload[3][0]["CAPTURE_QUERY_ID"],
        "published_projection_descriptive_eda_admitted": True,
        "native_lineage_or_ml_feature_admission_claimed": False,
    }
    return rows, metadata


def verify_context(path: Path) -> str:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8-sig"))
    expected = {
        "CURRENT_USER()": "MATTHEWCARAWAY",
        "CURRENT_ROLE()": "OH_LYME_PROD_RUNTIME",
        "CURRENT_DATABASE()": "ONE_HEALTH_LYME_GAP_ATLAS_PROD",
        "CURRENT_SCHEMA()": "PRESENTATION",
        "CURRENT_WAREHOUSE()": "OH_LYME_PROD_INGEST_XS_WH",
    }
    if value != [expected]:
        raise ValueError("Captured context does not match explicitly authorized consumer identity")
    return hashlib.sha256(raw).hexdigest()


def verify_selection_commit(commit: str, selected_taxon: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
        raise ValueError("Full registered selection commit required before outcomes")
    result = subprocess.run(
        ["git", "show", f"{commit}:{SELECTION_RECORD}"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    if CAPTURE_SHA not in result.stdout or selected_taxon not in result.stdout:
        raise ValueError("Committed selection does not identify the pinned capture and taxon")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--mode", choices=("screen", "analyze"), default="screen")
    parser.add_argument("--selection-commit")
    args = parser.parse_args()
    context_digest = verify_context(args.context)
    rows, metadata = validate_capture(load_pinned(args.capture, CAPTURE_SHA))
    metadata["context_sha256"] = context_digest
    screen = screen_taxa(rows)
    if args.mode == "screen":
        result = {**metadata, "screen": screen}
    else:
        taxon = screen["selected_taxon"]
        if taxon is None or args.selection_commit is None:
            raise ValueError("Outcome-blind eligible taxon and committed selection required")
        verify_selection_commit(args.selection_commit, taxon)
        result = {
            **metadata,
            "selection_commit": args.selection_commit,
            "analysis": analyze_selected(rows, taxon),
        }
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
