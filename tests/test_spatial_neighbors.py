"""Fake-data checks for the issue 113 neighbor design and within-state contrast."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.coverage_audit import CENSUS_REGIONS, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.cross_domain import bh
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import prepare_finding
from lyme_gap_atlas_ml.spatial_neighbors import (
    QUERY_NAMES,
    County,
    SpatialNeighborError,
    assert_catalog_clear,
    assert_lab_edges,
    assert_measures,
    assess_spatial,
    coverage_adjusted_divergence,
    fit_within_state,
    lab_findings,
    moran_i,
    parse_counties,
    release_gate,
    require_reference,
)
from lyme_gap_atlas_ml.test_selection import holm

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "113_spatial_neighbors.sql"


def test_moran_i_on_a_line_of_alternating_ends_is_negative() -> None:
    statistic = moran_i((1.0, 0.0, 1.0), ((1,), (0, 2), (1,)))
    assert statistic is not None
    assert statistic == pytest.approx(-1.0)


def test_catalog_guards_reject_an_adjacency_source() -> None:
    assert_catalog_clear(())
    with pytest.raises(SpatialNeighborError):
        assert_catalog_clear(({"TABLE_SCHEMA": "PRESENTATION", "COLUMN_NAME": "NEIGHBOR_FIPS"},))
    assert_measures(({"MEASURE_ID": "county_geometry"},))
    assert_measures(())
    with pytest.raises(SpatialNeighborError):
        assert_measures(({"MEASURE_ID": "county_adjacency"},))
    assert_lab_edges(0)
    with pytest.raises(SpatialNeighborError):
        assert_lab_edges(1)


def test_release_gate_and_reference_counts() -> None:
    release_gate(
        {
            "RELEASE_ID": PINNED_RELEASE_ID,
            "SCHEMA_VERSION": "2.0.0",
            "METHODOLOGY_VERSION": "semantic-2.0.0",
            "SCOPE": "US_COUNTIES",
            "BUNDLE_SHA256": "53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d",
        }
    )
    with pytest.raises(SpatialNeighborError):
        require_reference(())


def test_parse_rejects_a_floor_on_an_unpublished_county() -> None:
    row = _row("48001", "TX", published=False)
    row["CASE_COUNT_FLOOR_2023"] = 5
    with pytest.raises(SpatialNeighborError):
        parse_counties((row,), release_id=PINNED_RELEASE_ID)


def test_within_state_flags_a_high_peer_and_holds_the_cdc_floor() -> None:
    texas = _spread("TX", 41, start=1, base=20.0, spike=400.0)
    floor = texas[-2]
    texas[-2] = _county(floor.fips, "TX", "Floor County", incidence=1.0, case_floor=5)
    unpublished = _county(_fips("TX", 99), "TX", "Unpublished", published=False)
    alabama = _spread("AL", 20, start=1, base=15.0, spike=300.0)
    district = _spread("DC", 5, start=1, base=12.0, spike=250.0)
    counties = [*texas, unpublished, *alabama, *district]
    result = fit_within_state(tuple(counties), draws=40)
    assert result.band_states["state_native"] == 1
    assert result.band_states["shrunk"] == 1
    assert result.band_states["below_band"] == 1
    high = any(
        item.county.fips == texas[-1].fips and item.kind == "high" for item in result.high_flags
    )
    assert high
    assert all(item.county.state != "DC" for item in result.high_flags)
    assert all(item.county.fips != unpublished.fips for item in result.high_flags)
    assert all(item.county.case_floor != 5 for item in result.low_flags)
    assert result.floor_heaps >= 1
    assert result.neighbor_disposition == "stop"
    assert result.product_disposition == "investigate"
    again = fit_within_state(tuple(counties), draws=40)
    assert again.eta_tail == result.eta_tail
    assert result.eta_holm == result.eta_tail
    assert result.eta_bh == result.eta_tail


def test_chart_bins_require_eleven_states() -> None:
    counties: list[County] = []
    for index, state in enumerate(list(CENSUS_REGIONS)[:11]):
        counties.extend(_spread(state, 11, start=1, base=10.0 + index))
    result = fit_within_state(tuple(counties), draws=20)
    assert result.chart_states == 11
    assert sum(count for _label, count in result.chart_bins) == 11
    for finding in lab_findings(result):
        prepare_finding(finding, finding_id=finding.finding_id or "")


def test_divergence_keeps_coverage_classes_out_of_the_residual() -> None:
    counties = _spread("TX", 12, start=1, base=10.0, spike=500.0)
    gap = _county(_fips("TX", 80), "TX", "Gap", published=False)
    floor = _county(_fips("TX", 81), "TX", "Censored", incidence=4.0, case_floor=5)
    other = _county(_fips("TX", 82), "TX", "Peer", incidence=30.0, case_floor=20)
    published = [county.fips for county in counties]
    edges = [(published[index], published[index + 1]) for index in range(len(published) - 1)]
    edges.append((published[0], published[-1]))
    edges.append((published[1], gap.fips))
    edges.append((floor.fips, other.fips))
    island = _county(_fips("TX", 83), "TX", "Island", incidence=12.0, case_floor=20)
    result = coverage_adjusted_divergence((*counties, gap, floor, other, island), edges)
    assert result.one_published == 1
    assert result.floor_limited == 1
    assert result.islands >= 1
    assert all(item.left != floor.fips and item.right != floor.fips for item in result.flagged)
    flagged_pairs = {(item.left, item.right) for item in result.flagged}
    assert (min(published[1], gap.fips), max(published[1], gap.fips)) not in flagged_pairs
    with pytest.raises(SpatialNeighborError):
        coverage_adjusted_divergence(counties, ((published[0], published[0]),))
    with pytest.raises(SpatialNeighborError):
        coverage_adjusted_divergence(
            counties,
            ((published[0], published[1]), (published[1], published[0])),
        )


def test_spatial_gates_and_holm() -> None:
    empty = assess_spatial(_spread("TX", 11, start=1, base=1.0), ())
    assert empty.reason == "no_edges"
    small = _spread("TX", 5, start=1, base=1.0)
    small_edges = [(small[index].fips, small[index + 1].fips) for index in range(4)]
    assert assess_spatial(small, small_edges).reason == "component_below_11"
    flat = [
        _county(_fips("TX", index), "TX", f"Flat {index}", incidence=8.0, case_floor=20)
        for index in range(1, 12)
    ]
    flat_edges = [(flat[index].fips, flat[index + 1].fips) for index in range(10)]
    assert assess_spatial(flat, flat_edges).reason == "zero_variance"
    blocked = []
    states = list(CENSUS_REGIONS)[:11]
    for index, state in enumerate(states):
        blocked.append(
            _county(
                f"{index + 1:05d}",
                state,
                state,
                incidence=float(index),
                case_floor=20,
            )
        )
    blocked_edges = [(blocked[index].fips, blocked[index + 1].fips) for index in range(10)]
    blocked_result = assess_spatial(blocked, blocked_edges, draws=20)
    assert blocked_result.reason == "permutation_not_estimable"
    assert blocked_result.moran_i is not None
    clustered = _spread("TX", 11, start=1, base=0.0)
    for index, county in enumerate(clustered):
        incidence = 0.0 if index < 6 else 10.0
        clustered[index] = _county(
            county.fips,
            "TX",
            county.name,
            incidence=incidence,
            case_floor=20,
        )
    edges = [(clustered[index].fips, clustered[index + 1].fips) for index in range(10)]
    fitted = assess_spatial(clustered, edges, draws=30)
    assert fitted.estimable
    assert fitted.moran_i is not None and fitted.moran_i > 0
    assert fitted.holm == holm(fitted.local_tails)
    assert fitted.bh == bh(fitted.local_tails)


def test_sql_file_has_no_geometry_or_payload_text() -> None:
    text = SQL_PATH.read_text(encoding="utf-8")
    load_marked_queries(text, QUERY_NAMES)
    upper = text.upper()
    for token in ("GEOMETRY_JSON", "PAYLOAD", "PART_TEXT", "CONTEXT_LIMITATIONS"):
        assert token not in upper


def _spread(
    state: str,
    count: int,
    *,
    start: int,
    base: float,
    spike: float | None = None,
) -> list[County]:
    counties: list[County] = []
    for offset in range(count):
        fips = _fips(state, start + offset)
        incidence = base + float(offset % 5)
        if spike is not None and offset == count - 1:
            incidence = spike
        counties.append(_county(fips, state, f"County {fips}", incidence=incidence, case_floor=20))
    return counties


def _fips(state: str, local: int) -> str:
    ordered = list(CENSUS_REGIONS)
    return f"{ordered.index(state) + 1:02d}{local:03d}"


def _county(
    fips: str,
    state: str,
    name: str,
    *,
    incidence: float | None = None,
    case_floor: int | None = None,
    published: bool = True,
) -> County:
    return County(
        fips=fips,
        name=name,
        state=state,
        population=1000,
        human_status="published_count_floor" if published else "no_county_linked_record",
        case_floor=case_floor,
        incidence=incidence,
    )


def _row(fips: str, state: str, *, published: bool) -> dict[str, object]:
    return {
        "FIPS": fips,
        "COUNTY": "Example",
        "STATE": state,
        "RELEASE_ID": PINNED_RELEASE_ID,
        "POPULATION": 1000,
        "HUMAN_STATUS": "published_count_floor" if published else "no_county_linked_record",
        "CASE_COUNT_FLOOR_2023": 20 if published else None,
        "INCIDENCE_FLOOR_2023": 10.0 if published else None,
    }


def test_numpy_generator_is_the_permutation_source() -> None:
    generator = np.random.default_rng(1132026)
    assert generator.random() != np.random.default_rng(1132027).random()
