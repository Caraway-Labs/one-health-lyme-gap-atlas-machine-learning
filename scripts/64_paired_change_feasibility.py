"""One bounded public CDC coverage read or exact snapshot replay for ML #64."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from lyme_gap_atlas_ml.paired_change import summarize_publisher_coverage

QUERY = {
    "$select": "year,fips,case_status,count(*) as n",
    "$where": "year between '2011' and '2019'",
    "$group": "year,fips,case_status",
    "$order": "year,fips,case_status",
    "$limit": "10000",
}
URL = "https://data.cdc.gov/resource/qtbi-xd4i.json?" + urlencode(QUERY)
MAX_BYTES = 2_000_000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--publisher", action="store_true", help="One public GET, 30-second timeout")
    mode.add_argument("--snapshot", type=Path, help="Replay existing aggregate response")
    parser.add_argument("--sha256", help="Required expected response digest for replay")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/ml64"))
    args = parser.parse_args()
    if args.publisher:
        with urlopen(URL, timeout=30) as response:  # noqa: S310
            body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("Response exceeds byte limit")
        receipt = {"url": URL, "retrieved_at": datetime.now(UTC).isoformat()}
    else:
        if not args.sha256:
            parser.error("--snapshot requires --sha256 to pin existing source bytes")
        if args.snapshot.stat().st_size > MAX_BYTES:
            raise ValueError("Snapshot exceeds byte limit")
        body = args.snapshot.read_bytes()
        receipt = {"url": URL, "mode": "EXACT_SNAPSHOT_REPLAY"}
    digest = hashlib.sha256(body).hexdigest()
    if args.sha256 and args.sha256 != digest:
        raise ValueError("Source response SHA-256 mismatch")
    rows = json.loads(body)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("Unexpected source response shape")
    summary = summarize_publisher_coverage(rows)
    result = {
        "source_scope": "PUBLISHER_CURRENT_NOT_GOVERNED_RUN_PINNED",
        "receipt": {**receipt, "sha256": digest, "bytes": len(body), "aggregate_rows": len(rows)},
        **summary,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.publisher:
        (args.output_dir / "publisher-response.json").write_bytes(body)
    text = json.dumps(result, indent=2)
    (args.output_dir / "coverage-result.json").write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
