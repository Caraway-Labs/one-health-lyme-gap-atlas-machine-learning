from copy import deepcopy

import pytest

from lyme_gap_atlas_ml import tier1_features as features


def _rows() -> list[dict[str, object]]:
    rows = []
    for number in range(3144):
        rows.append(
            {
                "FIPS": f"{number:05d}",
                "HUMAN_STATUS": "published_count_floor"
                if number % 2
                else "no_county_linked_record",
                "SCAPULARIS_STATUS": "Unknown",
                "PACIFICUS_STATUS": "Unknown",
                "BURGDORFERI_STATUS": ("Present", "No records", "Unknown")[number % 3],
                "SVI_PERCENTILE": number / 3143,
                "RUCC_2023": number % 9 + 1,
            }
        )
    return rows


def test_deterministic_matrix_and_distinct_states() -> None:
    rows = _rows()
    matrix, report = features.build_matrix(list(reversed(rows)))
    assert matrix[0]["county_fips"] == "00000"
    assert list(matrix[0]) == list(features.OUTPUT_COLUMNS)
    assert matrix[0]["pathogen_present"] == 1
    assert matrix[1]["pathogen_no_records"] == 1
    assert matrix[2]["pathogen_unknown"] == 1
    assert matrix[0]["human_published_floor"] == 0
    assert matrix[0]["human_evidence_state"] == "no_county_linked_record"
    assert report["duplicate_keys"] == 0
    assert report["feature_complete_counties"] == 3144
    assert all(stat["missing"] == 0 for stat in report["feature_stats"].values())
    assert features.build_matrix(rows) == (matrix, report)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("HUMAN_STATUS", "unknown"),
        ("BURGDORFERI_STATUS", "Absent"),
        ("SCAPULARIS_STATUS", "Established"),
        ("SVI_PERCENTILE", None),
        ("SVI_PERCENTILE", 1.2),
        ("RUCC_2023", 10),
    ],
)
def test_unreviewed_value_fails_closed(field: str, value: object) -> None:
    rows = _rows()
    rows[0][field] = value
    with pytest.raises(ValueError):
        features.build_matrix(rows)


def test_duplicate_key_fails_closed() -> None:
    rows = deepcopy(_rows())
    rows[1]["FIPS"] = rows[0]["FIPS"]
    with pytest.raises(ValueError, match="duplicate"):
        features.build_matrix(rows)


def test_priority_fields_never_enter_matrix() -> None:
    rows = _rows()
    for row in rows:
        row["DEFAULT_SCORE"] = 99
        row["PRIORITY_TIER"] = "HIGH"
    matrix, _ = features.build_matrix(rows)
    assert not any("score" in name or "tier" in name for name in matrix[0])
    assert "county_fips" not in features.FEATURE_COLUMNS
