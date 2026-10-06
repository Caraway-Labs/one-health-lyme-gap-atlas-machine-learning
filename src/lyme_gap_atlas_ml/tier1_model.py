"""Reproduce two unsupervised Tier 1 surveillance-review anomaly candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib  # type: ignore[import-untyped]
import numpy as np
import numpy.typing as npt
from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]

from lyme_gap_atlas_ml import tier1_features as features

REFERENCE_VERSION = "tier1-statistical-reference-v1"
FOREST_VERSION = "tier1-isolation-forest-v1"
SEED = 27
N_ESTIMATORS = 100
CONTEXT_COLUMNS = (
    "human_evidence_state",
    "pathogen_evidence_state",
    "vector_evidence_state",
    "rucc_2023_context",
    "feature_evidence_state",
)
OUTPUT_COLUMNS = (
    "county_fips",
    "method",
    "raw_anomaly_score",
    "anomaly_percentile",
    "feature_set_version",
    "release_id",
    "bundle_sha256",
    "model_config_version",
    "run_id",
    *CONTEXT_COLUMNS,
    "descriptive_reasons",
)


def _validated_matrix(rows: list[dict[str, Any]]) -> npt.NDArray[np.float64]:
    if not rows or len({str(row["county_fips"]) for row in rows}) != len(rows):
        raise ValueError("Empty matrix or duplicate county keys")
    matrix = []
    for row in rows:
        if (row["feature_set_version"], row["release_id"], row["bundle_sha256"]) != (
            features.VERSION,
            features.RELEASE_ID,
            features.BUNDLE_SHA256,
        ):
            raise ValueError("Feature or governed release mismatch")
        if len(str(row["county_fips"])) != 5 or not str(row["county_fips"]).isdigit():
            raise ValueError("Invalid county FIPS")
        human = int(row["human_published_floor"])
        magnitude = float(row["human_case_count_floor_log1p"])
        if human not in (0, 1) or (human == 0 and magnitude != 0.0):
            raise ValueError("Human missing-state placeholder mismatch")
        if row["human_evidence_state"] != (
            "published_count_floor" if human else "no_county_linked_record"
        ):
            raise ValueError("Human evidence state mismatch")
        pathogen = tuple(int(row[column]) for column in features.FEATURE_COLUMNS[2:5])
        if pathogen not in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            raise ValueError("Invalid pathogen one-hot state")
        if (
            row["pathogen_evidence_state"]
            != {(1, 0, 0): "Present", (0, 1, 0): "No records", (0, 0, 1): "Unknown"}[pathogen]
        ):
            raise ValueError("Pathogen evidence state mismatch")
        expected_state = "PARTIAL" if human == 0 or pathogen[2] else "OBSERVED"
        if row["feature_evidence_state"] != expected_state:
            raise ValueError("Feature evidence state mismatch")
        values = [float(row[column]) for column in features.FEATURE_COLUMNS]
        if not all(np.isfinite(values)) or not 0 <= values[-1] <= 1:
            raise ValueError("Invalid predictor value")
        matrix.append(values)
    result = np.asarray(matrix, dtype=float)
    if np.any(np.ptp(result, axis=0) == 0):
        raise ValueError("Constant predictor in training matrix")
    return result


def _percentiles(scores: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """Average tied ranks, scaled to [0, 100]; high means unusual."""
    order = np.argsort(scores, kind="stable")
    result = np.empty(len(scores), dtype=float)
    for group in np.split(order, np.flatnonzero(np.diff(scores[order])) + 1):
        result[group] = 100 * (
            float(np.mean(np.arange(len(scores))[np.isin(order, group)])) / max(len(scores) - 1, 1)
        )
    return result


def _reference(matrix: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    """RMS of four domain contributions; pathogen is one mismatched-state bit."""
    human = matrix[:, 0]
    magnitude = matrix[:, 1]
    svi = matrix[:, 5]

    def z(values: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        return np.asarray((values - np.mean(values)) / np.std(values), dtype=float)

    # Modal pathogen state contributes one bit regardless of three encoded columns.
    pathogen = np.argmax(matrix[:, 2:5], axis=1)
    modal = int(np.argmax(np.bincount(pathogen)))
    mismatch = (pathogen != modal).astype(float)
    return np.asarray(
        np.sqrt((z(human) ** 2 + z(magnitude) ** 2 + z(mismatch) ** 2 + z(svi) ** 2) / 4),
        dtype=float,
    )


def score(rows: list[dict[str, Any]], run_id: str) -> tuple[list[dict[str, Any]], IsolationForest]:
    matrix = _validated_matrix(rows)
    forest = IsolationForest(
        n_estimators=N_ESTIMATORS, random_state=SEED, contamination="auto", n_jobs=1
    )
    forest.fit(matrix)
    scores = {
        REFERENCE_VERSION: _reference(matrix),
        FOREST_VERSION: -forest.score_samples(matrix),
    }
    output = []
    for method, raw in scores.items():
        percentiles = _percentiles(raw)
        for index, row in enumerate(rows):
            record = {key: row[key] for key in ("county_fips", *CONTEXT_COLUMNS)}
            record.update(
                method=method,
                raw_anomaly_score=float(raw[index]),
                anomaly_percentile=float(percentiles[index]),
                feature_set_version=features.VERSION,
                release_id=features.RELEASE_ID,
                bundle_sha256=features.BUNDLE_SHA256,
                model_config_version=method,
                run_id=run_id,
                descriptive_reasons="",
            )
            output.append(record)
    return output, forest


def summary(output: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"scored_counties": len(output) // 2, "methods": {}}
    by_method = {
        name: [row for row in output if row["method"] == name]
        for name in (REFERENCE_VERSION, FOREST_VERSION)
    }
    for name, rows in by_method.items():
        ranked = sorted(rows, key=lambda row: (-row["raw_anomaly_score"], row["county_fips"]))
        scores = np.array([row["raw_anomaly_score"] for row in rows])
        percentiles = np.array([row["anomaly_percentile"] for row in rows])
        slices = {}
        for column in (
            "human_evidence_state",
            "pathogen_evidence_state",
            "feature_evidence_state",
            "rucc_2023_context",
        ):
            slices[column] = {
                str(value): {
                    "count": len(group),
                    "median_score": float(np.median([item["raw_anomaly_score"] for item in group])),
                    "median_percentile": float(
                        np.median([item["anomaly_percentile"] for item in group])
                    ),
                    "top_10_count": sum(item in ranked[:10] for item in group),
                }
                for value in sorted({row[column] for row in rows}, key=str)
                for group in [[row for row in rows if row[column] == value]]
            }
        result["methods"][name] = {
            "score_min_median_max": [
                float(np.min(scores)),
                float(np.median(scores)),
                float(np.max(scores)),
            ],
            "percentile_min_median_max": [
                float(np.min(percentiles)),
                float(np.median(percentiles)),
                float(np.max(percentiles)),
            ],
            "top_10_fips": [row["county_fips"] for row in ranked[:10]],
            "slices": slices,
        }
    left, right = by_method.values()
    result["top_10_overlap"] = len(
        set(result["methods"][REFERENCE_VERSION]["top_10_fips"])
        & set(result["methods"][FOREST_VERSION]["top_10_fips"])
    )
    result["pearson_score_correlation"] = float(
        np.corrcoef(
            [row["raw_anomaly_score"] for row in left], [row["raw_anomaly_score"] for row in right]
        )[0, 1]
    )
    result["duplicate_output_keys"] = len(output) - len(
        {(row["method"], row["county_fips"]) for row in output}
    )
    result["missing_output_fields"] = dict(
        Counter(
            key
            for row in output
            for key in OUTPUT_COLUMNS
            if key != "descriptive_reasons" and row.get(key) is None
        )
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(".local/ml-27"))
    args = parser.parse_args()
    connection = os.environ.get("SNOWFLAKE_CONNECTION_NAME")
    if not connection:
        raise SystemExit("Set SNOWFLAKE_CONNECTION_NAME to an approved read-only DEV connection")
    features._validate_context(connection)
    features._validate_release(connection)
    rows, coverage = features.build_matrix(features._query(connection, features.COUNTY_SQL))
    generated_at = datetime.now(UTC).isoformat()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    run_id = "ml-27-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output, forest = score(rows, run_id)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "county-scores.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(output)
    artifact = args.output_dir / "isolation-forest.joblib"
    joblib.dump(forest, artifact)
    report = summary(output)
    report.update(
        run_id=run_id,
        generated_at_utc=generated_at,
        code_commit=commit,
        feature_set_version=features.VERSION,
        release_id=features.RELEASE_ID,
        bundle_sha256=features.BUNDLE_SHA256,
        feature_coverage=coverage,
        predictor_order=list(features.FEATURE_COLUMNS),
        random_seed=SEED,
        forest_n_estimators=N_ESTIMATORS,
        forest_contamination="auto",
        artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
    )
    (args.output_dir / "run-summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "run_id",
                    "scored_counties",
                    "top_10_overlap",
                    "pearson_score_correlation",
                    "artifact_sha256",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
