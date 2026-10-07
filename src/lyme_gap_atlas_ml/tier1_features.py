"""Read-only, release-pinned Tier 1 county feature generation."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

VERSION = "tier1-county-features-v1"
DATABASE = "ONE_HEALTH_LYME_GAP_ATLAS_DEV"
RELEASE_ID = "governed-2026-09-17-unknown-coverage"
BUNDLE_SHA256 = "55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233"


@dataclass(frozen=True)
class Snapshot:
    environment: str
    database: str
    role: str
    warehouse: str
    release_id: str
    bundle_sha256: str
    feature_version: str


SNAPSHOTS = {
    "dev": Snapshot(
        "dev",
        DATABASE,
        "OH_LYME_DEV_READ",
        "OH_LYME_DEV_INGEST_XS_WH",
        RELEASE_ID,
        BUNDLE_SHA256,
        VERSION,
    ),
    "prod": Snapshot(
        "prod",
        "ONE_HEALTH_LYME_GAP_ATLAS_PROD",
        "OH_LYME_PROD_READ",
        "COMPUTE_WH",
        "governed-2026-09-18-unknown-coverage",
        "038aa3f8c383a70699aff92c752f2bbcc6687a726d0c2f142c9f368841b42026",
        "tier1-county-features-v2",
    ),
}
FEATURE_COLUMNS = (
    "human_published_floor",
    "human_case_count_floor_log1p",
    "pathogen_present",
    "pathogen_no_records",
    "pathogen_unknown",
    "svi_percentile_2022",
)
OUTPUT_COLUMNS = (
    "county_fips",
    *FEATURE_COLUMNS,
    "human_evidence_state",
    "pathogen_evidence_state",
    "vector_evidence_state",
    "rucc_2023_context",
    "feature_evidence_state",
    "feature_set_version",
    "release_id",
    "bundle_sha256",
)
COUNTY_SQL = (
    "SELECT FIPS, HUMAN_STATUS, CASE_COUNT_FLOOR_2023, TICK_STATUS, "
    "SCAPULARIS_STATUS, PACIFICUS_STATUS, "
    "BURGDORFERI_STATUS, SVI_PERCENTILE, RUCC_2023 "
    f"FROM {DATABASE}.PRESENTATION.CURRENT_COUNTY_ATLAS_V ORDER BY FIPS"
)


def county_sql(snapshot: Snapshot) -> str:
    return COUNTY_SQL.replace(DATABASE, snapshot.database)


def _query(
    connection: str, sql: str, snapshot: Snapshot = SNAPSHOTS["dev"]
) -> list[dict[str, Any]]:
    statement = (
        f"USE WAREHOUSE {snapshot.warehouse}; " if snapshot.environment == "prod" else ""
    ) + sql
    completed = subprocess.run(
        ["snow", "sql", "-c", connection, "--format", "JSON", "-q", statement],
        check=True,
        capture_output=True,
        text=True,
    )
    result: list[dict[str, Any]] = json.loads(completed.stdout)
    return cast(list[dict[str, Any]], result[-1] if snapshot.environment == "prod" else result)


def _validate_context(connection: str, snapshot: Snapshot = SNAPSHOTS["dev"]) -> None:
    rows = _query(
        connection,
        "SELECT CURRENT_USER() AS USER_NAME, CURRENT_ROLE() AS ROLE_NAME, "
        "CURRENT_DATABASE() AS DATABASE_NAME, CURRENT_WAREHOUSE() AS WAREHOUSE_NAME",
        snapshot,
    )
    if len(rows) != 1 or not rows[0]["USER_NAME"]:
        raise ValueError("Snowflake identity could not be verified")
    if (rows[0]["ROLE_NAME"], rows[0]["DATABASE_NAME"], rows[0]["WAREHOUSE_NAME"]) != (
        snapshot.role,
        snapshot.database,
        snapshot.warehouse,
    ):
        raise ValueError("Expected pinned read-only environment and warehouse context")


def _validate_release(connection: str, snapshot: Snapshot = SNAPSHOTS["dev"]) -> None:
    rows = _query(
        connection,
        f"SELECT RELEASE_ID, BUNDLE_SHA256 FROM {snapshot.database}.PRESENTATION.CURRENT_RELEASE_V",
        snapshot,
    )
    if len(rows) != 1 or (rows[0]["RELEASE_ID"], rows[0]["BUNDLE_SHA256"]) != (
        snapshot.release_id,
        snapshot.bundle_sha256,
    ):
        raise ValueError("Current governed release differs from the pinned feature snapshot")


def build_matrix(
    source: list[dict[str, Any]], snapshot: Snapshot = SNAPSHOTS["dev"]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate source semantics, then return sorted rows and a bounded coverage summary."""
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_states: dict[str, Counter[str]] = {
        name: Counter()
        for name in ("HUMAN_STATUS", "BURGDORFERI_STATUS", "SCAPULARIS_STATUS", "PACIFICUS_STATUS")
    }
    published_floors: list[int] = []
    for row in sorted(source, key=lambda item: str(item["FIPS"])):
        fips = str(row["FIPS"])
        if len(fips) != 5 or not fips.isdigit() or fips in seen:
            raise ValueError("Invalid or duplicate county FIPS")
        seen.add(fips)
        human = row["HUMAN_STATUS"]
        pathogen = row["BURGDORFERI_STATUS"]
        scapularis = row["SCAPULARIS_STATUS"]
        pacificus = row["PACIFICUS_STATUS"]
        if human not in {"published_count_floor", "no_county_linked_record"}:
            raise ValueError(f"Unrecognized human state: {human}")
        floor = row["CASE_COUNT_FLOOR_2023"]
        if human == "published_count_floor":
            if isinstance(floor, bool) or not isinstance(floor, int) or floor < 0:
                raise ValueError("Published count floor must be a nonnegative integer")
            published_floors.append(floor)
            human_magnitude = math.log1p(floor)
        else:
            if floor is not None:
                raise ValueError("No-county-record state must have null count floor")
            # A model placeholder, never an observed count or observed zero.
            human_magnitude = 0.0
        if pathogen not in {"Present", "No records", "Unknown"}:
            raise ValueError(f"Unrecognized pathogen state: {pathogen}")
        vector_states = (
            {"Unknown"}
            if snapshot.environment == "dev"
            else {"Established", "Reported", "No records", "Unknown"}
        )
        if scapularis not in vector_states or pacificus not in vector_states:
            raise ValueError("Vector state is outside the reviewed feature admission")
        tick = row.get("TICK_STATUS", "Unknown" if snapshot.environment == "dev" else None)
        if tick not in vector_states:
            raise ValueError("Aggregate vector state is outside the reviewed feature admission")
        if snapshot.environment == "dev" and tick != "Unknown":
            raise ValueError("DEV vector context changed")
        svi = row["SVI_PERCENTILE"]
        if svi is None or not 0 <= float(svi) <= 1:
            raise ValueError("SVI is unavailable or outside [0, 1]")
        rucc = row["RUCC_2023"]
        if rucc is None or int(rucc) not in range(1, 10):
            raise ValueError("RUCC context is unavailable or outside 1–9")
        for name in source_states:
            source_states[name][str(row[name])] += 1
        output.append(
            {
                "county_fips": fips,
                "human_published_floor": int(human == "published_count_floor"),
                "human_case_count_floor_log1p": human_magnitude,
                "pathogen_present": int(pathogen == "Present"),
                "pathogen_no_records": int(pathogen == "No records"),
                "pathogen_unknown": int(pathogen == "Unknown"),
                "svi_percentile_2022": float(svi),
                "human_evidence_state": human,
                "pathogen_evidence_state": pathogen,
                "vector_evidence_state": tick,
                "rucc_2023_context": int(rucc),
                "feature_evidence_state": (
                    "PARTIAL"
                    if human == "no_county_linked_record" or pathogen == "Unknown"
                    else "OBSERVED"
                ),
                "feature_set_version": snapshot.feature_version,
                "release_id": snapshot.release_id,
                "bundle_sha256": snapshot.bundle_sha256,
            }
        )
    if len(output) != 3144:
        raise ValueError(f"Expected 3,144 canonical counties, got {len(output)}")
    feature_stats = {
        name: {
            "missing": sum(row[name] is None for row in output),
            "distinct": len({row[name] for row in output}),
            "encoded_zero": sum(row[name] == 0 for row in output),
        }
        for name in FEATURE_COLUMNS
    }
    if any(item["distinct"] < 2 for item in feature_stats.values()):
        raise ValueError("Selected predictor is constant")
    if not published_floors:
        raise ValueError("No published human count floors in selected release")
    transformed_floors = [math.log1p(value) for value in published_floors]
    report = {
        "feature_set_version": snapshot.feature_version,
        "release_id": snapshot.release_id,
        "bundle_sha256": snapshot.bundle_sha256,
        "expected_counties": 3144,
        "matrix_rows": len(output),
        "duplicate_keys": len(output) - len(seen),
        "feature_complete_counties": len(output),
        "partial_evidence_counties": sum(
            row["feature_evidence_state"] == "PARTIAL" for row in output
        ),
        "not_estimable_counties": 0,
        "excluded_counties": 0,
        "feature_stats": feature_stats,
        "human_count_floor": {
            "published_non_null_rows": len(published_floors),
            "no_county_record_rows": len(output) - len(published_floors),
            "published_observed_zero_count": published_floors.count(0),
            "model_placeholder_count": len(output) - len(published_floors),
            "published_floor_min_median_max": [
                min(published_floors),
                statistics.median(published_floors),
                max(published_floors),
            ],
            "published_log1p_min_median_max": [
                min(transformed_floors),
                statistics.median(transformed_floors),
                max(transformed_floors),
            ],
            "all_rows_log1p_min_median_max": [
                min(row["human_case_count_floor_log1p"] for row in output),
                statistics.median(row["human_case_count_floor_log1p"] for row in output),
                max(row["human_case_count_floor_log1p"] for row in output),
            ],
        },
        "source_states": {name: dict(counts) for name, counts in source_states.items()},
        "svi_range": [
            min(row["svi_percentile_2022"] for row in output),
            max(row["svi_percentile_2022"] for row in output),
        ],
        "rucc_distribution": dict(
            sorted(Counter(str(row["rucc_2023_context"]) for row in output).items())
        ),
        "leakage_checks": {
            "priority_score_or_tier_selected": False,
            "derived_from_priority": False,
            "county_fips_used_as_predictor": False,
            "state_or_region_used_as_predictor": False,
            "supervised_label_used": False,
        },
    }
    return output, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--environment", choices=SNAPSHOTS, default="dev")
    args = parser.parse_args()
    snapshot = SNAPSHOTS[args.environment]
    connection = os.environ.get("SNOWFLAKE_CONNECTION_NAME")
    if not connection:
        raise SystemExit("Set SNOWFLAKE_CONNECTION_NAME to an approved read-only connection")
    _validate_context(connection, snapshot)
    _validate_release(connection, snapshot)
    matrix, report = build_matrix(_query(connection, county_sql(snapshot), snapshot), snapshot)
    report["generated_at_utc"] = datetime.now(UTC).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(matrix)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
