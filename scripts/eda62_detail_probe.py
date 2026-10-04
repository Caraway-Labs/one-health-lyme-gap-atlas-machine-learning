"""One documented anonymous public county detail probe; no cohort acquisition."""

import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

URL = (
    "https://api.carawaylabs.com/v1/counties/01001?"
    "dataset_version=governed-2026-09-18-unknown-coverage"
)
MAX_BYTES = 1_000_000


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Ignored private outputs path")
    args = parser.parse_args()
    ignored_root = Path(__file__).resolve().parents[1] / "outputs"
    if not args.output.resolve().is_relative_to(ignored_root.resolve()):
        raise ValueError("Private detail must stay in this worktree's ignored outputs directory")
    with urlopen(URL, timeout=30) as response:  # noqa: S310
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Detail response exceeds 1 MB bound")
    value = json.loads(raw)
    release = value["release"]
    if value["fips"] != "01001" or (
        release["release_id"] != "governed-2026-09-18-unknown-coverage"
        or release["bundle_sha256"]
        != "038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026"
    ):
        raise ValueError("Detail identity does not match registered public shared release")
    args.output.write_bytes(raw)
    required = {"scapularis_status", "pacificus_status", "svi_percentile"}
    print(
        json.dumps(
            {
                "url": URL,
                "timeout_seconds": 30,
                "max_bytes": MAX_BYTES,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "release_id": release["release_id"],
                "bundle_sha256": release["bundle_sha256"],
                "required_fields_present": sorted(required.intersection(value)),
                "required_fields_missing": sorted(required - set(value)),
                "county_n": 1,
                "eligible_species_group_n": None,
                "outcome_statistics_inspected": False,
                "source_authority_verified": False,
                "limitation": "one detail probe cannot establish national positive-group N",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
