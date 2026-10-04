"""One fixed, release-pinned, bounded public detail projection check; no fanout."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

from lyme_gap_atlas_ml.shared_capture_65 import PROD_RELEASE


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    url = f"https://api.carawaylabs.com/v1/counties/01001?dataset_version={PROD_RELEASE}"
    with urlopen(url, timeout=30) as response:
        payload = response.read(262145)
        status = response.status
    if len(payload) > 262144:
        raise ValueError("fixed detail byte bound exceeded")
    (output / "detail-01001.json").write_bytes(payload)
    summary = {
        "url": url,
        "http_status": status,
        "timeout_seconds": 30,
        "max_bytes": 262144,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "observed_at": datetime.now(UTC).isoformat(),
        "fields": sorted(json.loads(payload)),
    }
    (output / "detail-probe.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
