"""Acquire once or replay a private #65 governed snapshot; print no county rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from lyme_gap_atlas_ml.evidence_association_65 import analyze_counties
from lyme_gap_atlas_ml.snowflake.evidence_65 import acquire, open_bounded_connection


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--acquire", action="store_true")
    action.add_argument("--snapshot", type=Path)
    parser.add_argument("--expected-sha256", help="Required for replay; digest from original run")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
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
        result["disposition"] = "NOT_ESTIMABLE"
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
