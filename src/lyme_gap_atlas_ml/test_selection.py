"""Issue 116 test selection. County rows stay in memory; nothing here opens Snowflake."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeVar

from lyme_gap_atlas_ml.coverage_audit import (
    CENSUS_REGIONS,
    PINNED_BUNDLE_SHA256,
    PINNED_RELEASE_ID,
    REFERENCE_COUNTIES,
)
from lyme_gap_atlas_ml.evidence_association_65 import analyze_aggregate_counties
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import CorrelationRecord, FindingRecord
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric

SPEC_ID = "116-test-selection/v1.2"
SEED = 1162026
NAIVE_SEED = 1162027
REPRODUCTION_SEED = 6501
REPLICATES = 2000
MIN_CLUSTERS = 10
MATERIAL_SHARE_MOVE = 0.02
SMALL_CELL = 11
HUMAN_PUBLISHED = "published_count_floor"
HUMAN_NONE = "no_county_linked_record"
TICK_KNOWN = ("Established", "Reported", "No records")
PATHOGEN_KNOWN = ("Present", "No records")
TICK_ALLOWED = frozenset((*TICK_KNOWN, "Unknown"))
PATHOGEN_ALLOWED = frozenset((*PATHOGEN_KNOWN, "Unknown"))
HUMAN_KNOWN = frozenset({HUMAN_PUBLISHED, HUMAN_NONE})
REFERENCE_V_TICK_PATHOGEN = "0.5607"
REFERENCE_V_HUMAN_TICK = "0.4780"
REFERENCE_V_HUMAN_PATHOGEN = "0.5705"
REFERENCE_INTERVAL = ("0.4650", "0.6524")
FAMILY = (
    "q1_share_diff",
    "q2_share_diff",
    "h3_spearman_svi",
    "h4_spearman_rucc",
)
QUERY_NAMES = ("release_identity", "cohort_rows")
ATLAS = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V"
RELEASE = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V"
SOURCE_OBJECTS = (RELEASE, ATLAS)
SVI_BINS = (
    (0.0, 0.2, "0.00-0.20"),
    (0.2, 0.4, "0.20-0.40"),
    (0.4, 0.6, "0.40-0.60"),
    (0.6, 0.8, "0.60-0.80"),
    (0.8, 1.0, "0.80-1.00"),
)
SVI_BIN_REFERENCE = {
    "0.00-0.20": (629, 169),
    "0.20-0.40": (629, 187),
    "0.40-0.60": (628, 166),
    "0.60-0.80": (629, 89),
    "0.80-1.00": (628, 40),
}
RUCC_REFERENCE = {
    1: (443, 168),
    2: (385, 103),
    3: (358, 106),
    4: (201, 58),
    5: (76, 8),
    6: (379, 66),
    7: (247, 34),
    8: (466, 70),
    9: (589, 38),
}


class SelectionError(ValueError):
    """The frozen cohort or a frozen gate cannot be applied."""


_RowT = TypeVar("_RowT")


@dataclass(frozen=True)
class MethodDecision:
    method: str
    decision: str
    use: str


METHOD_DECISIONS = (
    MethodDecision("Welch t", "rejected", "Binary floor; counties are not independent"),
    MethodDecision("Paired t", "rejected", "One county row; no paired period"),
    MethodDecision("Mann-Whitney", "rejected", "Ranks restate the share; independence fails"),
    MethodDecision("Wilcoxon signed-rank", "rejected", "No paired county periods"),
    MethodDecision(
        "ANOVA / Welch ANOVA", "rejected", "Rural codes are ordered; code cells are unequal"
    ),
    MethodDecision("Kruskal-Wallis", "rejected", "Nine-code table stays descriptive"),
    MethodDecision("Chi-square", "rejected", "Numerator of V only; counties are not independent"),
    MethodDecision("Fisher exact", "rejected", "National tables are not small; dependence remains"),
    MethodDecision("Spearman", "chosen", "H3 and H4, with a state-cluster interval"),
    MethodDecision("Pearson", "rejected", "Wrong scale; the correlation sweep is issue 114"),
    MethodDecision("Regression", "rejected", "No sampling model for reporting or dependence"),
    MethodDecision(
        "Climate stratum test", "not_estimable", "January daily climate is not an atlas stratum"
    ),
)


@dataclass(frozen=True)
class County:
    fips: str
    county: str
    state: str
    release_id: str
    human: str | None
    tick: str | None
    pathogen: str | None
    rucc: int | None
    svi: float | None
    in_scope: bool


@dataclass(frozen=True)
class IntervalEstimate:
    low: float | None
    high: float | None
    failed: int
    replicates: int
    clusters: int
    kept: int
    estimable: bool
    tail_share: float | None


@dataclass(frozen=True)
class Contrast:
    name: str
    label: str
    estimate: float | None
    n: int
    n_left: int
    n_right: int
    cluster: IntervalEstimate
    naive: IntervalEstimate
    width_ratio: float | None
    holm: float | None

    @property
    def estimable(self) -> bool:
        return self.cluster.estimable and self.estimate is not None

    @property
    def excludes_zero(self) -> bool:
        low = self.cluster.low
        high = self.cluster.high
        return self.estimable and low is not None and high is not None and (high < 0 or low > 0)

    @property
    def dependence_changes_reading(self) -> bool:
        if not (self.cluster.estimable and self.naive.estimable):
            return False
        if self.cluster.low is None or self.cluster.high is None:
            return False
        if self.naive.low is None or self.naive.high is None:
            return False
        naive_excludes = self.naive.high < 0 or self.naive.low > 0
        cluster_includes = self.cluster.low <= 0 <= self.cluster.high
        return naive_excludes and cluster_includes


@dataclass(frozen=True)
class Association:
    v: float
    chi2: float
    n: int
    rows: int
    columns: int
    min_expected: float


@dataclass(frozen=True)
class Reproduced:
    name: str
    association: Association | None
    cluster: IntervalEstimate
    naive: IntervalEstimate
    width_ratio: float | None
    display: str | None
    target: str


@dataclass(frozen=True)
class ShareCell:
    label: str
    n: int
    published: int
    reference_n: int | None
    reference_published: int | None

    @property
    def publishable(self) -> bool:
        return _publishable(self.published, self.n)


@dataclass(frozen=True)
class Sensitivity:
    name: str
    estimate: float | None
    move: float | None
    sign_change: bool
    material: bool


@dataclass(frozen=True)
class SpotCheck:
    rule: str
    county: County | None


@dataclass(frozen=True)
class SelectionResult:
    release_id: str
    svi_rescaled: bool
    svi_max: float | None
    counties: int
    published_n: int
    no_record_n: int
    other_human_n: int
    q1_excluded_rucc: int
    q2_excluded_svi: int
    contrasts: tuple[Contrast, ...]
    q1_v: Reproduced
    reproduced: tuple[Reproduced, ...]
    tick_interval_display: tuple[str, str] | None
    tick_helper_n: int | None
    tick_helper_v: float | None
    collapse_v: float | None
    rucc_cells: tuple[ShareCell, ...]
    svi_cells: tuple[ShareCell, ...]
    svi_exact_one_n: int
    svi_exact_one_published: int
    sensitivities: tuple[Sensitivity, ...]
    spots: tuple[SpotCheck, ...]
    q3: str
    disposition: str
    family_complete: bool
    v_display_match: bool
    interval_display_match: bool
    material_sensitivity: bool

    def contrast(self, name: str) -> Contrast:
        for item in self.contrasts:
            if item.name == name:
                return item
        raise SelectionError("contrast is not in the frozen family")


def prepare_counties(
    rows: Sequence[Mapping[str, object]],
    *,
    release_id: str,
) -> tuple[County, ...]:
    """Validate the in-memory atlas projection. Does not read a warehouse."""
    if len(rows) != REFERENCE_COUNTIES:
        raise SelectionError("county projection must contain 3144 rows")
    seen: set[str] = set()
    prepared: list[County] = []
    for row in rows:
        fips = _text(row.get("FIPS"), "FIPS")
        if len(fips) != 5 or not fips.isdigit() or fips in seen:
            raise SelectionError("invalid or duplicate county FIPS")
        seen.add(fips)
        state = _text(row.get("STATE"), "STATE")
        if state not in CENSUS_REGIONS:
            raise SelectionError("state is outside the Census map")
        row_release = _text(row.get("RELEASE_ID"), "RELEASE_ID")
        if row_release != release_id:
            raise SelectionError("mixed or unexpected release")
        scope = row.get("IN_CONTIGUOUS_TICK_SCOPE")
        if type(scope) is not bool:
            raise SelectionError("scope must be boolean")
        tick = _optional_text(row.get("TICK_STATUS"))
        pathogen = _optional_text(row.get("BURGDORFERI_STATUS"))
        if tick not in TICK_ALLOWED and tick is not None:
            raise SelectionError("unrecognized tick status")
        if pathogen not in PATHOGEN_ALLOWED and pathogen is not None:
            raise SelectionError("unrecognized pathogen status")
        prepared.append(
            County(
                fips=fips,
                county=_optional_text(row.get("COUNTY")) or "",
                state=state,
                release_id=row_release,
                human=_optional_text(row.get("HUMAN_STATUS")),
                tick=tick,
                pathogen=pathogen,
                rucc=_optional_rucc(row.get("RUCC_2023")),
                svi=_optional_float(row.get("SVI_PERCENTILE")),
                in_scope=scope,
            )
        )
    return tuple(prepared)


def analyze(counties: Sequence[County]) -> SelectionResult:
    """Apply the frozen spec. Randomness is the three declared seeds."""
    if len(counties) != REFERENCE_COUNTIES:
        raise SelectionError("county projection must contain 3144 rows")
    release_id = counties[0].release_id
    svi_values = [county.svi for county in counties if county.svi is not None]
    svi_max = max(svi_values) if svi_values else None
    rescaled = svi_max is not None and svi_max > 1.5
    scale = 100.0 if rescaled else 1.0
    scaled = tuple(_scale(county, scale) for county in counties)
    published_n = sum(county.human == HUMAN_PUBLISHED for county in scaled)
    no_record_n = sum(county.human == HUMAN_NONE for county in scaled)
    other_human_n = sum(county.human not in HUMAN_KNOWN for county in scaled)
    q1_rows = tuple(county for county in scaled if _q1(county))
    q2_rows = tuple(county for county in scaled if _q2(county))
    q1 = _share_contrast(
        "q1_share_diff",
        "Metro minus nonmetro published-floor share",
        q1_rows,
        lambda county: county.rucc is not None and county.rucc <= 3,
    )
    q2 = _share_contrast(
        "q2_share_diff",
        "Lower minus higher vulnerability published-floor share",
        q2_rows,
        lambda county: county.svi is not None and county.svi < 0.5,
    )
    h3 = _spearman_contrast(
        "h3_spearman_svi",
        "Spearman, vulnerability percentile and published floor",
        q2_rows,
        lambda county: county.svi if county.svi is not None else 0.0,
    )
    h4 = _spearman_contrast(
        "h4_spearman_rucc",
        "Spearman, rural-urban code and published floor",
        q1_rows,
        lambda county: float(county.rucc) if county.rucc is not None else 0.0,
    )
    family = (q1, q2, h3, h4)
    holm = _holm_family(family)
    contrasts = tuple(_with_holm(item, holm) for item in family)
    q1_v = _binary_v(q1_rows, lambda county: county.rucc is not None and county.rucc <= 3)
    reproduced, helper_n, helper_v, collapse_v, tick_interval = _reproduce(counties)
    sensitivities = _sensitivities(scaled, q1.estimate, q2.estimate)
    rucc_cells = _rucc_cells(q1_rows)
    svi_cells, exact_n, exact_published = _svi_cells(q2_rows)
    family_complete = all(item.estimable for item in contrasts)
    v_match = all(item.display == item.target for item in reproduced)
    interval_match = tick_interval == REFERENCE_INTERVAL
    material = any(item.material for item in sensitivities)
    result = SelectionResult(
        release_id=release_id,
        svi_rescaled=rescaled,
        svi_max=svi_max,
        counties=len(scaled),
        published_n=published_n,
        no_record_n=no_record_n,
        other_human_n=other_human_n,
        q1_excluded_rucc=sum(_known_human(county) and not _known_rucc(county) for county in scaled),
        q2_excluded_svi=sum(_known_human(county) and county.svi is None for county in scaled),
        contrasts=contrasts,
        q1_v=q1_v,
        reproduced=reproduced,
        tick_interval_display=tick_interval,
        tick_helper_n=helper_n,
        tick_helper_v=helper_v,
        collapse_v=collapse_v,
        rucc_cells=rucc_cells,
        svi_cells=svi_cells,
        svi_exact_one_n=exact_n,
        svi_exact_one_published=exact_published,
        sensitivities=sensitivities,
        spots=_spots(counties),
        q3="not_estimable",
        disposition="stop",
        family_complete=family_complete,
        v_display_match=v_match,
        interval_display_match=interval_match,
        material_sensitivity=material,
    )
    disposition = _disposition(result)
    return SelectionResult(
        release_id=result.release_id,
        svi_rescaled=result.svi_rescaled,
        svi_max=result.svi_max,
        counties=result.counties,
        published_n=result.published_n,
        no_record_n=result.no_record_n,
        other_human_n=result.other_human_n,
        q1_excluded_rucc=result.q1_excluded_rucc,
        q2_excluded_svi=result.q2_excluded_svi,
        contrasts=result.contrasts,
        q1_v=result.q1_v,
        reproduced=result.reproduced,
        tick_interval_display=result.tick_interval_display,
        tick_helper_n=result.tick_helper_n,
        tick_helper_v=result.tick_helper_v,
        collapse_v=result.collapse_v,
        rucc_cells=result.rucc_cells,
        svi_cells=result.svi_cells,
        svi_exact_one_n=result.svi_exact_one_n,
        svi_exact_one_published=result.svi_exact_one_published,
        sensitivities=result.sensitivities,
        spots=result.spots,
        q3=result.q3,
        disposition=disposition,
        family_complete=result.family_complete,
        v_display_match=result.v_display_match,
        interval_display_match=result.interval_display_match,
        material_sensitivity=result.material_sensitivity,
    )


def cramers_v(table: Sequence[Sequence[int]]) -> Association | None:
    """Cramér's V after dropping empty margins. Returns none when V is undefined."""
    if not table or not table[0] or any(len(row) != len(table[0]) for row in table):
        raise SelectionError("rectangular nonempty table required")
    if any(type(value) is not int or value < 0 for row in table for value in row):
        raise SelectionError("nonnegative integer counts required")
    active_rows = [index for index, row in enumerate(table) if sum(row)]
    active_cols = [index for index in range(len(table[0])) if sum(row[index] for row in table)]
    if len(active_rows) < 2 or len(active_cols) < 2:
        return None
    observed = [[table[row][col] for col in active_cols] for row in active_rows]
    row_sums = [sum(row) for row in observed]
    col_sums = [sum(row[col] for row in observed) for col in range(len(active_cols))]
    total = sum(row_sums)
    chi2 = 0.0
    min_expected = float(total)
    for row_index, row_sum in enumerate(row_sums):
        for col_index, col_sum in enumerate(col_sums):
            expected = row_sum * col_sum / total
            min_expected = min(min_expected, expected)
            gap = observed[row_index][col_index] - expected
            chi2 += gap * gap / expected
    denominator = total * min(len(row_sums) - 1, len(col_sums) - 1)
    return Association(
        v=math.sqrt(chi2 / denominator),
        chi2=chi2,
        n=total,
        rows=len(row_sums),
        columns=len(col_sums),
        min_expected=min_expected,
    )


def holm(pairs: Sequence[tuple[str, float]]) -> dict[str, float]:
    """Holm step-down. The input order is not the adjustment order."""
    if not pairs:
        return {}
    ordered = sorted(pairs, key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    family = len(ordered)
    for rank, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, (family - rank) * value))
        adjusted[name] = running
    return adjusted


def release_gate(row: Mapping[str, object]) -> None:
    """Stop unless the live pin is the #109 release."""
    if _text(row.get("RELEASE_ID"), "RELEASE_ID") != PINNED_RELEASE_ID:
        raise SelectionError("live release does not match the frozen pin")
    bundle = _text(row.get("BUNDLE_SHA256"), "BUNDLE_SHA256").lower()
    if bundle != PINNED_BUNDLE_SHA256:
        raise SelectionError("live bundle does not match the frozen pin")


def lab_metrics(result: SelectionResult) -> tuple[EdaMetric, ...]:
    """Aggregate metrics. A 1–10 numerator or complement is omitted."""
    rows: list[EdaMetric] = [
        _metric("county_rows", result.counties, result.counties, "count"),
        _metric("published_floor_n", result.published_n, result.counties, "count"),
        _metric("no_county_record_n", result.no_record_n, result.counties, "count"),
    ]
    if result.other_human_n == 0 or result.other_human_n >= SMALL_CELL:
        rows.append(_metric("other_human_n", result.other_human_n, result.counties, "count"))
    for contrast in result.contrasts:
        rows.extend(_contrast_metrics(contrast))
    rows.extend(_reproduced_metrics(result.q1_v))
    for reproduced in result.reproduced:
        rows.extend(_reproduced_metrics(reproduced))
    for cell in (*result.rucc_cells, *result.svi_cells):
        if cell.publishable:
            share = cell.published / cell.n
            rows.append(
                _metric(
                    f"published_share_{_slug(cell.label)}",
                    share,
                    cell.n,
                    "share",
                    {"cell": cell.label},
                )
            )
    for sensitivity in result.sensitivities:
        if sensitivity.estimate is not None:
            rows.append(
                _metric(
                    f"sensitivity_{_slug(sensitivity.name)}",
                    sensitivity.estimate,
                    result.counties,
                    "share",
                    {"sign_change": sensitivity.sign_change, "material": sensitivity.material},
                )
            )
    return tuple(rows)


def lab_correlations(result: SelectionResult) -> tuple[CorrelationRecord, ...]:
    """Association rows. The p-value column stays empty: tail shares are metrics."""
    rows: list[CorrelationRecord] = []
    q1 = result.q1_v
    if q1.association is not None and q1.cluster.estimable:
        rows.append(_correlation("RUCC_METRO", "HUMAN_PUBLISHED_FLOOR", "cramers_v", q1))
    mapping = {
        "h3_spearman_svi": ("SVI_PERCENTILE", "HUMAN_PUBLISHED_FLOOR", "spearman"),
        "h4_spearman_rucc": ("RUCC_2023", "HUMAN_PUBLISHED_FLOOR", "spearman"),
    }
    for contrast in result.contrasts:
        if contrast.name not in mapping or not contrast.estimable or contrast.estimate is None:
            continue
        left, right, method = mapping[contrast.name]
        rows.append(
            CorrelationRecord(
                var_a=left,
                var_b=right,
                method=method,
                n=contrast.n,
                coefficient=contrast.estimate,
                ci_low=contrast.cluster.low,
                ci_high=contrast.cluster.high,
                p_value=None,
            )
        )
    labels = {
        "tick_pathogen": ("TICK_STATUS", "BURGDORFERI_STATUS"),
        "human_tick": ("HUMAN_STATUS", "TICK_STATUS"),
        "human_pathogen": ("HUMAN_STATUS", "BURGDORFERI_STATUS"),
    }
    for item in result.reproduced:
        pair = labels.get(item.name)
        if pair is None or item.association is None or not item.cluster.estimable:
            continue
        rows.append(_correlation(pair[0], pair[1], "cramers_v_state_cluster", item))
    return tuple(rows)


def lab_findings(result: SelectionResult) -> tuple[FindingRecord, ...]:
    """Aggregate statements. County identifiers stay out of this table."""
    q1 = result.contrast("q1_share_diff")
    q2 = result.contrast("q2_share_diff")
    tick = _reproduced_named(result, "tick_pathogen")
    return (
        FindingRecord(
            topic="q1_rural_urban",
            statement=_share_statement("Metro minus nonmetro", q1),
            disposition=result.disposition,
            n_underlying=q1.n if q1.n >= SMALL_CELL else result.counties,
            effect_size=q1.estimate,
            ci_low=q1.cluster.low,
            ci_high=q1.cluster.high,
            uncertainty_note=_width_note(q1),
            evidence={"family": "q1", "excludes_zero": q1.excludes_zero},
        ),
        FindingRecord(
            topic="q2_svi",
            statement=_share_statement("Lower minus higher vulnerability", q2),
            disposition=result.disposition,
            n_underlying=q2.n if q2.n >= SMALL_CELL else result.counties,
            effect_size=q2.estimate,
            ci_low=q2.cluster.low,
            ci_high=q2.cluster.high,
            uncertainty_note=_width_note(q2),
            evidence={"family": "q2", "excludes_zero": q2.excludes_zero},
        ),
        FindingRecord(
            topic="october13_cramers_v",
            statement=_reproduction_statement(result, tick),
            disposition=result.disposition,
            n_underlying=tick.association.n if tick.association is not None else result.counties,
            effect_size=tick.association.v if tick.association is not None else None,
            ci_low=tick.cluster.low,
            ci_high=tick.cluster.high,
            uncertainty_note="State-cluster percentile interval. Not a sampling p-value.",
            evidence={
                "v_display_match": result.v_display_match,
                "interval_display_match": result.interval_display_match,
            },
        ),
        FindingRecord(
            topic="q3_climate",
            statement=(
                "Climate strata versus tick or pathogen documentation are not estimable. "
                "The pinned release has a January daily climate view and no atlas climate stratum. "
                "No test was applied."
            ),
            disposition=result.disposition,
            n_underlying=result.counties,
            uncertainty_note="Predeclared no-go from the issue 109 coverage of this release.",
            evidence={"question": "q3", "status": "not_estimable"},
        ),
    )


def _disposition(result: SelectionResult) -> str:
    shares = (
        result.contrast("q1_share_diff").estimable,
        result.contrast("q2_share_diff").estimable,
    )
    if not any(shares):
        return "stop"
    dependence = any(item.dependence_changes_reading for item in result.contrasts[:2])
    revise = (
        not result.family_complete
        or not result.v_display_match
        or not result.interval_display_match
        or not result.contrast("q1_share_diff").excludes_zero
        or not result.contrast("q2_share_diff").excludes_zero
        or dependence
        or result.material_sensitivity
    )
    return "revise" if revise else "keep"


def _share_contrast(
    name: str,
    label: str,
    rows: Sequence[County],
    left: Callable[[County], bool],
) -> Contrast:
    grouped = _state_binary(rows, left)
    estimate, n_left, n_right = _pooled_share(grouped)
    cluster = _cluster_interval(
        tuple(sorted(grouped)), lambda draw: _draw_share(grouped, draw), SEED
    )
    naive = _naive_interval(rows, lambda draw: _row_share(draw, left), NAIVE_SEED)
    return _contrast(name, label, estimate, len(rows), n_left, n_right, cluster, naive, None)


def _spearman_contrast(
    name: str,
    label: str,
    rows: Sequence[County],
    predictor: Callable[[County], float],
) -> Contrast:
    pairs = {state: _pairs(group, predictor) for state, group in _by_state(rows).items()}
    flat = [pair for group in pairs.values() for pair in group]
    estimate = _spearman(flat)
    cluster = _cluster_interval(
        tuple(sorted(pairs)),
        lambda draw: _spearman([pair for key in draw for pair in pairs[key]]),
        SEED,
    )
    naive = _naive_interval(
        rows,
        lambda draw: _spearman([(predictor(county), _floor(county)) for county in draw]),
        NAIVE_SEED,
    )
    return _contrast(name, label, estimate, len(rows), len(rows), 0, cluster, naive, None)


def _binary_v(rows: Sequence[County], left: Callable[[County], bool]) -> Reproduced:
    table = _binary_table(rows, left)
    association = cramers_v(table)
    grouped = _state_tables(rows, lambda county: (str(int(left(county))), _floor_label(county)))
    cluster = _cluster_interval(
        tuple(sorted(grouped)),
        lambda draw: _v_of(_sum_tables(grouped, draw)),
        SEED,
    )
    naive = _naive_interval(rows, lambda draw: _v_of(_binary_table(draw, left)), NAIVE_SEED)
    return Reproduced(
        name="q1_v",
        association=association,
        cluster=cluster,
        naive=naive,
        width_ratio=_width(cluster, naive),
        display=_display(association.v) if association is not None else None,
        target="companion",
    )


def _reproduce(
    counties: Sequence[County],
) -> tuple[tuple[Reproduced, ...], int | None, float | None, float | None, tuple[str, str] | None]:
    payload = analyze_aggregate_counties(_helper_rows(counties), counties[0].release_id)
    primary = payload["primary"]
    helper_v = primary.get("v")
    helper_n = primary.get("n")
    robustness = payload["primary_state_robustness"]
    interval = robustness.get("interval")
    tick_cluster = _from_helper_interval(interval, int(robustness.get("failed_replicates") or 0))
    display = _interval_display(interval)
    eligible = tuple(county for county in counties if _reproduction_row(county))
    helper_rows = tuple(county for county in counties if _helper_eligible(county))
    tick = _category_v(
        "tick_pathogen",
        helper_rows,
        TICK_KNOWN,
        PATHOGEN_KNOWN,
        lambda county: county.tick or "",
        lambda county: county.pathogen or "",
        REFERENCE_V_TICK_PATHOGEN,
        tick_cluster,
    )
    tick = _prefer_helper(tick, primary, tick_cluster)
    human_tick = _category_v(
        "human_tick",
        eligible,
        (HUMAN_PUBLISHED, HUMAN_NONE),
        TICK_KNOWN,
        lambda county: county.human or "",
        lambda county: county.tick or "",
        REFERENCE_V_HUMAN_TICK,
        None,
    )
    human_pathogen = _category_v(
        "human_pathogen",
        eligible,
        (HUMAN_PUBLISHED, HUMAN_NONE),
        PATHOGEN_KNOWN,
        lambda county: county.human or "",
        lambda county: county.pathogen or "",
        REFERENCE_V_HUMAN_PATHOGEN,
        None,
    )
    sensitivity = payload["sensitivity"]
    collapse = sensitivity.get("v")
    helper_v_float = float(helper_v) if isinstance(helper_v, (int, float)) else None
    helper_n_int = int(helper_n) if isinstance(helper_n, int) else None
    collapse_v = float(collapse) if isinstance(collapse, (int, float)) else None
    return (tick, human_tick, human_pathogen), helper_n_int, helper_v_float, collapse_v, display


def _category_v(
    name: str,
    rows: Sequence[County],
    row_levels: Sequence[str],
    col_levels: Sequence[str],
    row_value: Callable[[County], str],
    col_value: Callable[[County], str],
    target: str,
    supplied_cluster: IntervalEstimate | None,
) -> Reproduced:
    table = _category_table(rows, row_levels, col_levels, row_value, col_value)
    association = cramers_v(table)
    grouped = _prefix_tables(rows, row_levels, col_levels, row_value, col_value)
    cluster = supplied_cluster or _cluster_interval(
        tuple(sorted(grouped)),
        lambda draw: _v_of(_sum_tables(grouped, draw)),
        REPRODUCTION_SEED,
    )
    naive = _naive_interval(
        rows,
        lambda draw: _v_of(_category_table(draw, row_levels, col_levels, row_value, col_value)),
        NAIVE_SEED,
    )
    return Reproduced(
        name=name,
        association=association,
        cluster=cluster,
        naive=naive,
        width_ratio=_width(cluster, naive),
        display=_display(association.v) if association is not None else None,
        target=target,
    )


def _sensitivities(
    counties: Sequence[County],
    q1_estimate: float | None,
    q2_estimate: float | None,
) -> tuple[Sensitivity, ...]:
    rows: list[Sensitivity] = []
    for region in ("Northeast", "Midwest", "South", "West"):
        kept = tuple(county for county in counties if CENSUS_REGIONS[county.state] != region)
        q1_rows = tuple(county for county in kept if _q1(county))
        q2_rows = tuple(county for county in kept if _q2(county))
        q1_value, _, _ = _pooled_share(_state_binary(q1_rows, _metro))
        q2_value, _, _ = _pooled_share(_state_binary(q2_rows, _low_svi))
        rows.append(_sensitivity(f"q1_without_{region}", q1_estimate, q1_value))
        rows.append(_sensitivity(f"q2_without_{region}", q2_estimate, q2_value))
    q1_rows = tuple(county for county in counties if _q1(county))
    q2_rows = tuple(county for county in counties if _q2(county))
    q1_kept = _drop_small_states(q1_rows)
    q2_kept = _drop_small_states(q2_rows)
    q1_value, _, _ = _pooled_share(_state_binary(q1_kept, _metro))
    q2_value, _, _ = _pooled_share(_state_binary(q2_kept, _low_svi))
    rows.append(_sensitivity("q1_states_at_least_15", q1_estimate, q1_value))
    rows.append(_sensitivity("q2_states_at_least_15", q2_estimate, q2_value))
    return tuple(rows)


def _sensitivity(name: str, baseline: float | None, estimate: float | None) -> Sensitivity:
    if baseline is None or estimate is None:
        return Sensitivity(name, estimate, None, False, False)
    move = abs(estimate - baseline)
    sign_change = (baseline > 0 and estimate < 0) or (baseline < 0 and estimate > 0)
    return Sensitivity(
        name, estimate, move, sign_change, move >= MATERIAL_SHARE_MOVE or sign_change
    )


def _spots(counties: Sequence[County]) -> tuple[SpotCheck, ...]:
    return (
        SpotCheck("published_floor_rucc_1", _first(counties, _spot_metro_published)),
        SpotCheck("no_county_record_rucc_9", _first(counties, _spot_rural_none)),
        SpotCheck("null_svi", _first(counties, lambda county: county.svi is None)),
    )


def _first(counties: Sequence[County], rule: Callable[[County], bool]) -> County | None:
    matches = [county for county in counties if rule(county)]
    if not matches:
        return None
    return min(matches, key=lambda county: county.fips)


def state_cluster_interval(
    keys: Sequence[str],
    statistic: Callable[[Sequence[str]], float | None],
    seed: int,
) -> IntervalEstimate:
    """Percentile interval from resampling state keys. This is the #116 procedure."""
    return _cluster_interval(keys, statistic, seed)


def resample_interval(
    rows: Sequence[_RowT],
    statistic: Callable[[Sequence[_RowT]], float | None],
    seed: int,
) -> IntervalEstimate:
    """Resample rows with replacement. #116 uses this only as a dependence diagnostic."""
    if len(rows) < SMALL_CELL:
        return _empty_interval(len(rows))
    rng = random.Random(seed)
    values: list[float] = []
    total = len(rows)
    for _ in range(REPLICATES):
        draw = [rows[rng.randrange(total)] for _ in range(total)]
        value = statistic(draw)
        if value is not None and math.isfinite(value):
            values.append(value)
    return _interval_from_values(values, total)


def spearman_rho(pairs: Sequence[tuple[float, float]]) -> float | None:
    """Average-rank Spearman correlation from the #116 rank procedure."""
    return _spearman(pairs)


def _cluster_interval(
    keys: Sequence[str],
    statistic: Callable[[Sequence[str]], float | None],
    seed: int,
) -> IntervalEstimate:
    if len(keys) < MIN_CLUSTERS:
        return _empty_interval(len(keys))
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(REPLICATES):
        draw = rng.choices(keys, k=len(keys))
        value = statistic(draw)
        if value is not None and math.isfinite(value):
            values.append(value)
    return _interval_from_values(values, len(keys))


def _naive_interval(
    rows: Sequence[County],
    statistic: Callable[[Sequence[County]], float | None],
    seed: int,
) -> IntervalEstimate:
    return resample_interval(rows, statistic, seed)


def _interval_from_values(values: Sequence[float], clusters: int) -> IntervalEstimate:
    failed = REPLICATES - len(values)
    if failed * 100 > REPLICATES * 5 or len(values) < 2:
        return IntervalEstimate(None, None, failed, REPLICATES, clusters, len(values), False, None)
    ordered = sorted(values)
    return IntervalEstimate(
        low=_quantile(ordered, 0.025),
        high=_quantile(ordered, 0.975),
        failed=failed,
        replicates=REPLICATES,
        clusters=clusters,
        kept=len(values),
        estimable=True,
        tail_share=_tail(ordered),
    )


def _empty_interval(clusters: int) -> IntervalEstimate:
    return IntervalEstimate(None, None, REPLICATES, REPLICATES, clusters, 0, False, None)


def _from_helper_interval(interval: object, failed: int) -> IntervalEstimate:
    if (
        isinstance(interval, list)
        and len(interval) == 2
        and all(isinstance(item, (int, float)) for item in interval)
    ):
        low = float(interval[0])
        high = float(interval[1])
        kept = REPLICATES - failed
        return IntervalEstimate(low, high, failed, REPLICATES, 0, kept, True, None)
    return _empty_interval(0)


def _quantile(ordered: Sequence[float], probability: float) -> float:
    index = (len(ordered) - 1) * probability
    low = math.floor(index)
    high = math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def _tail(values: Sequence[float]) -> float:
    total = len(values)
    below = sum(value <= 0 for value in values)
    above = sum(value >= 0 for value in values)
    return min(1.0, 2.0 * min(below, above) / total)


def _holm_family(contrasts: Sequence[Contrast]) -> dict[str, float] | None:
    if not all(item.estimable and item.cluster.tail_share is not None for item in contrasts):
        return None
    pairs = [
        (item.name, item.cluster.tail_share)
        for item in contrasts
        if item.cluster.tail_share is not None
    ]
    return holm(pairs)


def _with_holm(contrast: Contrast, adjusted: dict[str, float] | None) -> Contrast:
    holm_value = None if adjusted is None else adjusted.get(contrast.name)
    return _contrast(
        contrast.name,
        contrast.label,
        contrast.estimate,
        contrast.n,
        contrast.n_left,
        contrast.n_right,
        contrast.cluster,
        contrast.naive,
        holm_value,
    )


def _contrast(
    name: str,
    label: str,
    estimate: float | None,
    n: int,
    n_left: int,
    n_right: int,
    cluster: IntervalEstimate,
    naive: IntervalEstimate,
    holm_value: float | None,
) -> Contrast:
    return Contrast(
        name=name,
        label=label,
        estimate=estimate,
        n=n,
        n_left=n_left,
        n_right=n_right,
        cluster=cluster,
        naive=naive,
        width_ratio=_width(cluster, naive),
        holm=holm_value,
    )


def _state_binary(
    rows: Sequence[County],
    left: Callable[[County], bool],
) -> dict[str, tuple[int, int, int, int]]:
    grouped: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
    for county in rows:
        bucket = grouped[county.state]
        index = 0 if left(county) else 2
        bucket[index + 1] += 1
        if county.human == HUMAN_PUBLISHED:
            bucket[index] += 1
    return {
        state: (counts[0], counts[1], counts[2], counts[3]) for state, counts in grouped.items()
    }


def _pooled_share(
    grouped: Mapping[str, tuple[int, int, int, int]],
) -> tuple[float | None, int, int]:
    left_k = sum(value[0] for value in grouped.values())
    left_n = sum(value[1] for value in grouped.values())
    right_k = sum(value[2] for value in grouped.values())
    right_n = sum(value[3] for value in grouped.values())
    if left_n == 0 or right_n == 0:
        return None, left_n, right_n
    return left_k / left_n - right_k / right_n, left_n, right_n


def _draw_share(
    grouped: Mapping[str, tuple[int, int, int, int]],
    draw: Sequence[str],
) -> float | None:
    estimate, _, _ = _pooled_share({key: grouped[key] for key in draw})
    return estimate


def _row_share(rows: Sequence[County], left: Callable[[County], bool]) -> float | None:
    estimate, _, _ = _pooled_share(_state_binary(rows, left))
    return estimate


def _by_state(rows: Sequence[County]) -> dict[str, tuple[County, ...]]:
    grouped: dict[str, list[County]] = defaultdict(list)
    for county in rows:
        grouped[county.state].append(county)
    return {state: tuple(group) for state, group in grouped.items()}


def _pairs(
    rows: Sequence[County],
    predictor: Callable[[County], float],
) -> tuple[tuple[float, float], ...]:
    return tuple((predictor(county), _floor(county)) for county in rows)


def _spearman(pairs: Sequence[tuple[float, float]]) -> float | None:
    if len(pairs) < 3:
        return None
    left = [pair[0] for pair in pairs]
    right = [pair[1] for pair in pairs]
    if len(set(left)) < 2 or len(set(right)) < 2:
        return None
    return _pearson(_average_ranks(left), _average_ranks(right))


def _average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(values):
        end = start
        while end + 1 < len(values) and values[order[end + 1]] == values[order[start]]:
            end += 1
        rank = (start + 1 + end + 1) / 2
        for index in range(start, end + 1):
            ranks[order[index]] = rank
        start = end + 1
    return ranks


def _pearson(left: Sequence[float], right: Sequence[float]) -> float | None:
    total = len(left)
    mean_left = sum(left) / total
    mean_right = sum(right) / total
    gap_left = [value - mean_left for value in left]
    gap_right = [value - mean_right for value in right]
    square_left = sum(value * value for value in gap_left)
    square_right = sum(value * value for value in gap_right)
    if square_left == 0 or square_right == 0:
        return None
    return sum(a * b for a, b in zip(gap_left, gap_right, strict=True)) / math.sqrt(
        square_left * square_right
    )


def _binary_table(rows: Sequence[County], left: Callable[[County], bool]) -> list[list[int]]:
    table = [[0, 0], [0, 0]]
    for county in rows:
        row = 0 if left(county) else 1
        column = 0 if county.human == HUMAN_PUBLISHED else 1
        table[row][column] += 1
    return table


def _category_table(
    rows: Sequence[County],
    row_levels: Sequence[str],
    col_levels: Sequence[str],
    row_value: Callable[[County], str],
    col_value: Callable[[County], str],
) -> list[list[int]]:
    table = [[0 for _ in col_levels] for _ in row_levels]
    row_index = {level: index for index, level in enumerate(row_levels)}
    col_index = {level: index for index, level in enumerate(col_levels)}
    for county in rows:
        table[row_index[row_value(county)]][col_index[col_value(county)]] += 1
    return table


def _state_tables(
    rows: Sequence[County],
    key: Callable[[County], tuple[str, str]],
) -> dict[str, list[list[int]]]:
    levels_row: list[str] = []
    levels_col: list[str] = []
    for county in rows:
        row_level, col_level = key(county)
        if row_level not in levels_row:
            levels_row.append(row_level)
        if col_level not in levels_col:
            levels_col.append(col_level)
    grouped: dict[str, list[list[int]]] = {}
    for county in rows:
        block = grouped.setdefault(
            county.state,
            [[0 for _ in levels_col] for _ in levels_row],
        )
        row_level, col_level = key(county)
        block[levels_row.index(row_level)][levels_col.index(col_level)] += 1
    return grouped


def _prefix_tables(
    rows: Sequence[County],
    row_levels: Sequence[str],
    col_levels: Sequence[str],
    row_value: Callable[[County], str],
    col_value: Callable[[County], str],
) -> dict[str, list[list[int]]]:
    grouped: dict[str, list[list[int]]] = {}
    row_index = {level: index for index, level in enumerate(row_levels)}
    col_index = {level: index for index, level in enumerate(col_levels)}
    for county in rows:
        block = grouped.setdefault(
            county.fips[:2],
            [[0 for _ in col_levels] for _ in row_levels],
        )
        block[row_index[row_value(county)]][col_index[col_value(county)]] += 1
    return grouped


def _sum_tables(
    grouped: Mapping[str, list[list[int]]],
    draw: Sequence[str],
) -> list[list[int]]:
    base = grouped[draw[0]]
    table = [[0 for _ in row] for row in base]
    for key in draw:
        block = grouped[key]
        for row_index, row in enumerate(block):
            for col_index, value in enumerate(row):
                table[row_index][col_index] += value
    return table


def _v_of(table: Sequence[Sequence[int]]) -> float | None:
    association = cramers_v(table)
    if association is None:
        return None
    return association.v


def _rucc_cells(rows: Sequence[County]) -> tuple[ShareCell, ...]:
    cells: list[ShareCell] = []
    for code in range(1, 10):
        group = [county for county in rows if county.rucc == code]
        published = sum(county.human == HUMAN_PUBLISHED for county in group)
        reference = RUCC_REFERENCE[code]
        cells.append(ShareCell(f"rucc_{code}", len(group), published, reference[0], reference[1]))
    return tuple(cells)


def _svi_cells(rows: Sequence[County]) -> tuple[tuple[ShareCell, ...], int, int]:
    cells: list[ShareCell] = []
    for low, high, label in SVI_BINS:
        group = [county for county in rows if county.svi is not None and low <= county.svi < high]
        published = sum(county.human == HUMAN_PUBLISHED for county in group)
        reference = SVI_BIN_REFERENCE[label]
        cells.append(ShareCell(label, len(group), published, reference[0], reference[1]))
    exact = [county for county in rows if county.svi == 1]
    return (
        tuple(cells),
        len(exact),
        sum(county.human == HUMAN_PUBLISHED for county in exact),
    )


def _drop_small_states(rows: Sequence[County]) -> tuple[County, ...]:
    counts: dict[str, int] = defaultdict(int)
    for county in rows:
        counts[county.state] += 1
    return tuple(county for county in rows if counts[county.state] >= 15)


def _helper_rows(counties: Sequence[County]) -> list[dict[str, object]]:
    return [
        {
            "FIPS": county.fips,
            "RELEASE_ID": county.release_id,
            "IN_CONTIGUOUS_TICK_SCOPE": county.in_scope,
            "VECTOR_STATUS": county.tick,
            "BURGDORFERI_STATUS": county.pathogen,
        }
        for county in counties
    ]


def _scale(county: County, scale: float) -> County:
    svi = None if county.svi is None else county.svi / scale
    return County(
        fips=county.fips,
        county=county.county,
        state=county.state,
        release_id=county.release_id,
        human=county.human,
        tick=county.tick,
        pathogen=county.pathogen,
        rucc=county.rucc,
        svi=svi,
        in_scope=county.in_scope,
    )


def _known_human(county: County) -> bool:
    return county.human in HUMAN_KNOWN


def _known_rucc(county: County) -> bool:
    return county.rucc is not None and 1 <= county.rucc <= 9


def _q1(county: County) -> bool:
    return _known_human(county) and _known_rucc(county)


def _q2(county: County) -> bool:
    return _known_human(county) and county.svi is not None


def _metro(county: County) -> bool:
    return county.rucc is not None and county.rucc <= 3


def _low_svi(county: County) -> bool:
    return county.svi is not None and county.svi < 0.5


def _prefer_helper(
    tick: Reproduced,
    primary: Mapping[str, object],
    cluster: IntervalEstimate,
) -> Reproduced:
    helper_v = primary.get("v")
    helper_n = primary.get("n")
    if not isinstance(helper_v, (int, float)) or isinstance(helper_v, bool):
        return tick
    if not isinstance(helper_n, int) or isinstance(helper_n, bool):
        return tick
    chi2 = primary.get("chi2")
    minimum = tick.association.min_expected if tick.association is not None else 0.0
    association = Association(
        v=float(helper_v),
        chi2=float(chi2) if isinstance(chi2, (int, float)) and not isinstance(chi2, bool) else 0.0,
        n=helper_n,
        rows=3,
        columns=2,
        min_expected=minimum,
    )
    return Reproduced(
        name="tick_pathogen",
        association=association,
        cluster=cluster,
        naive=tick.naive,
        width_ratio=_width(cluster, tick.naive),
        display=_display(float(helper_v)),
        target=REFERENCE_V_TICK_PATHOGEN,
    )


def _helper_eligible(county: County) -> bool:
    return county.in_scope and county.tick in TICK_KNOWN and county.pathogen in PATHOGEN_KNOWN


def _reproduction_row(county: County) -> bool:
    return (
        county.in_scope
        and county.tick in TICK_KNOWN
        and county.pathogen in PATHOGEN_KNOWN
        and county.human in HUMAN_KNOWN
    )


def _floor(county: County) -> float:
    return 1.0 if county.human == HUMAN_PUBLISHED else 0.0


def _floor_label(county: County) -> str:
    return "published" if county.human == HUMAN_PUBLISHED else "no_record"


def _spot_metro_published(county: County) -> bool:
    return county.human == HUMAN_PUBLISHED and county.rucc == 1


def _spot_rural_none(county: County) -> bool:
    return county.human == HUMAN_NONE and county.rucc == 9


def _width(cluster: IntervalEstimate, naive: IntervalEstimate) -> float | None:
    if (
        cluster.low is None
        or cluster.high is None
        or naive.low is None
        or naive.high is None
        or not cluster.estimable
        or not naive.estimable
    ):
        return None
    naive_width = naive.high - naive.low
    if naive_width <= 0:
        return None
    return (cluster.high - cluster.low) / naive_width


def _display(value: float) -> str:
    return f"{value:.4f}"


def _interval_display(interval: object) -> tuple[str, str] | None:
    if (
        isinstance(interval, list)
        and len(interval) == 2
        and all(isinstance(item, (int, float)) for item in interval)
    ):
        return (_display(float(interval[0])), _display(float(interval[1])))
    return None


def _publishable(published: int, total: int) -> bool:
    complement = total - published
    small_piece = 0 < published < SMALL_CELL or 0 < complement < SMALL_CELL
    return total >= SMALL_CELL and not small_piece


def _metric(
    name: str,
    value: float | int,
    n: int,
    unit: str,
    dimensions: Mapping[str, object] | None = None,
) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        metric_value=float(value),
        n_underlying=n,
        geography_type="nation",
        geography_id="US",
        unit=unit,
        dimensions=dimensions,
    )


def _contrast_metrics(contrast: Contrast) -> list[EdaMetric]:
    if contrast.estimate is None or contrast.n < SMALL_CELL:
        return []
    rows = [
        _metric(contrast.name, contrast.estimate, contrast.n, "coefficient"),
    ]
    if contrast.cluster.low is not None and contrast.cluster.high is not None:
        rows.append(
            _metric(f"{contrast.name}_cluster_low", contrast.cluster.low, contrast.n, "coefficient")
        )
        rows.append(
            _metric(
                f"{contrast.name}_cluster_high", contrast.cluster.high, contrast.n, "coefficient"
            )
        )
    if contrast.width_ratio is not None:
        rows.append(
            _metric(f"{contrast.name}_width_ratio", contrast.width_ratio, contrast.n, "ratio")
        )
    if contrast.cluster.tail_share is not None:
        rows.append(
            _metric(f"{contrast.name}_tail_share", contrast.cluster.tail_share, contrast.n, "share")
        )
    if contrast.holm is not None:
        rows.append(_metric(f"{contrast.name}_holm", contrast.holm, contrast.n, "share"))
    return rows


def _reproduced_metrics(item: Reproduced) -> list[EdaMetric]:
    if item.association is None:
        return []
    rows = [_metric(f"{item.name}_v", item.association.v, item.association.n, "coefficient")]
    if item.cluster.low is not None and item.cluster.high is not None:
        rows.append(
            _metric(f"{item.name}_cluster_low", item.cluster.low, item.association.n, "coefficient")
        )
        rows.append(
            _metric(
                f"{item.name}_cluster_high", item.cluster.high, item.association.n, "coefficient"
            )
        )
    if item.width_ratio is not None:
        rows.append(
            _metric(f"{item.name}_width_ratio", item.width_ratio, item.association.n, "ratio")
        )
    return rows


def _correlation(left: str, right: str, method: str, item: Reproduced) -> CorrelationRecord:
    association = item.association
    if association is None:
        raise SelectionError("correlation row requires an association")
    return CorrelationRecord(
        var_a=left,
        var_b=right,
        method=method,
        n=association.n,
        coefficient=association.v,
        ci_low=item.cluster.low,
        ci_high=item.cluster.high,
        p_value=None,
    )


def _share_statement(label: str, contrast: Contrast) -> str:
    if contrast.estimate is None or contrast.cluster.low is None or contrast.cluster.high is None:
        return f"{label} published-floor share difference is not estimable."
    ratio = "not estimable" if contrast.width_ratio is None else f"{contrast.width_ratio:.2f}"
    return (
        f"{label} published-floor share difference is {contrast.estimate:.4f}. "
        f"State-cluster interval {contrast.cluster.low:.4f} to {contrast.cluster.high:.4f}. "
        f"The state-cluster interval is {ratio} times the county-resample interval width. "
        "Counties are not treated as independent."
    )


def _width_note(contrast: Contrast) -> str:
    if contrast.holm is None or contrast.cluster.tail_share is None:
        return "State-cluster percentile interval. Holm was not applied to an incomplete family."
    return (
        "State-cluster percentile interval. "
        f"State-resample tail share {contrast.cluster.tail_share:.4f}. "
        f"Holm-adjusted tail share {contrast.holm:.4f}. Not a sampling p-value."
    )


def _reproduction_statement(result: SelectionResult, tick: Reproduced) -> str:
    shown = ", ".join(
        f"{item.name} {item.display if item.display is not None else 'not estimable'}"
        for item in result.reproduced
    )
    interval = "not estimable"
    if result.tick_interval_display is not None:
        interval = f"{result.tick_interval_display[0]} to {result.tick_interval_display[1]}"
    match = "match" if result.v_display_match and result.interval_display_match else "do not match"
    del tick
    return (
        f"October 13 displays {shown}. Tick by pathogen state-cluster interval {interval}. "
        f"The four-decimal displays {match} the epic targets "
        f"{REFERENCE_V_TICK_PATHOGEN}, {REFERENCE_V_HUMAN_TICK}, {REFERENCE_V_HUMAN_PATHOGEN}, "
        f"and {REFERENCE_INTERVAL[0]} to {REFERENCE_INTERVAL[1]}."
    )


def _reproduced_named(result: SelectionResult, name: str) -> Reproduced:
    for item in result.reproduced:
        if item.name == name:
            return item
    raise SelectionError("reproduction target is missing")


def _slug(value: str) -> str:
    return value.replace(".", "_").replace("-", "_").replace(" ", "_")


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SelectionError(f"{label} is missing")
    return value.strip()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SelectionError("status value is not text")
    stripped = value.strip()
    return stripped or None


def _optional_rucc(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise SelectionError("rural-urban code is not an integer")
    if value < 1 or value > 9:
        raise SelectionError("rural-urban code is outside 1 through 9")
    return value


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SelectionError("vulnerability percentile is not numeric")
    number = float(value)
    if not math.isfinite(number):
        raise SelectionError("vulnerability percentile is not finite")
    return number
