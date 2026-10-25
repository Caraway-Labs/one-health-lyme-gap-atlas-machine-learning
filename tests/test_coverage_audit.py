"""Offline checks for the issue 109 coverage assembly."""

from __future__ import annotations

from pathlib import Path

import pytest

from lyme_gap_atlas_ml.coverage_audit import (
    CENSUS_REGIONS,
    HEATMAP_SIGNALS,
    PINNED_BUNDLE_SHA256,
    PINNED_RELEASE_ID,
    QUERY_NAMES,
    FetchedCoverage,
    RegionRow,
    assemble_coverage,
    headline_disposition,
    heatmap_cell_label,
    load_queries,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import prepare_column_profile, prepare_missingness

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql" / "validation" / "109_county_signal_coverage.sql"


def test_suppressed_heatmap_cells_are_labeled_rather_than_blank() -> None:
    assert heatmap_cell_label(None) == "<11"
    assert heatmap_cell_label(0.0) == "0"
    assert heatmap_cell_label(0.7929) == "79"


def test_registered_sql_matches_the_region_map_and_rejects_nothing_safe() -> None:
    queries = load_queries(SQL.read_text(encoding="utf-8"))
    assert tuple(queries) == QUERY_NAMES
    assert len(CENSUS_REGIONS) == 51
    assert len(set(CENSUS_REGIONS.values())) == 4


def test_headline_disposition_requires_the_october_13_counts_and_alignment() -> None:
    assert (
        headline_disposition(
            counties=3144,
            published_human_floor=651,
            no_county_linked_record=2493,
            alignments_hold=True,
        )
        == "keep"
    )
    assert (
        headline_disposition(
            counties=3144,
            published_human_floor=650,
            no_county_linked_record=2494,
            alignments_hold=True,
        )
        == "revise"
    )
    assert (
        headline_disposition(
            counties=3144,
            published_human_floor=651,
            no_county_linked_record=2493,
            alignments_hold=False,
        )
        == "revise"
    )


def _region(name: str, total: int, human: int) -> RegionRow:
    counts = {key: 0 for _signal, key in HEATMAP_SIGNALS}
    counts["HUMAN_UNDOC_N"] = human
    counts["CASE_NULL_N"] = human
    counts["INCIDENCE_NULL_N"] = human
    return RegionRow(name, total, counts)


def _fetched() -> FetchedCoverage:
    numeric: dict[str, object] = {}
    for column in (
        "POPULATION",
        "SVI_PERCENTILE",
        "UNINSURED_PERCENTILE",
        "UNINSURED_PERCENT",
        "RUCC_2023",
        "EVIDENCE_COMPLETENESS",
        "CASE_COUNT_FLOOR_2023",
        "INCIDENCE_FLOOR_2023",
    ):
        non_null = 40 if "FLOOR" in column else 100
        numeric[f"{column}_NON_NULL"] = non_null
        numeric[f"{column}_DISTINCT"] = 10
        numeric[f"{column}_MIN"] = 5
        numeric[f"{column}_MAX"] = 20
        numeric[f"{column}_MEAN"] = 8.0
        numeric[f"{column}_STDDEV"] = 1.0
        for suffix in ("P01", "P05", "P25", "P50", "P75", "P95", "P99"):
            numeric[f"{column}_{suffix}"] = 7.0
    levels = (
        ("HUMAN_STATUS", "published_count_floor", 40),
        ("HUMAN_STATUS", "no_county_linked_record", 60),
        ("TICK_STATUS", "Established", 50),
        ("TICK_STATUS", "No records", 50),
        ("SCAPULARIS_STATUS", "Established", 40),
        ("SCAPULARIS_STATUS", "No records", 60),
        ("PACIFICUS_STATUS", "Established", 10),
        ("PACIFICUS_STATUS", "No records", 90),
        ("BURGDORFERI_STATUS", "Present", 30),
        ("BURGDORFERI_STATUS", "No records", 70),
        ("RUCC_2023", "1", 100),
        ("EVIDENCE_COMPLETENESS", "50", 100),
        ("IN_CONTIGUOUS_TICK_SCOPE", "TRUE", 100),
    )
    return FetchedCoverage(
        row_n=100,
        fips_n=100,
        fips_pattern_n=100,
        release_n=1,
        release_min=PINNED_RELEASE_ID,
        release_max=PINNED_RELEASE_ID,
        release_id=PINNED_RELEASE_ID,
        bundle_sha256=PINNED_BUNDLE_SHA256,
        schema_version="2.0.0",
        methodology_version="semantic-2.0.0",
        scope="US_COUNTIES",
        sources=(("human", "2023"), ("tick", "through 2025-12-31")),
        levels=levels,
        regions=(
            _region("Northeast", 40, 30),
            _region("Midwest", 20, 10),
            _region("South", 20, 10),
            _region("West", 20, 10),
        ),
        states=(("CT", "HUMAN_STATUS", "published_count_floor", 4),),
        joints=(
            ("published_count_floor", "Established", "Present", 36),
            ("no_county_linked_record", "No records", "No records", 4),
        ),
        numeric=numeric,
        unallocated={
            "ROW_N": 51,
            "NULL_N": 0,
            "DISTINCT_N": 20,
            "MIN_VALUE": 3,
            "MAX_VALUE": 200,
            "MEAN_VALUE": 40.0,
            "STDDEV_VALUE": 10.0,
            "P01": 3.0,
            "P05": 5.0,
            "P25": 10.0,
            "P50": 20.0,
            "P75": 40.0,
            "P95": 100.0,
            "P99": 180.0,
        },
        geometry_null_n=0,
        nlcd_measures=(("nlcd_forest_area_share_county_year", 2, 2),),
        nlcd_counties=2,
        climate_row_n=3100,
        climate_county_n=100,
        climate_measure_n=2,
        climate_day_n=31,
        climate_min=None,
        climate_max=None,
        climate_status=(("complete", "OBSERVED", 3100, 100),),
    )


def test_assembly_hides_small_joint_cells_and_small_land_cover() -> None:
    assembled = assemble_coverage(_fetched())
    assert assembled.disposition == "revise"
    joints = [metric for metric in assembled.metrics if metric.metric_name == "joint_county_count"]
    assert {metric.n_underlying for metric in joints} == {4, 36}
    finding = next(item for item in assembled.findings if item.topic == "joint_partition")
    evidence = finding.evidence
    assert evidence is not None
    cells = evidence["cells"]
    assert isinstance(cells, list)
    assert cells
    assert all(cell["counties"] >= 11 for cell in cells)
    land = next(item for item in assembled.findings if item.topic == "land_cover_and_climate")
    assert "below the small-cell minimum" in land.statement
    assert "2" not in land.statement
    nlcd = next(row for row in assembled.missingness if row.column_name == "NLCD_COUNTY")
    prepared = prepare_missingness(nlcd)
    assert prepared.missing_n is None
    assert 2 not in prepared.bind("109-coverage-missingness-20261025T0000Z")
    allocated = next(
        row for row in assembled.profiles if row.column_name == "STATE_UNALLOCATED_RECORDS_2023"
    )
    profile = prepare_column_profile(allocated)
    assert profile.min_value is None
    midwest = assembled.charts.heatmap_shares[0][1]
    assert midwest is None


def test_release_pin_mismatch_is_a_stop_for_the_caller() -> None:
    fetched = _fetched()
    broken = FetchedCoverage(
        **{**fetched.__dict__, "release_id": "other-release"},
    )
    with pytest.raises(Exception, match="release pin"):
        from lyme_gap_atlas_ml.coverage_audit import check_integrity

        check_integrity(broken)
