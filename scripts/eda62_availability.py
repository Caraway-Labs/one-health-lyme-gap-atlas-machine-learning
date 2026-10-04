"""Audit an outcome-blind governed-view profile; never infer negative evidence."""

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

TAXA_MEASURES = {"scapularis_status", "pacificus_status"}


def audit_profile(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Audit only this view; never claim that all consumer routes lack inputs."""
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
        "execution_status": "VIEW_EXCLUDES_INPUTS" if blocked else "ELIGIBILITY_NOT_SCREENED",
        "scientific_disposition": None,
        "unpublished_required_measures": missing,
        "selected_taxon": None,
        "group_n": {"ESTABLISHED": None, "REPORTED": None},
        "effect": None,
        "uncertainty": None,
        "outcome_statistics_inspected": False,
        "publication_profile": list(rows),
    }


def audit_atlas_screen(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Recognize complete all-Unknown taxon screens without inventing negatives."""
    if not rows or len(rows) >= 12:
        raise ValueError("Empty or potentially truncated atlas screen")
    if len({row["RELEASE_ID"] for row in rows}) != 1:
        raise ValueError("Mixed atlas releases")
    by_taxon: dict[str, list[dict[str, Any]]] = {}
    seen = set()
    for row in rows:
        taxon = row["TAXON_FIELD"]
        if taxon not in {"SCAPULARIS_STATUS", "PACIFICUS_STATUS"}:
            raise ValueError("Unsupported taxon field")
        key = (taxon, row["SOURCE_STATUS"])
        if key in seen:
            raise ValueError("Duplicate status aggregate")
        seen.add(key)
        for field in (
            "COUNTY_ROWS",
            "UNIQUE_COUNTIES",
            "UNIQUE_STATES",
            "INVALID_FIPS",
            "SVI_NULL",
            "SVI_INVALID_DOMAIN",
        ):
            if type(row[field]) is not int or row[field] < 0:
                raise ValueError("Invalid atlas counts")
        if row["COUNTY_ROWS"] != row["UNIQUE_COUNTIES"] or row["INVALID_FIPS"]:
            raise ValueError("Invalid or duplicate county identities")
        if any(
            row[field] > row["COUNTY_ROWS"]
            for field in (
                "UNIQUE_STATES",
                "SVI_NULL",
                "SVI_INVALID_DOMAIN",
            )
        ):
            raise ValueError("Inconsistent atlas counts")
        by_taxon.setdefault(taxon, []).append(row)
    all_unknown = set(by_taxon) == {"SCAPULARIS_STATUS", "PACIFICUS_STATUS"} and all(
        len(group) == 1 and group[0]["SOURCE_STATUS"] == "Unknown" and group[0]["COUNTY_ROWS"] > 0
        for group in by_taxon.values()
    )
    return {
        "release_id": rows[0]["RELEASE_ID"],
        "execution_status": "NO_POSITIVE_CONTRAST" if all_unknown else "SCREENING_PENDING",
        "scientific_disposition_for_this_release": "NOT_ESTIMABLE" if all_unknown else None,
        "selected_taxon": None,
        "positive_group_n_by_taxon": {
            taxon: {"ESTABLISHED": 0, "REPORTED": 0} for taxon in sorted(by_taxon)
        }
        if all_unknown
        else None,
        "unknown_county_n_by_taxon": {
            taxon: group[0]["UNIQUE_COUNTIES"] for taxon, group in sorted(by_taxon.items())
        }
        if all_unknown
        else None,
        "outcome_statistics_inspected": False,
        "source_authority_verified": False,
        "profile": list(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path, help="JSON array from the availability SELECT")
    parser.add_argument("--atlas-screen", action="store_true")
    args = parser.parse_args()
    payload = args.profile.read_bytes()
    result = (audit_atlas_screen if args.atlas_screen else audit_profile)(json.loads(payload))
    result["profile_sha256"] = hashlib.sha256(payload).hexdigest()
    filename = (
        "62-county-atlas-screen.sql" if args.atlas_screen else "62-vector-svi-availability.sql"
    )
    query = Path(__file__).resolve().parents[1] / "sql/validation" / filename
    result["sql_sha256_lf_utf8"] = hashlib.sha256(query.read_text().encode("utf-8")).hexdigest()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
