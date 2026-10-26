"""County-level distributions for issue 107.

Statistics are computed on the raw values. Histogram bins use fixed edges.
Nothing here opens Snowflake or writes a file.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from lyme_gap_atlas_ml.class_anomaly import MAD_SCALE, PERCENTILE_EDGES, POPULATION_EDGES
from lyme_gap_atlas_ml.coverage_audit import (
    CENSUS_REGIONS,
    PINNED_BUNDLE_SHA256,
    PINNED_RELEASE_ID,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import ColumnProfileRecord, FindingRecord
from lyme_gap_atlas_ml.snowflake.eda_writer import SMALL_CELL_MINIMUM, EdaMetric

Vector = np.ndarray[Any, Any]

SPEC_ID = "107-county-distributions/v1"
SEED = 1072026
REFERENCE_COUNTIES = 3144
REFERENCE_HIGH = 315
REFERENCE_MEDIUM = 628
REFERENCE_LOW = 2201
REFERENCE_SUFFICIENT = 651
REFERENCE_INSUFFICIENT = 2493
TIER_RELEASE_ID = "governed-2026-09-18-unknown-coverage"
TIER_MODEL = "tier1-statistical-reference-v1"
TIER_POLICY = "tier1-review-percentile-v1"
MAD_Z = 3.5
IQR_K = 1.5
QUANTILES = (0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99)
CASE_EDGES = (5, 6, 10, 20, 50, 100, 250, 500, 1000, 2500, 10000)
INCIDENCE_EDGES = (0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 2000)
TEMPERATURE_EDGES = tuple(range(-40, 51, 10))
PRECIP_EDGES = (0, 0.1, 1, 5, 10, 25, 50, 100, 250)
CLIMATE_MEASURES = (
    "nclimgrid_prcp_county_day",
    "nclimgrid_tavg_county_day",
    "nclimgrid_tmax_county_day",
    "nclimgrid_tmin_county_day",
)
CLIMATE_EDGES = {
    "nclimgrid_prcp_county_day": PRECIP_EDGES,
    "nclimgrid_tavg_county_day": TEMPERATURE_EDGES,
    "nclimgrid_tmax_county_day": TEMPERATURE_EDGES,
    "nclimgrid_tmin_county_day": TEMPERATURE_EDGES,
}
ATLAS = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V"
TIER_VIEW = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_TIER1_COUNTY_REVIEW_V"
CLIMATE = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V"
RELEASE = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V"
SOURCES = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_SOURCE_METADATA_V"
OBSERVATIONS = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V"
SOURCE_OBJECTS = (RELEASE, ATLAS, TIER_VIEW, CLIMATE, SOURCES, OBSERVATIONS)
REGION_ORDER = ("Northeast", "Midwest", "South", "West")
HUMAN_PUBLISHED = "published_count_floor"
HUMAN_NONE = "no_county_linked_record"
FLOOR_SIGNALS = frozenset({"case_count_floor_2023", "incidence_floor_2023"})
SIGNAL_EDGES = {
    "case_count_floor_2023": CASE_EDGES,
    "incidence_floor_2023": INCIDENCE_EDGES,
    "population": POPULATION_EDGES,
    "svi_percentile": PERCENTILE_EDGES,
    "uninsured_percentile": PERCENTILE_EDGES,
}
SIGNAL_COLUMNS = {
    "case_count_floor_2023": "CASE_COUNT_FLOOR_2023",
    "incidence_floor_2023": "INCIDENCE_FLOOR_2023",
    "population": "POPULATION",
    "svi_percentile": "SVI_PERCENTILE",
    "uninsured_percentile": "UNINSURED_PERCENTILE",
}


class DistributionError(ValueError):
    """The distribution summary cannot be built."""


@dataclass(frozen=True)
class AtlasCounty:
    fips: str
    county: str
    state: str
    population: float | None
    human_status: str
    case_floor: float | None
    incidence_floor: float | None
    svi_percentile: float | None
    uninsured_percentile: float | None
    rucc: int | None


@dataclass(frozen=True)
class TierCounty:
    fips: str
    tier: str
    percentile: float | None
    score: float | None
    sufficiency: str
    human_evidence_state: str


@dataclass(frozen=True)
class ClimateDay:
    measure_id: str
    fips: str
    value: float


@dataclass(frozen=True)
class Summary:
    n: int
    mean: float | None
    weighted_mean: float | None
    median: float | None
    weighted_median: float | None
    mode: float | None
    modal_bin: str | None
    iqr: float | None
    variance: float | None
    sd: float | None
    weighted_second_moment: float | None
    skewness: float | None
    quantiles: Mapping[str, float]
    weighted_quantiles: Mapping[str, float]
    histogram: tuple[tuple[str, int], ...]
    ecdf: tuple[tuple[str, float], ...]
    minimum: float | None
    maximum: float | None
    iqr_low: int
    iqr_high: int
    mad_low: int
    mad_high: int
    mad_estimable: bool
    peaks: int
    weight_n: int


@dataclass(frozen=True)
class OutlierExample:
    county: str
    state: str
    value: float
    robust_z: float


@dataclass(frozen=True)
class SignalGroup:
    signal: str
    geography_type: str
    geography_id: str
    summary: Summary


@dataclass(frozen=True)
class TierProfile:
    high: int
    medium: int
    low: int
    other_tier: int
    sufficient: int
    insufficient: int
    other_sufficiency: int
    percentile_rescaled: bool
    stored_versus_rule: int
    score_bounds: Mapping[str, tuple[float, float, float]]
    sufficiency_by_tier: Mapping[tuple[str, str], int]
    high_by_region: Mapping[str, int]
    high_by_rucc: Mapping[str, int]
    region_n: Mapping[str, int]
    rucc_n: Mapping[str, int]
    sufficiency_versus_human: int
    human_evidence_levels: tuple[str, ...]


@dataclass(frozen=True)
class Analysis:
    counties: int
    distinct_fips: int
    published: int
    unpublished: int
    svi_rescaled: bool
    uninsured_rescaled: bool
    signals: tuple[SignalGroup, ...]
    climate_days: tuple[SignalGroup, ...]
    climate_county_means: tuple[SignalGroup, ...]
    tier: TierProfile
    nonpublishing_states: int
    counties_in_nonpublishing_states: int
    null_floors_in_nonpublishing_states: int
    null_floors_in_publishing_states: int
    case_floor_at_5: int
    incidence_peaks: int
    incidence_examples: tuple[OutlierExample, ...]
    disposition: str
    nlcd_counties: int
    climate_days_read: int


def linear_quantile(values: Sequence[float] | Vector, probability: float) -> float:
    """Linear quantile at index ``(n - 1) * p``, the ``PERCENTILE_CONT`` definition."""
    array = np.sort(np.asarray(values, dtype=float))
    if array.size == 0:
        raise DistributionError("quantile of an empty series")
    if not 0 <= probability <= 1:
        raise DistributionError("probability is outside 0 to 1")
    if array.size == 1:
        return float(array[0])
    position = (array.size - 1) * probability
    low = int(math.floor(position))
    high = int(math.ceil(position))
    weight = position - low
    return float(array[low] * (1.0 - weight) + array[high] * weight)


def weighted_quantile(
    values: Sequence[float] | Vector,
    weights: Sequence[float] | Vector,
    probability: float,
) -> float:
    """Smallest sorted value whose cumulative weight share reaches ``probability``."""
    array = np.asarray(values, dtype=float)
    weight = np.asarray(weights, dtype=float)
    if array.shape != weight.shape or array.size == 0:
        raise DistributionError("weighted quantile inputs do not align")
    order = np.argsort(array, kind="mergesort")
    sorted_values = array[order]
    cumulative = np.cumsum(weight[order])
    total = float(cumulative[-1])
    if total <= 0:
        raise DistributionError("weights sum to zero")
    index = int(np.searchsorted(cumulative, probability * total, side="left"))
    return float(sorted_values[min(index, sorted_values.size - 1)])


def histogram(
    values: Sequence[float] | Vector,
    edges: Sequence[float],
) -> tuple[tuple[str, int], ...]:
    """Count raw values on fixed half-open edges, with underflow and overflow."""
    if len(edges) < 2 or any(edges[index] >= edges[index + 1] for index in range(len(edges) - 1)):
        raise DistributionError("histogram edges must be strictly increasing")
    array = np.asarray(values, dtype=float)
    under = int(np.sum(array < edges[0]))
    over = int(np.sum(array > edges[-1]))
    inside = array[(array >= edges[0]) & (array <= edges[-1])]
    counts, _bounds = np.histogram(inside, bins=np.asarray(edges, dtype=float))
    bins = [("underflow", under)]
    for index, count in enumerate(counts):
        bins.append((f"[{edges[index]:g}, {edges[index + 1]:g})", int(count)))
    bins.append(("overflow", over))
    if sum(count for _label, count in bins) != int(array.size):
        raise DistributionError("histogram counts do not cover the raw values")
    return tuple(bins)


def sample_skewness(values: Sequence[float] | Vector) -> float | None:
    """Bias-corrected moment skewness. ``None`` when fewer than three values."""
    array = np.asarray(values, dtype=float)
    count = int(array.size)
    if count < 3:
        return None
    centered = array - float(array.mean())
    second = float(np.mean(centered**2))
    third = float(np.mean(centered**3))
    if second == 0:
        return 0.0
    bias = math.sqrt(count * (count - 1)) / (count - 2)
    return float(bias * third / (second**1.5))


def summarize(
    values: Sequence[float],
    weights: Sequence[float] | None,
    edges: Sequence[float],
) -> Summary:
    """Center, spread, histogram, and outlier counts on one raw series."""
    array = np.asarray(values, dtype=float)
    count = int(array.size)
    bins = histogram(array, edges) if count else (("underflow", 0), ("overflow", 0))
    if count == 0:
        return _empty(bins)
    quantiles = {f"p{int(p * 100):02d}": linear_quantile(array, p) for p in QUANTILES}
    median = quantiles["p50"]
    q1 = quantiles["p25"]
    q3 = quantiles["p75"]
    iqr = q3 - q1
    variance = float(np.var(array, ddof=1)) if count >= 2 else None
    deviation = math.sqrt(variance) if variance is not None else None
    mode = _mode(array)
    modal = _modal_bin(bins)
    low_fence = q1 - IQR_K * iqr
    high_fence = q3 + IQR_K * iqr
    mad = float(np.median(np.abs(array - median)))
    mad_ok = mad > 0
    if mad_ok:
        robust = (array - median) / (MAD_SCALE * mad)
        mad_low = int(np.sum(robust < -MAD_Z))
        mad_high = int(np.sum(robust > MAD_Z))
    else:
        mad_low = 0
        mad_high = 0
    weighted = _weighted(array, weights)
    return Summary(
        n=count,
        mean=float(array.mean()),
        weighted_mean=weighted[0],
        median=median,
        weighted_median=weighted[1],
        mode=mode,
        modal_bin=modal,
        iqr=iqr,
        variance=variance,
        sd=deviation,
        weighted_second_moment=weighted[2],
        skewness=sample_skewness(array),
        quantiles=quantiles,
        weighted_quantiles=weighted[3],
        histogram=bins,
        ecdf=_ecdf(array, edges),
        minimum=float(array.min()),
        maximum=float(array.max()),
        iqr_low=int(np.sum(array < low_fence)),
        iqr_high=int(np.sum(array > high_fence)),
        mad_low=mad_low,
        mad_high=mad_high,
        mad_estimable=mad_ok,
        peaks=_peaks(bins),
        weight_n=weighted[4],
    )


def analyze(
    counties: Sequence[AtlasCounty],
    tiers: Sequence[TierCounty],
    climate: Sequence[ClimateDay],
    *,
    nlcd_counties: int,
) -> Analysis:
    """Build the prespecified summaries. County names stay on the result object."""
    if len({county.fips for county in counties}) != len(counties):
        raise DistributionError("duplicate county FIPS")
    svi_scale = _needs_percent_scale(county.svi_percentile for county in counties)
    uninsured_scale = _needs_percent_scale(county.uninsured_percentile for county in counties)
    scaled = tuple(
        _scale_county(county, svi=svi_scale, uninsured=uninsured_scale) for county in counties
    )
    signals = _signal_groups(scaled)
    climate_days, climate_means = _climate_groups(climate, scaled)
    tier = _tier_profile(scaled, tiers)
    publishing = _publishing(scaled)
    incidence = _signal(signals, "incidence_floor_2023", "national", "US")
    return Analysis(
        counties=len(scaled),
        distinct_fips=len({county.fips for county in scaled}),
        published=sum(county.human_status == HUMAN_PUBLISHED for county in scaled),
        unpublished=sum(county.human_status == HUMAN_NONE for county in scaled),
        svi_rescaled=svi_scale,
        uninsured_rescaled=uninsured_scale,
        signals=signals,
        climate_days=climate_days,
        climate_county_means=climate_means,
        tier=tier,
        nonpublishing_states=publishing[0],
        counties_in_nonpublishing_states=publishing[1],
        null_floors_in_nonpublishing_states=publishing[2],
        null_floors_in_publishing_states=publishing[3],
        case_floor_at_5=sum(county.case_floor == 5 for county in scaled),
        incidence_peaks=incidence.summary.peaks if incidence is not None else 0,
        incidence_examples=_incidence_examples(scaled),
        disposition=_disposition(len(scaled), scaled, tier),
        nlcd_counties=nlcd_counties,
        climate_days_read=len(climate),
    )


def lab_metrics(result: Analysis) -> list[EdaMetric]:
    """Aggregate metrics. A 1–10 cell is left for the writer to suppress."""
    rows: list[EdaMetric] = []
    for group in (*result.signals, *result.climate_days, *result.climate_county_means):
        rows.extend(_summary_metrics(group))
    rows.extend(_tier_metrics(result))
    rows.extend(_quality_metrics(result))
    if len(rows) > 5000:
        raise DistributionError("metric list exceeds the lab writer limit")
    return rows


def column_profiles(result: Analysis) -> list[ColumnProfileRecord]:
    """National unweighted profiles for the atlas signals and raw climate measures."""
    profiles: list[ColumnProfileRecord] = []
    for signal, column in SIGNAL_COLUMNS.items():
        group = _signal(result.signals, signal, "national", "US")
        if group is None:
            continue
        null_count = result.counties - group.summary.n if signal in FLOOR_SIGNALS else 0
        row_count = result.counties if signal in FLOOR_SIGNALS else group.summary.n
        profiles.append(_profile(ATLAS, column, group.summary, row_count, null_count))
    for group in result.climate_days:
        if group.geography_type == "national":
            profiles.append(
                _profile(CLIMATE, group.geography_id.upper(), group.summary, group.summary.n, 0)
            )
    return profiles


def findings(result: Analysis) -> list[FindingRecord]:
    """Aggregate statements. County names stay in the write-up, not here."""
    tier = result.tier
    disposition = result.disposition
    floor = _signal(result.signals, "incidence_floor_2023", "national", "US")
    skew = "not estimable"
    if floor is not None and floor.summary.skewness is not None:
        skew = f"{floor.summary.skewness:.2f}"
    median = "not estimable"
    if floor is not None and floor.summary.median is not None:
        median = f"{floor.summary.median:.2f}"
    return [
        FindingRecord(
            topic="county distribution",
            statement=(
                f"Published incidence floors cover {result.published} counties. "
                f"The unweighted median is {median} per 100,000 and the bias-corrected "
                f"skewness is {skew}. {result.case_floor_at_5} published case floors sit on "
                f"the privacy floor of 5. {result.unpublished} counties have no county-linked "
                "human record and are outside that distribution."
            ),
            disposition=disposition,
            n_underlying=result.counties,
            evidence={
                "published": result.published,
                "unpublished": result.unpublished,
                "floor_of_5": result.case_floor_at_5,
                "incidence_peaks": result.incidence_peaks,
            },
        ),
        FindingRecord(
            topic="outlier review",
            statement=(
                "IQR and scaled-MAD flags are review candidates. A floor of 5 is heaping "
                "from the privacy rule. A missing floor in a state that publishes no county "
                "floor is that state's publication rule. Neither flag is a disease finding. "
                f"Non-publishing states: {result.nonpublishing_states}. "
                f"Null floors in those states: {result.null_floors_in_nonpublishing_states}. "
                f"Null floors in states that do publish: {result.null_floors_in_publishing_states}."
            ),
            disposition=disposition,
            n_underlying=result.counties,
            evidence={
                "nonpublishing_states": result.nonpublishing_states,
                "null_nonpublishing": result.null_floors_in_nonpublishing_states,
                "null_publishing": result.null_floors_in_publishing_states,
            },
        ),
        FindingRecord(
            topic="tier boundary",
            statement=(
                f"Stored tiers are HIGH {tier.high}, MEDIUM {tier.medium}, LOW {tier.low}. "
                f"Sufficiency is SUFFICIENT {tier.sufficient} and INSUFFICIENT "
                f"{tier.insufficient}. INSUFFICIENT is not relabeled LOW. "
                f"Recomputed percentile cuts disagree with the stored tier on "
                f"{tier.stored_versus_rule} counties. The tier view remains the September batch."
            ),
            disposition=disposition,
            n_underlying=result.counties,
            evidence={
                "high": tier.high,
                "medium": tier.medium,
                "low": tier.low,
                "sufficient": tier.sufficient,
                "insufficient": tier.insufficient,
                "rule_disagreements": tier.stored_versus_rule,
            },
        ),
    ]


def chart_bins(bins: Sequence[tuple[str, int]]) -> tuple[tuple[str, int | None], ...]:
    """Hide a 1–10 bin count. A zero on a large total stays visible."""
    total = sum(count for _label, count in bins)
    if total < SMALL_CELL_MINIMUM:
        return tuple((label, None) for label, _count in bins)
    return tuple(
        (label, None if 0 < count < SMALL_CELL_MINIMUM else count) for label, count in bins
    )


def box_groups(
    counties: Sequence[AtlasCounty],
) -> tuple[tuple[str, tuple[float, ...]], ...]:
    """Published incidence by RUCC, omitting a code with fewer than 11 values."""
    grouped: dict[int, list[float]] = {}
    for county in counties:
        if county.rucc is None or county.incidence_floor is None:
            continue
        if county.human_status != HUMAN_PUBLISHED:
            continue
        grouped.setdefault(county.rucc, []).append(county.incidence_floor)
    return tuple(
        (str(code), tuple(grouped[code]))
        for code in sorted(grouped)
        if len(grouped[code]) >= SMALL_CELL_MINIMUM
    )


def _disposition(count: int, counties: Sequence[AtlasCounty], tier: TierProfile) -> str:
    fips_ok = count == REFERENCE_COUNTIES and len({county.fips for county in counties}) == count
    if not fips_ok:
        return "stop"
    published = sum(county.human_status == HUMAN_PUBLISHED for county in counties)
    unpublished = sum(county.human_status == HUMAN_NONE for county in counties)
    matched = (
        published == REFERENCE_SUFFICIENT
        and unpublished == REFERENCE_INSUFFICIENT
        and tier.high == REFERENCE_HIGH
        and tier.medium == REFERENCE_MEDIUM
        and tier.low == REFERENCE_LOW
        and tier.sufficient == REFERENCE_SUFFICIENT
        and tier.insufficient == REFERENCE_INSUFFICIENT
        and tier.other_tier == 0
        and tier.other_sufficiency == 0
    )
    return "keep" if matched else "revise"


def _signal_groups(counties: Sequence[AtlasCounty]) -> tuple[SignalGroup, ...]:
    groups: list[SignalGroup] = []
    for signal, edges in SIGNAL_EDGES.items():
        eligible = _eligible(counties, signal)
        for geography_type, geography_id, members in _slices(eligible, signal):
            values, weights = _series(members, signal)
            groups.append(
                SignalGroup(
                    signal=signal,
                    geography_type=geography_type,
                    geography_id=geography_id,
                    summary=summarize(values, weights, edges),
                )
            )
    return tuple(groups)


def _slices(
    counties: Sequence[AtlasCounty],
    signal: str,
) -> tuple[tuple[str, str, tuple[AtlasCounty, ...]], ...]:
    slices: list[tuple[str, str, tuple[AtlasCounty, ...]]] = [("national", "US", tuple(counties))]
    for region in REGION_ORDER:
        members = tuple(
            county
            for county in counties
            if CENSUS_REGIONS.get(county.state, "Unassigned") == region
        )
        slices.append(("census_region", region, members))
    for code in range(1, 10):
        slices.append(
            (
                "rucc",
                str(code),
                tuple(county for county in counties if county.rucc == code),
            )
        )
    if signal not in FLOOR_SIGNALS:
        for status in (HUMAN_PUBLISHED, HUMAN_NONE):
            slices.append(
                (
                    "human_status",
                    status,
                    tuple(county for county in counties if county.human_status == status),
                )
            )
    return tuple(slices)


def _eligible(counties: Sequence[AtlasCounty], signal: str) -> tuple[AtlasCounty, ...]:
    if signal in FLOOR_SIGNALS:
        return tuple(
            county
            for county in counties
            if county.human_status == HUMAN_PUBLISHED and _value(county, signal) is not None
        )
    return tuple(county for county in counties if _value(county, signal) is not None)


def _series(
    counties: Sequence[AtlasCounty],
    signal: str,
) -> tuple[list[float], list[float] | None]:
    values: list[float] = []
    weights: list[float] = []
    weighted = True
    for county in counties:
        value = _value(county, signal)
        if value is None:
            continue
        values.append(value)
        if county.population is None or county.population <= 0:
            weighted = False
        else:
            weights.append(county.population)
    if not weighted or len(weights) != len(values):
        return values, None
    return values, weights


def _value(county: AtlasCounty, signal: str) -> float | None:
    if signal == "case_count_floor_2023":
        return county.case_floor
    if signal == "incidence_floor_2023":
        return county.incidence_floor
    if signal == "population":
        return county.population
    if signal == "svi_percentile":
        return county.svi_percentile
    if signal == "uninsured_percentile":
        return county.uninsured_percentile
    raise DistributionError(f"unknown signal {signal}")


def _climate_groups(
    days: Sequence[ClimateDay],
    counties: Sequence[AtlasCounty],
) -> tuple[tuple[SignalGroup, ...], tuple[SignalGroup, ...]]:
    population = {
        county.fips: county.population
        for county in counties
        if county.population is not None and county.population > 0
    }
    regions = {county.fips: CENSUS_REGIONS.get(county.state, "Unassigned") for county in counties}
    raw: list[SignalGroup] = []
    means: list[SignalGroup] = []
    for measure in CLIMATE_MEASURES:
        measure_days = tuple(day for day in days if day.measure_id == measure)
        if not measure_days:
            continue
        edges = CLIMATE_EDGES[measure]
        raw.append(
            SignalGroup(
                signal=measure,
                geography_type="national",
                geography_id=measure,
                summary=summarize([day.value for day in measure_days], None, edges),
            )
        )
        for region in REGION_ORDER:
            regional = [day.value for day in measure_days if regions.get(day.fips) == region]
            raw.append(
                SignalGroup(
                    signal=measure,
                    geography_type="census_region",
                    geography_id=region,
                    summary=summarize(regional, None, edges),
                )
            )
        by_county: dict[str, list[float]] = {}
        for day in measure_days:
            by_county.setdefault(day.fips, []).append(day.value)
        paired = [
            (float(np.mean(np.asarray(vals, dtype=float))), population.get(fips))
            for fips, vals in by_county.items()
        ]
        county_values = [value for value, _weight in paired]
        if all(weight is not None for _value, weight in paired):
            weights = [float(weight) for _value, weight in paired if weight is not None]
        else:
            weights = None
        means.append(
            SignalGroup(
                signal=f"{measure}_county_mean",
                geography_type="national",
                geography_id=measure,
                summary=summarize(county_values, weights, edges),
            )
        )
    return tuple(raw), tuple(means)


def _tier_profile(counties: Sequence[AtlasCounty], tiers: Sequence[TierCounty]) -> TierProfile:
    percentiles = [row.percentile for row in tiers]
    rescaled = _fraction_scale(percentiles)
    points = [
        None if value is None else value * 100 if rescaled else value for value in percentiles
    ]
    stored_versus_rule = 0
    high = medium = low = other = 0
    sufficient = insufficient = other_sufficiency = 0
    cross: dict[tuple[str, str], int] = {}
    scores: dict[str, list[float]] = {}
    by_fips = {row.fips: row for row in tiers}
    for row, point in zip(tiers, points, strict=True):
        if row.tier == "HIGH":
            high += 1
        elif row.tier == "MEDIUM":
            medium += 1
        elif row.tier == "LOW":
            low += 1
        else:
            other += 1
        if row.sufficiency == "SUFFICIENT":
            sufficient += 1
        elif row.sufficiency == "INSUFFICIENT":
            insufficient += 1
        else:
            other_sufficiency += 1
        cross[(row.sufficiency, row.tier)] = cross.get((row.sufficiency, row.tier), 0) + 1
        if row.score is not None:
            scores.setdefault(row.tier, []).append(row.score)
        if point is not None:
            ruled = "HIGH" if point >= 90 else "MEDIUM" if point >= 70 else "LOW"
            if ruled != row.tier:
                stored_versus_rule += 1
    human = {county.fips: county.human_status for county in counties}
    region_of = {county.fips: CENSUS_REGIONS.get(county.state, "Unassigned") for county in counties}
    rucc_of = {county.fips: county.rucc for county in counties}
    mismatches = 0
    high_region: dict[str, int] = dict.fromkeys(REGION_ORDER, 0)
    high_rucc: dict[str, int] = {str(code): 0 for code in range(1, 10)}
    region_n: dict[str, int] = dict.fromkeys(REGION_ORDER, 0)
    rucc_n: dict[str, int] = {str(code): 0 for code in range(1, 10)}
    for fips, row in by_fips.items():
        status = human.get(fips)
        if status is None:
            mismatches += 1
            continue
        expected = "SUFFICIENT" if status == HUMAN_PUBLISHED else "INSUFFICIENT"
        if row.human_evidence_state != status or (
            row.sufficiency in {"SUFFICIENT", "INSUFFICIENT"} and row.sufficiency != expected
        ):
            mismatches += 1
        region = region_of.get(fips)
        if region in region_n:
            region_n[region] = region_n[region] + 1
            if row.tier == "HIGH":
                high_region[region] = high_region[region] + 1
        code = rucc_of.get(fips)
        if code is not None:
            rucc_n[str(code)] = rucc_n[str(code)] + 1
            if row.tier == "HIGH":
                high_rucc[str(code)] = high_rucc[str(code)] + 1
    bounds = {
        tier: (min(values), linear_quantile(values, 0.5), max(values))
        for tier, values in scores.items()
        if values
    }
    return TierProfile(
        high=high,
        medium=medium,
        low=low,
        other_tier=other,
        sufficient=sufficient,
        insufficient=insufficient,
        other_sufficiency=other_sufficiency,
        percentile_rescaled=rescaled,
        stored_versus_rule=stored_versus_rule,
        score_bounds=bounds,
        sufficiency_by_tier=cross,
        high_by_region=high_region,
        high_by_rucc=high_rucc,
        region_n=region_n,
        rucc_n=rucc_n,
        sufficiency_versus_human=mismatches,
        human_evidence_levels=tuple(sorted({row.human_evidence_state for row in tiers})),
    )


def _publishing(counties: Sequence[AtlasCounty]) -> tuple[int, int, int, int]:
    published_by_state: dict[str, int] = {}
    for county in counties:
        if county.human_status == HUMAN_PUBLISHED:
            published_by_state[county.state] = published_by_state.get(county.state, 0) + 1
    states = {county.state for county in counties}
    quiet = {state for state in states if published_by_state.get(state, 0) == 0}
    in_quiet = 0
    null_quiet = 0
    null_publishing = 0
    for county in counties:
        missing = county.case_floor is None
        if county.state in quiet:
            in_quiet += 1
            if missing:
                null_quiet += 1
        elif missing:
            null_publishing += 1
    return len(quiet), in_quiet, null_quiet, null_publishing


def _incidence_examples(counties: Sequence[AtlasCounty]) -> tuple[OutlierExample, ...]:
    rows = [
        county
        for county in counties
        if county.human_status == HUMAN_PUBLISHED and county.incidence_floor is not None
    ]
    if len(rows) < SMALL_CELL_MINIMUM:
        return ()
    values = np.asarray([county.incidence_floor for county in rows], dtype=float)
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad == 0:
        return ()
    scored = [
        OutlierExample(
            county=county.county,
            state=county.state,
            value=float(county.incidence_floor or 0),
            robust_z=float((float(county.incidence_floor or 0) - median) / (MAD_SCALE * mad)),
        )
        for county in rows
    ]
    ranked = sorted(scored, key=lambda item: item.robust_z, reverse=True)
    return tuple(item for item in ranked if item.robust_z > MAD_Z)[:8]


def _summary_metrics(group: SignalGroup) -> list[EdaMetric]:
    summary = group.summary
    base = {
        "signal": group.signal,
        "weighting": "county" if group.summary.weight_n == 0 else "both",
    }
    rows = [
        _stat(group, "mean", summary.mean, "signal_units", base),
        _stat(group, "median", summary.median, "signal_units", base),
        _stat(group, "iqr", summary.iqr, "signal_units", base),
        _stat(group, "variance", summary.variance, "signal_units_squared", base),
        _stat(group, "sd", summary.sd, "signal_units", base),
        _stat(group, "skewness", summary.skewness, "skewness", base),
    ]
    if summary.mode is not None:
        rows.append(_stat(group, "mode", summary.mode, "signal_units", base))
    if summary.weighted_mean is not None:
        rows.append(
            _stat(
                group,
                "weighted_mean",
                summary.weighted_mean,
                "signal_units",
                {**base, "weighting": "population"},
            )
        )
        rows.append(
            _stat(
                group,
                "weighted_median",
                summary.weighted_median,
                "signal_units",
                {**base, "weighting": "population"},
            )
        )
        rows.append(
            _stat(
                group,
                "weighted_second_moment",
                summary.weighted_second_moment,
                "signal_units_squared",
                {**base, "weighting": "population"},
            )
        )
    for name, value in summary.quantiles.items():
        rows.append(_stat(group, "quantile", value, "signal_units", {**base, "quantile": name}))
    for name, value in summary.weighted_quantiles.items():
        rows.append(
            _stat(
                group,
                "weighted_quantile",
                value,
                "signal_units",
                {**base, "weighting": "population", "quantile": name},
            )
        )
    for label, count in summary.histogram:
        if not _keep_histogram(group):
            continue
        rows.append(_count(group, "histogram_count", count, {**base, "bin": label}))
    if group.geography_type == "national":
        for label, share in summary.ecdf:
            rows.append(_stat(group, "ecdf", share, "share", {**base, "edge": label}))
    rows.extend(
        (
            _count(group, "iqr_low_count", summary.iqr_low, base),
            _count(group, "iqr_high_count", summary.iqr_high, base),
            _count(group, "mad_low_count", summary.mad_low, base),
            _count(group, "mad_high_count", summary.mad_high, base),
            _count(group, "peak_count", summary.peaks, base),
        )
    )
    return [row for row in rows if row is not None]


def _tier_metrics(result: Analysis) -> list[EdaMetric]:
    tier = result.tier
    rows: list[EdaMetric] = []
    for name, count in (
        ("HIGH", tier.high),
        ("MEDIUM", tier.medium),
        ("LOW", tier.low),
    ):
        rows.append(
            EdaMetric(
                metric_name="tier_count",
                n_underlying=count if count else result.counties,
                metric_value=float(count),
                geography_type="tier",
                geography_id=name,
                dimensions={"sufficiency": "all"},
                unit="counties",
            )
        )
    for name, count in (("SUFFICIENT", tier.sufficient), ("INSUFFICIENT", tier.insufficient)):
        rows.append(
            EdaMetric(
                metric_name="sufficiency_count",
                n_underlying=count if count else result.counties,
                metric_value=float(count),
                geography_type="sufficiency",
                geography_id=name,
                unit="counties",
            )
        )
    for (sufficiency, label), count in sorted(tier.sufficiency_by_tier.items()):
        underlying = count if count >= SMALL_CELL_MINIMUM or count == 0 else count
        if count == 0:
            underlying = result.counties
        rows.append(
            EdaMetric(
                metric_name="tier_by_sufficiency",
                n_underlying=underlying,
                metric_value=float(count),
                geography_type="tier",
                geography_id=label,
                dimensions={"sufficiency": sufficiency},
                unit="counties",
            )
        )
    for region, count in tier.high_by_region.items():
        rows.append(
            _share_metric(
                "high_share",
                count,
                tier.region_n.get(region, 0),
                "census_region",
                region,
            )
        )
    for code, count in tier.high_by_rucc.items():
        rows.append(_share_metric("high_share", count, tier.rucc_n.get(code, 0), "rucc", code))
    for label, bounds in tier.score_bounds.items():
        names = ("score_min", "score_median", "score_max")
        for metric_name, value in zip(names, bounds, strict=True):
            rows.append(
                EdaMetric(
                    metric_name=metric_name,
                    n_underlying=result.counties,
                    metric_value=value,
                    geography_type="tier",
                    geography_id=label,
                    unit="score",
                )
            )
    rows.append(
        EdaMetric(
            metric_name="tier_rule_disagreement",
            n_underlying=tier.stored_versus_rule or result.counties,
            metric_value=float(tier.stored_versus_rule),
            geography_type="national",
            geography_id="US",
            unit="counties",
        )
    )
    return rows


def _quality_metrics(result: Analysis) -> list[EdaMetric]:
    pairs = (
        ("nonpublishing_states", result.nonpublishing_states),
        ("counties_in_nonpublishing_states", result.counties_in_nonpublishing_states),
        ("null_floors_in_nonpublishing_states", result.null_floors_in_nonpublishing_states),
        ("null_floors_in_publishing_states", result.null_floors_in_publishing_states),
        ("case_floor_at_5", result.case_floor_at_5),
        ("nlcd_counties", result.nlcd_counties),
        ("sufficiency_human_mismatch", result.tier.sufficiency_versus_human),
    )
    rows: list[EdaMetric] = []
    for name, count in pairs:
        underlying = result.counties if count == 0 or count >= SMALL_CELL_MINIMUM else count
        if name == "nlcd_counties":
            underlying = count if count else result.counties
        rows.append(
            EdaMetric(
                metric_name=name,
                n_underlying=underlying,
                metric_value=float(count),
                geography_type="national",
                geography_id="US",
                unit="counties",
            )
        )
    return rows


def _stat(
    group: SignalGroup,
    name: str,
    value: float | None,
    unit: str,
    dimensions: Mapping[str, object],
) -> EdaMetric | None:
    if value is None:
        return None
    return EdaMetric(
        metric_name=name,
        n_underlying=group.summary.n,
        metric_value=float(value),
        geography_type=group.geography_type,
        geography_id=group.geography_id,
        dimensions=dict(dimensions),
        unit=unit,
    )


def _count(
    group: SignalGroup,
    name: str,
    count: int,
    dimensions: Mapping[str, object],
) -> EdaMetric:
    if group.summary.n < SMALL_CELL_MINIMUM or 0 < count < SMALL_CELL_MINIMUM:
        underlying = count if 0 < count < SMALL_CELL_MINIMUM else group.summary.n
    else:
        underlying = group.summary.n if count == 0 else count
    if group.summary.n < SMALL_CELL_MINIMUM:
        underlying = group.summary.n
    return EdaMetric(
        metric_name=name,
        n_underlying=max(underlying, 0),
        metric_value=float(count),
        geography_type=group.geography_type,
        geography_id=group.geography_id,
        dimensions=dict(dimensions),
        unit="counties",
    )


def _share_metric(
    name: str,
    numerator: int,
    denominator: int,
    geography_type: str,
    geography_id: str,
) -> EdaMetric:
    small = denominator < SMALL_CELL_MINIMUM or 0 < numerator < SMALL_CELL_MINIMUM
    return EdaMetric(
        metric_name=name,
        n_underlying=numerator if small and numerator else denominator,
        metric_value=None if small or denominator == 0 else numerator / denominator,
        geography_type=geography_type,
        geography_id=geography_id,
        unit="share",
    )


def _keep_histogram(group: SignalGroup) -> bool:
    if group.signal in CLIMATE_MEASURES and group.geography_type != "national":
        return False
    return group.geography_type != "rucc" or group.signal == "incidence_floor_2023"


def _profile(
    source: str,
    column: str,
    summary: Summary,
    row_count: int,
    null_count: int,
) -> ColumnProfileRecord:
    percentiles = {
        "p01": summary.quantiles.get("p01"),
        "p05": summary.quantiles.get("p05"),
        "p25": summary.quantiles.get("p25"),
        "p50": summary.quantiles.get("p50"),
        "p75": summary.quantiles.get("p75"),
        "p95": summary.quantiles.get("p95"),
        "p99": summary.quantiles.get("p99"),
    }
    return ColumnProfileRecord(
        source_object=source,
        column_name=column,
        row_count=row_count,
        null_count=null_count,
        data_type="FLOAT",
        distinct_count=None,
        min_value=None if summary.minimum is None else f"{summary.minimum:.6g}",
        max_value=None if summary.maximum is None else f"{summary.maximum:.6g}",
        mean_value=summary.mean,
        stddev_value=summary.sd,
        percentiles=percentiles,
    )


def _fraction_scale(values: Sequence[float | None]) -> bool:
    numeric = [
        float(value)
        for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    return bool(numeric) and max(numeric) <= 1.5


def _empty(bins: tuple[tuple[str, int], ...]) -> Summary:
    return Summary(
        n=0,
        mean=None,
        weighted_mean=None,
        median=None,
        weighted_median=None,
        mode=None,
        modal_bin=None,
        iqr=None,
        variance=None,
        sd=None,
        weighted_second_moment=None,
        skewness=None,
        quantiles={},
        weighted_quantiles={},
        histogram=bins,
        ecdf=(),
        minimum=None,
        maximum=None,
        iqr_low=0,
        iqr_high=0,
        mad_low=0,
        mad_high=0,
        mad_estimable=False,
        peaks=0,
        weight_n=0,
    )


def _weighted(
    array: Vector,
    weights: Sequence[float] | None,
) -> tuple[float | None, float | None, float | None, dict[str, float], int]:
    if weights is None:
        return None, None, None, {}, 0
    weight = np.asarray(weights, dtype=float)
    total = float(weight.sum())
    if total <= 0 or weight.size != array.size:
        return None, None, None, {}, 0
    mean = float(np.sum(weight * array) / total)
    second = float(np.sum(weight * (array - mean) ** 2) / total)
    quantiles = {
        f"p{int(probability * 100):02d}": weighted_quantile(array, weight, probability)
        for probability in QUANTILES
    }
    return mean, quantiles["p50"], second, quantiles, int(array.size)


def _mode(array: Vector) -> float | None:
    _unique, counts = np.unique(array, return_counts=True)
    highest = int(counts.max())
    if highest <= 1 or int(np.sum(counts == highest)) > 1:
        return None
    return float(_unique[int(np.argmax(counts))])


def _modal_bin(bins: Sequence[tuple[str, int]]) -> str | None:
    if not bins or sum(count for _label, count in bins) == 0:
        return None
    return max(bins, key=lambda item: (item[1], -bins.index(item)))[0]


def _peaks(bins: Sequence[tuple[str, int]]) -> int:
    interior = [(label, count) for label, count in bins if label not in {"underflow", "overflow"}]
    if len(interior) < 3:
        return 0
    peaks = 0
    full = list(bins)
    for label, count in interior:
        index = next(position for position, item in enumerate(full) if item[0] == label)
        left = full[index - 1][1]
        right = full[index + 1][1]
        if count > left and count > right and count >= SMALL_CELL_MINIMUM:
            peaks += 1
    return peaks


def _ecdf(array: Vector, edges: Sequence[float]) -> tuple[tuple[str, float], ...]:
    count = int(array.size)
    if count == 0:
        return ()
    return tuple((f"{edge:g}", float(np.sum(array <= edge) / count)) for edge in edges)


def _needs_percent_scale(values: Iterable[float | None]) -> bool:
    numeric = [
        float(value)
        for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    return bool(numeric) and max(numeric) > 1.5


def _scale_county(county: AtlasCounty, *, svi: bool, uninsured: bool) -> AtlasCounty:
    if not svi and not uninsured:
        return county
    return AtlasCounty(
        fips=county.fips,
        county=county.county,
        state=county.state,
        population=county.population,
        human_status=county.human_status,
        case_floor=county.case_floor,
        incidence_floor=county.incidence_floor,
        svi_percentile=None
        if county.svi_percentile is None
        else county.svi_percentile / 100
        if svi
        else county.svi_percentile,
        uninsured_percentile=None
        if county.uninsured_percentile is None
        else county.uninsured_percentile / 100
        if uninsured
        else county.uninsured_percentile,
        rucc=county.rucc,
    )


def _signal(
    groups: Sequence[SignalGroup],
    signal: str,
    geography_type: str,
    geography_id: str,
) -> SignalGroup | None:
    for group in groups:
        if (
            group.signal == signal
            and group.geography_type == geography_type
            and group.geography_id == geography_id
        ):
            return group
    return None


def release_matches(row: Mapping[str, object]) -> bool:
    """Return whether the live release row is the frozen pin."""
    return (
        str(row.get("RELEASE_ID")) == PINNED_RELEASE_ID
        and str(row.get("BUNDLE_SHA256")) == PINNED_BUNDLE_SHA256
        and str(row.get("SCHEMA_VERSION")) == "2.0.0"
        and str(row.get("METHODOLOGY_VERSION")) == "semantic-2.0.0"
        and str(row.get("SCOPE")) == "US_COUNTIES"
    )
