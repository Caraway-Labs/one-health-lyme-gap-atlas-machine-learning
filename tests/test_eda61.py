"""Synthetic algorithm tests only; fixture N is never real cohort evidence."""

import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import pytest

from lyme_gap_atlas_ml import eda61
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
        {
            "source_record_id": f"svi-{i}",
            "county_fips": f"0100{i}",
            "population": 1000,
            "svi_percentile": 0.5,
        }
        for i in range(1, 4)
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
    rows, accounting = cohort(svi, human, [str(row["county_fips"]) for row in svi])
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
            [
                {
                    "source_record_id": "svi-a",
                    "county_fips": "01001",
                    "population": 10,
                    "svi_percentile": 0.5,
                }
            ],
            [
                {
                    "source_record_id": "a",
                    "county_fips": "01001",
                    "report_year": 2022,
                    "case_status": "confirmed",
                    "frequency": frequency,
                }
            ],
            ["01001"],
        )


def test_duplicate_and_unmatched_mapping_fail() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        cohort(
            [
                {"source_record_id": "svi-a", "county_fips": "01001"},
                {"source_record_id": "svi-b", "county_fips": "01001"},
            ],
            [],
            ["01001"],
        )
    human = {
        "source_record_id": "a",
        "county_fips": "01001",
        "report_year": 2022,
        "case_status": "confirmed",
        "frequency": 1,
    }
    with pytest.raises(ValueError, match="mapping"):
        cohort([], [human], ["01003"])
    with pytest.raises(ValueError, match="identity"):
        cohort([{"source_record_id": "svi-a", "county_fips": "01001"}], [human, human], ["01001"])


def test_sentinel_exclusion_and_explicit_zero() -> None:
    svi = [
        {
            "source_record_id": "svi-a",
            "county_fips": "01001",
            "population": 100,
            "svi_percentile": -999,
        },
        {
            "source_record_id": "svi-b",
            "county_fips": "01003",
            "population": 0,
            "svi_percentile": 0.5,
        },
        {
            "source_record_id": "svi-c",
            "county_fips": "01005",
            "population": 100,
            "svi_percentile": 0,
        },
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
    rows, accounting = cohort(svi, human, [str(row["county_fips"]) for row in svi])
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


def test_absent_svi_row_is_missing_source_not_unmapped_county() -> None:
    human = [
        {
            "source_record_id": "human-a",
            "county_fips": "01001",
            "report_year": 2022,
            "case_status": "confirmed",
            "frequency": 1,
        }
    ]
    rows, accounting = cohort([], human, ["01001", "01003"])
    assert rows == []
    assert accounting["svi_source_rows"] == 0
    assert accounting["svi_unique_source_counties"] == 0
    assert accounting["canonical_unique_counties"] == 2
    assert accounting["county_linked_outcome_counties"] == 1
    assert accounting["county_exclusions_nonexclusive"] == {
        "missing_svi_source_row": 2,
        "no_county_linked_record": 1,
        "unique_excluded_counties": 2,
    }
    assert accounting["outcome_states_canonical_counties"] == {
        "observed_zero_floor": 0,
        "observed_positive_floor": 1,
        "no_county_linked_record": 1,
    }
    with pytest.raises(ValueError, match="canonical mapping"):
        cohort([], human, ["01003"])


def test_canonical_frame_and_svi_source_rows_cannot_be_placeholders() -> None:
    with pytest.raises(ValueError, match="canonical county frame"):
        cohort([], [], ["bad"])
    with pytest.raises(ValueError, match="canonical county frame"):
        cohort([], [], ["01001", "01001"])
    with pytest.raises(ValueError, match="SVI source-record identity"):
        cohort(
            [{"county_fips": "01001", "population": None, "svi_percentile": None}], [], ["01001"]
        )
    rows, accounting = cohort(
        [
            {
                "source_record_id": "real-svi-a",
                "county_fips": "01001",
                "population": None,
                "svi_percentile": None,
            }
        ],
        [],
        ["01001"],
    )
    assert rows == []
    assert accounting["svi_source_rows"] == 1
    assert "missing_svi_source_row" not in accounting["county_exclusions_nonexclusive"]


GATES = (
    "source_authority",
    "case_scope_2022",
    "population_acs_2018_2022_compatibility",
    "canonical_mapping",
    "source_record_identity",
    "source_release_membership",
)


def replay_packet(tmp_path: Path) -> tuple[Path, Path, dict, dict]:
    """Explicitly synthetic local approval/input; never a governed evidence packet."""
    data = {
        "canonical_fips": ["01001", "01003", "01005", "01007"],
        "svi": [
            {
                "source_record_id": f"synthetic-svi-{i}",
                "county_fips": fips,
                "population": 1000,
                "svi_percentile": i / 4,
            }
            for i, fips in enumerate(["01001", "01003", "01005", "01007"], start=1)
        ],
        "human": [
            {
                "source_record_id": f"synthetic-human-{i}",
                "county_fips": fips,
                "report_year": 2022,
                "case_status": "confirmed",
                "frequency": i,
            }
            for i, fips in enumerate(["01001", "01003", "01005", "01007"], start=1)
        ],
    }
    snapshot, approval = tmp_path / "synthetic-input.json", tmp_path / "synthetic-approval.json"
    snapshot.write_text(json.dumps(data), encoding="utf-8")
    evidence = {
        "snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "gates": {
            gate: {"status": "PASS", "evidence_ref": "synthetic-test-only"} for gate in GATES
        },
        "sources": [
            {
                "resource_key": resource,
                "release_id": "synthetic-release",
                "data_source_version_id": "synthetic-version",
                "ingestion_run_id": "synthetic-run",
                "artifact_id": "synthetic-artifact",
                "artifact_sha256": "a" * 64,
                "source_query_sha256": "b" * 64,
            }
            for resource in ("cdc_lyme_x5j9_wybp", "cdc_atsdr_svi_2022_county")
        ],
    }
    approval.write_text(json.dumps(evidence), encoding="utf-8")
    return snapshot, approval, data, evidence


def test_successful_snapshot_replay_keeps_source_and_cohort_accounting(tmp_path: Path) -> None:
    snapshot, approval, _, evidence = replay_packet(tmp_path)
    result = replay(snapshot, approval)
    assert result["snapshot_sha256"] == evidence["snapshot_sha256"]
    assert result["source_evidence"] == evidence
    assert result["accounting"]["canonical_unique_counties"] == 4
    assert result["accounting"]["svi_source_rows"] == 4
    assert result["analysis"]["n"] == 4
    assert result["analysis"]["spearman"] == pytest.approx(1)


@pytest.mark.parametrize("gate", GATES)
@pytest.mark.parametrize("failure", ["missing", "not_pass", "missing_reference"])
def test_every_replay_prerequisite_fails_closed(tmp_path: Path, gate: str, failure: str) -> None:
    snapshot, approval, _, evidence = replay_packet(tmp_path)
    if failure == "missing":
        del evidence["gates"][gate]
    elif failure == "not_pass":
        evidence["gates"][gate]["status"] = "BLOCKED"
    else:
        del evidence["gates"][gate]["evidence_ref"]
    approval.write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(ValueError, match=gate):
        replay(snapshot, approval)


@pytest.mark.parametrize("field,cap", [("human", 250000), ("svi", 3144), ("canonical_fips", 3144)])
def test_replay_rejects_every_extraction_cap(tmp_path: Path, field: str, cap: int) -> None:
    snapshot, approval, data, evidence = replay_packet(tmp_path)
    data[field] = [data[field][0]] * (cap + 1)
    snapshot.write_text(json.dumps(data), encoding="utf-8")
    evidence["snapshot_sha256"] = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    approval.write_text(json.dumps(evidence), encoding="utf-8")
    with pytest.raises(ValueError, match="row caps"):
        replay(snapshot, approval)


def test_bootstrap_resamples_all_counties_in_each_selected_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [
        County(f"{state:02}{member:03}", 1000, (state * 3 + member) / 100, member)
        for state in range(1, 21)
        for member in range(1, 4)
    ]
    draws = []

    def observed_correlation(x, y):
        draws.append(list(x))
        return 0.5

    monkeypatch.setattr(eda61, "correlation", observed_correlation)
    result = analyze(rows)
    assert result["state_cluster_bootstrap"]["valid_draws"] == 2000
    assert len(draws) == 2002  # primary, registered sensitivity, then bootstrap
    for draw in draws[2:]:
        counts = Counter(draw)
        assert len(draw) == len(rows)
        for state in range(1, 21):
            assert len({counts[(state * 3 + member) / 100] for member in range(1, 4)}) == 1
