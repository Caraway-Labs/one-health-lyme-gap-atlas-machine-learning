"""Synthetic algorithm tests only; fixture N is never real cohort evidence."""

import hashlib
import json
import math
import sys
from pathlib import Path

import pytest

from lyme_gap_atlas_ml.eda61 import County, analyze, cohort, correlation, quantile, ranks

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.eda61 import replay  # noqa: E402


def test_spearman_ties_and_undefined_constant() -> None:
    assert ranks([5, 1, 1, 9]) == [3, 1.5, 1.5, 4]
    assert correlation([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1)
    assert correlation([1, 1, 2, 3], [1, 2, 2, 3]) == pytest.approx(5 / 6)
    assert correlation([1, 1, 1], [1, 2, 3]) is None
    with pytest.raises(ValueError):
        correlation([1], [1, 2])


def test_unknown_is_not_zero_and_source_rows_are_not_counties() -> None:
    svi = [
        {"county_fips": f"0100{i}", "population": 1000, "svi_percentile": 0.5} for i in range(1, 4)
    ]
    human = [
        {
            "source_record_id": "a",
            "county_fips": "01001",
            "report_year": 2022,
            "case_status": "confirmed",
            "frequency": 0,
        },
        {
            "source_record_id": "b",
            "county_fips": "01001",
            "report_year": 2022,
            "case_status": "probable",
            "frequency": 2,
        },
        {
            "source_record_id": "c",
            "county_fips": "suppressed",
            "report_year": 2022,
            "case_status": "confirmed",
            "frequency": 20,
        },
    ]
    rows, accounting = cohort(svi, human)
    assert rows == [County("01001", 1000, 0.5, 2)]
    assert rows[0].rate == 200
    assert accounting["source_observation_rows"] == 3
    assert accounting["primary_unique_counties"] == 1
    assert accounting["county_exclusions_nonexclusive"] == {
        "no_county_linked_record": 2,
        "unique_excluded_counties": 2,
    }


@pytest.mark.parametrize("frequency", [None, "suppressed", -1, math.inf, 0.5, True])
def test_invalid_eligible_frequency_fails(frequency: object) -> None:
    with pytest.raises(ValueError, match="frequency"):
        cohort(
            [{"county_fips": "01001", "population": 10, "svi_percentile": 0.5}],
            [
                {
                    "source_record_id": "a",
                    "county_fips": "01001",
                    "report_year": 2022,
                    "case_status": "confirmed",
                    "frequency": frequency,
                }
            ],
        )


def test_duplicate_and_unmatched_mapping_fail() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        cohort([{"county_fips": "01001"}, {"county_fips": "01001"}], [])
    human = {
        "source_record_id": "a",
        "county_fips": "01001",
        "report_year": 2022,
        "case_status": "confirmed",
        "frequency": 1,
    }
    with pytest.raises(ValueError, match="mapping"):
        cohort([], [human])
    with pytest.raises(ValueError, match="identity"):
        cohort([{"county_fips": "01001"}], [human, human])


def test_sentinel_exclusion_and_explicit_zero() -> None:
    svi = [
        {"county_fips": "01001", "population": 100, "svi_percentile": -999},
        {"county_fips": "01003", "population": 0, "svi_percentile": 0.5},
        {"county_fips": "01005", "population": 100, "svi_percentile": 0},
    ]
    human = [
        {
            "source_record_id": str(i),
            "county_fips": row["county_fips"],
            "report_year": 2022,
            "case_status": "confirmed",
            "frequency": 0,
        }
        for i, row in enumerate(svi)
    ]
    rows, accounting = cohort(svi, human)
    assert rows == [County("01005", 100, 0, 0)]
    assert accounting["county_exclusions_nonexclusive"] == {
        "missing_or_invalid_svi": 1,
        "invalid_population": 1,
        "unique_excluded_counties": 2,
    }


def test_population_sensitivity_frozen_and_no_naive_inference() -> None:
    rows = [County(f"010{i:02}", i * 100, i / 10, i * i) for i in range(1, 10)]
    result = analyze(rows)
    assert result["spearman"] == pytest.approx(1)
    assert result["sensitivity"] == {
        "population_bounds": [108, 892],
        "n": 7,
        "spearman": pytest.approx(1),
    }
    assert result["status"] == "SIGNAL"
    assert result["between_state_rank_variance_share"] == {"svi": 0, "floor_per_100k": 0}
    assert result["state_cluster_bootstrap"]["descriptive_95_percent_interval"] is None
    assert "p_value" not in result
    assert quantile([0, 10], 0.25) == 2.5


def test_empty_and_constant_are_scientifically_not_estimable() -> None:
    assert analyze([])["status"] == "NOT_ESTIMABLE"
    assert analyze([County(f"0100{i}", 100, 0.5, i) for i in range(1, 5)])["status"] == (
        "NOT_ESTIMABLE"
    )


def test_state_bootstrap_is_deterministic_and_clustered() -> None:
    rows = [
        County(f"{state:02}001", 1000 + state, state / 20, state * state) for state in range(1, 21)
    ]
    first = analyze(rows)
    assert first == analyze(rows)
    assert first["state_groups"] == 20
    assert first["between_state_rank_variance_share"] == {"svi": 1, "floor_per_100k": 1}
    assert first["state_cluster_bootstrap"]["valid_draws"] == 2000
    assert first["state_cluster_bootstrap"]["descriptive_95_percent_interval"] == [1, 1]


def test_replay_requires_reviewed_digest_and_all_prerequisites(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text('{"svi": [], "human": []}', encoding="utf-8")
    approval = tmp_path / "approval.json"
    evidence = {"snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest()}
    approval.write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(ValueError, match="source_authority"):
        replay(snapshot, approval)
    snapshot.write_text('{"svi": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        replay(snapshot, approval)
