"""Audit an outcome-blind governed-view profile; never infer negative evidence."""

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

TAXA_MEASURES = {"scapularis_status", "pacificus_status"}


def audit_profile(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Profile counts are publication counts, never eligible contrast group N."""
    if not rows or len(rows) >= 10:
        raise ValueError("Expected 1–9 governed profile rows; empty/truncated input is ambiguous")
    releases = {str(row["RELEASE_VERSION"]) for row in rows}
    if len(releases) != 1:
        raise ValueError("Expected one immutable published release")
    measures = set()
    for row in rows:
        measure = str(row["MEASURE_ID"])
        if measure in measures:
            raise ValueError("Duplicate measure profile")
        measures.add(measure)
        n_rows, n_counties = row["OBSERVATION_ROWS"], row["UNIQUE_COUNTIES"]
        if type(n_rows) is not int or type(n_counties) is not int or not 0 <= n_counties <= n_rows:
            raise ValueError("Invalid publication counts")
    missing = sorted((TAXA_MEASURES | {"svi_percentile_2022"}) - measures)
    blocked = "svi_percentile_2022" not in measures or not measures.intersection(TAXA_MEASURES)
    # A later view extension still needs source/state eligibility and N screening.
    return {
        "release_version": next(iter(releases)),
        "execution_status": "ACCESS_BLOCKED" if blocked else "ELIGIBILITY_NOT_SCREENED",
        "scientific_disposition": None,
        "unpublished_required_measures": missing,
        "selected_taxon": None,
        "group_n": {"ESTABLISHED": None, "REPORTED": None},
        "effect": None,
        "uncertainty": None,
        "outcome_statistics_inspected": False,
        "publication_profile": list(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path, help="JSON array from the availability SELECT")
    args = parser.parse_args()
    payload = args.profile.read_bytes()
    result = audit_profile(json.loads(payload))
    result["profile_sha256"] = hashlib.sha256(payload).hexdigest()
    query = Path(__file__).resolve().parents[1] / "sql/validation/62-vector-svi-availability.sql"
    result["sql_sha256_lf_utf8"] = hashlib.sha256(query.read_text().encode("utf-8")).hexdigest()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
