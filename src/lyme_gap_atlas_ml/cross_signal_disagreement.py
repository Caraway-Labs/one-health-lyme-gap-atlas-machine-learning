"""Issue 111 documentation classes. County rows stay in memory.

The numeric residual in the cross-signal disagreement contract is not computed.
These signals are not on one approved comparison scale.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal

from lyme_gap_atlas_ml.coverage_audit import CENSUS_REGIONS, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import FindingRecord
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric
from lyme_gap_atlas_ml.test_selection import (
    HUMAN_NONE,
    HUMAN_PUBLISHED,
    SMALL_CELL,
    IntervalEstimate,
    cramers_v,
    holm,
    release_gate,
    resample_interval,
    spearman_rho,
    state_cluster_interval,
)

SPEC_ID = "111-cross-signal-disagreement/v1"
SEED = 1112026
NAIVE_SEED = 1112027
PINNED_SCHEMA = "2.0.0"
PINNED_METHODOLOGY = "semantic-2.0.0"
PINNED_SCOPE = "US_COUNTIES"
MATERIAL_MOVE = 0.02
SVI_RESCALE_ABOVE = 1.5
CLASS_UNKNOWN = "insufficient_unknown"
CLASS_HUMAN_ONLY = "human_without_vector_documentation"
CLASS_DOUBLE = "double_gap"
CLASS_ESTABLISHED_BLANK = "established_no_pathogen_record"
CLASS_REPORTED_PRESENT = "reported_pathogen_present"
CLASS_REPORTED_BLANK = "reported_no_pathogen_record"
CLASS_PATHOGEN_ONLY = "pathogen_without_tick_record"
CLASS_NONE = "concordant_undocumented"
CLASS_DOCUMENTED = "concordant_documented"
CLASSES = (
    CLASS_UNKNOWN,
    CLASS_HUMAN_ONLY,
    CLASS_DOUBLE,
    CLASS_ESTABLISHED_BLANK,
    CLASS_REPORTED_PRESENT,
    CLASS_REPORTED_BLANK,
    CLASS_PATHOGEN_ONLY,
    CLASS_NONE,
    CLASS_DOCUMENTED,
)
POSITIVE_CLASSES = frozenset(
    {
        CLASS_DOUBLE,
        CLASS_ESTABLISHED_BLANK,
        CLASS_REPORTED_PRESENT,
        CLASS_REPORTED_BLANK,
        CLASS_PATHOGEN_ONLY,
    }
)
CANDIDATE_CLASSES = POSITIVE_CLASSES | {CLASS_HUMAN_ONLY}
ESTABLISHED_GAP_CLASSES = frozenset({CLASS_DOUBLE, CLASS_ESTABLISHED_BLANK})
TICK_ALLOWED = frozenset({"Established", "Reported", "No records", "Unknown"})
PATHOGEN_ALLOWED = frozenset({"Present", "No records", "Unknown"})
HUMAN_ALLOWED = frozenset({HUMAN_PUBLISHED, HUMAN_NONE})
READING_SOURCE = "source_coverage"
READING_ARTIFACT = "reporting_artifact"
READING_WEAKER = "weaker_tick_record"
READING_FOLLOW = "follow_up"
REGIONS = ("Northeast", "Midwest", "South", "West")
REFERENCE_POSITIVE = 1269
REFERENCE_HUMAN_ONLY = 25
REFERENCE_UNKNOWN = 35
REFERENCE_DOUBLE = 228
REFERENCE_ESTABLISHED_GAP = 810
REFERENCE_COUNTIES = 3144
REFERENCE_PUBLISHED = 651
REFERENCE_NO_HUMAN = 2493
ZERO_FLOOR_REFERENCE = frozenset(
    {
        "AK",
        "AR",
        "CO",
        "GA",
        "HI",
        "ID",
        "KS",
        "LA",
        "MO",
        "MS",
        "MT",
        "NE",
        "NM",
        "ND",
        "OK",
        "SD",
        "TX",
        "WA",
        "WY",
    }
)
EXPECTED_VINTAGES = {
    "context_nlcd_2025": "C1V2-2025",
    "context_rucc": "2023",
    "context_svi": "2022 (2018-2022 ACS)",
    "human": "2023",
    "pathogen": "through 2025-12-31",
    "tick": "through 2025-12-31",
}
QUERY_NAMES = ("release_identity", "source_vintages", "cohort_rows")
ATLAS = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V"
RELEASE = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V"
SOURCES = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_SOURCE_METADATA_V"
SOURCE_OBJECTS = (RELEASE, ATLAS, SOURCES)
POPULATION_BINS = (
    (0.0, 10_000.0, "under_10000"),
    (10_000.0, 50_000.0, "10000_to_50000"),
    (50_000.0, 100_000.0, "50000_to_100000"),
    (100_000.0, 500_000.0, "100000_to_500000"),
    (500_000.0, math.inf, "500000_or_more"),
)
SVI_BINS = (
    (0.0, 0.2, "svi_0.00_0.20"),
    (0.2, 0.4, "svi_0.20_0.40"),
    (0.4, 0.6, "svi_0.40_0.60"),
    (0.6, 0.8, "svi_0.60_0.80"),
    (0.8, 1.0, "svi_0.80_1.00"),
)


class CrossSignalError(ValueError):
    """The frozen cohort or a frozen gate cannot be applied."""


@dataclass(frozen=True)
class County:
    fips: str
    county: str
    state: str
    release_id: str
    population: float | None
    svi: float | None
    rucc: int | None
    human: str
    tick: str
    pathogen: str
    in_scope: bool


@dataclass(frozen=True)
class Candidate:
    fips: str
    county: str
    state: str
    region: str
    documentation_class: str
    human: str
    tick: str
    pathogen: str
    supporting: str
    contradicting: str
    zero_floor_state: bool
    partial_reporting_state: bool
    pathogen_unobserved: bool
    tick_reported_not_established: bool
    no_vector_record: bool
    vintage_mismatch: bool
    review_reading: str
    rucc: int | None
    svi: float | None
    population: float | None
    in_scope: bool


@dataclass(frozen=True)
class ReferenceCheck:
    name: str
    observed: int
    expected: int

    @property
    def matched(self) -> bool:
        return self.observed == self.expected


@dataclass(frozen=True)
class ContrastEstimate:
    name: str
    label: str
    estimate: float | None
    n: int
    cluster: IntervalEstimate
    naive: IntervalEstimate
    holm: float | None
    width_ratio: float | None
    sensitivity: float | None
    move: float | None
    material: bool


@dataclass(frozen=True)
class StratumCell:
    geography_type: str
    geography_id: str
    count: int
    denominator: int


@dataclass(frozen=True)
class Analysis:
    counties: int
    release_id: str
    svi_rescaled: bool
    svi_max: float | None
    counts: dict[str, int]
    by_state: dict[tuple[str, str], int]
    by_region: dict[tuple[str, str], int]
    state_denominator: dict[str, int]
    region_denominator: dict[str, int]
    zero_floor_states: frozenset[str]
    zero_floor_matches: bool
    candidates: tuple[Candidate, ...]
    examples: dict[str, tuple[Candidate, ...]]
    references: tuple[ReferenceCheck, ...]
    references_match: bool
    follow_up_n: int
    artifact_double_gap_n: int
    disposition: str
    contrasts: tuple[ContrastEstimate, ...]
    holm_applied: bool
    cramers_v_metro: float | None
    strata: tuple[StratumCell, ...]
    exclusions: dict[str, int]
    population_sum: dict[str, float]
    count_intervals: dict[tuple[str, str, str], IntervalEstimate]
    share_intervals: dict[tuple[str, str, str], IntervalEstimate]
    sensitivity_material: bool

    @property
    def positive_n(self) -> int:
        return sum(self.counts[name] for name in POSITIVE_CLASSES)

    @property
    def established_gap_n(self) -> int:
        return sum(self.counts[name] for name in ESTABLISHED_GAP_CLASSES)


def prepare_counties(
    rows: Sequence[Mapping[str, object]],
    *,
    release_id: str,
) -> tuple[County, ...]:
    """Validate atlas rows. Duplicate FIPS, bad status, and unmapped states stop."""
    counties: list[County] = []
    seen: set[str] = set()
    for row in rows:
        county = _county(row, release_id)
        if county.fips in seen:
            raise CrossSignalError("duplicate FIPS")
        seen.add(county.fips)
        counties.append(county)
    return tuple(counties)


def require_live_cohort(
    counties: Sequence[County],
    release: Mapping[str, object],
    vintages: Mapping[str, str],
) -> None:
    """Stop unless the pin, the vintage strings, and the 3,144-county gate hold."""
    release_gate(release)
    if _text(release.get("SCHEMA_VERSION"), "SCHEMA_VERSION") != PINNED_SCHEMA:
        raise CrossSignalError("live schema does not match the frozen pin")
    if _text(release.get("METHODOLOGY_VERSION"), "METHODOLOGY_VERSION") != PINNED_METHODOLOGY:
        raise CrossSignalError("live methodology does not match the frozen pin")
    if _text(release.get("SCOPE"), "SCOPE") != PINNED_SCOPE:
        raise CrossSignalError("live scope does not match the frozen pin")
    if dict(vintages) != EXPECTED_VINTAGES:
        raise CrossSignalError("source vintages do not match the frozen pin")
    if len(counties) != REFERENCE_COUNTIES:
        raise CrossSignalError("county count is not 3144")
    if len({county.fips for county in counties}) != REFERENCE_COUNTIES:
        raise CrossSignalError("FIPS are not unique")
    releases = {county.release_id for county in counties}
    if releases != {PINNED_RELEASE_ID}:
        raise CrossSignalError("atlas release is not constant")


def analyze(counties: Sequence[County]) -> Analysis:
    """Classify every county, then attach the prespecified intervals."""
    if not counties:
        raise CrossSignalError("cohort is empty")
    scaled, rescaled = _scale_svi(counties)
    classes = [_assign(county) for county in scaled]
    if any(name not in CLASSES for name in classes):
        raise CrossSignalError("unmapped documentation class")
    counts = {name: classes.count(name) for name in CLASSES}
    zero_floor = _zero_floor_states(scaled)
    candidates = tuple(
        sorted(
            (
                _candidate(county, name, zero_floor)
                for county, name in zip(scaled, classes, strict=True)
                if name in CANDIDATE_CLASSES
            ),
            key=lambda item: item.fips,
        )
    )
    by_state, by_region, state_n, region_n = _geographies(scaled, classes)
    published = sum(county.human == HUMAN_PUBLISHED for county in scaled)
    references = _references(len(scaled), published, counts, zero_floor)
    references_match = all(item.matched for item in references) and zero_floor == (
        ZERO_FLOOR_REFERENCE
    )
    follow_up = sum(1 for item in candidates if _follow_up(item))
    artifact = sum(
        1
        for item in candidates
        if item.documentation_class == CLASS_DOUBLE and item.review_reading == READING_ARTIFACT
    )
    contrasts, holm_applied, cramers, strata, exclusions = _associations(
        scaled, classes, zero_floor
    )
    intervals = _class_intervals(scaled, classes)
    population_sum = {
        name: sum(
            county.population or 0.0
            for county, label in zip(scaled, classes, strict=True)
            if label == name and county.population is not None
        )
        for name in CLASSES
    }
    svi_values = [county.svi for county in scaled if county.svi is not None]
    return Analysis(
        counties=len(scaled),
        release_id=scaled[0].release_id,
        svi_rescaled=rescaled,
        svi_max=None if not svi_values else max(svi_values),
        counts=counts,
        by_state=by_state,
        by_region=by_region,
        state_denominator=state_n,
        region_denominator=region_n,
        zero_floor_states=zero_floor,
        zero_floor_matches=zero_floor == ZERO_FLOOR_REFERENCE,
        candidates=candidates,
        examples={
            "reporting_artifact": _examples(candidates, CLASS_DOUBLE, READING_ARTIFACT),
            "source_coverage": _examples(candidates, CLASS_HUMAN_ONLY, None),
            "follow_up": _examples(candidates, CLASS_DOUBLE, READING_FOLLOW),
        },
        references=references,
        references_match=references_match,
        follow_up_n=follow_up,
        artifact_double_gap_n=artifact,
        disposition=product_disposition(references_match, follow_up),
        contrasts=contrasts,
        holm_applied=holm_applied,
        cramers_v_metro=cramers,
        strata=strata,
        exclusions=exclusions,
        population_sum=population_sum,
        count_intervals=intervals[0],
        share_intervals=intervals[1],
        sensitivity_material=any(item.material for item in contrasts),
    )


def product_disposition(references_match: bool, follow_up_n: int) -> str:
    """Apply the frozen word. Advance is not a result of this rule."""
    if follow_up_n < SMALL_CELL:
        return "stop"
    if not references_match:
        return "revise"
    return "investigate"


def lab_finding_disposition(disposition: str) -> str:
    """Map the product word onto the lab finding vocabulary."""
    if disposition == "investigate":
        return "follow-up"
    if disposition in {"revise", "stop"}:
        return disposition
    raise CrossSignalError("disposition is not investigate, revise, or stop")


def display_count(count: int) -> str:
    """Label a chart cell. A 1-10 count is not drawn as its value."""
    if 0 < count < SMALL_CELL:
        return "<11"
    return str(count)


def matrix_cells(result: Analysis) -> tuple[tuple[str, str, str], ...]:
    """Census region by class. The third item is the chart label."""
    cells: list[tuple[str, str, str]] = []
    for region in REGIONS:
        for name in CLASSES:
            cells.append((region, name, display_count(result.by_region.get((region, name), 0))))
    return tuple(cells)


def state_review_bars(result: Analysis) -> tuple[tuple[str, str, float | None], ...]:
    """Alphabetical state counts of classes 3-7. Suppressed bars have no height."""
    bars: list[tuple[str, str, float | None]] = []
    for state in sorted(result.state_denominator):
        count = sum(result.by_state.get((state, name), 0) for name in POSITIVE_CLASSES)
        label = display_count(count)
        height = None if label == "<11" else float(count)
        bars.append((state, label, height))
    return tuple(bars)


def lab_metrics(result: Analysis) -> tuple[EdaMetric, ...]:
    """Aggregate metrics. A 1-10 count is passed through so the writer can suppress it."""
    metrics: list[EdaMetric] = []
    for name in CLASSES:
        _append_count(metrics, result, "national", "US", name, result.counts[name], result.counties)
    for region in REGIONS:
        for name in CLASSES:
            _append_count(
                metrics,
                result,
                "census_region",
                region,
                name,
                result.by_region.get((region, name), 0),
                result.region_denominator.get(region, 0),
            )
    for state, denominator in sorted(result.state_denominator.items()):
        for name in CLASSES:
            _append_count(
                metrics,
                result,
                "state",
                state,
                name,
                result.by_state.get((state, name), 0),
                denominator,
            )
    for cell in result.strata:
        _append_count(
            metrics,
            result,
            cell.geography_type,
            cell.geography_id,
            "positive_cdc_no_human",
            cell.count,
            cell.denominator,
        )
    for contrast in result.contrasts:
        metrics.extend(_contrast_metrics(contrast))
    if result.cramers_v_metro is not None:
        metrics.append(
            _metric(
                "cramers_v_metro",
                result.contrasts[0].n,
                result.cramers_v_metro,
                "association",
                "h1_metro",
                {"companion": "cramers_v"},
                "coefficient",
            )
        )
    follow_denominator = result.counts[CLASS_DOUBLE]
    if result.follow_up_n == 0 and follow_denominator >= SMALL_CELL:
        metrics.append(
            _metric(
                "follow_up_double_gap",
                follow_denominator,
                0.0,
                "national",
                "US",
                {"reading": READING_FOLLOW, "zero_count": True},
                "counties",
            )
        )
    else:
        metrics.append(
            _metric(
                "follow_up_double_gap",
                result.follow_up_n,
                float(result.follow_up_n),
                "national",
                "US",
                {"reading": READING_FOLLOW},
                "counties",
            )
        )
    for name, count in sorted(result.exclusions.items()):
        metrics.append(
            _metric(
                "exclusion_count",
                count if count else result.counties,
                float(count),
                "national",
                "US",
                {"exclusion": name, "zero_count": count == 0},
                "counties",
            )
        )
    return tuple(metrics)


def lab_findings(result: Analysis) -> tuple[FindingRecord, ...]:
    """Aggregate findings. County names stay out of these statements."""
    disposition = lab_finding_disposition(result.disposition)
    matched = "match" if result.references_match else "differ from"
    return (
        FindingRecord(
            topic="reference reproduction",
            statement=(
                f"October 13 reference counts {matched} this release. "
                "Positive CDC documentation without a county-linked human record is "
                f"{_count_text(result.positive_n)}. The double gap is "
                f"{_count_text(result.counts[CLASS_DOUBLE])}. "
                f"The established-tick gap is {_count_text(result.established_gap_n)}. "
                "No records and Unknown are not negatives, and a missing human floor is not zero."
            ),
            disposition=disposition,
            n_underlying=result.counties,
            evidence=_large_counts(
                {
                    "positive_cdc_no_human": result.positive_n,
                    "double_gap": result.counts[CLASS_DOUBLE],
                    "established_tick_gap": result.established_gap_n,
                },
                references_match=result.references_match,
            ),
            effect_size=None if result.positive_n < SMALL_CELL else float(result.positive_n),
            uncertainty_note="Reference checks are exact integers, not intervals.",
        ),
        FindingRecord(
            topic="reporting split",
            statement=(
                "Double-gap counties in a state that publishes no county floor: "
                f"{_count_text(result.artifact_double_gap_n)}. "
                "Double-gap counties in a state that publishes a floor, the follow-up reading: "
                f"{_count_text(result.follow_up_n)}. "
                "The numeric contract residual was not computed."
            ),
            disposition=disposition,
            n_underlying=result.counts[CLASS_DOUBLE],
            evidence=_large_counts(
                {
                    "reporting_artifact": result.artifact_double_gap_n,
                    "follow_up": result.follow_up_n,
                },
                zero_floor_matches=result.zero_floor_matches,
            ),
            effect_size=None
            if result.counts[CLASS_DOUBLE] < SMALL_CELL
            else result.follow_up_n / result.counts[CLASS_DOUBLE],
            uncertainty_note="State publication is the reporting split, not a risk model.",
        ),
        FindingRecord(
            topic="publishing-state associations",
            statement=_association_statement(result),
            disposition=disposition,
            n_underlying=result.contrasts[0].n,
            evidence={"holm_applied": result.holm_applied},
            effect_size=result.contrasts[0].estimate,
            ci_low=result.contrasts[0].cluster.low,
            ci_high=result.contrasts[0].cluster.high,
            uncertainty_note="State-cluster percentile interval. Counties are not independent.",
        ),
    )


def _associations(
    counties: Sequence[County],
    classes: Sequence[str],
    zero_floor: frozenset[str],
) -> tuple[
    tuple[ContrastEstimate, ...],
    bool,
    float | None,
    tuple[StratumCell, ...],
    dict[str, int],
]:
    labeled = list(zip(counties, classes, strict=True))
    publishing = [item for item in labeled if item[0].state not in zero_floor]
    everyone = list(labeled)
    rucc_rows = [item for item in publishing if _known_rucc(item[0])]
    svi_rows = [item for item in publishing if item[0].svi is not None]
    pop_rows = [item for item in publishing if _positive_population(item[0])]
    builders = (
        ("h1_metro_share_diff", "Metro minus nonmetro share", rucc_rows, _metro_diff),
        ("h2_svi_share_diff", "Lower minus higher vulnerability share", svi_rows, _svi_diff),
        ("h3_spearman_rucc", "Spearman, rural-urban code", rucc_rows, _rucc_rho),
        ("h4_spearman_log_population", "Spearman, log10 population", pop_rows, _population_rho),
    )
    drafts: list[ContrastEstimate] = []
    for name, label, rows, statistic in builders:
        sensitivity_rows = _sensitivity_rows(name, everyone)
        estimate = statistic(rows)
        cluster = _cluster_statistic(rows, statistic)
        naive = resample_interval(rows, statistic, NAIVE_SEED)
        material, move = _material(estimate, statistic(sensitivity_rows))
        drafts.append(
            ContrastEstimate(
                name=name,
                label=label,
                estimate=estimate,
                n=len(rows),
                cluster=cluster,
                naive=naive,
                holm=None,
                width_ratio=_width(cluster, naive),
                sensitivity=statistic(sensitivity_rows),
                move=move,
                material=material,
            )
        )
    adjusted = _apply_holm(drafts)
    return (
        adjusted,
        all(item.holm is not None for item in adjusted),
        _metro_v(rucc_rows),
        _strata(labeled),
        {
            "null_rucc": sum(not _known_rucc(county) for county in counties),
            "null_svi": sum(county.svi is None for county in counties),
            "nonpositive_population": sum(not _positive_population(county) for county in counties),
        },
    )


def _sensitivity_keeps(name: str, item: tuple[County, str]) -> bool:
    county = item[0]
    if name in {"h1_metro_share_diff", "h3_spearman_rucc"}:
        return _known_rucc(county)
    if name == "h2_svi_share_diff":
        return county.svi is not None
    return _positive_population(county)


def _sensitivity_rows(
    name: str,
    labeled: list[tuple[County, str]],
) -> list[tuple[County, str]]:
    return [item for item in labeled if _sensitivity_keeps(name, item)]


def _cluster_statistic(
    rows: Sequence[tuple[County, str]],
    statistic: Callable[[Sequence[tuple[County, str]]], float | None],
) -> IntervalEstimate:
    grouped: dict[str, list[tuple[County, str]]] = defaultdict(list)
    for item in rows:
        grouped[item[0].state].append(item)
    keys = tuple(sorted(grouped))

    def draw(states: Sequence[str]) -> float | None:
        pooled: list[tuple[County, str]] = []
        for state in states:
            pooled.extend(grouped[state])
        return statistic(pooled)

    return state_cluster_interval(keys, draw, SEED)


def _apply_holm(drafts: Sequence[ContrastEstimate]) -> tuple[ContrastEstimate, ...]:
    if not all(item.cluster.estimable and item.cluster.tail_share is not None for item in drafts):
        return tuple(drafts)
    adjusted = holm(
        [
            (item.name, item.cluster.tail_share)
            for item in drafts
            if item.cluster.tail_share is not None
        ]
    )
    return tuple(replace(item, holm=adjusted[item.name]) for item in drafts)


def _metro_diff(rows: Sequence[tuple[County, str]]) -> float | None:
    return _share_diff(rows, lambda county: county.rucc is not None and county.rucc <= 3)


def _svi_diff(rows: Sequence[tuple[County, str]]) -> float | None:
    return _share_diff(rows, lambda county: county.svi is not None and county.svi < 0.5)


def _share_diff(
    rows: Sequence[tuple[County, str]],
    left: Callable[[County], bool],
) -> float | None:
    left_rows = [item for item in rows if left(item[0])]
    right_rows = [item for item in rows if not left(item[0])]
    if not left_rows or not right_rows:
        return None
    return _rate(left_rows) - _rate(right_rows)


def _rate(rows: Sequence[tuple[County, str]]) -> float:
    return sum(label in POSITIVE_CLASSES for _, label in rows) / len(rows)


def _rucc_rho(rows: Sequence[tuple[County, str]]) -> float | None:
    pairs = tuple(
        (float(county.rucc), 1.0 if label in POSITIVE_CLASSES else 0.0)
        for county, label in rows
        if county.rucc is not None
    )
    return spearman_rho(pairs)


def _population_rho(rows: Sequence[tuple[County, str]]) -> float | None:
    pairs = tuple(
        (math.log10(county.population), 1.0 if label in POSITIVE_CLASSES else 0.0)
        for county, label in rows
        if county.population is not None and county.population > 0
    )
    return spearman_rho(pairs)


def _metro_v(rows: Sequence[tuple[County, str]]) -> float | None:
    table = [[0, 0], [0, 0]]
    for county, label in rows:
        if county.rucc is None:
            continue
        row = 0 if label in POSITIVE_CLASSES else 1
        column = 0 if county.rucc <= 3 else 1
        table[row][column] += 1
    association = cramers_v(table)
    if association is None:
        return None
    return association.v


def _strata(labeled: Sequence[tuple[County, str]]) -> tuple[StratumCell, ...]:
    cells: list[StratumCell] = []
    for code in range(1, 10):
        rows = [item for item in labeled if item[0].rucc == code]
        cells.append(_cell("rucc", f"rucc_{code}", rows))
    for lower, upper, label in SVI_BINS:
        rows = [
            item for item in labeled if item[0].svi is not None and lower <= item[0].svi < upper
        ]
        cells.append(_cell("svi_bin", label, rows))
    exact = [item for item in labeled if item[0].svi == 1.0]
    cells.append(_cell("svi_bin", "svi_exactly_1", exact))
    for lower, upper, label in POPULATION_BINS:
        rows = [
            item
            for item in labeled
            if item[0].population is not None and lower <= item[0].population < upper
        ]
        cells.append(_cell("population_bin", label, rows))
    return tuple(cells)


def _cell(
    geography_type: str,
    geography_id: str,
    rows: Sequence[tuple[County, str]],
) -> StratumCell:
    return StratumCell(
        geography_type=geography_type,
        geography_id=geography_id,
        count=sum(label in POSITIVE_CLASSES for _, label in rows),
        denominator=len(rows),
    )


def _class_intervals(
    counties: Sequence[County],
    classes: Sequence[str],
) -> tuple[
    dict[tuple[str, str, str], IntervalEstimate],
    dict[tuple[str, str, str], IntervalEstimate],
]:
    labeled = list(zip(counties, classes, strict=True))
    by_state: dict[str, list[tuple[County, str]]] = defaultdict(list)
    for item in labeled:
        by_state[item[0].state].append(item)
    count_intervals: dict[tuple[str, str, str], IntervalEstimate] = {}
    share_intervals: dict[tuple[str, str, str], IntervalEstimate] = {}
    blocks: list[tuple[str, str, tuple[str, ...]]] = [("national", "US", tuple(sorted(by_state)))]
    for region in REGIONS:
        keys = tuple(state for state in sorted(by_state) if CENSUS_REGIONS[state] == region)
        blocks.append(("census_region", region, keys))
    for name in CLASSES:
        for geography_type, geography_id, keys in blocks:
            count_intervals[(geography_type, geography_id, name)] = state_cluster_interval(
                keys,
                _count_statistic(by_state, name),
                SEED,
            )
            share_intervals[(geography_type, geography_id, name)] = state_cluster_interval(
                keys,
                _share_statistic(by_state, name),
                SEED,
            )
    return count_intervals, share_intervals


def _count_statistic(
    grouped: Mapping[str, Sequence[tuple[County, str]]],
    class_name: str,
) -> Callable[[Sequence[str]], float]:
    def statistic(draw: Sequence[str]) -> float:
        return float(sum(label == class_name for state in draw for _, label in grouped[state]))

    return statistic


def _share_statistic(
    grouped: Mapping[str, Sequence[tuple[County, str]]],
    class_name: str,
) -> Callable[[Sequence[str]], float | None]:
    def statistic(draw: Sequence[str]) -> float | None:
        return _draw_share(draw, grouped, class_name)

    return statistic


def _draw_share(
    draw: Sequence[str],
    grouped: Mapping[str, Sequence[tuple[County, str]]],
    class_name: str,
) -> float | None:
    total = sum(len(grouped[state]) for state in draw)
    if total == 0:
        return None
    count = sum(label == class_name for state in draw for _, label in grouped[state])
    return count / total


def _append_count(
    metrics: list[EdaMetric],
    result: Analysis,
    geography_type: str,
    geography_id: str,
    class_name: str,
    count: int,
    denominator: int,
) -> None:
    dimensions: dict[str, object] = {"documentation_class": class_name}
    if count == 0 and denominator >= SMALL_CELL:
        metrics.append(
            _metric(
                "class_count",
                denominator,
                0.0,
                geography_type,
                geography_id,
                {**dimensions, "zero_count": True},
                "counties",
            )
        )
    else:
        metrics.append(
            _metric(
                "class_count",
                count,
                float(count),
                geography_type,
                geography_id,
                dimensions,
                "counties",
            )
        )
    if _share_publishable(count, denominator):
        metrics.append(
            _metric(
                "class_share",
                denominator,
                count / denominator,
                geography_type,
                geography_id,
                dimensions,
                "share",
            )
        )
    if geography_type == "state":
        return
    key = (geography_type, geography_id, class_name)
    count_interval = result.count_intervals.get(key)
    share_interval = result.share_intervals.get(key)
    if count >= SMALL_CELL and count_interval is not None and count_interval.estimable:
        metrics.append(
            _bound(
                "class_count_low",
                count,
                count_interval.low,
                geography_type,
                geography_id,
                dimensions,
            )
        )
        metrics.append(
            _bound(
                "class_count_high",
                count,
                count_interval.high,
                geography_type,
                geography_id,
                dimensions,
            )
        )
    share_ready = _share_publishable(count, denominator) and share_interval is not None
    if share_ready and share_interval is not None and share_interval.estimable:
        metrics.append(
            _bound(
                "class_share_low",
                denominator,
                share_interval.low,
                geography_type,
                geography_id,
                dimensions,
            )
        )
        metrics.append(
            _bound(
                "class_share_high",
                denominator,
                share_interval.high,
                geography_type,
                geography_id,
                dimensions,
            )
        )


def _contrast_metrics(contrast: ContrastEstimate) -> list[EdaMetric]:
    dimensions: dict[str, object] = {"contrast": contrast.name}
    rows = [
        _metric(
            "association_estimate",
            contrast.n,
            contrast.estimate,
            "association",
            contrast.name,
            dimensions,
            "coefficient",
        )
    ]
    if contrast.cluster.estimable:
        rows.append(
            _bound(
                "association_low",
                contrast.n,
                contrast.cluster.low,
                "association",
                contrast.name,
                dimensions,
            )
        )
        rows.append(
            _bound(
                "association_high",
                contrast.n,
                contrast.cluster.high,
                "association",
                contrast.name,
                dimensions,
            )
        )
    if contrast.holm is not None:
        rows.append(
            _metric(
                "association_holm",
                contrast.n,
                contrast.holm,
                "association",
                contrast.name,
                dimensions,
                "tail_share",
            )
        )
    return rows


def _metric(
    name: str,
    n_underlying: int,
    value: float | None,
    geography_type: str,
    geography_id: str,
    dimensions: dict[str, object],
    unit: str,
) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        n_underlying=n_underlying,
        metric_value=value,
        geography_type=geography_type,
        geography_id=geography_id,
        dimensions=dimensions,
        unit=unit,
    )


def _bound(
    name: str,
    n_underlying: int,
    value: float | None,
    geography_type: str,
    geography_id: str,
    dimensions: dict[str, object],
) -> EdaMetric:
    return _metric(name, n_underlying, value, geography_type, geography_id, dimensions, "bound")


def _share_publishable(count: int, denominator: int) -> bool:
    if denominator < SMALL_CELL:
        return False
    complement = denominator - count
    return (count == 0 or count >= SMALL_CELL) and (complement == 0 or complement >= SMALL_CELL)


def _references(
    total: int,
    published: int,
    counts: Mapping[str, int],
    zero_floor: frozenset[str],
) -> tuple[ReferenceCheck, ...]:
    no_human = total - published
    return (
        ReferenceCheck("counties", total, REFERENCE_COUNTIES),
        ReferenceCheck("published_floor", published, REFERENCE_PUBLISHED),
        ReferenceCheck("no_county_linked_record", no_human, REFERENCE_NO_HUMAN),
        ReferenceCheck(
            "positive_cdc_no_human",
            sum(counts[name] for name in POSITIVE_CLASSES),
            REFERENCE_POSITIVE,
        ),
        ReferenceCheck("human_without_vector", counts[CLASS_HUMAN_ONLY], REFERENCE_HUMAN_ONLY),
        ReferenceCheck("unknown_or_out_of_scope", counts[CLASS_UNKNOWN], REFERENCE_UNKNOWN),
        ReferenceCheck("double_gap", counts[CLASS_DOUBLE], REFERENCE_DOUBLE),
        ReferenceCheck(
            "established_tick_gap",
            sum(counts[name] for name in ESTABLISHED_GAP_CLASSES),
            REFERENCE_ESTABLISHED_GAP,
        ),
        ReferenceCheck("zero_floor_states", len(zero_floor), len(ZERO_FLOOR_REFERENCE)),
    )


def _geographies(
    counties: Sequence[County],
    classes: Sequence[str],
) -> tuple[dict[tuple[str, str], int], dict[tuple[str, str], int], dict[str, int], dict[str, int]]:
    by_state: dict[tuple[str, str], int] = defaultdict(int)
    by_region: dict[tuple[str, str], int] = defaultdict(int)
    state_n: dict[str, int] = defaultdict(int)
    region_n: dict[str, int] = defaultdict(int)
    for county, name in zip(counties, classes, strict=True):
        by_state[(county.state, name)] += 1
        by_region[(CENSUS_REGIONS[county.state], name)] += 1
        state_n[county.state] += 1
        region_n[CENSUS_REGIONS[county.state]] += 1
    return dict(by_state), dict(by_region), dict(state_n), dict(region_n)


def _examples(
    candidates: Sequence[Candidate],
    documentation_class: str,
    reading: str | None,
) -> tuple[Candidate, ...]:
    matched = [
        item
        for item in candidates
        if item.documentation_class == documentation_class
        and (reading is None or item.review_reading == reading)
    ]
    return tuple(sorted(matched, key=lambda item: item.fips)[:3])


def _candidate(county: County, documentation_class: str, zero_floor: frozenset[str]) -> Candidate:
    zero = county.state in zero_floor
    pathogen_blank = county.pathogen == "No records"
    no_vector = county.tick == "No records" and pathogen_blank
    reported = county.tick == "Reported"
    return Candidate(
        fips=county.fips,
        county=county.county,
        state=county.state,
        region=CENSUS_REGIONS[county.state],
        documentation_class=documentation_class,
        human=county.human,
        tick=county.tick,
        pathogen=county.pathogen,
        supporting=_tokens(
            human_published_floor=county.human == HUMAN_PUBLISHED,
            tick_established=county.tick == "Established",
            tick_reported=reported,
            pathogen_present=county.pathogen == "Present",
        ),
        contradicting=_tokens(
            human_no_county_linked_record=county.human == HUMAN_NONE,
            tick_no_records=county.tick == "No records",
            pathogen_no_records=pathogen_blank,
        ),
        zero_floor_state=zero,
        partial_reporting_state=not zero and county.human == HUMAN_NONE,
        pathogen_unobserved=pathogen_blank,
        tick_reported_not_established=reported,
        no_vector_record=no_vector,
        vintage_mismatch=True,
        review_reading=_reading(documentation_class, county, zero),
        rucc=county.rucc,
        svi=county.svi,
        population=county.population,
        in_scope=county.in_scope,
    )


def _reading(documentation_class: str, county: County, zero_floor: bool) -> str:
    source = documentation_class in {CLASS_HUMAN_ONLY, CLASS_PATHOGEN_ONLY}
    if source or county.pathogen == "No records":
        return READING_SOURCE
    if zero_floor:
        return READING_ARTIFACT
    if county.tick == "Reported":
        return READING_WEAKER
    return READING_FOLLOW


def _follow_up(candidate: Candidate) -> bool:
    return (
        candidate.documentation_class == CLASS_DOUBLE and candidate.review_reading == READING_FOLLOW
    )


def _tokens(**flags: bool) -> str:
    return ",".join(name for name, present in flags.items() if present)


def _assign(county: County) -> str:
    if county.tick == "Unknown" or county.pathogen == "Unknown" or not county.in_scope:
        return CLASS_UNKNOWN
    blank_tick = county.tick == "No records"
    blank_pathogen = county.pathogen == "No records"
    no_human = county.human == HUMAN_NONE
    if county.human == HUMAN_PUBLISHED and blank_tick and blank_pathogen:
        return CLASS_HUMAN_ONLY
    if no_human and county.tick == "Established" and county.pathogen == "Present":
        return CLASS_DOUBLE
    if no_human and county.tick == "Established" and blank_pathogen:
        return CLASS_ESTABLISHED_BLANK
    if no_human and county.tick == "Reported" and county.pathogen == "Present":
        return CLASS_REPORTED_PRESENT
    if no_human and county.tick == "Reported" and blank_pathogen:
        return CLASS_REPORTED_BLANK
    if no_human and blank_tick and county.pathogen == "Present":
        return CLASS_PATHOGEN_ONLY
    if no_human and blank_tick and blank_pathogen:
        return CLASS_NONE
    if county.human == HUMAN_PUBLISHED:
        return CLASS_DOCUMENTED
    raise CrossSignalError("unmapped documentation class")


def _zero_floor_states(counties: Sequence[County]) -> frozenset[str]:
    published = {county.state for county in counties if county.human == HUMAN_PUBLISHED}
    return frozenset(county.state for county in counties if county.state not in published)


def _scale_svi(counties: Sequence[County]) -> tuple[tuple[County, ...], bool]:
    values = [county.svi for county in counties if county.svi is not None]
    if not values or max(values) <= SVI_RESCALE_ABOVE:
        return tuple(counties), False
    scaled = tuple(
        replace(county, svi=None if county.svi is None else county.svi / 100) for county in counties
    )
    return scaled, True


def _county(row: Mapping[str, object], release_id: str) -> County:
    fips = _text(row.get("FIPS"), "FIPS")
    if len(fips) != 5 or not fips.isdigit():
        raise CrossSignalError("FIPS is not five digits")
    state = _text(row.get("STATE"), "STATE")
    if state not in CENSUS_REGIONS:
        raise CrossSignalError("state is outside the Census map")
    human = _text(row.get("HUMAN_STATUS"), "HUMAN_STATUS")
    tick = _text(row.get("TICK_STATUS"), "TICK_STATUS")
    pathogen = _text(row.get("BURGDORFERI_STATUS"), "BURGDORFERI_STATUS")
    if human not in HUMAN_ALLOWED or tick not in TICK_ALLOWED or pathogen not in PATHOGEN_ALLOWED:
        raise CrossSignalError("status is outside the published levels")
    row_release = _text(row.get("RELEASE_ID"), "RELEASE_ID")
    if row_release != release_id:
        raise CrossSignalError("atlas release is not constant")
    return County(
        fips=fips,
        county=_text(row.get("COUNTY"), "COUNTY"),
        state=state,
        release_id=row_release,
        population=_optional_float(row.get("POPULATION")),
        svi=_optional_float(row.get("SVI_PERCENTILE")),
        rucc=_optional_rucc(row.get("RUCC_2023")),
        human=human,
        tick=tick,
        pathogen=pathogen,
        in_scope=_bool(row.get("IN_CONTIGUOUS_TICK_SCOPE")),
    )


def _association_statement(result: Analysis) -> str:
    first = result.contrasts[0]
    estimate = "not estimable" if first.estimate is None else f"{first.estimate:.4f}"
    low = "not estimable" if first.cluster.low is None else f"{first.cluster.low:.4f}"
    high = "not estimable" if first.cluster.high is None else f"{first.cluster.high:.4f}"
    holm = "applied" if result.holm_applied else "not applied"
    material = "material" if result.sensitivity_material else "not material"
    return (
        "On states that publish a county floor, the metro minus nonmetro share difference "
        f"is {estimate}. Its state-cluster interval is {low} to {high}. "
        f"Holm was {holm}. The all-state sensitivity is {material}. "
        "These associations describe documentation. They are not risk or causation."
    )


def _count_text(count: int) -> str:
    if 0 < count < SMALL_CELL:
        return "below 11"
    return str(count)


def _large_counts(counts: Mapping[str, int], **flags: bool) -> dict[str, object]:
    evidence: dict[str, object] = {
        key: value for key, value in counts.items() if value == 0 or value >= SMALL_CELL
    }
    evidence.update(flags)
    return evidence


def _material(baseline: float | None, sensitivity: float | None) -> tuple[bool, float | None]:
    if baseline is None or sensitivity is None:
        return False, None
    move = abs(sensitivity - baseline)
    opposite = (baseline > 0 > sensitivity) or (baseline < 0 < sensitivity)
    return move >= MATERIAL_MOVE or opposite, move


def _width(cluster: IntervalEstimate, naive: IntervalEstimate) -> float | None:
    if not (cluster.estimable and naive.estimable):
        return None
    if None in {cluster.low, cluster.high, naive.low, naive.high}:
        return None
    assert cluster.low is not None and cluster.high is not None
    assert naive.low is not None and naive.high is not None
    naive_width = naive.high - naive.low
    if naive_width == 0:
        return None
    return (cluster.high - cluster.low) / naive_width


def _known_rucc(county: County) -> bool:
    return county.rucc is not None and 1 <= county.rucc <= 9


def _positive_population(county: County) -> bool:
    return county.population is not None and county.population > 0


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CrossSignalError(f"{label} is missing")
    return value.strip()


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise CrossSignalError("numeric field is not usable")
    number = float(value)
    if not math.isfinite(number):
        raise CrossSignalError("numeric field is not finite")
    return number


def _optional_rucc(value: object) -> int | None:
    if value is None:
        return None
    number = _optional_float(value)
    if number is None or not number.is_integer() or number < 1 or number > 9:
        raise CrossSignalError("rural-urban code is not 1 through 9")
    return int(number)


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise CrossSignalError("scope flag is not usable")
