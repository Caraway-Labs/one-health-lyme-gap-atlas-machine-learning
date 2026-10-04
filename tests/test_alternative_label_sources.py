"""Inventory boundaries use synthetic cells, never actual sample counts."""

import pytest

from lyme_gap_atlas_ml.alternative_label_sources import summarize_wi


def test_count_rows_are_distinct_from_rates_and_missing_is_not_zero() -> None:
    body = (
        b"Fips,Year,Sub-topic,Topic,Number Total\n"
        b"55001,2011,Counts,Cases,0\n"
        b"55003,2011,Counts,Cases,\n"
        b"55001,2011,Crude Rates per 100000,Incidence,0\n"
    )
    result = summarize_wi(body)
    assert result["count_rows"] == 2
    assert result["count_signs"] == {"explicit_zero": 1, "unavailable": 1}


def test_duplicate_count_keys_fail() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        summarize_wi(
            b"Fips,Year,Sub-topic,Topic,Number Total\n"
            b"55001,2011,Counts,Cases,0\n55001,2011,Counts,Cases,1\n"
        )
