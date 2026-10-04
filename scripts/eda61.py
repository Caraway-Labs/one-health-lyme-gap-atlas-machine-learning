"""Replay #61 from a reviewed immutable local snapshot; never query a warehouse."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lyme_gap_atlas_ml.eda61 import analyze, cohort


def replay(snapshot: Path, approval: Path) -> dict[str, object]:
    raw = snapshot.read_bytes()
    evidence = json.loads(approval.read_text(encoding="utf-8"))
    digest = hashlib.sha256(raw).hexdigest()
    if evidence.get("snapshot_sha256") != digest:
        raise ValueError("snapshot digest differs from reviewed approval")
    required = (
        "source_authority",
        "case_scope_2022",
        "population_acs_2018_2022_compatibility",
        "canonical_mapping",
        "source_record_identity",
        "source_release_membership",
    )
    for gate in required:
        item = evidence.get("gates", {}).get(gate, {})
        if item.get("status") != "PASS" or not item.get("evidence_ref"):
            raise ValueError(f"unvalidated scientific/source prerequisite: {gate}")
    sources = evidence.get("sources", [])
    if len(sources) != 2:
        raise ValueError("exactly two governed source identities required")
    if {source.get("resource_key") for source in sources} != {
        "cdc_lyme_x5j9_wybp",
        "cdc_atsdr_svi_2022_county",
    }:
        raise ValueError("requires the governed Lyme and SVI resources")
    for source in sources:
        for field in (
            "resource_key",
            "release_id",
            "data_source_version_id",
            "ingestion_run_id",
            "artifact_id",
            "artifact_sha256",
            "source_query_sha256",
        ):
            if not source.get(field):
                raise ValueError(f"missing source identity: {field}")
        for field in ("artifact_sha256", "source_query_sha256"):
            value = source[field]
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError(f"invalid source digest: {field}")
    data = json.loads(raw)
    if len(data["human"]) > 250000 or len(data["svi"]) > 3144:
        raise ValueError("snapshot exceeds the reviewed extraction row caps")
    counties, accounting = cohort(data["svi"], data["human"])
    return {
        "snapshot_sha256": digest,
        "source_evidence": evidence,
        "accounting": accounting,
        "analysis": analyze(counties),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    result = replay(options.snapshot, options.approval)
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
