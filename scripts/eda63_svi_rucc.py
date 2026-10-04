"""Replay the bounded Snowflake CLI snapshot; never initiate warehouse I/O."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lyme_gap_atlas_ml.eda63 import BUNDLE_SHA256, RELEASE, analyze, cohort

CANONICAL_NORMALIZED_SHA256 = "f2651ec6a9375476e3ff09efb4c2a699cd5690ffd3f0c982aeacad967c21c241"
PROJECTION_NORMALIZED_SHA256 = "011bab4449c3a0bd2ea2dda10c68aa76033b0ae910a954a54221f30c99ac9b6c"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--canonical-fips", type=Path, required=True)
    parser.add_argument("--replicates", type=int, default=2000)
    args = parser.parse_args()
    raw = args.snapshot.read_bytes()
    if len(raw) > 5_000_000:
        raise ValueError("snapshot exceeds 5 MB input bound")
    payload = json.loads(raw.decode("utf-8-sig"))
    if len(payload) != 4 or len(payload[1]) != 1 or len(payload[2]) > 10:
        raise ValueError("expected session status, one release, source metadata, county projection")
    release = payload[1][0]
    if release["RELEASE_ID"] != RELEASE or release["BUNDLE_SHA256"] != BUNDLE_SHA256:
        raise ValueError("published release identity/digest mismatch")
    sources = {source["SOURCE_KEY"]: source for source in payload[2]}
    if (
        sources.get("context_svi", {}).get("VINTAGE") != "2022 (2018-2022 ACS)"
        or sources.get("context_rucc", {}).get("VINTAGE") != "2023"
    ):
        raise ValueError("source vintage mismatch")
    canonical_raw = args.canonical_fips.read_bytes()
    canonical_lines = canonical_raw.decode("utf-8-sig").splitlines()
    if len(canonical_lines) != len(set(canonical_lines)):
        raise ValueError("duplicate canonical identity")
    canonical_normalized = ("\n".join(sorted(canonical_lines)) + "\n").encode()
    if hashlib.sha256(canonical_normalized).hexdigest() != CANONICAL_NORMALIZED_SHA256:
        raise ValueError("canonical identity digest mismatch")
    projection_digest = hashlib.sha256(
        json.dumps(payload[3], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if projection_digest != PROJECTION_NORMALIZED_SHA256:
        raise ValueError("county projection digest mismatch; changed snapshot requires review")
    counties, counts = cohort(payload[3], set(canonical_lines))
    result = {
        "release": release,
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "canonical_sha256": hashlib.sha256(canonical_raw).hexdigest(),
        "projection_normalized_sha256": projection_digest,
        "counts": counts,
        "analysis": analyze(counties, args.replicates),
    }
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
