"""Acquire once or replay a private #65 governed snapshot; print no county rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from lyme_gap_atlas_ml.evidence_association_65 import analyze_aggregate_counties, analyze_counties
from lyme_gap_atlas_ml.public_capture_65 import load_public_capture
from lyme_gap_atlas_ml.shared_capture_65 import PROD_RELEASE, SharedInputError, load_shared_capture
from lyme_gap_atlas_ml.snowflake.evidence_65 import acquire, open_bounded_connection


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--acquire", action="store_true")
    action.add_argument("--snapshot", type=Path)
    action.add_argument("--shared-counties", type=Path, help="Local #63 PROD capture; no network")
    action.add_argument("--public-capture-directory", type=Path, help="Retained #63 public files")
    parser.add_argument("--expected-sha256", help="Required for replay; digest from original run")
    parser.add_argument("--provenance", type=Path)
    parser.add_argument("--expected-provenance-sha256")
    parser.add_argument("--public-manifest", type=Path)
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument("--detail", type=Path)
    parser.add_argument("--expected-detail-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.public_capture_directory:
        if not (
            args.public_manifest
            and args.expected_manifest_sha256
            and args.expected_sha256
            and args.detail
            and args.expected_detail_sha256
        ):
            parser.error("public replay requires manifest/scores/detail paths and byte digests")
        try:
            rows, provenance = load_public_capture(
                args.public_capture_directory,
                args.public_manifest,
                args.expected_manifest_sha256,
                args.expected_sha256,
                args.detail,
                args.expected_detail_sha256,
            )
            result = analyze_aggregate_counties(rows, PROD_RELEASE)
        except (OSError, ValueError, KeyError, TypeError) as error:
            result = {
                "status": "INPUT_BLOCKED",
                "scientific_estimability": "UNASSESSED",
                "counts": None,
                "error_type": type(error).__name__,
            }
            (args.output / "summary.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            print(json.dumps(result, indent=2))
            return 2
        result.update(provenance=provenance, scope_amendment="65-public-aggregate/v3")
        (args.output / "summary.json").write_text(
            json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.shared_counties:
        if not (args.expected_sha256 and args.provenance and args.expected_provenance_sha256):
            parser.error("shared input requires county digest, provenance and provenance digest")
        try:
            rows, provenance = load_shared_capture(
                args.shared_counties,
                args.provenance,
                args.expected_sha256,
                args.expected_provenance_sha256,
            )
            result = analyze_counties(rows, PROD_RELEASE)
        except (SharedInputError, OSError, ValueError) as error:
            # No data/counts/connector messages are printed for an invalid input.
            result = {
                "status": "INPUT_BLOCKED",
                "scientific_estimability": "UNASSESSED",
                "counts": None,
                "error_type": type(error).__name__,
            }
            (args.output / "summary.json").write_text(
                json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 2
        result.update(
            county_sha256=args.expected_sha256,
            provenance_sha256=args.expected_provenance_sha256,
            provenance=provenance,
            scope_amendment="65-prod-scope-amendment/v2",
        )
        (args.output / "summary.json").write_text(
            json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    if args.acquire:
        connection = open_bounded_connection()
        try:
            snapshot = acquire(connection)
        finally:
            connection.close()
        snapshot["observed_at"] = datetime.now(UTC).isoformat()
        path = args.output / "snapshot.json"
        path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    else:
        if not args.expected_sha256:
            parser.error("--snapshot requires --expected-sha256")
        path = args.snapshot
        if hashlib.sha256(path.read_bytes()).hexdigest() != args.expected_sha256:
            raise ValueError("private snapshot digest mismatch")
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if snapshot["status"] != "ACQUIRED":
        result = {k: v for k, v in snapshot.items() if k != "counties"}
        result["snapshot_sha256"] = digest
        result["disposition"] = "INPUT_BLOCKED"
        result["scientific_estimability"] = "UNASSESSED"
        result["counts"] = None
        result["reason"] = "access/execution blocked; no empirical cohort inspected"
        exit_code = 2
    else:
        result = analyze_counties(snapshot["counties"], snapshot["release"]["RELEASE_ID"])
        result.update(
            snapshot_sha256=digest,
            release=snapshot["release"],
            sources=snapshot["sources"],
            queries=snapshot["queries"],
            observed_at=snapshot["observed_at"],
        )
        exit_code = 0
    (args.output / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
