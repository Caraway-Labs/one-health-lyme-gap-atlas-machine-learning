"""Validate and replay the explicitly amended retrospective #61 input route offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lyme_gap_atlas_ml.eda61 import analyze
from lyme_gap_atlas_ml.eda61_research import MappingBlocked, admit, checked_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consumer", type=Path, required=True)
    parser.add_argument("--consumer-sha256", required=True)
    parser.add_argument("--publisher-dir", type=Path, required=True)
    parser.add_argument("--publisher-sha256", required=True)
    parser.add_argument("--metadata-sha256", required=True)
    parser.add_argument("--count-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--geography-amendment-v3", action="store_true")
    options = parser.parse_args()
    root = options.publisher_dir
    receipts = json.loads((root / "receipt.json").read_text(encoding="utf-8"))
    successful = {r["path"]: r for r in receipts if r["status"] == 200}
    names = ("rows-2022.json", "metadata-before.json", "metadata-after.json", "count-2022.json")
    pinned = (
        options.publisher_sha256,
        options.metadata_sha256,
        options.metadata_sha256,
        options.count_sha256,
    )
    if any(
        successful[name]["sha256"] != digest for name, digest in zip(names, pinned, strict=True)
    ):
        raise ValueError("retained receipt differs from independently pinned digests")
    inputs = [
        checked_bytes(root / name, digest) for name, digest in zip(names, pinned, strict=True)
    ]
    try:
        counties, result = admit(
            options.consumer.read_bytes(),
            options.consumer_sha256,
            inputs[0],
            options.publisher_sha256,
            inputs[1],
            inputs[2],
            inputs[3],
            successful["rows-2022.json"]["url"],
            geography_amendment_v3=options.geography_amendment_v3,
        )
    except MappingBlocked as error:
        options.output.parent.mkdir(parents=True, exist_ok=True)
        result = error.evidence
        result["request_receipts"] = receipts
        options.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"validation": "MAPPING_BLOCKED", "statistics_computed": False}))
        raise SystemExit(2) from error
    result["request_receipts"] = receipts
    if not options.validate_only:
        result["analysis"] = analyze(counties)
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(
        json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "validation": "PASS",
                "primary_counties": len(counties),
                "statistics_computed": not options.validate_only,
            }
        )
    )


if __name__ == "__main__":
    main()
