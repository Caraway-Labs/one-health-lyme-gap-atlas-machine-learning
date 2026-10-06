"""Build and validate the one selected Tier 1 county output batch offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from lyme_gap_atlas_ml import tier1_features, tier1_model, tier1_selection

EVALUATION_VERSION = "tier1-selection-evaluation-v1"
OUTPUT_CONTRACT_VERSION = "tier1-persisted-output-v1"
LIMITATION_REF = "docs/contracts/tier1-persisted-output-v1.md"
EXPECTED_TIERS = {"HIGH": 315, "MEDIUM": 628, "LOW": 2201}
EXPECTED_SUFFICIENCY = {"SUFFICIENT": 651, "INSUFFICIENT": 2493, "NOT_ESTIMABLE": 0}


def batch_id(source_commit: str) -> str:
    """A deterministic identity for this pinned source, model and policy."""
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise ValueError("Source commit must be a full lowercase SHA")
    return (
        "tier1-review-priority-"
        + hashlib.sha256(
            "|".join(
                (
                    tier1_features.RELEASE_ID,
                    tier1_features.BUNDLE_SHA256,
                    tier1_features.VERSION,
                    tier1_selection.SELECTED_MODEL_VERSION,
                    EVALUATION_VERSION,
                    tier1_selection.TIER_POLICY_VERSION,
                    source_commit,
                )
            ).encode()
        ).hexdigest()[:16]
    )


def reasons(feature: dict[str, Any], svi_center: float) -> list[dict[str, str]]:
    """Describe source evidence and context; never attribute model causality."""
    result: list[dict[str, str]] = []
    if feature["human_evidence_state"] == "published_count_floor":
        result.append(
            {
                "code": "PUBLISHED_HUMAN_FLOOR",
                "text": (
                    "Published county-linked human count-floor signal is present; "
                    "its magnitude is a lower bound."
                ),
            }
        )
    else:
        result.append(
            {
                "code": "NO_COUNTY_HUMAN_RECORD",
                "text": (
                    "No county-linked human record is available; "
                    "the model uses an explicit placeholder."
                ),
            }
        )
    pathogen = feature["pathogen_evidence_state"]
    result.append(
        {
            "code": {
                "Present": "PATHOGEN_PRESENT",
                "No records": "PATHOGEN_NO_RECORDS",
                "Unknown": "PATHOGEN_UNKNOWN",
            }[pathogen],
            "text": {
                "Present": "Publisher reports pathogen Present.",
                "No records": "Publisher reports No records; this is not evidence of absence.",
                "Unknown": "Publisher pathogen evidence state is Unknown.",
            }[pathogen],
        }
    )
    svi = float(feature["svi_percentile_2022"])
    if abs(svi - svi_center) >= 0.25:
        result.append(
            {
                "code": "SVI_CONTEXT_DIFFERENCE",
                "text": "SVI context differs from the scored-population center.",
            }
        )
    return result


def build(
    rows: list[dict[str, Any]], source_commit: str, generated_at: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Regenerate selected scores from feature rows and fail closed on drift."""
    if len(rows) != 3144 or len({row["county_fips"] for row in rows}) != len(rows):
        raise ValueError("Incomplete or duplicate county feature population")
    matrix = tier1_model._validated_matrix(rows)
    scores = tier1_model._reference(matrix)
    percentiles = tier1_model._percentiles(scores)
    identity = batch_id(source_commit)
    svi_center = float(np.mean(matrix[:, 5]))
    output: list[dict[str, Any]] = []
    for i, feature in enumerate(rows):
        classified = tier1_selection.classify(
            {
                "method": tier1_selection.SELECTED_MODEL_VERSION,
                "anomaly_percentile": float(percentiles[i]),
                "feature_evidence_state": feature["feature_evidence_state"],
            }
        )
        output.append(
            {
                "county_fips": feature["county_fips"],
                "model_version": tier1_selection.SELECTED_MODEL_VERSION,
                "feature_set_version": tier1_features.VERSION,
                "evaluation_version": EVALUATION_VERSION,
                "tier_policy_version": tier1_selection.TIER_POLICY_VERSION,
                "prediction_batch_version": identity,
                "run_id": identity,
                "release_id": tier1_features.RELEASE_ID,
                "bundle_sha256": tier1_features.BUNDLE_SHA256,
                "source_commit": source_commit,
                "generated_at_utc": generated_at,
                "raw_model_score": float(scores[i]),
                "priority_percentile": float(percentiles[i]),
                "priority_tier": classified["priority_tier"],
                "evidence_sufficiency": classified["evidence_sufficiency"],
                "human_evidence_state": feature["human_evidence_state"],
                "pathogen_evidence_state": feature["pathogen_evidence_state"],
                "feature_evidence_state": feature["feature_evidence_state"],
                "reasons": reasons(feature, svi_center),
                "limitation_ref": LIMITATION_REF,
            }
        )
    output.sort(key=lambda row: row["county_fips"])
    expected_fips = {str(row["county_fips"]) for row in rows}
    validate(output, identity, expected_fips=expected_fips)
    digest = hashlib.sha256(
        json.dumps(output, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    manifest = {
        "schema": OUTPUT_CONTRACT_VERSION,
        "batch_id": identity,
        "source_commit": source_commit,
        "generated_at_utc": generated_at,
        "row_count": len(output),
        "output_sha256": digest,
        "tier_counts": dict(Counter(row["priority_tier"] for row in output)),
        "sufficiency_counts": dict(Counter(row["evidence_sufficiency"] for row in output)),
        "release_id": tier1_features.RELEASE_ID,
        "bundle_sha256": tier1_features.BUNDLE_SHA256,
    }
    return manifest, output


def validate(rows: list[dict[str, Any]], identity: str, *, expected_fips: set[str]) -> None:
    """Require exact equality with the regenerated governed feature population."""
    if len(rows) != 3144 or len({row.get("county_fips") for row in rows}) != len(rows):
        raise ValueError("Incomplete or duplicate county output population")
    if len(expected_fips) != 3144 or {row.get("county_fips") for row in rows} != expected_fips:
        raise ValueError("County output population differs from governed feature population")
    tiers: Counter[str] = Counter()
    sufficiency: Counter[str] = Counter()
    for row in rows:
        if not isinstance(row.get("county_fips"), str) or not re.fullmatch(
            r"[0-9]{5}", row["county_fips"]
        ):
            raise ValueError("Invalid county FIPS")
        if (
            row.get("model_version"),
            row.get("feature_set_version"),
            row.get("evaluation_version"),
            row.get("tier_policy_version"),
            row.get("release_id"),
            row.get("bundle_sha256"),
            row.get("prediction_batch_version"),
            row.get("run_id"),
        ) != (
            tier1_selection.SELECTED_MODEL_VERSION,
            tier1_features.VERSION,
            EVALUATION_VERSION,
            tier1_selection.TIER_POLICY_VERSION,
            tier1_features.RELEASE_ID,
            tier1_features.BUNDLE_SHA256,
            identity,
            identity,
        ):
            raise ValueError("Selected model or lineage mismatch")
        if (
            not isinstance(row.get("source_commit"), str)
            or batch_id(row["source_commit"]) != identity
            or not row.get("generated_at_utc")
            or row.get("limitation_ref") != LIMITATION_REF
        ):
            raise ValueError("Missing required output metadata")
        state = row.get("evidence_sufficiency")
        tier = row.get("priority_tier")
        score = row.get("raw_model_score")
        percentile = row.get("priority_percentile")
        if state not in EXPECTED_SUFFICIENCY or tier not in (*EXPECTED_TIERS, None):
            raise ValueError("Invalid tier or evidence sufficiency")
        if state == "NOT_ESTIMABLE":
            if any(value is not None for value in (score, percentile, tier)):
                raise ValueError("NOT_ESTIMABLE cannot carry a score, percentile, or tier")
        else:
            if (
                not isinstance(score, (int, float))
                or not math.isfinite(score)
                or not isinstance(percentile, (int, float))
                or not 0 <= percentile <= 100
            ):
                raise ValueError("Invalid selected score or percentile")
            expected = "HIGH" if percentile >= 90 else "MEDIUM" if percentile >= 70 else "LOW"
            if tier != expected:
                raise ValueError("Tier differs from selected policy")
            if state != (
                "SUFFICIENT" if row.get("feature_evidence_state") == "OBSERVED" else "INSUFFICIENT"
            ):
                raise ValueError("Evidence sufficiency differs from feature state")
        reason_list = row.get("reasons")
        if (
            not isinstance(reason_list, list)
            or not 2 <= len(reason_list) <= 3
            or any(set(reason) != {"code", "text"} for reason in reason_list)
        ):
            raise ValueError("Reasons must be two or three bounded descriptive codes")
        allowed_codes = {
            "PUBLISHED_HUMAN_FLOOR",
            "NO_COUNTY_HUMAN_RECORD",
            "PATHOGEN_PRESENT",
            "PATHOGEN_NO_RECORDS",
            "PATHOGEN_UNKNOWN",
            "SVI_CONTEXT_DIFFERENCE",
        }
        if any(reason["code"] not in allowed_codes or not reason["text"] for reason in reason_list):
            raise ValueError("Unknown or empty descriptive reason")
        if any(
            len(reason["text"]) > 180
            or any(
                term in reason["text"].lower()
                for term in ("caused", "risk", "outbreak", "incidence")
            )
            for reason in reason_list
        ):
            raise ValueError("Reason text exceeds bounded noncausal vocabulary")
        if tier is not None:
            tiers[str(tier)] += 1
        sufficiency[state] += 1
    if dict(tiers) != EXPECTED_TIERS or any(
        sufficiency[key] != count for key, count in EXPECTED_SUFFICIENCY.items()
    ):
        raise ValueError("Pinned batch count drift; diagnose before publication")


def main() -> None:
    """Read the pinned DEV release and write a local, unpublished batch artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(".local/ml-32"))
    args = parser.parse_args()
    connection = os.environ.get("SNOWFLAKE_CONNECTION_NAME")
    if not connection:
        raise SystemExit("Set SNOWFLAKE_CONNECTION_NAME to an approved read-only DEV connection")
    tier1_features._validate_context(connection)
    tier1_features._validate_release(connection)
    features, _ = tier1_features.build_matrix(
        tier1_features._query(connection, tier1_features.COUNTY_SQL)
    )
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest, rows = build(features, commit, generated_at)
    from lyme_gap_atlas_ml.unsupervised_lineage import SCHEMA, validate_tier1_lineage

    lineage = {
        "schema": SCHEMA,
        "supervision_mode": "unsupervised",
        "model_version": tier1_selection.SELECTED_MODEL_VERSION,
        "feature_set_version": tier1_features.VERSION,
        "evaluation_version": EVALUATION_VERSION,
        "tier_policy_version": tier1_selection.TIER_POLICY_VERSION,
        "release_id": tier1_features.RELEASE_ID,
        "bundle_sha256": tier1_features.BUNDLE_SHA256,
        "source_commit": commit,
        "prediction_batch_version": manifest["batch_id"],
        "generated_at_utc": generated_at,
        "output_sha256": manifest["output_sha256"],
        "row_count": len(rows),
        "intended_use_ref": LIMITATION_REF,
    }
    validate_tier1_lineage(lineage)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("manifest.json", manifest),
        ("lineage.json", lineage),
        ("county-output.json", rows),
    ):
        (args.output_dir / name).write_text(
            json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8"
        )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
