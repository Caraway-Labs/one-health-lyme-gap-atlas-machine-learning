"""Fictional numerical/validation cases; never evidence of real county counts."""

import json
import sys
from pathlib import Path

import pytest

from lyme_gap_atlas_ml.eda63 import RELEASE, County, analyze, cohort, omnibus, quantile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.eda63_svi_rucc import main  # noqa: E402


def test_rank_omnibus_known_no_ties() -> None:
    result = omnibus({1: [1, 2, 3], 2: [4, 5, 6], 3: [7, 8, 9]})
    assert result["h"] == pytest.approx(7.2)
    assert result["epsilon_squared"] == pytest.approx(5.2 / 6)


def test_tie_correction_and_no_difference() -> None:
    assert omnibus({1: [0, 0], 2: [1, 1]})["h"] == pytest.approx(3)
    assert omnibus({1: [0, 1], 2: [0, 1]})["epsilon_squared"] == 0
    with pytest.raises(ValueError, match="all outcomes tied"):
        omnibus({1: [1, 1], 2: [1, 1]})


def test_quantile() -> None:
    assert quantile([0, 1], 0.25) == 0.25
    assert quantile([0.5], 0.75) == 0.5


def fictional_rows() -> list[dict[str, object]]:
    return [
        {
            "FIPS": f"01{i:03d}"
            if i < 1000
            else f"02{i - 1000:03d}"
            if i < 2000
            else f"04{i - 2000:03d}"
            if i < 3000
            else f"05{i - 3000:03d}",
            "RELEASE_ID": RELEASE,
            "SVI_PERCENTILE": 0.5,
            "RUCC_2023": 1,
        }
        for i in range(3144)
    ]


def test_missing_invalid_and_zero_are_separate() -> None:
    rows = fictional_rows()
    rows[0]["SVI_PERCENTILE"] = 0
    rows[1]["SVI_PERCENTILE"] = None
    rows[2]["SVI_PERCENTILE"] = -999
    rows[3]["RUCC_2023"] = 1.5
    rows[4]["SVI_PERCENTILE"] = float("nan")
    rows[4]["RUCC_2023"] = True
    counties, counts = cohort(rows, {str(row["FIPS"]) for row in rows})
    assert counties[0].svi == 0
    assert counts["excluded_counties"] == 4
    assert counts["source_observation_rows"] is None
    assert counts["exclusions"] == {
        "svi_invalid_or_missing": 2,
        "rucc_invalid_or_missing": 1,
        "both_invalid_or_missing": 1,
    }


def test_duplicate_and_release_fail_closed() -> None:
    rows = fictional_rows()
    canonical = {str(row["FIPS"]) for row in rows}
    rows[0]["FIPS"] = rows[1]["FIPS"]
    with pytest.raises(ValueError, match="duplicate"):
        cohort(rows, canonical)
    rows = fictional_rows()
    rows[0]["RELEASE_ID"] = "wrong"
    with pytest.raises(ValueError, match="release mismatch"):
        cohort(rows, canonical)


def test_unsupported_group_descriptive_only() -> None:
    result = analyze([County("01001", 0.2, 1), County("01003", 0.8, 2)])
    assert result["status"] == "DESCRIPTIVE_ONLY"
    assert "omnibus" not in result


def test_state_resampling_is_deterministic_and_bounded() -> None:
    counties = [
        County(f"{state}{group:01d}{i:02d}", (i + group) / 40, group)
        for state in ["01", "02", "04"]
        for group in range(1, 10)
        for i in range(20)
    ]
    first = analyze(counties, replicates=10)
    assert first == analyze(counties, replicates=10)
    assert first["iid_p_value"] is None
    assert first["posthoc"] == "not_performed"
    assert first["state_block_sensitivity"]["states"] == 3
    with pytest.raises(ValueError, match="bounded"):
        analyze(counties, replicates=2001)


def test_replay_rejects_wrong_release_before_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps([[{}], [{"RELEASE_ID": "wrong", "BUNDLE_SHA256": "wrong"}], [], []])
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["replay", "--snapshot", str(snapshot), "--canonical-fips", str(tmp_path / "absent.txt")],
    )
    with pytest.raises(ValueError, match="identity/digest mismatch"):
        main()


def test_replay_rejects_changed_canonical_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lyme_gap_atlas_ml.eda63 import BUNDLE_SHA256

    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            [
                [{}],
                [{"RELEASE_ID": RELEASE, "BUNDLE_SHA256": BUNDLE_SHA256}],
                [
                    {"SOURCE_KEY": "context_svi", "VINTAGE": "2022 (2018-2022 ACS)"},
                    {"SOURCE_KEY": "context_rucc", "VINTAGE": "2023"},
                ],
                [],
            ]
        )
    )
    canonical = tmp_path / "canonical.txt"
    canonical.write_text("01001\n")
    monkeypatch.setattr(
        sys, "argv", ["replay", "--snapshot", str(snapshot), "--canonical-fips", str(canonical)]
    )
    with pytest.raises(ValueError, match="canonical identity digest mismatch"):
        main()
