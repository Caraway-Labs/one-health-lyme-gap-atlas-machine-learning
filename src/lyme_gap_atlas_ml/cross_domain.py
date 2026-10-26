"""Cross-domain associations and a PCA baseline for issue 114.

The functions here do not open Snowflake. County rows stay in memory. Aggregate
lab records suppress a count from 1 to 10. The results write-up may name counties.
Spearman, Cramér's V, Holm, and the state-cluster interval are the #116 helpers.
Kruskal epsilon-squared is the #63 omnibus.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

import numpy as np

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.coverage_audit import (
    CENSUS_REGIONS,
    PINNED_BUNDLE_SHA256,
    PINNED_RELEASE_ID,
    REFERENCE_COUNTIES,
)
from lyme_gap_atlas_ml.eda63 import omnibus
from lyme_gap_atlas_ml.eda63 import quantile as rank_quantile  # noqa: I001
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import CorrelationRecord, FindingRecord
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric
from lyme_gap_atlas_ml.test_selection import (
    HUMAN_NONE,
    HUMAN_PUBLISHED,
    PATHOGEN_ALLOWED,
    PATHOGEN_KNOWN,
    REPLICATES,
    TICK_ALLOWED,
    TICK_KNOWN,
    Association,
    IntervalEstimate,
    cramers_v,
    holm,
    resample_interval,
    state_cluster_interval,
)

SPEC_ID = "114-cross-domain/v1"
SCHEMA_VERSION = "2.0.0"
METHODOLOGY_VERSION = "semantic-2.0.0"
SCOPE = "US_COUNTIES"
SEED = 1142026
NAIVE_SEED = 1142027
OCT13_TWO_COMPONENT = 0.885
SHARE_BAND = 0.005
REGION_SHARE_MOVE = 0.02
SIGNED_MOVE = 0.05
UNSIGNED_MOVE = 0.05
BH_FLAG = 0.05
REDUNDANCY_RHO = 0.80
VIF_DROP = 5.0
VECTOR_V_COLLAPSE = 0.80
LOADING_DROP = 0.20
LOADING_KEEP = 0.30
VARIANCE_TARGET = 0.80
MIN_PCA_N = 500
MIN_STATES = 15
QUERY_NAMES = ("release_identity", "cohort_rows")
CONTEXT_FEATURES = ("log_population", "svi_percentile", "uninsured_percentile")
CROSS_FEATURES = (
    *CONTEXT_FEATURES,
    "rucc_2023",
    "human_published",
    "tick_established",
    "tick_reported",
    "pathogen_present",
)
PREFERENCE = (
    "log_population",
    "svi_percentile",
    "rucc_2023",
    "uninsured_percentile",
)
SIGN_ANCHORS = ("log_population", "svi_percentile", "uninsured_percentile")
EXPERIMENT_METRICS = ("explained_variance_share", "loading", "condition_number", "vif")
HEATMAP_FEATURES = CROSS_FEATURES
CLIMATE_FIELDS = (
    ("nclimgrid_tavg_county_day", "not_estimable", "usable native-double days were 0 to 1"),
    ("nclimgrid_prcp_county_day", "not_estimable", "usable native-double days were 0 to 6"),
    (
        "nclimgrid_tmax_county_day",
        "not_estimable",
        "repeats average temperature and was not in the 20-day cohort",
    ),
    (
        "nclimgrid_tmin_county_day",
        "not_estimable",
        "repeats average temperature and was not in the 20-day cohort",
    ),
)
REPRODUCTION_REFERENCES = {
    "tick_pathogen": ("0.5607", 0.4650, 0.6524),
    "human_tick": ("0.4780", 0.3785, 0.5810),
    "human_pathogen": ("0.5705", 0.4354, 0.7130),
    "svi_human": ("-0.1971", -0.3067, -0.0721),
    "rucc_human": ("-0.2455", -0.3266, -0.1661),
}
Vector = np.ndarray[Any, Any]


class CrossDomainError(ValueError):
    """The frozen cohort or pin is not usable."""


@dataclass(frozen=True)
class County:
    fips: str
    name: str
    state: str
    population: float | None
    svi: float | None
    uninsured: float | None
    rucc: int | None
    human: str
    tick: str
    pathogen: str
    in_scope: bool


@dataclass(frozen=True)
class Spot:
    label: str
    fips: str
    name: str
    state: str
    human: str
    tick: str
    pathogen: str


@dataclass(frozen=True)
class PairSpec:
    pair_id: str
    label: str
    var_a: str
    var_b: str
    method: str
    signed: bool


@dataclass(frozen=True)
class PairResult:
    spec: PairSpec
    estimate: float | None
    n: int
    cluster: IntervalEstimate | None
    naive: IntervalEstimate | None
    width_ratio: float | None
    partial: float | None
    partial_low: float | None
    partial_high: float | None
    partial_n: int
    region_material: bool
    bh: float | None
    holm_adjusted: float | None
    qualified: bool
    confounder: bool
    redundancy: bool
    rank_tier: int


@dataclass(frozen=True)
class ReproductionResult:
    name: str
    estimate: float | None
    corrected: float | None
    n: int
    display: str | None
    matches_reference: bool
    cited_low: float | None
    cited_high: float | None
    partial: float | None


@dataclass(frozen=True)
class Loading:
    feature: str
    component: int
    value: float
    low: float | None
    high: float | None


@dataclass(frozen=True)
class PcaFit:
    name: str
    n: int
    features: tuple[str, ...]
    shares: tuple[float, ...]
    two_component: float | None
    condition_number: float | None
    vifs: dict[str, float | None]
    loadings: tuple[Loading, ...]
    region_shares: dict[str, float | None]
    region_material: bool
    estimable: bool


@dataclass(frozen=True)
class ExperimentMetric:
    split_name: str
    metric_name: str
    metric_value: float | None
    ci_low: float | None
    ci_high: float | None
    n: int | None


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_id: str
    model_family: str
    hypothesis: str
    config: dict[str, object]
    split_definition: dict[str, object]
    status: str
    metrics: tuple[ExperimentMetric, ...]


@dataclass(frozen=True)
class Analysis:
    release_id: str
    counties: int
    published_n: int
    no_record_n: int
    svi_rescaled: bool
    uninsured_rescaled: bool
    context_n: int
    cross_n: int
    pairs: tuple[PairResult, ...]
    reproduction: tuple[ReproductionResult, ...]
    context_pca: PcaFit
    cross_pca: PcaFit
    small_state_share: float | None
    scope_share: float | None
    small_state_material: bool
    scope_material: bool
    representation: str
    follow_up: str
    recommendations: tuple[str, ...]
    spots: tuple[Spot, ...]
    heatmap_labels: tuple[str, ...]
    heatmap: tuple[tuple[float | None, ...], ...]
    family_complete: bool

    def pair(self, pair_id: str) -> PairResult:
        for item in self.pairs:
            if item.spec.pair_id == pair_id:
                return item
        raise CrossDomainError(f"unknown pair {pair_id}")


DISCOVERY: tuple[PairSpec, ...] = (
    PairSpec(
        "D1",
        "SVI x uninsured percentile",
        "svi_percentile",
        "uninsured_percentile",
        "spearman",
        True,
    ),
    PairSpec("D2", "SVI x log population", "svi_percentile", "log_population", "spearman", True),
    PairSpec(
        "D3",
        "uninsured percentile x log population",
        "uninsured_percentile",
        "log_population",
        "spearman",
        True,
    ),
    PairSpec("D4", "SVI x RUCC", "svi_percentile", "rucc_2023", "spearman", True),
    PairSpec(
        "D5", "uninsured percentile x RUCC", "uninsured_percentile", "rucc_2023", "spearman", True
    ),
    PairSpec("D6", "log population x RUCC", "log_population", "rucc_2023", "spearman", True),
    PairSpec(
        "D7",
        "uninsured percentile x human published",
        "uninsured_percentile",
        "human_published",
        "spearman",
        True,
    ),
    PairSpec(
        "D8",
        "log population x human published",
        "log_population",
        "human_published",
        "spearman",
        True,
    ),
    PairSpec(
        "D9", "SVI x pathogen present", "svi_percentile", "pathogen_present", "spearman", True
    ),
    PairSpec(
        "D10",
        "uninsured percentile x pathogen present",
        "uninsured_percentile",
        "pathogen_present",
        "spearman",
        True,
    ),
    PairSpec(
        "D11",
        "log population x pathogen present",
        "log_population",
        "pathogen_present",
        "spearman",
        True,
    ),
    PairSpec("D12", "RUCC x pathogen present", "rucc_2023", "pathogen_present", "spearman", True),
    PairSpec(
        "D13", "SVI by tick status", "svi_percentile", "tick_status", "kruskal_epsilon", False
    ),
    PairSpec(
        "D14",
        "uninsured percentile by tick status",
        "uninsured_percentile",
        "tick_status",
        "kruskal_epsilon",
        False,
    ),
    PairSpec(
        "D15",
        "log population by tick status",
        "log_population",
        "tick_status",
        "kruskal_epsilon",
        False,
    ),
    PairSpec("D16", "RUCC by tick status", "rucc_2023", "tick_status", "kruskal_epsilon", False),
)


def bh(pairs: Sequence[tuple[str, float]]) -> dict[str, float]:
    """Benjamini-Hochberg on #116 tail shares. Not a design-based p-value."""
    if not pairs:
        return {}
    ordered = sorted(pairs, key=lambda item: (item[1], item[0]))
    family = len(ordered)
    raw = [min(1.0, (family / (index + 1)) * value) for index, (_, value) in enumerate(ordered)]
    adjusted = [0.0] * family
    running = 1.0
    for index in range(family - 1, -1, -1):
        running = min(running, raw[index])
        adjusted[index] = running
    return {name: adjusted[index] for index, (name, _) in enumerate(ordered)}


def bias_corrected_cramers_v(table: Sequence[Sequence[int]]) -> float | None:
    """Bergsma correction applied to the chi-square from `cramers_v`. None when V is undefined."""
    association = cramers_v(table)
    if association is None:
        return None
    return _correct(association)


def release_matches(row: Mapping[str, object]) -> None:
    """Stop unless the live pin matches the frozen release."""
    if _text(row.get("RELEASE_ID")) != PINNED_RELEASE_ID:
        raise CrossDomainError("live release does not match the frozen pin")
    if _text(row.get("SCHEMA_VERSION")) != SCHEMA_VERSION:
        raise CrossDomainError("live schema does not match the frozen pin")
    if _text(row.get("BUNDLE_SHA256")).lower() != PINNED_BUNDLE_SHA256:
        raise CrossDomainError("live bundle does not match the frozen pin")
    if _text(row.get("METHODOLOGY_VERSION")) != METHODOLOGY_VERSION:
        raise CrossDomainError("live methodology does not match the frozen pin")
    if _text(row.get("SCOPE")) != SCOPE:
        raise CrossDomainError("live scope does not match the frozen pin")


def load_cross_domain_queries(text: str) -> dict[str, str]:
    """Split the issue 114 validation file and reject unsafe SQL."""
    return load_marked_queries(text, QUERY_NAMES)


def spearman_arrays(left: Vector, right: Vector) -> float | None:
    """Average-rank Spearman. The #116 helper is the reference on paired tuples."""
    if left.shape != right.shape or left.size < 3:
        return None
    if np.unique(left).size < 2 or np.unique(right).size < 2:
        return None
    return _pearson(_average_rank(left), _average_rank(right))


def prepare_counties(
    rows: Sequence[Mapping[str, object]],
    *,
    release_id: str,
) -> tuple[County, ...]:
    """Validate identity. Do not impute a missing context field or an Unknown status."""
    if release_id != PINNED_RELEASE_ID:
        raise CrossDomainError("release id does not match the frozen pin")
    if len(rows) != REFERENCE_COUNTIES:
        raise CrossDomainError("county count is not 3144")
    seen: set[str] = set()
    counties: list[County] = []
    for row in rows:
        fips = row.get("FIPS")
        state = row.get("STATE")
        if not isinstance(fips, str) or len(fips) != 5 or not fips.isdigit():
            raise CrossDomainError("five-digit string FIPS required")
        if fips in seen:
            raise CrossDomainError("duplicate FIPS")
        seen.add(fips)
        if not isinstance(state, str) or state not in CENSUS_REGIONS:
            raise CrossDomainError("state is outside the Census map")
        if _text(row.get("RELEASE_ID")) != release_id:
            raise CrossDomainError("mixed release")
        human = _text(row.get("HUMAN_STATUS"))
        tick = _text(row.get("TICK_STATUS"))
        pathogen = _text(row.get("BURGDORFERI_STATUS"))
        if tick not in TICK_ALLOWED or pathogen not in PATHOGEN_ALLOWED:
            raise CrossDomainError("tick or pathogen status is outside the frozen levels")
        name = row.get("COUNTY")
        counties.append(
            County(
                fips=fips,
                name=name.strip() if isinstance(name, str) else "",
                state=state,
                population=_positive(row.get("POPULATION")),
                svi=_unit(row.get("SVI_PERCENTILE")),
                uninsured=_unit(row.get("UNINSURED_PERCENTILE")),
                rucc=_rucc(row.get("RUCC_2023")),
                human=human,
                tick=tick,
                pathogen=pathogen,
                in_scope=_flag(row.get("IN_CONTIGUOUS_TICK_SCOPE")),
            )
        )
    return tuple(sorted(counties, key=lambda county: county.fips))


def analyze(counties: Sequence[County]) -> Analysis:
    """Fit the frozen register. The live runner uses this gate."""
    if len(counties) != REFERENCE_COUNTIES:
        raise CrossDomainError("county count is not 3144")
    return fit_counties(counties)


def fit_counties(counties: Sequence[County]) -> Analysis:
    """Fit one prepared cohort. The 3,144 gate lives in `analyze`."""
    frame = _frame(counties)
    complete = int(np.isfinite(frame.columns["log_population"]).sum())
    if len(counties) >= REFERENCE_COUNTIES and complete < MIN_PCA_N:
        raise CrossDomainError("three-feature cohort is below 500")
    pairs = _attach_intervals(tuple(_fit_pair(spec, frame) for spec in DISCOVERY), frame)
    signed = [item for item in pairs if item.spec.signed]
    family_complete = all(
        item.cluster is not None and item.cluster.estimable and item.cluster.tail_share is not None
        for item in signed
    )
    tail_pairs = _tail_pairs(signed)
    bh_values = bh(tail_pairs) if family_complete else {}
    holm_values = holm(tail_pairs) if family_complete else {}
    annotated = tuple(
        _annotate(item, bh_values.get(item.spec.pair_id), holm_values.get(item.spec.pair_id))
        for item in pairs
    )
    ranked = tuple(sorted(annotated, key=_rank_key))
    reproduction = _reproduction(frame)
    context_pca = _pca(frame, "context", CONTEXT_FEATURES, _context_mask(frame))
    cross_mask = _cross_mask(frame)
    cross_pca = _pca(frame, "cross_domain", CROSS_FEATURES, cross_mask)
    small_share, small_material = _share_sensitivity(
        frame, _small_state_mask(frame, _context_mask(frame)), context_pca
    )
    scope_share, scope_material = _share_sensitivity(
        frame, _context_mask(frame) & frame.in_scope, context_pca
    )
    representation = _representation(context_pca)
    follow_up = _follow_up(ranked, family_complete)
    return Analysis(
        release_id=PINNED_RELEASE_ID,
        counties=len(counties),
        published_n=sum(county.human == HUMAN_PUBLISHED for county in counties),
        no_record_n=sum(county.human == HUMAN_NONE for county in counties),
        svi_rescaled=frame.svi_rescaled,
        uninsured_rescaled=frame.uninsured_rescaled,
        context_n=int(_context_mask(frame).sum()),
        cross_n=int(cross_mask.sum()),
        pairs=ranked,
        reproduction=reproduction,
        context_pca=context_pca,
        cross_pca=cross_pca,
        small_state_share=small_share,
        scope_share=scope_share,
        small_state_material=small_material,
        scope_material=scope_material,
        representation=representation,
        follow_up=follow_up,
        recommendations=_recommendations(ranked, reproduction, context_pca, cross_pca),
        spots=_spots(counties),
        heatmap_labels=HEATMAP_FEATURES,
        heatmap=_heatmap(frame, cross_mask),
        family_complete=family_complete,
    )


def pca_experiments(analysis: Analysis, run_id: str) -> tuple[ExperimentSpec, ...]:
    """One experiment row per PCA block. Identifiers include the run id."""
    return (
        _experiment(
            analysis.context_pca,
            run_id,
            "Three-feature correlation PCA on SVI, uninsured percentile, and log population.",
        ),
        _experiment(
            analysis.cross_pca,
            run_id,
            "Cross-domain correlation PCA on the complete-case documentation block.",
        ),
    )


def lab_correlations(analysis: Analysis) -> tuple[CorrelationRecord, ...]:
    """Marginal and partial coefficients. The p-value column stays empty."""
    rows: list[CorrelationRecord] = []
    for item in analysis.pairs:
        if item.estimate is None or item.cluster is None or not item.cluster.estimable:
            continue
        rows.append(
            CorrelationRecord(
                var_a=item.spec.var_a,
                var_b=item.spec.var_b,
                method=item.spec.method,
                n=item.n,
                coefficient=item.estimate,
                ci_low=item.cluster.low,
                ci_high=item.cluster.high,
            )
        )
        if item.partial is None or item.partial_low is None or item.partial_high is None:
            continue
        rows.append(
            CorrelationRecord(
                var_a=item.spec.var_a,
                var_b=item.spec.var_b,
                method=f"partial_{item.spec.method}",
                n=item.partial_n,
                coefficient=item.partial,
                ci_low=item.partial_low,
                ci_high=item.partial_high,
            )
        )
    for reproduced in analysis.reproduction:
        if reproduced.estimate is None:
            continue
        left, right = _reproduction_names(reproduced.name)
        cited = reproduced.matches_reference
        rows.append(
            CorrelationRecord(
                var_a=left,
                var_b=right,
                method=_reproduction_method(reproduced.name),
                n=reproduced.n,
                coefficient=reproduced.estimate,
                ci_low=reproduced.cited_low if cited else None,
                ci_high=reproduced.cited_high if cited else None,
            )
        )
        if reproduced.corrected is None:
            continue
        rows.append(
            CorrelationRecord(
                var_a=left,
                var_b=right,
                method="cramers_v_bias",
                n=reproduced.n,
                coefficient=reproduced.corrected,
            )
        )
    return tuple(rows)


def lab_metrics(analysis: Analysis) -> tuple[EdaMetric, ...]:
    """Aggregate metrics for the register, the PCA shares, and the loadings."""
    rows: list[EdaMetric] = [
        _metric("county_rows", analysis.counties, analysis.counties, "count"),
        _metric("published_floor_n", analysis.published_n, analysis.counties, "count"),
        _metric("no_county_record_n", analysis.no_record_n, analysis.counties, "count"),
        _metric("context_complete_n", analysis.context_n, analysis.counties, "count"),
        _metric("cross_domain_complete_n", analysis.cross_n, analysis.counties, "count"),
    ]
    for item in analysis.pairs:
        if item.estimate is None:
            continue
        rows.append(
            _metric(
                f"{item.spec.pair_id}_estimate",
                item.estimate,
                item.n,
                "coefficient",
                {"method": item.spec.method},
            )
        )
        if item.bh is not None:
            rows.append(_metric(f"{item.spec.pair_id}_bh_tail", item.bh, item.n, "tail_share"))
        if item.holm_adjusted is not None:
            rows.append(
                _metric(f"{item.spec.pair_id}_holm_tail", item.holm_adjusted, item.n, "tail_share")
            )
        if item.width_ratio is not None:
            rows.append(
                _metric(f"{item.spec.pair_id}_width_ratio", item.width_ratio, item.n, "ratio")
            )
    rows.extend(_pca_metrics(analysis.context_pca))
    rows.extend(_pca_metrics(analysis.cross_pca))
    if analysis.small_state_share is not None:
        rows.append(
            _metric(
                "context_share_states_at_least_15",
                analysis.small_state_share,
                analysis.context_n,
                "share",
            )
        )
    if analysis.scope_share is not None:
        rows.append(
            _metric(
                "context_share_contiguous_scope", analysis.scope_share, analysis.context_n, "share"
            )
        )
    return tuple(rows)


def lab_findings(analysis: Analysis) -> tuple[FindingRecord, ...]:
    """Aggregate statements. County identifiers stay out of this table."""
    top = next((item for item in analysis.pairs if item.qualified), None)
    context = analysis.context_pca
    return (
        FindingRecord(
            topic="context_pca",
            statement=_pca_statement(context, analysis.representation),
            disposition=analysis.representation
            if analysis.representation in {"keep", "revise", "stop"}
            else "revise",
            n_underlying=max(context.n, 11),
            effect_size=context.two_component,
            uncertainty_note=(
                "Correlation-matrix PCA. State-cluster loading intervals are metrics, "
                "not a causal interval."
            ),
            evidence={"target": OCT13_TWO_COMPONENT, "representation": analysis.representation},
        ),
        FindingRecord(
            topic="follow_up",
            statement=_follow_statement(analysis, top),
            disposition=_finding_disposition(analysis.follow_up),
            n_underlying=analysis.counties,
            effect_size=None if top is None else top.estimate,
            ci_low=None if top is None or top.cluster is None else top.cluster.low,
            ci_high=None if top is None or top.cluster is None else top.cluster.high,
            uncertainty_note=(
                "BH adjusts signed tail shares. Crossing zero is a description of the interval."
            ),
            evidence={"follow_up": analysis.follow_up, "family_complete": analysis.family_complete},
        ),
        FindingRecord(
            topic="climate_block",
            statement=(
                "January climate associations are not estimable. "
                "VALUE_NATIVE_DOUBLE usable days were 0 to 1 for average temperature "
                "and 0 to 6 for precipitation. No county reached 20 days. "
                "Maximum and minimum temperature are not separate features. "
                "No climate column entered the PCA."
            ),
            disposition=_finding_disposition(analysis.follow_up),
            n_underlying=analysis.counties,
            uncertainty_note=(
                "Cited from the #110 aggregate on this release. The day view was not read again."
            ),
            evidence={"status": "not_estimable"},
        ),
        FindingRecord(
            topic="feature_block",
            statement=_recommendation_statement(analysis),
            disposition=analysis.representation
            if analysis.representation in {"keep", "revise", "stop"}
            else "revise",
            n_underlying=max(analysis.cross_n, 11),
            uncertainty_note=(
                "Keep or drop is a representation recommendation, not a model admission."
            ),
            evidence={"has_recommendations": True},
        ),
    )


@dataclass
class _Frame:
    states: Vector
    regions: Vector
    columns: dict[str, Vector]
    tick_code: Vector
    in_scope: Vector
    svi_rescaled: bool
    uninsured_rescaled: bool


def _frame(counties: Sequence[County]) -> _Frame:
    svi = np.array(
        [math.nan if county.svi is None else county.svi for county in counties], dtype=float
    )
    uninsured = np.array(
        [math.nan if county.uninsured is None else county.uninsured for county in counties],
        dtype=float,
    )
    svi, svi_rescaled = _rescale(svi)
    uninsured, uninsured_rescaled = _rescale(uninsured)
    population = np.array(
        [math.nan if county.population is None else county.population for county in counties],
        dtype=float,
    )
    log_population = np.where(
        np.isfinite(population) & (population > 0), np.log(population), np.nan
    )
    rucc = np.array(
        [math.nan if county.rucc is None else float(county.rucc) for county in counties]
    )
    human = np.array(
        [
            1.0
            if county.human == HUMAN_PUBLISHED
            else 0.0
            if county.human == HUMAN_NONE
            else math.nan
            for county in counties
        ]
    )
    scope = np.array(
        [
            county.in_scope and county.tick in TICK_KNOWN and county.pathogen in PATHOGEN_KNOWN
            for county in counties
        ]
    )
    pathogen = np.array(
        [
            1.0
            if county.pathogen == "Present"
            else 0.0
            if county.pathogen == "No records"
            else math.nan
            for county in counties
        ]
    )
    pathogen = np.where(scope, pathogen, np.nan)
    tick_code = np.array(
        [
            TICK_KNOWN.index(county.tick) if county.tick in TICK_KNOWN and county.in_scope else -1
            for county in counties
        ],
        dtype=int,
    )
    established = np.where(
        tick_code < 0, np.nan, np.where(tick_code == TICK_KNOWN.index("Established"), 1.0, 0.0)
    )
    reported = np.where(
        tick_code < 0, np.nan, np.where(tick_code == TICK_KNOWN.index("Reported"), 1.0, 0.0)
    )
    return _Frame(
        states=np.array([county.state for county in counties]),
        regions=np.array([CENSUS_REGIONS[county.state] for county in counties]),
        columns={
            "log_population": log_population,
            "svi_percentile": svi,
            "uninsured_percentile": uninsured,
            "rucc_2023": rucc,
            "human_published": human,
            "tick_established": established,
            "tick_reported": reported,
            "pathogen_present": pathogen,
        },
        tick_code=tick_code,
        in_scope=scope,
        svi_rescaled=svi_rescaled,
        uninsured_rescaled=uninsured_rescaled,
    )


def _fit_pair(spec: PairSpec, frame: _Frame) -> PairResult:
    mask = _pair_mask(spec, frame, partial=False)
    partial_mask = _pair_mask(spec, frame, partial=True)
    estimate = _coefficient(spec, frame, np.flatnonzero(mask))
    partial = _partial_coefficient(spec, frame, np.flatnonzero(partial_mask))
    region_material = _region_material(spec, frame, mask, estimate)
    return PairResult(
        spec=spec,
        estimate=estimate,
        n=int(mask.sum()),
        cluster=None,
        naive=None,
        width_ratio=None,
        partial=partial,
        partial_low=None,
        partial_high=None,
        partial_n=int(partial_mask.sum()),
        region_material=region_material,
        bh=None,
        holm_adjusted=None,
        qualified=False,
        confounder=False,
        redundancy=False,
        rank_tier=3,
    )


def _attach_intervals(pairs: tuple[PairResult, ...], frame: _Frame) -> tuple[PairResult, ...]:
    """One state-cluster pass per distinct state set, shared by every pair on that set."""
    marginal = _interval_jobs(pairs, frame, partial=False)
    partial = _interval_jobs(pairs, frame, partial=True)
    cluster = _cluster_jobs(marginal, frame, SEED)
    naive = _naive_jobs(marginal, frame, NAIVE_SEED)
    partial_intervals = _cluster_jobs(partial, frame, SEED)
    attached: list[PairResult] = []
    for item in pairs:
        item_cluster = cluster.get(item.spec.pair_id)
        item_naive = naive.get(item.spec.pair_id)
        item_partial = partial_intervals.get(item.spec.pair_id)
        attached.append(
            PairResult(
                spec=item.spec,
                estimate=item.estimate,
                n=item.n,
                cluster=item_cluster,
                naive=item_naive,
                width_ratio=_width(item_cluster, item_naive),
                partial=item.partial,
                partial_low=None if item_partial is None else item_partial.low,
                partial_high=None if item_partial is None else item_partial.high,
                partial_n=item.partial_n,
                region_material=item.region_material,
                bh=None,
                holm_adjusted=None,
                qualified=False,
                confounder=False,
                redundancy=False,
                rank_tier=3,
            )
        )
    return tuple(attached)


def _annotate(
    item: PairResult,
    bh_value: float | None,
    holm_value: float | None,
) -> PairResult:
    excludes = _excludes_zero(item.cluster)
    partial_excludes = _bounds_exclude_zero(item.partial_low, item.partial_high)
    confounder = _confounder(item, excludes, partial_excludes)
    redundancy = bool(
        item.spec.method == "spearman"
        and item.estimate is not None
        and abs(item.estimate) >= REDUNDANCY_RHO
        and {item.spec.var_a, item.spec.var_b} <= set(PREFERENCE)
    )
    qualified = bool(
        item.spec.signed
        and excludes
        and bh_value is not None
        and bh_value <= BH_FLAG
        and item.partial is not None
        and item.estimate is not None
        and item.partial * item.estimate > 0
        and not item.region_material
        and not confounder
    )
    if qualified:
        tier = 0
    elif item.spec.signed and excludes:
        tier = 1
    elif not item.spec.signed and excludes:
        tier = 2
    else:
        tier = 3
    return PairResult(
        spec=item.spec,
        estimate=item.estimate,
        n=item.n,
        cluster=item.cluster,
        naive=item.naive,
        width_ratio=item.width_ratio,
        partial=item.partial,
        partial_low=item.partial_low,
        partial_high=item.partial_high,
        partial_n=item.partial_n,
        region_material=item.region_material,
        bh=bh_value,
        holm_adjusted=holm_value,
        qualified=qualified,
        confounder=confounder,
        redundancy=redundancy,
        rank_tier=tier,
    )


def _reproduction(frame: _Frame) -> tuple[ReproductionResult, ...]:
    mask = frame.in_scope & np.isfinite(frame.columns["human_published"])
    indices = np.flatnonzero(mask)
    tables = {
        "tick_pathogen": _category_table(
            frame.tick_code[indices], _pathogen_code(frame)[indices], 3, 2
        ),
        "human_tick": _category_table(
            frame.columns["human_published"][indices].astype(int), frame.tick_code[indices], 2, 3
        ),
        "human_pathogen": _category_table(
            frame.columns["human_published"][indices].astype(int),
            _pathogen_code(frame)[indices],
            2,
            2,
        ),
    }
    rows = [_v_result(name, table, indices, frame) for name, table in tables.items()]
    rows.append(_spearman_reference("svi_human", "svi_percentile", "human_published", frame))
    rows.append(_spearman_reference("rucc_human", "rucc_2023", "human_published", frame))
    return tuple(rows)


def _pca(frame: _Frame, name: str, features: tuple[str, ...], mask: Vector) -> PcaFit:
    indices = np.flatnonzero(mask)
    matrix = _matrix(frame, indices, features)
    fit = _fit_matrix(matrix, features)
    if fit is None:
        return PcaFit(name, int(mask.sum()), features, (), None, None, {}, (), {}, True, False)
    shares, vectors, condition = fit
    loadings = _loading_intervals(frame, mask, features, vectors)
    region_shares: dict[str, float | None] = {}
    material = False
    full = shares[0] + shares[1] if len(shares) >= 2 else None
    for region in ("Northeast", "Midwest", "South", "West"):
        held = np.flatnonzero(mask & (frame.regions != region))
        held_fit = _fit_matrix(_matrix(frame, held, features), features)
        share = None
        if held_fit is not None and len(held_fit[0]) >= 2:
            share = float(held_fit[0][0] + held_fit[0][1])
        region_shares[region] = share
        if full is None or share is None or abs(share - full) >= REGION_SHARE_MOVE:
            material = True
    return PcaFit(
        name=name,
        n=int(mask.sum()),
        features=features,
        shares=tuple(float(share) for share in shares),
        two_component=None if full is None else float(full),
        condition_number=condition,
        vifs=_vifs(matrix, features),
        loadings=loadings,
        region_shares=region_shares,
        region_material=material,
        estimable=True,
    )


def _loading_intervals(
    frame: _Frame,
    mask: Vector,
    features: tuple[str, ...],
    vectors: Vector,
) -> tuple[Loading, ...]:
    grouped = _groups(mask, frame.states)
    keys = tuple(sorted(grouped))
    components = min(2, len(features))
    slots = [
        (component, feature_index, feature)
        for component in range(components)
        for feature_index, feature in enumerate(features)
    ]
    store: dict[tuple[int, int], list[float | None]] = {slot[:2]: [] for slot in slots}

    def statistic(draw: Sequence[str]) -> float | None:
        chosen = _draw_indices(draw, grouped)
        fit = None if chosen is None else _fit_matrix(_matrix(frame, chosen, features), features)
        for component, feature_index, _feature in slots:
            if fit is None:
                store[(component, feature_index)].append(None)
            else:
                store[(component, feature_index)].append(float(fit[1][feature_index, component]))
        return 0.0

    if len(keys) >= 10:
        state_cluster_interval(keys, statistic, SEED)
    rows: list[Loading] = []
    for component, feature_index, feature in slots:
        interval = _from_draws(store[(component, feature_index)], len(keys))
        rows.append(
            Loading(
                feature=feature,
                component=component + 1,
                value=float(vectors[feature_index, component]),
                low=None if not interval.estimable else interval.low,
                high=None if not interval.estimable else interval.high,
            )
        )
    return tuple(rows)


def _fit_matrix(
    matrix: Vector,
    features: tuple[str, ...],
) -> tuple[Vector, Vector, float] | None:
    if matrix.shape[0] < 3 or matrix.shape[1] != len(features):
        return None
    if np.any(~np.isfinite(matrix)):
        return None
    deviation = np.std(matrix, axis=0, ddof=1)
    if np.any(deviation == 0) or np.any(~np.isfinite(deviation)):
        return None
    corr = np.corrcoef(matrix, rowvar=False)
    if not isinstance(corr, np.ndarray) or corr.shape != (len(features), len(features)):
        return None
    if not np.all(np.isfinite(corr)):
        return None
    raw_values, raw_vectors = np.linalg.eigh(corr)
    values = np.clip(np.asarray(raw_values, dtype=float), 0, None)
    vectors = np.asarray(raw_vectors, dtype=float)
    order = np.argsort(values)[::-1]
    values = values[order]
    vectors = _orient(vectors[:, order], features)
    total = float(values.sum())
    if total <= 0:
        return None
    condition = float(np.linalg.cond(corr))
    if not math.isfinite(condition):
        return None
    return values / total, vectors, condition


def _recommendations(
    pairs: Sequence[PairResult],
    reproduction: Sequence[ReproductionResult],
    context: PcaFit,
    cross: PcaFit,
) -> tuple[str, ...]:
    notes = list(_context_keep_drop(pairs, cross))
    vector = next((item for item in reproduction if item.name == "tick_pathogen"), None)
    corrected = None if vector is None else vector.corrected
    if corrected is None:
        notes.append(
            "Tick and pathogen bias-corrected V is not estimable. "
            "Keep both documentation fields out of a collapsed block."
        )
    elif corrected >= VECTOR_V_COLLAPSE:
        notes.append(
            "Bias-corrected tick by pathogen V is at least 0.80. "
            "Use one vector-documentation block in a linear representation "
            "and keep both fields for a contingency table."
        )
    else:
        notes.append(
            "Bias-corrected tick by pathogen V is below 0.80. "
            "Keep tick status and pathogen status as separate documentation fields."
        )
    notes.append(_human_loading_note(cross))
    notes.append("Drop January climate. No native-double field reached 20 usable days.")
    if context.two_component is not None:
        notes.append(
            "Three-feature two-component share is "
            f"{_fmt(context.two_component)} against the October 13 figure 0.8850."
        )
    return tuple(notes)


def _context_keep_drop(pairs: Sequence[PairResult], cross: PcaFit) -> tuple[str, ...]:
    dropped: list[str] = []
    for item in pairs:
        if not item.redundancy:
            continue
        later = _later(item.spec.var_a, item.spec.var_b)
        if later not in dropped:
            dropped.append(later)
    for feature in reversed(PREFERENCE):
        vif = cross.vifs.get(feature)
        high_vif = vif is not None and vif >= VIF_DROP and feature != PREFERENCE[0]
        if high_vif and feature not in dropped:
            dropped.append(feature)
    kept = [feature for feature in PREFERENCE if feature not in dropped]
    if not kept:
        kept = [PREFERENCE[0]]
    return (
        "Keep in the joint context block: " + ", ".join(kept) + ".",
        "Drop from the joint context block: " + (", ".join(dropped) if dropped else "none") + ".",
    )


def _human_loading_note(cross: PcaFit) -> str:
    if not cross.estimable or not cross.shares:
        return (
            "Human published indicator: cross-domain PCA is not estimable, "
            "so the loading rule does not fire."
        )
    cumulative = 0.0
    components: list[int] = []
    for index, share in enumerate(cross.shares):
        cumulative += share
        components.append(index + 1)
        if cumulative >= VARIANCE_TARGET:
            break
    values = [
        abs(loading.value)
        for loading in cross.loadings
        if loading.feature == "human_published" and loading.component in components
    ]
    if not values:
        return "Human published indicator has no loading on the retained components."
    largest = max(values)
    if largest < LOADING_DROP:
        decision = (
            "Drop it from the low-dimensional predictor block "
            "and keep it as a documentation outcome."
        )
    elif largest >= LOADING_KEEP:
        decision = "Keep it in the low-dimensional block and as a documentation outcome."
    else:
        decision = (
            "It sits between the 0.20 and 0.30 loading cuts. "
            "Keep it as a documentation outcome and do not treat it as a required predictor."
        )
    return (
        "Human published largest absolute loading on the components that reach 80% is "
        f"{_fmt(largest)}. {decision}"
    )


def pca_share(values: Vector) -> float | None:
    """Two-component share for a complete standardized matrix. Tests use this directly."""
    fit = _fit_matrix(values, tuple(f"c{index}" for index in range(values.shape[1])))
    if fit is None or len(fit[0]) < 2:
        return None
    return float(fit[0][0] + fit[0][1])


def _experiment(fit: PcaFit, run_id: str, hypothesis: str) -> ExperimentSpec:
    metrics: list[ExperimentMetric] = []
    if fit.two_component is not None:
        metrics.append(
            ExperimentMetric(
                "pc1_pc2", "explained_variance_share", fit.two_component, None, None, fit.n
            )
        )
    for index, share in enumerate(fit.shares):
        metrics.append(
            ExperimentMetric(
                f"pc{index + 1}",
                "explained_variance_share",
                float(share),
                None,
                None,
                fit.n,
            )
        )
    for loading in fit.loadings:
        metrics.append(
            ExperimentMetric(
                f"pc{loading.component}_{loading.feature}",
                "loading",
                loading.value,
                loading.low,
                loading.high,
                fit.n,
            )
        )
    if fit.condition_number is not None:
        metrics.append(
            ExperimentMetric("full", "condition_number", fit.condition_number, None, None, fit.n)
        )
    for feature, vif in fit.vifs.items():
        if vif is None or not math.isfinite(vif):
            continue
        metrics.append(ExperimentMetric(feature, "vif", vif, None, None, fit.n))
    return ExperimentSpec(
        experiment_id=f"{run_id}-pca-{fit.name}",
        model_family="pca",
        hypothesis=hypothesis,
        config={
            "spec_id": SPEC_ID,
            "features": list(fit.features),
            "standardization": "correlation_matrix_ddof_1",
            "seed": SEED,
        },
        split_definition={"cohort": fit.name, "complete_case": True, "imputation": "none"},
        status="succeeded" if fit.estimable else "failed",
        metrics=tuple(metrics),
    )


def _pair_mask(spec: PairSpec, frame: _Frame, *, partial: bool) -> Vector:
    if spec.method == "spearman":
        mask = np.isfinite(frame.columns[spec.var_a]) & np.isfinite(frame.columns[spec.var_b])
    else:
        mask = np.isfinite(frame.columns[spec.var_a]) & (frame.tick_code >= 0)
    if partial:
        for control in _controls(spec):
            mask = mask & np.isfinite(frame.columns[control])
    return cast(Vector, mask)


def _controls(spec: PairSpec) -> tuple[str, ...]:
    names = [spec.var_a]
    if spec.method == "spearman":
        names.append(spec.var_b)
    controls: list[str] = []
    if "log_population" not in names:
        controls.append("log_population")
    if "rucc_2023" not in names:
        controls.append("rucc_2023")
    return tuple(controls)


def _coefficient(spec: PairSpec, frame: _Frame, indices: Vector) -> float | None:
    if indices.size == 0:
        return None
    if spec.method == "spearman":
        return spearman_arrays(
            frame.columns[spec.var_a][indices], frame.columns[spec.var_b][indices]
        )
    return _epsilon(frame.columns[spec.var_a][indices], frame.tick_code[indices])


def _partial_coefficient(spec: PairSpec, frame: _Frame, indices: Vector) -> float | None:
    if indices.size < 3:
        return None
    controls = _controls(spec)
    if spec.method == "spearman":
        return _partial_spearman(
            frame.columns[spec.var_a][indices],
            frame.columns[spec.var_b][indices],
            [frame.columns[name][indices] for name in controls],
            frame.states[indices],
        )
    outcome = _residual_rank(
        frame.columns[spec.var_a][indices],
        [frame.columns[name][indices] for name in controls],
        frame.states[indices],
    )
    if outcome is None:
        return None
    return _epsilon(outcome, frame.tick_code[indices])


@dataclass(frozen=True)
class _Job:
    pair_id: str
    spec: PairSpec
    partial: bool
    keys: tuple[str, ...]
    grouped: dict[str, Vector]
    indices: Vector


def _interval_jobs(
    pairs: Sequence[PairResult],
    frame: _Frame,
    *,
    partial: bool,
) -> tuple[_Job, ...]:
    jobs: list[_Job] = []
    for item in pairs:
        mask = _pair_mask(item.spec, frame, partial=partial)
        grouped = _groups(mask, frame.states)
        jobs.append(
            _Job(
                pair_id=item.spec.pair_id,
                spec=item.spec,
                partial=partial,
                keys=tuple(sorted(grouped)),
                grouped=grouped,
                indices=np.flatnonzero(mask),
            )
        )
    return tuple(jobs)


def _cluster_jobs(
    jobs: Sequence[_Job],
    frame: _Frame,
    seed: int,
) -> dict[str, IntervalEstimate]:
    buckets: dict[tuple[str, ...], list[_Job]] = defaultdict(list)
    for job in jobs:
        buckets[job.keys].append(job)
    found: dict[str, IntervalEstimate] = {}
    for keys, bucket in buckets.items():
        store: dict[str, list[float | None]] = {job.pair_id: [] for job in bucket}

        def statistic(
            draw: Sequence[str],
            bucket: Sequence[_Job] = tuple(bucket),
            store: dict[str, list[float | None]] = store,
        ) -> float | None:
            for job in bucket:
                indices = _draw_indices(draw, job.grouped)
                value = None if indices is None else _job_value(job, frame, indices)
                store[job.pair_id].append(value)
            return 0.0

        if len(keys) >= 10:
            state_cluster_interval(keys, statistic, seed)
        for job in bucket:
            found[job.pair_id] = _from_draws(store[job.pair_id], len(keys))
    return found


def _naive_jobs(
    jobs: Sequence[_Job],
    frame: _Frame,
    seed: int,
) -> dict[str, IntervalEstimate]:
    buckets: dict[bytes, list[_Job]] = defaultdict(list)
    for job in jobs:
        buckets[job.indices.tobytes()].append(job)
    found: dict[str, IntervalEstimate] = {}
    for bucket in buckets.values():
        indices = bucket[0].indices
        store: dict[str, list[float | None]] = {job.pair_id: [] for job in bucket}

        def statistic(
            draw: Sequence[int],
            bucket: Sequence[_Job] = tuple(bucket),
            indices: Vector = indices,
            store: dict[str, list[float | None]] = store,
        ) -> float | None:
            chosen = indices[np.asarray(draw, dtype=int)]
            for job in bucket:
                store[job.pair_id].append(_job_value(job, frame, chosen))
            return 0.0

        if indices.size >= 11:
            resample_interval(list(range(int(indices.size))), statistic, seed)
        for job in bucket:
            found[job.pair_id] = _from_draws(store[job.pair_id], int(indices.size))
    return found


def _job_value(job: _Job, frame: _Frame, indices: Vector) -> float | None:
    if job.partial:
        return _partial_coefficient(job.spec, frame, indices)
    return _coefficient(job.spec, frame, indices)


def _from_draws(values: Sequence[float | None], clusters: int) -> IntervalEstimate:
    kept = [value for value in values if value is not None and math.isfinite(value)]
    failed = REPLICATES - len(kept)
    if failed * 100 > REPLICATES * 5 or len(kept) < 2:
        return IntervalEstimate(None, None, failed, REPLICATES, clusters, len(kept), False, None)
    ordered = sorted(kept)
    below = sum(value <= 0 for value in ordered)
    above = sum(value >= 0 for value in ordered)
    return IntervalEstimate(
        low=rank_quantile(ordered, 0.025),
        high=rank_quantile(ordered, 0.975),
        failed=failed,
        replicates=REPLICATES,
        clusters=clusters,
        kept=len(kept),
        estimable=True,
        tail_share=min(1.0, 2.0 * min(below, above) / len(ordered)),
    )


def _region_material(spec: PairSpec, frame: _Frame, mask: Vector, estimate: float | None) -> bool:
    if estimate is None:
        return True
    move = SIGNED_MOVE if spec.signed else UNSIGNED_MOVE
    for region in ("Northeast", "Midwest", "South", "West"):
        held = np.flatnonzero(mask & (frame.regions != region))
        value = _coefficient(spec, frame, held)
        if value is None or abs(value - estimate) >= move:
            return True
        if spec.signed and value * estimate < 0:
            return True
    return False


def _context_mask(frame: _Frame) -> Vector:
    mask = np.ones(frame.states.shape[0], dtype=bool)
    for name in CONTEXT_FEATURES:
        mask = mask & np.isfinite(frame.columns[name])
    return mask


def _cross_mask(frame: _Frame) -> Vector:
    mask = _context_mask(frame) & np.isfinite(frame.columns["rucc_2023"])
    mask = mask & np.isfinite(frame.columns["human_published"]) & frame.in_scope
    return cast(
        Vector,
        mask & (frame.tick_code >= 0) & np.isfinite(frame.columns["pathogen_present"]),
    )


def _small_state_mask(frame: _Frame, mask: Vector) -> Vector:
    grouped = _groups(mask, frame.states)
    keep = {state for state, indices in grouped.items() if indices.size >= MIN_STATES}
    return mask & np.isin(frame.states, np.array(sorted(keep)))


def _share_sensitivity(frame: _Frame, mask: Vector, fit: PcaFit) -> tuple[float | None, bool]:
    if fit.two_component is None:
        return None, False
    held = _fit_matrix(_matrix(frame, np.flatnonzero(mask), CONTEXT_FEATURES), CONTEXT_FEATURES)
    if held is None or len(held[0]) < 2:
        return None, True
    share = float(held[0][0] + held[0][1])
    return share, abs(share - fit.two_component) >= REGION_SHARE_MOVE


def _representation(fit: PcaFit) -> str:
    if not fit.estimable or fit.two_component is None or fit.n < MIN_PCA_N:
        return "stop"
    inside = abs(fit.two_component - OCT13_TWO_COMPONENT) <= SHARE_BAND
    vif_high = any(value is not None and value >= VIF_DROP for value in fit.vifs.values())
    if inside and not fit.region_material and not vif_high:
        return "keep"
    return "revise"


def _follow_up(pairs: Sequence[PairResult], family_complete: bool) -> str:
    signed = [item for item in pairs if item.spec.signed]
    if not any(item.cluster is not None and item.cluster.estimable for item in signed):
        return "stop"
    if family_complete and any(item.qualified for item in signed):
        return "advance"
    return "investigate"


def _heatmap(frame: _Frame, mask: Vector) -> tuple[tuple[float | None, ...], ...]:
    indices = np.flatnonzero(mask)
    rows: list[tuple[float | None, ...]] = []
    for left_name in HEATMAP_FEATURES:
        row: list[float | None] = []
        for right_name in HEATMAP_FEATURES:
            if left_name == right_name:
                row.append(1.0 if indices.size >= 3 else None)
            else:
                row.append(
                    spearman_arrays(
                        frame.columns[left_name][indices], frame.columns[right_name][indices]
                    )
                )
        rows.append(tuple(row))
    return tuple(rows)


def _spots(counties: Sequence[County]) -> tuple[Spot, ...]:
    return (
        _spot("published_floor", counties, lambda county: county.human == HUMAN_PUBLISHED),
        _spot("no_county_record", counties, lambda county: county.human == HUMAN_NONE),
        _spot("outside_tick_scope", counties, lambda county: not county.in_scope),
    )


def _spot(label: str, counties: Sequence[County], rule: Any) -> Spot:
    matches = [county for county in counties if rule(county)]
    if not matches:
        return Spot(label, "", "", "", "", "", "")
    county = min(matches, key=lambda item: item.fips)
    return Spot(
        label, county.fips, county.name, county.state, county.human, county.tick, county.pathogen
    )


def _v_result(
    name: str, table: list[list[int]], indices: Vector, frame: _Frame
) -> ReproductionResult:
    association = cramers_v(table)
    corrected = None if association is None else _correct(association)
    reference, low, high = REPRODUCTION_REFERENCES[name]
    display = None if association is None else f"{association.v:.4f}"
    partial = _stratified_v(frame, indices, name)
    return ReproductionResult(
        name=name,
        estimate=None if association is None else association.v,
        corrected=corrected,
        n=0 if association is None else association.n,
        display=display,
        matches_reference=display == reference,
        cited_low=low if display == reference else None,
        cited_high=high if display == reference else None,
        partial=partial,
    )


def _spearman_reference(name: str, left: str, right: str, frame: _Frame) -> ReproductionResult:
    mask = np.isfinite(frame.columns[left]) & np.isfinite(frame.columns[right])
    indices = np.flatnonzero(mask)
    estimate = spearman_arrays(frame.columns[left][indices], frame.columns[right][indices])
    reference, low, high = REPRODUCTION_REFERENCES[name]
    display = None if estimate is None else f"{estimate:.4f}"
    partial = _partial_spearman(
        frame.columns[left][indices],
        frame.columns[right][indices],
        [
            frame.columns[name][indices]
            for name in _controls(PairSpec(name, name, left, right, "spearman", True))
        ],
        frame.states[indices],
    )
    return ReproductionResult(
        name=name,
        estimate=estimate,
        corrected=None,
        n=int(indices.size),
        display=display,
        matches_reference=display == reference,
        cited_low=low if display == reference else None,
        cited_high=high if display == reference else None,
        partial=partial,
    )


def _stratified_v(frame: _Frame, indices: Vector, name: str) -> float | None:
    if indices.size < 500:
        return None
    log_population = frame.columns["log_population"][indices]
    rucc = frame.columns["rucc_2023"][indices]
    usable = np.isfinite(log_population) & np.isfinite(rucc)
    if int(usable.sum()) < 500:
        return None
    chosen = indices[usable]
    edges = np.quantile(frame.columns["log_population"][chosen], [1 / 3, 2 / 3])
    tertile = np.digitize(frame.columns["log_population"][chosen], np.asarray(edges, dtype=float))
    metro = frame.columns["rucc_2023"][chosen] <= 3
    weighted = 0.0
    total = 0
    states: set[str] = set()
    for tertile_id in (0, 1, 2):
        for is_metro in (True, False):
            stratum = chosen[(tertile == tertile_id) & (metro == is_metro)]
            if stratum.size < 11:
                continue
            table = _reproduction_table(frame, stratum, name)
            corrected = bias_corrected_cramers_v(table)
            if corrected is None:
                continue
            weighted += corrected * stratum.size
            total += int(stratum.size)
            states.update(str(state) for state in frame.states[stratum])
    if total < 500 or len(states) < 10:
        return None
    return weighted / total


def _reproduction_table(frame: _Frame, indices: Vector, name: str) -> list[list[int]]:
    if name == "tick_pathogen":
        return _category_table(frame.tick_code[indices], _pathogen_code(frame)[indices], 3, 2)
    if name == "human_tick":
        return _category_table(
            frame.columns["human_published"][indices].astype(int), frame.tick_code[indices], 2, 3
        )
    return _category_table(
        frame.columns["human_published"][indices].astype(int),
        _pathogen_code(frame)[indices],
        2,
        2,
    )


def _category_table(
    left: Vector, right: Vector, left_levels: int, right_levels: int
) -> list[list[int]]:
    table = [[0 for _ in range(right_levels)] for _ in range(left_levels)]
    for row_value, column_value in zip(left.tolist(), right.tolist(), strict=True):
        row_index = int(row_value)
        column_index = int(column_value)
        if 0 <= row_index < left_levels and 0 <= column_index < right_levels:
            table[row_index][column_index] += 1
    return table


def _pathogen_code(frame: _Frame) -> Vector:
    present = frame.columns["pathogen_present"]
    codes = np.full(present.shape, -1, dtype=int)
    finite = np.isfinite(present)
    codes[finite] = np.asarray(present[finite], dtype=float).astype(int)
    return codes


def _correct(association: Association) -> float | None:
    n = association.n
    rows = association.rows
    columns = association.columns
    if n <= 1:
        return None
    phi2 = association.chi2 / n
    phi2_tilde = max(0.0, phi2 - (rows - 1) * (columns - 1) / (n - 1))
    row_tilde = rows - (rows - 1) ** 2 / (n - 1)
    column_tilde = columns - (columns - 1) ** 2 / (n - 1)
    denominator = min(row_tilde - 1, column_tilde - 1)
    if denominator <= 0:
        return None
    return math.sqrt(phi2_tilde / denominator)


def _partial_spearman(
    left: Vector,
    right: Vector,
    controls: Sequence[Vector],
    states: Vector,
) -> float | None:
    left_residual = _residual_rank(left, controls, states)
    right_residual = _residual_rank(right, controls, states)
    if left_residual is None or right_residual is None:
        return None
    return _pearson(left_residual, right_residual)


def _residual_rank(values: Vector, controls: Sequence[Vector], states: Vector) -> Vector | None:
    if values.size < 3:
        return None
    ranked = _demean(_average_rank(values), states)
    design = [_demean(_average_rank(control), states) for control in controls]
    return _residual(ranked, design)


def _residual(values: Vector, columns: Sequence[Vector]) -> Vector | None:
    if not columns:
        return values
    kept = [column for column in columns if float(np.var(column)) > 1e-12]
    if not kept:
        return values
    design = np.column_stack(kept)
    beta = np.asarray(np.linalg.lstsq(design, values, rcond=None)[0], dtype=float)
    residual = values - design @ beta
    if not np.all(np.isfinite(residual)):
        return None
    return cast(Vector, residual)


def _demean(values: Vector, states: Vector) -> Vector:
    out = np.array(values, dtype=float, copy=True)
    for state in np.unique(states):
        mask = states == state
        out[mask] -= out[mask].mean()
    return out


def _epsilon(values: Vector, groups: Vector) -> float | None:
    bundled: dict[int, list[float]] = defaultdict(list)
    for value, group in zip(values.tolist(), groups.tolist(), strict=True):
        if int(group) < 0 or not math.isfinite(float(value)):
            continue
        bundled[int(group)].append(float(value))
    if len(bundled) < 2 or any(not rows for rows in bundled.values()):
        return None
    try:
        result = omnibus(bundled)
    except ValueError:
        return None
    epsilon = result.get("epsilon_squared")
    if not isinstance(epsilon, float) or not math.isfinite(epsilon):
        return None
    return epsilon


def _groups(mask: Vector, states: Vector) -> dict[str, Vector]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, keep in enumerate(mask.tolist()):
        if keep:
            grouped[str(states[index])].append(index)
    return {state: np.asarray(indices, dtype=int) for state, indices in grouped.items()}


def _draw_indices(draw: Sequence[str], grouped: Mapping[str, Vector]) -> Vector | None:
    parts = [grouped[key] for key in draw if key in grouped and grouped[key].size]
    if not parts:
        return None
    return np.concatenate(parts)


def _matrix(frame: _Frame, indices: Vector, features: tuple[str, ...]) -> Vector:
    if indices.size == 0:
        return np.empty((0, len(features)))
    return np.column_stack([frame.columns[name][indices] for name in features])


def _orient(vectors: Vector, features: tuple[str, ...]) -> Vector:
    oriented = np.array(vectors, dtype=float, copy=True)
    for component, anchor in enumerate(SIGN_ANCHORS):
        if component >= oriented.shape[1] or anchor not in features:
            continue
        if oriented[features.index(anchor), component] < 0:
            oriented[:, component] *= -1
    return oriented


def _vifs(matrix: Vector, features: tuple[str, ...]) -> dict[str, float | None]:
    if matrix.shape[0] < 3:
        return {name: None for name in features}
    deviation = np.std(matrix, axis=0, ddof=1)
    if np.any(deviation == 0):
        return {name: None for name in features}
    standardized = (matrix - matrix.mean(axis=0)) / deviation
    found: dict[str, float | None] = {}
    for index, name in enumerate(features):
        others = np.delete(standardized, index, axis=1)
        target = standardized[:, index]
        beta = np.asarray(np.linalg.lstsq(others, target, rcond=None)[0], dtype=float)
        fitted = others @ beta
        ss_tot = float(np.sum((target - target.mean()) ** 2))
        ss_res = float(np.sum((target - fitted) ** 2))
        if ss_tot <= 0:
            found[name] = None
            continue
        r2 = 1 - ss_res / ss_tot
        found[name] = math.inf if r2 >= 1 - 1e-10 else 1 / (1 - r2)
    return found


def _average_rank(values: Vector) -> Vector:
    """1-based average ranks. Ties share the mean of their positions."""
    size = int(values.shape[0])
    order = np.argsort(values, kind="mergesort")
    sorted_values = values[order]
    if size == 0:
        return np.empty(0, dtype=float)
    change = np.flatnonzero(sorted_values[1:] != sorted_values[:-1]) + 1
    starts = np.concatenate((np.array([0]), change))
    ends = np.concatenate((change, np.array([size])))
    ranks = np.empty(size, dtype=float)
    ranks[order] = np.repeat((starts + ends + 1) / 2, ends - starts)
    return ranks


def _pearson(left: Vector, right: Vector) -> float | None:
    left_centered = left - left.mean()
    right_centered = right - right.mean()
    denominator = math.sqrt(
        float(np.dot(left_centered, left_centered) * np.dot(right_centered, right_centered))
    )
    if denominator <= 0 or not math.isfinite(denominator):
        return None
    value = float(np.dot(left_centered, right_centered) / denominator)
    if not math.isfinite(value):
        return None
    return value


def _rescale(values: Vector) -> tuple[Vector, bool]:
    finite = values[np.isfinite(values)]
    if finite.size and float(np.max(finite)) > 1.5:
        return values / 100, True
    return values, False


def _width(cluster: IntervalEstimate | None, naive: IntervalEstimate | None) -> float | None:
    if (
        cluster is None
        or naive is None
        or not cluster.estimable
        or not naive.estimable
        or cluster.low is None
        or cluster.high is None
        or naive.low is None
        or naive.high is None
    ):
        return None
    naive_width = naive.high - naive.low
    if naive_width == 0:
        return None
    return (cluster.high - cluster.low) / naive_width


def _excludes_zero(interval: IntervalEstimate | None) -> bool:
    if interval is None or not interval.estimable:
        return False
    return _bounds_exclude_zero(interval.low, interval.high)


def _bounds_exclude_zero(low: float | None, high: float | None) -> bool:
    if low is None or high is None:
        return False
    return low > 0 or high < 0


def _confounder(item: PairResult, excludes: bool, partial_excludes: bool) -> bool:
    if item.partial is None or item.estimate is None:
        return True
    if item.spec.signed and item.partial * item.estimate < 0:
        return True
    if item.spec.signed and excludes and not partial_excludes:
        return True
    return not item.spec.signed and abs(item.partial) < 0.5 * abs(item.estimate)


def _rank_key(item: PairResult) -> tuple[int, float, str]:
    magnitude = 0.0 if item.estimate is None else -abs(item.estimate)
    return (item.rank_tier, magnitude, item.spec.pair_id)


def _later(left: str, right: str) -> str:
    return left if PREFERENCE.index(left) > PREFERENCE.index(right) else right


def _pca_metrics(fit: PcaFit) -> tuple[EdaMetric, ...]:
    rows: list[EdaMetric] = []
    if fit.two_component is not None:
        rows.append(_metric(f"{fit.name}_two_component_share", fit.two_component, fit.n, "share"))
    for index, share in enumerate(fit.shares):
        rows.append(_metric(f"{fit.name}_share_pc{index + 1}", float(share), fit.n, "share"))
    for loading in fit.loadings:
        rows.append(
            _metric(
                f"{fit.name}_loading_pc{loading.component}_{loading.feature}",
                loading.value,
                fit.n,
                "loading",
                {"low": loading.low, "high": loading.high},
            )
        )
    if fit.condition_number is not None:
        rows.append(
            _metric(f"{fit.name}_condition_number", fit.condition_number, fit.n, "condition")
        )
    for feature, vif in fit.vifs.items():
        if vif is not None and math.isfinite(vif):
            rows.append(_metric(f"{fit.name}_vif_{feature}", vif, fit.n, "vif"))
    return tuple(rows)


def _metric(
    name: str,
    value: float,
    n: int,
    unit: str,
    dimensions: dict[str, object] | None = None,
) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        metric_value=value,
        n_underlying=n,
        geography_type="national",
        geography_id="US",
        dimensions=dimensions,
        unit=unit,
    )


def _pca_statement(fit: PcaFit, representation: str) -> str:
    if fit.two_component is None:
        return "The three-feature PCA is not estimable. Representation call: stop."
    return (
        f"Three-feature two-component share {_fmt(fit.two_component)} on n {fit.n}. "
        f"October 13 comparison target 0.8850. Representation call: {representation}."
    )


def _follow_statement(analysis: Analysis, top: PairResult | None) -> str:
    if top is None:
        return (
            f"Follow-up call: {analysis.follow_up}. "
            "No signed discovery row met the frozen gate of an interval off zero, "
            "a BH-adjusted tail share at most 0.05, a partial coefficient with the same sign, "
            "and a stable Census-region point."
        )
    low = None if top.cluster is None else top.cluster.low
    high = None if top.cluster is None else top.cluster.high
    return (
        f"Follow-up call: {analysis.follow_up}. Highest gated row {top.spec.pair_id} "
        f"{top.spec.label} estimate {_fmt(top.estimate)}, "
        f"state-cluster {_fmt(low)} to {_fmt(high)}, "
        f"partial {_fmt(top.partial)}. "
        "A later story can repeat that contrast. This run does not open it."
    )


def _recommendation_statement(analysis: Analysis) -> str:
    text = " ".join(analysis.recommendations)
    if len(text) > 1800:
        return text[:1800]
    return text


def _finding_disposition(follow_up: str) -> str:
    if follow_up == "advance":
        return "follow-up"
    if follow_up == "stop":
        return "stop"
    return "revise"


def _tail_pairs(pairs: Sequence[PairResult]) -> list[tuple[str, float]]:
    values: list[tuple[str, float]] = []
    for item in pairs:
        if item.cluster is None or item.cluster.tail_share is None:
            continue
        values.append((item.spec.pair_id, item.cluster.tail_share))
    return values


def _reproduction_method(name: str) -> str:
    if name in {"svi_human", "rucc_human"}:
        return "spearman"
    return "cramers_v"


def _reproduction_names(name: str) -> tuple[str, str]:
    mapping = {
        "tick_pathogen": ("TICK_STATUS", "BURGDORFERI_STATUS"),
        "human_tick": ("HUMAN_STATUS", "TICK_STATUS"),
        "human_pathogen": ("HUMAN_STATUS", "BURGDORFERI_STATUS"),
        "svi_human": ("SVI_PERCENTILE", "HUMAN_PUBLISHED_FLOOR"),
        "rucc_human": ("RUCC_2023", "HUMAN_PUBLISHED_FLOOR"),
    }
    return mapping[name]


def _fmt(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "not estimable"
    return f"{value:.4f}"


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CrossDomainError("required text is missing")
    return value.strip()


def _unit(value: object) -> float | None:
    return _float(value)


def _positive(value: object) -> float | None:
    number = _float(value)
    if number is None or number <= 0:
        return None
    return number


def _float(value: object) -> float | None:
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _rucc(value: object) -> int | None:
    number = _float(value)
    if number is None or not float(number).is_integer():
        return None
    code = int(number)
    if 1 <= code <= 9:
        return code
    return None


def _flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() == "true"
    number = _float(value)
    return number == 1
