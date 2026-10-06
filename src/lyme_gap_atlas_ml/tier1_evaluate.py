"""Bounded, offline diagnostics for the pinned Tier 1 candidate output and matrix."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]

from lyme_gap_atlas_ml import tier1_model


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def evaluate(features_path: Path, scores_path: Path) -> dict[str, Any]:
    rows = read_csv(features_path)
    scores = read_csv(scores_path)
    if len(rows) != 3144 or len(scores) != 6288:
        raise ValueError("Pinned county population/output size changed")
    matrix = tier1_model._validated_matrix(rows)
    by_fips = {row["county_fips"]: row for row in rows}
    if len(by_fips) != len(rows):
        raise ValueError("Duplicate input county")
    result: dict[str, Any] = {"candidates": {}, "spot_checks": {}}
    for method in (tier1_model.REFERENCE_VERSION, tier1_model.FOREST_VERSION):
        candidate = [row for row in scores if row["method"] == method]
        if len(candidate) != len(rows) or {row["county_fips"] for row in candidate} != set(by_fips):
            raise ValueError("Incomplete candidate output")
        ranked = sorted(
            candidate, key=lambda row: (-float(row["raw_anomaly_score"]), row["county_fips"])
        )
        values = np.array([float(row["raw_anomaly_score"]) for row in candidate])
        detail: dict[str, Any] = {
            "score_quantiles": {
                str(p): float(np.percentile(values, p))
                for p in (0, 10, 25, 50, 70, 75, 90, 95, 99, 100)
            },
            "unique_scores": len(np.unique(values)),
            "largest_exact_tie": max(Counter(values).values()),
            "top_fips": {
                str(n): [item["county_fips"] for item in ranked[:n]] for n in (10, 25, 50)
            },
            "top_slices": {},
            "svi_bands": {},
        }
        for n in (10, 25, 50):
            top = [by_fips[item["county_fips"]] for item in ranked[:n]]
            detail["top_slices"][str(n)] = {
                key: dict(Counter(item[key] for item in top))
                for key in (
                    "human_evidence_state",
                    "pathogen_evidence_state",
                    "feature_evidence_state",
                    "rucc_2023_context",
                )
            }
        for label, low, high in (
            ("low", 0, 1 / 3),
            ("middle", 1 / 3, 2 / 3),
            ("high", 2 / 3, 1.01),
        ):
            group = [
                row
                for row in candidate
                if low <= float(by_fips[row["county_fips"]]["svi_percentile_2022"]) < high
            ]
            detail["svi_bands"][label] = {
                "count": len(group),
                "median_percentile": float(
                    np.median([float(row["anomaly_percentile"]) for row in group])
                ),
            }
        result["candidates"][method] = detail
        selected = ranked[:5] + ranked[len(ranked) // 2 : len(ranked) // 2 + 3] + ranked[-3:]
        result["spot_checks"][method] = [
            {
                "fips": item["county_fips"],
                "score": float(item["raw_anomaly_score"]),
                "percentile": float(item["anomaly_percentile"]),
                "human": by_fips[item["county_fips"]]["human_evidence_state"],
                "human_floor_log1p": float(
                    by_fips[item["county_fips"]]["human_case_count_floor_log1p"]
                ),
                "pathogen": by_fips[item["county_fips"]]["pathogen_evidence_state"],
                "svi": float(by_fips[item["county_fips"]]["svi_percentile_2022"]),
                "rucc": by_fips[item["county_fips"]]["rucc_2023_context"],
                "evidence": by_fips[item["county_fips"]]["feature_evidence_state"],
            }
            for item in selected
        ]
    result["overlap"] = {
        str(n): len(
            set(result["candidates"][tier1_model.REFERENCE_VERSION]["top_fips"][str(n)])
            & set(result["candidates"][tier1_model.FOREST_VERSION]["top_fips"][str(n)])
        )
        for n in (10, 25, 50)
    }
    # A small feature-block ablation tests whether reference extremes depend on SVI.
    reference_original = tier1_model._reference(matrix)
    reference_modified = tier1_model._reference(matrix[:, :])  # original for exact rerun proof
    result["reference_exact_rerun"] = bool(np.array_equal(reference_original, reference_modified))
    # Reweight the remaining three domains after removing contextual SVI.
    result["reference_without_svi_top_overlap"] = _top_overlap(
        reference_original, _reference_without_svi(matrix), 50
    )
    forest = IsolationForest(
        n_estimators=tier1_model.N_ESTIMATORS,
        random_state=tier1_model.SEED,
        contamination="auto",
        n_jobs=1,
    )
    a = -forest.fit(matrix).score_samples(matrix)
    rerun = IsolationForest(
        n_estimators=tier1_model.N_ESTIMATORS,
        random_state=tier1_model.SEED,
        contamination="auto",
        n_jobs=1,
    )
    b = -rerun.fit(matrix).score_samples(matrix)
    result["forest_exact_rerun"] = bool(np.array_equal(a, b))
    changed_seed = IsolationForest(
        n_estimators=tier1_model.N_ESTIMATORS,
        random_state=tier1_model.SEED + 1,
        contamination="auto",
        n_jobs=1,
    )
    result["forest_seed_plus_one_top50_overlap"] = _top_overlap(
        a, -changed_seed.fit(matrix).score_samples(matrix), 50
    )
    return result


def _top_overlap(a: np.ndarray[Any, Any], b: np.ndarray[Any, Any], n: int) -> int:
    return int(len(set(np.argsort(a)[-n:]) & set(np.argsort(b)[-n:])))


def _reference_without_svi(matrix: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
    def z(value: np.ndarray[Any, Any]) -> np.ndarray[Any, Any]:
        return np.asarray((value - np.mean(value)) / np.std(value), dtype=float)

    pathogen = np.argmax(matrix[:, 2:5], axis=1)
    modal = int(np.argmax(np.bincount(pathogen)))
    mismatch = (pathogen != modal).astype(float)
    return np.asarray(
        np.sqrt((z(matrix[:, 0]) ** 2 + z(matrix[:, 1]) ** 2 + z(mismatch) ** 2) / 3), dtype=float
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("features", type=Path)
    parser.add_argument("scores", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(evaluate(args.features, args.scores), indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
