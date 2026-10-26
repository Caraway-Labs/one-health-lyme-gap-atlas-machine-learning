"""Within-state incidence contrasts and a neighbor design for issue 113.

Live counties are not given neighbor weights. The coverage-adjusted pair
design and Moran's I run only when the caller supplies edges. Aggregate lab
records suppress counts from 1 to 10. The results write-up may name counties.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from lyme_gap_atlas_ml.class_anomaly import MAD_SCALE, Z_FLAG
from lyme_gap_atlas_ml.coverage_audit import (
    CENSUS_REGIONS,
    PINNED_BUNDLE_SHA256,
    PINNED_RELEASE_ID,
    REFERENCE_COUNTIES,
    REFERENCE_NO_COUNTY_LINKED_RECORD,
    REFERENCE_PUBLISHED_HUMAN_FLOOR,
)
from lyme_gap_atlas_ml.cross_domain import bh
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import FindingRecord
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric
from lyme_gap_atlas_ml.state_anomaly import SHRINK_MIN, STATE_NATIVE_MIN, shrunk_mad
from lyme_gap_atlas_ml.test_selection import holm

SPEC_ID = "113-spatial-neighbor-outliers/v1"
SEED = 1132026
STATE_DRAWS = 2000
SPATIAL_DRAWS = 999
CDC_FLOOR = 5
COMPONENT_MIN = 11
HOLM_FLAG = 0.05
HUMAN_PUBLISHED = "published_count_floor"
HUMAN_UNPUBLISHED = "no_county_linked_record"
SCHEMA_VERSION = "2.0.0"
METHODOLOGY_VERSION = "semantic-2.0.0"
SCOPE = "US_COUNTIES"
NATIONAL_HIGH_107 = 37
NATIONAL_LOW_107 = 0
SILENT_STATES_107 = 19
SILENT_COUNTIES_107 = 1437
INCIDENCE_EDGES = (0.0, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 2000.0)
EXPECTED_VINTAGES = {
    "human": "2023",
    "tick": "through 2025-12-31",
    "pathogen": "through 2025-12-31",
    "context_svi": "2022 (2018-2022 ACS)",
    "context_rucc": "2023",
    "context_nlcd_2025": "C1V2-2025",
}
PRIOR_INCIDENCE_TAIL = (
    ("Dukes County", "MA"),
    ("Nantucket County", "MA"),
    ("Cameron County", "PA"),
    ("Jefferson County", "PA"),
    ("Washington County", "RI"),
    ("Tucker County", "WV"),
    ("Knox County", "ME"),
    ("Webster County", "WV"),
)
Vector = np.ndarray[Any, Any]
FINDING_IDS = (
    "11311311-0000-4000-8000-000000000001",
    "11311311-0000-4000-8000-000000000002",
)
QUERY_NAMES = (
    "release_identity",
    "source_vintages",
    "adjacency_columns",
    "spatial_measures",
    "adjacency_lab_rows",
    "cohort_rows",
)


class SpatialNeighborError(ValueError):
    """The cohort, catalog guard, or edge list cannot support the frozen spec."""


@dataclass(frozen=True)
class County:
    fips: str
    name: str
    state: str
    population: int | None
    human_status: str
    case_floor: int | None
    incidence: float | None

    @property
    def published(self) -> bool:
        return self.human_status == HUMAN_PUBLISHED


@dataclass(frozen=True)
class Flagged:
    county: County
    peer_rule: str
    peer_n: int
    median: float
    scale: float
    z: float
    kind: str


@dataclass(frozen=True)
class StateMedian:
    state: str
    published: int
    median: float


@dataclass(frozen=True)
class Analysis:
    county_n: int
    published_n: int
    unpublished_n: int
    states_without_published: int
    counties_in_silent_states: int
    silent_matches_107: bool
    national_median: float
    national_mad: float
    national_high: int
    national_low: int
    national_matches_107: bool
    band_states: dict[str, int]
    band_counties: dict[str, int]
    high_flags: tuple[Flagged, ...]
    low_flags: tuple[Flagged, ...]
    floor_heaps: int
    case_floor_below_cdc: int
    mad_not_estimable_states: int
    eta_sq: float | None
    eta_tail: float | None
    eta_holm: float | None
    eta_bh: float | None
    draws: int
    seed: int
    chart_states: int
    chart_bins: tuple[tuple[str, int], ...]
    state_medians: tuple[StateMedian, ...]
    prior_overlap: tuple[Flagged, ...]
    within_state_disposition: str
    neighbor_disposition: str
    product_disposition: str


@dataclass(frozen=True)
class PairFlag:
    left: str
    right: str
    stratum: str
    absolute_gap: float
    residual: float
    z: float


@dataclass(frozen=True)
class DivergenceResult:
    edges: int
    islands: int
    both_unpublished: int
    one_published: int
    floor_limited: int
    eligible: dict[str, int]
    flagged: tuple[PairFlag, ...]
    strata_not_estimable: tuple[str, ...]


@dataclass(frozen=True)
class SpatialResult:
    estimable: bool
    reason: str
    component_n: int
    moran_i: float | None
    moran_tail: float | None
    local_tails: tuple[tuple[str, float], ...]
    holm: dict[str, float]
    bh: dict[str, float]
    flagged_fips: tuple[str, ...]


def release_gate(row: Mapping[str, object]) -> None:
    """Stop unless the live pin matches the frozen release."""
    if _text(row.get("RELEASE_ID")) != PINNED_RELEASE_ID:
        raise SpatialNeighborError("live release does not match the frozen pin")
    if _text(row.get("SCHEMA_VERSION")) != SCHEMA_VERSION:
        raise SpatialNeighborError("live schema does not match the frozen pin")
    if _text(row.get("METHODOLOGY_VERSION")) != METHODOLOGY_VERSION:
        raise SpatialNeighborError("live methodology does not match the frozen pin")
    if _text(row.get("SCOPE")) != SCOPE:
        raise SpatialNeighborError("live scope does not match the frozen pin")
    bundle = _text(row.get("BUNDLE_SHA256")).lower()
    if bundle != PINNED_BUNDLE_SHA256:
        raise SpatialNeighborError("live bundle does not match the frozen pin")


def vintage_gate(rows: Sequence[Mapping[str, object]]) -> None:
    """Stop if a pinned source vintage differs from the #107 record."""
    found = {_text(row.get("SOURCE_KEY")): _text(row.get("VINTAGE")) for row in rows}
    for key, vintage in EXPECTED_VINTAGES.items():
        if found.get(key) != vintage:
            raise SpatialNeighborError("source vintage does not match the frozen pin")


def assert_catalog_clear(rows: Sequence[Mapping[str, object]]) -> None:
    """Stop if an allow-listed column looks like adjacency or a centroid."""
    if rows:
        raise SpatialNeighborError("adjacency-like column is on the allow-list")


def assert_measures(rows: Sequence[Mapping[str, object]]) -> None:
    """Allow the geometry measure name and nothing else from the spatial filter."""
    found = {_text(row.get("MEASURE_ID")) for row in rows}
    if found - {"county_geometry"}:
        raise SpatialNeighborError("unexpected spatial measure id")


def assert_lab_edges(count: int) -> None:
    """The #107 lab table is not a governed adjacency source."""
    if count != 0:
        raise SpatialNeighborError("lab adjacency table is not an allow-listed source")


def parse_counties(rows: Sequence[Mapping[str, object]], *, release_id: str) -> tuple[County, ...]:
    """Validate identity and the published-floor alignment. Do not impute."""
    if release_id != PINNED_RELEASE_ID:
        raise SpatialNeighborError("release id does not match the frozen pin")
    seen: set[str] = set()
    counties: list[County] = []
    for row in rows:
        fips = row.get("FIPS")
        state = row.get("STATE")
        if not isinstance(fips, str) or len(fips) != 5 or not fips.isdigit():
            raise SpatialNeighborError("five-digit string FIPS required")
        if fips in seen:
            raise SpatialNeighborError("duplicate FIPS")
        seen.add(fips)
        if not isinstance(state, str) or state not in CENSUS_REGIONS:
            raise SpatialNeighborError("state is outside the Census map")
        if _text(row.get("RELEASE_ID")) != release_id:
            raise SpatialNeighborError("mixed release")
        human = _text(row.get("HUMAN_STATUS"))
        if human not in {HUMAN_PUBLISHED, HUMAN_UNPUBLISHED}:
            raise SpatialNeighborError("human status is outside the frozen levels")
        case_floor = _optional_int(row.get("CASE_COUNT_FLOOR_2023"), "CASE_COUNT_FLOOR_2023")
        incidence = _optional_float(row.get("INCIDENCE_FLOOR_2023"), "INCIDENCE_FLOOR_2023")
        published = human == HUMAN_PUBLISHED
        if published and (case_floor is None or incidence is None):
            raise SpatialNeighborError("published row is missing a floor")
        if not published and (case_floor is not None or incidence is not None):
            raise SpatialNeighborError("unpublished row has a floor")
        name = row.get("COUNTY")
        counties.append(
            County(
                fips=fips,
                name=name.strip() if isinstance(name, str) else "",
                state=state,
                population=_optional_int(row.get("POPULATION"), "POPULATION"),
                human_status=human,
                case_floor=case_floor,
                incidence=incidence,
            )
        )
    return tuple(sorted(counties, key=lambda county: county.fips))


def require_reference(counties: Sequence[County]) -> None:
    """Stop unless the headline split matches the pinned release."""
    published = sum(county.published for county in counties)
    unpublished = sum(not county.published for county in counties)
    if len(counties) != REFERENCE_COUNTIES:
        raise SpatialNeighborError("county count is not 3144")
    if published != REFERENCE_PUBLISHED_HUMAN_FLOOR:
        raise SpatialNeighborError("published floor count is not 651")
    if unpublished != REFERENCE_NO_COUNTY_LINKED_RECORD:
        raise SpatialNeighborError("unpublished count is not 2493")


def fit_within_state(
    counties: Sequence[County],
    *,
    seed: int = SEED,
    draws: int = STATE_DRAWS,
) -> Analysis:
    """Fit the frozen within-state contrast. Neighbor weights are not an input."""
    if draws < 1:
        raise SpatialNeighborError("permutation draws must be positive")
    published = tuple(county for county in counties if county.published)
    if not published:
        raise SpatialNeighborError("no published incidence floors")
    values = np.asarray([_incidence(county) for county in published], dtype=float)
    national_median, national_mad = _location_mad(values)
    national_high, national_low = _national_flags(values, national_median, national_mad)
    by_state: dict[str, list[County]] = defaultdict(list)
    for county in counties:
        by_state[county.state].append(county)
    silent_states = 0
    silent_counties = 0
    for group in by_state.values():
        if not any(county.published for county in group):
            silent_states += 1
            silent_counties += len(group)
    high: list[Flagged] = []
    low: list[Flagged] = []
    floor_heaps = 0
    below_cdc = sum(
        1 for county in published if county.case_floor is not None and county.case_floor < CDC_FLOOR
    )
    mad_not_estimable = 0
    band_states: dict[str, int] = defaultdict(int)
    band_counties: dict[str, int] = defaultdict(int)
    medians: list[StateMedian] = []
    for state in sorted(by_state):
        published_in_state = tuple(
            county for county in by_state[state] if county.published
        )
        if not published_in_state:
            continue
        state_values = np.asarray(
            [_incidence(county) for county in published_in_state],
            dtype=float,
        )
        median, state_mad = _location_mad(state_values)
        rule, scale = _peer_scale(
            state,
            published_in_state,
            state_mad,
            published,
            national_mad,
        )
        band_states[rule] += 1
        band_counties[rule] += len(published_in_state)
        if len(published_in_state) >= COMPONENT_MIN:
            medians.append(
                StateMedian(state=state, published=len(published_in_state), median=median)
            )
        if rule == "below_band":
            continue
        if scale <= 0:
            mad_not_estimable += 1
            continue
        peer_n = len(published_in_state)
        for county in published_in_state:
            z_value = (_incidence(county) - median) / (MAD_SCALE * scale)
            if z_value > Z_FLAG:
                high.append(_flag(county, rule, peer_n, median, scale, z_value, "high"))
            elif z_value < -Z_FLAG and county.case_floor == CDC_FLOOR:
                floor_heaps += 1
            elif (
                z_value < -Z_FLAG
                and county.case_floor is not None
                and county.case_floor > CDC_FLOOR
            ):
                low.append(_flag(county, rule, peer_n, median, scale, z_value, "low"))
    high_flags = tuple(sorted(high, key=lambda item: (-item.z, item.county.fips)))
    low_flags = tuple(sorted(low, key=lambda item: (item.z, item.county.fips)))
    labels = np.asarray([county.state for county in published], dtype=object)
    eta_sq, eta_tail, eta_holm, eta_bh = _permute_eta(values, labels, seed=seed, draws=draws)
    chart_bins = _chart_bins(medians)
    overlap = tuple(
        item
        for item in high_flags
        if _prior_match(item.county.name, item.county.state)
    )
    published_n = len(published)
    unpublished_n = len(counties) - published_n
    within = (
        "keep"
        if len(counties) == REFERENCE_COUNTIES
        and published_n == REFERENCE_PUBLISHED_HUMAN_FLOOR
        and unpublished_n == REFERENCE_NO_COUNTY_LINKED_RECORD
        else "revise"
    )
    return Analysis(
        county_n=len(counties),
        published_n=published_n,
        unpublished_n=unpublished_n,
        states_without_published=silent_states,
        counties_in_silent_states=silent_counties,
        silent_matches_107=silent_states == SILENT_STATES_107
        and silent_counties == SILENT_COUNTIES_107,
        national_median=national_median,
        national_mad=national_mad,
        national_high=national_high,
        national_low=national_low,
        national_matches_107=(
            national_high == NATIONAL_HIGH_107 and national_low == NATIONAL_LOW_107
        ),
        band_states=dict(band_states),
        band_counties=dict(band_counties),
        high_flags=high_flags,
        low_flags=low_flags,
        floor_heaps=floor_heaps,
        case_floor_below_cdc=below_cdc,
        mad_not_estimable_states=mad_not_estimable,
        eta_sq=eta_sq,
        eta_tail=eta_tail,
        eta_holm=eta_holm,
        eta_bh=eta_bh,
        draws=draws,
        seed=seed,
        chart_states=len(medians),
        chart_bins=chart_bins,
        state_medians=tuple(medians),
        prior_overlap=overlap,
        within_state_disposition=within,
        neighbor_disposition="stop",
        product_disposition="investigate",
    )


def coverage_adjusted_divergence(
    counties: Sequence[County],
    edges: Sequence[tuple[str, str]],
) -> DivergenceResult:
    """Pair residuals for a supplied edge list. Missing floors stay missing."""
    by_fips = {county.fips: county for county in counties}
    if len(by_fips) != len(counties):
        raise SpatialNeighborError("duplicate FIPS")
    normalized = _normalize_edges(edges)
    touched: set[str] = set()
    both_unpublished = 0
    one_published = 0
    floor_limited = 0
    eligible: dict[str, list[tuple[str, str, float]]] = {"within_state": [], "cross_state": []}
    for left, right in normalized:
        if left not in by_fips or right not in by_fips:
            raise SpatialNeighborError("edge endpoint is not in the county set")
        touched.add(left)
        touched.add(right)
        first = by_fips[left]
        second = by_fips[right]
        published_n = int(first.published) + int(second.published)
        if published_n == 0:
            both_unpublished += 1
            continue
        if published_n == 1:
            one_published += 1
            continue
        if first.case_floor == CDC_FLOOR or second.case_floor == CDC_FLOOR:
            floor_limited += 1
            continue
        stratum = "within_state" if first.state == second.state else "cross_state"
        gap = abs(_incidence(first) - _incidence(second))
        eligible[stratum].append((left, right, gap))
    flagged: list[PairFlag] = []
    not_estimable: list[str] = []
    for stratum, pairs in eligible.items():
        flags, estimable = _stratum_flags(stratum, pairs)
        flagged.extend(flags)
        if not estimable:
            not_estimable.append(stratum)
    islands = sum(county.fips not in touched for county in counties)
    return DivergenceResult(
        edges=len(normalized),
        islands=islands,
        both_unpublished=both_unpublished,
        one_published=one_published,
        floor_limited=floor_limited,
        eligible={key: len(value) for key, value in eligible.items()},
        flagged=tuple(sorted(flagged, key=lambda item: (-item.z, item.left, item.right))),
        strata_not_estimable=tuple(not_estimable),
    )


def moran_i(values: Sequence[float], neighbors: Sequence[Sequence[int]]) -> float | None:
    """Row-standardized global Moran's I. None when the variance or the weights are zero."""
    statistic, _local, _ok = _moran_parts(values, neighbors)
    return statistic


def assess_spatial(
    counties: Sequence[County],
    edges: Sequence[tuple[str, str]],
    *,
    seed: int = SEED,
    draws: int = SPATIAL_DRAWS,
) -> SpatialResult:
    """Moran's I and LISA on one supplied graph. Empty edges are not estimable."""
    if draws < 1:
        raise SpatialNeighborError("permutation draws must be positive")
    normalized = _normalize_edges(edges) if edges else ()
    if not normalized:
        return _spatial_empty("no_edges")
    published = {county.fips: county for county in counties if county.published}
    kept = tuple(
        pair for pair in normalized if pair[0] in published and pair[1] in published
    )
    components = _components(tuple(published), kept)
    if not components:
        return _spatial_empty("no_published_component")
    components.sort(key=lambda comp: (-len(comp), min(comp)))
    component = components[0]
    if len(component) < COMPONENT_MIN:
        return _spatial_empty("component_below_11", component_n=len(component))
    order = tuple(sorted(component))
    index = {fips: position for position, fips in enumerate(order)}
    neighbors: list[list[int]] = [[] for _ in order]
    for left, right in kept:
        if left in index and right in index:
            neighbors[index[left]].append(index[right])
            neighbors[index[right]].append(index[left])
    values = np.asarray([_incidence(published[fips]) for fips in order], dtype=float)
    if float(np.var(values)) == 0:
        return _spatial_empty("zero_variance", component_n=len(order))
    labels = [published[fips].state for fips in order]
    blocks = _blocks(labels)
    movable = sum(len(block) for block in blocks if len(block) >= 2)
    point, _local, ok = _moran_parts(values, neighbors)
    if not ok or point is None:
        return _spatial_empty("weights_not_usable", component_n=len(order))
    if movable < 2:
        return SpatialResult(
            estimable=False,
            reason="permutation_not_estimable",
            component_n=len(order),
            moran_i=point,
            moran_tail=None,
            local_tails=(),
            holm={},
            bh={},
            flagged_fips=(),
        )
    rng = np.random.default_rng(seed)
    global_hits = 0
    local_hits = np.zeros(len(order), dtype=int)
    observed_local = _local_i(values, neighbors)
    for _draw in range(draws):
        shuffled = _permute_blocks(values, blocks, rng)
        draw_i, draw_local, draw_ok = _moran_parts(shuffled, neighbors)
        if draw_ok and draw_i is not None and abs(draw_i) >= abs(point):
            global_hits += 1
        if draw_local is None:
            continue
        local_hits += (np.abs(draw_local) >= np.abs(observed_local)).astype(int)
    denominator = draws + 1
    moran_tail = (global_hits + 1) / denominator
    local_tails = tuple(
        (fips, (int(local_hits[position]) + 1) / denominator)
        for position, fips in enumerate(order)
    )
    adjusted_holm = holm(local_tails)
    adjusted_bh = bh(local_tails)
    flagged = tuple(
        fips for fips, _tail in local_tails if adjusted_holm[fips] <= HOLM_FLAG
    )
    return SpatialResult(
        estimable=True,
        reason="estimated",
        component_n=len(order),
        moran_i=point,
        moran_tail=moran_tail,
        local_tails=local_tails,
        holm=adjusted_holm,
        bh=adjusted_bh,
        flagged_fips=flagged,
    )


def lab_metrics(result: Analysis) -> list[EdaMetric]:
    """National and state aggregates. Flag counts use the flag count as n."""
    rows = [
        _metric("published_n", result.published_n, result.published_n, "count"),
        _metric("unpublished_n", result.unpublished_n, result.unpublished_n, "count"),
        _metric(
            "states_without_published",
            result.counties_in_silent_states,
            result.states_without_published,
            "count",
        ),
        _metric(
            "national_incidence_median",
            result.published_n,
            result.national_median,
            "per_100000",
        ),
        _metric(
            "national_incidence_mad",
            result.published_n,
            result.national_mad,
            "per_100000",
        ),
        _metric("national_mad_high_flags", result.national_high, result.national_high, "count"),
        _metric("national_mad_low_flags", result.national_low, result.national_low, "count"),
        _metric("high_divergence", len(result.high_flags), len(result.high_flags), "count"),
        _metric("low_divergence", len(result.low_flags), len(result.low_flags), "count"),
        _metric("floor_heaps", result.floor_heaps, result.floor_heaps, "count"),
        _metric(
            "case_floor_below_cdc",
            result.case_floor_below_cdc,
            result.case_floor_below_cdc,
            "count",
        ),
        _metric(
            "mad_not_estimable_states",
            result.mad_not_estimable_states,
            result.mad_not_estimable_states,
            "count",
        ),
        _metric("eta_sq", result.published_n, result.eta_sq, "share"),
        _metric("eta_tail", result.published_n, result.eta_tail, "tail"),
        _metric("eta_holm", result.published_n, result.eta_holm, "tail"),
        _metric("eta_bh", result.published_n, result.eta_bh, "tail"),
        _metric("adjacency_sources", result.county_n, 0, "count"),
        _metric("lab_adjacency_edges", result.county_n, 0, "count"),
        _metric("neighbor_estimable", result.county_n, 0, "indicator"),
        _metric(
            "prior_tail_overlap",
            len(result.prior_overlap),
            len(result.prior_overlap),
            "count",
        ),
    ]
    for rule, counties_n in sorted(result.band_counties.items()):
        rows.append(
            _metric(
                f"band_{rule}_counties",
                counties_n,
                result.band_states.get(rule, 0),
                "count",
            )
        )
    for state in result.state_medians:
        rows.append(
            EdaMetric(
                metric_name="incidence_median",
                n_underlying=state.published,
                metric_value=state.median,
                geography_type="state",
                geography_id=state.state,
                unit="per_100000",
            )
        )
    return rows


def lab_findings(result: Analysis) -> tuple[FindingRecord, ...]:
    """Two aggregate findings. County names stay in the write-up."""
    adjacency = FindingRecord(
        topic="adjacency source",
        statement=(
            "No allow-listed adjacency, centroid, latitude, longitude, or neighbor column "
            "was found. The lab edge count is zero. Neighbor contrasts, Moran's I, and LISA "
            "were not estimated. A governed FIPS-pair table is the follow-up."
        ),
        disposition="follow-up",
        n_underlying=result.county_n,
        finding_id=FINDING_IDS[0],
        uncertainty_note="Catalog names only. No coordinate column was selected.",
    )
    share = "not estimable" if result.eta_sq is None else "recorded as the effect size"
    within = FindingRecord(
        topic="within-state incidence",
        statement=(
            "Published incidence floors were compared with the state median using the "
            f"issue 106 size bands. The between-state share of squares is {share}. "
            "Holm and BH match the single permutation tail. This is not a neighbor contrast."
        ),
        disposition=result.within_state_disposition,
        n_underlying=result.published_n,
        effect_size=result.eta_sq,
        finding_id=FINDING_IDS[1],
        evidence={
            "published_n": result.published_n,
            "county_n": result.county_n,
            "eta_sq": result.eta_sq,
            "tail": result.eta_tail,
        },
        uncertainty_note="State-label permutation. Not a neighbor null.",
    )
    return (adjacency, within)


def _peer_scale(
    state: str,
    group: Sequence[County],
    state_mad: float,
    published: Sequence[County],
    national_mad: float,
) -> tuple[str, float]:
    count = len(group)
    if count >= STATE_NATIVE_MIN:
        return "state_native", state_mad
    if count < SHRINK_MIN:
        return "below_band", 0.0
    region = CENSUS_REGIONS[state]
    loo = np.asarray(
        [
            _incidence(county)
            for county in published
            if county.state != state and CENSUS_REGIONS[county.state] == region
        ],
        dtype=float,
    )
    loo_mad = 0.0 if len(loo) == 0 else _location_mad(loo)[1]
    scale = shrunk_mad(state_mad, count, loo_mad, int(len(loo)), national_mad)
    return "shrunk", scale


def _national_flags(values: Vector, median: float, mad: float) -> tuple[int, int]:
    if mad <= 0:
        return 0, 0
    z_values = (values - median) / (MAD_SCALE * mad)
    return int(np.sum(z_values > Z_FLAG)), int(np.sum(z_values < -Z_FLAG))


def _permute_eta(
    values: Vector,
    labels: Vector,
    *,
    seed: int,
    draws: int,
) -> tuple[float | None, float | None, float | None, float | None]:
    observed = _eta(values, labels)
    if observed is None:
        return None, None, None, None
    rng = np.random.default_rng(seed)
    hits = 0
    for _draw in range(draws):
        shuffled = rng.permutation(values)
        draw = _eta(shuffled, labels)
        if draw is not None and draw >= observed:
            hits += 1
    tail = (hits + 1) / (draws + 1)
    family = (("state_eta_sq", tail),)
    return observed, tail, holm(family)["state_eta_sq"], bh(family)["state_eta_sq"]


def _eta(values: Vector, labels: Vector) -> float | None:
    grand = float(values.mean())
    sst = float(np.sum((values - grand) ** 2))
    if sst == 0:
        return None
    ssb = 0.0
    for label in set(labels.tolist()):
        block = values[labels == label]
        ssb += len(block) * (float(block.mean()) - grand) ** 2
    return ssb / sst


def _stratum_flags(
    stratum: str,
    pairs: Sequence[tuple[str, str, float]],
) -> tuple[list[PairFlag], bool]:
    if len(pairs) < COMPONENT_MIN:
        return [], False
    gaps = np.asarray([item[2] for item in pairs], dtype=float)
    median, mad = _location_mad(gaps)
    if mad <= 0:
        return [], False
    flags: list[PairFlag] = []
    for left, right, gap in pairs:
        residual = gap - median
        z_value = residual / (MAD_SCALE * mad)
        if z_value > Z_FLAG:
            flags.append(
                PairFlag(
                    left=left,
                    right=right,
                    stratum=stratum,
                    absolute_gap=gap,
                    residual=residual,
                    z=z_value,
                )
            )
    return flags, True


def _normalize_edges(edges: Sequence[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    seen: set[tuple[str, str]] = set()
    ordered: list[tuple[str, str]] = []
    for left, right in edges:
        if left == right:
            raise SpatialNeighborError("edge is a self-loop")
        pair = (left, right) if left < right else (right, left)
        if pair in seen:
            raise SpatialNeighborError("edge is duplicated")
        seen.add(pair)
        ordered.append(pair)
    return tuple(ordered)


def _components(
    nodes: Sequence[str],
    edges: Sequence[tuple[str, str]],
) -> list[list[str]]:
    adjacent: dict[str, set[str]] = {node: set() for node in nodes}
    for left, right in edges:
        if left in adjacent and right in adjacent and left != right:
            adjacent[left].add(right)
            adjacent[right].add(left)
    seen: set[str] = set()
    components: list[list[str]] = []
    for node in nodes:
        if node in seen:
            continue
        stack = [node]
        seen.add(node)
        component: list[str] = []
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in adjacent[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        if any(adjacent[item] for item in component):
            components.append(component)
    return components


def _blocks(labels: Sequence[str]) -> tuple[Vector, ...]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, label in enumerate(labels):
        grouped[label].append(index)
    return tuple(np.asarray(indexes, dtype=int) for indexes in grouped.values())


def _permute_blocks(
    values: Vector,
    blocks: Sequence[Vector],
    rng: np.random.Generator,
) -> Vector:
    shuffled = values.copy()
    for block in blocks:
        if len(block) >= 2:
            shuffled[block] = rng.permutation(shuffled[block])
    return shuffled


def _moran_parts(
    values: Sequence[float] | Vector,
    neighbors: Sequence[Sequence[int]],
) -> tuple[float | None, Vector | None, bool]:
    array = np.asarray(values, dtype=float)
    count = int(array.shape[0])
    if count == 0 or len(neighbors) != count:
        return None, None, False
    centered = array - float(array.mean())
    denominator = float(centered @ centered)
    if denominator == 0:
        return None, None, False
    weighted = np.zeros(count, dtype=float)
    weight_sum = 0.0
    for index, neigh in enumerate(neighbors):
        if not neigh:
            continue
        weight = 1.0 / len(neigh)
        for other in neigh:
            weighted[index] += weight * centered[other]
            weight_sum += weight
    if weight_sum == 0:
        return None, None, False
    statistic = (count / weight_sum) * float(centered @ weighted) / denominator
    local = centered * weighted / (denominator / count)
    if not math.isfinite(statistic):
        return None, None, False
    return statistic, local, True


def _local_i(values: Vector, neighbors: Sequence[Sequence[int]]) -> Vector:
    _statistic, local, ok = _moran_parts(values, neighbors)
    if not ok or local is None:
        return np.zeros(len(values), dtype=float)
    return local


def _spatial_empty(reason: str, *, component_n: int = 0) -> SpatialResult:
    return SpatialResult(
        estimable=False,
        reason=reason,
        component_n=component_n,
        moran_i=None,
        moran_tail=None,
        local_tails=(),
        holm={},
        bh={},
        flagged_fips=(),
    )


def _chart_bins(medians: Sequence[StateMedian]) -> tuple[tuple[str, int], ...]:
    if len(medians) < COMPONENT_MIN:
        return ()
    labels = _edges_labels()
    counts = [0 for _ in labels]
    for item in medians:
        counts[_bin_index(item.median)] += 1
    return tuple((label, count) for label, count in zip(labels, counts, strict=True) if count)


def _edges_labels() -> tuple[str, ...]:
    labels = [f"[{INCIDENCE_EDGES[0]:g}, {INCIDENCE_EDGES[1]:g})"]
    for left, right in zip(INCIDENCE_EDGES, INCIDENCE_EDGES[1:], strict=False):
        if left == INCIDENCE_EDGES[0]:
            continue
        labels.append(f"[{left:g}, {right:g})")
    labels.append(f"[{INCIDENCE_EDGES[-1]:g}, inf)")
    return tuple(labels)


def _bin_index(value: float) -> int:
    if value < INCIDENCE_EDGES[0]:
        return 0
    for index, edge in enumerate(INCIDENCE_EDGES[1:], start=1):
        if value < edge:
            return index - 1
    return len(INCIDENCE_EDGES) - 1


def _incidence(county: County) -> float:
    if county.incidence is None:
        raise SpatialNeighborError("published row is missing a floor")
    return county.incidence


def _location_mad(values: Vector) -> tuple[float, float]:
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return median, mad


def _flag(
    county: County,
    rule: str,
    peer_n: int,
    median: float,
    scale: float,
    z_value: float,
    kind: str,
) -> Flagged:
    return Flagged(
        county=county,
        peer_rule=rule,
        peer_n=peer_n,
        median=median,
        scale=scale,
        z=z_value,
        kind=kind,
    )


def _prior_match(name: str, state: str) -> bool:
    left = " ".join(name.casefold().split())
    for citation, citation_state in PRIOR_INCIDENCE_TAIL:
        if state != citation_state:
            continue
        right = " ".join(citation.casefold().split())
        if left == right or left.startswith(right) or right.startswith(left):
            return True
    return False


def _metric(name: str, count: int, value: float | int | None, unit: str) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        n_underlying=count,
        metric_value=value,
        geography_type="national",
        geography_id="US",
        unit=unit,
    )


def _optional_int(value: object, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise SpatialNeighborError(f"{label} is not an integer")
    if value < 0:
        raise SpatialNeighborError(f"{label} is negative")
    return value


def _optional_float(value: object, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpatialNeighborError(f"{label} is not numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise SpatialNeighborError(f"{label} is not a usable floor")
    return number


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SpatialNeighborError("required text is missing")
    return value.strip()
