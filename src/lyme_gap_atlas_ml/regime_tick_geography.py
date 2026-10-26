"""Leave-state-out comparison of tick geography and the #188 regime.

Model A is tick geography plus the #188 context features. Model B adds the
publication-free regime id from ``out_of_fold_regimes``. A held-out state's
tick share uses tick status only. These functions do not open Snowflake.
"""

from __future__ import annotations

import math
import random
import statistics
import warnings
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import (  # type: ignore[import-untyped]
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.floor_presence import (
    County,
    out_of_fold_regimes,
    parse_counties,
    state_profiles,
)
from lyme_gap_atlas_ml.peer_clusters import sklearn_version
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import FindingRecord
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric
from lyme_gap_atlas_ml.state_regimes import (
    PATHOGEN_LEVELS,
    PATHOGEN_PRESENT,
    TICK_ESTABLISHED,
    TICK_LEVELS,
)

Vector = np.ndarray[Any, Any]

SPEC_ID = "194-regime-vs-tick-geography/v1"
ISSUE_NUMBER = 194
EXPECTED_COUNTIES = 3144
EXPECTED_STATES = 51
EXPECTED_PUBLISHED = 651
EXPECTED_ABSENT = 2493
SEED_PRIMARY = 1942026
SEED_SECOND = 1942027
BOOTSTRAP_SEED = 1942030
SHUFFLE_SEED = 1949001
BOOTSTRAP_REPLICATES = 2000
LOGISTIC_C = 1.0
LOGISTIC_MAX_ITER = 1000
GBT_MAX_ITER = 100
GBT_MAX_DEPTH = 3
GBT_LEARNING_RATE = 0.1
GBT_MIN_SAMPLES_LEAF = 20
GBT_L2 = 1.0
AUC_LIFT_MIN = 0.01
PR_LIFT_MIN = 0.0
BRIER_WORSE_MAX = 0.005
SHUFFLE_LIFT_MAX = 0.05
LOGISTIC_SEED_GAP_MAX = 1e-6
GBT_SEED_GAP_MAX = 0.02
CALIBRATION_BINS = 10
SMALL_CELL = 11
RUN_PREFIX = "194-regime-vs-tick-geography-"
QUERY_NAMES = ("release_identity", "cohort_rows")
SOURCE_OBJECTS = (
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
)
FAMILY_LOGISTIC = "logistic"
FAMILY_GBT = "gradient_boosting"
FAMILIES = (FAMILY_LOGISTIC, FAMILY_GBT)
FEATURE_BASELINE = "tick_geography"
FEATURE_CHALLENGER = "tick_geography_regime"
TICK_LEVEL_ORDER = ("Established", "Reported", "No records", "Unknown")
PATHOGEN_LEVEL_ORDER = ("Present", "No records", "Unknown")
RUCC_LEVELS = (1, 2, 3, 4, 5, 6, 7, 8, 9)
REGIME_LEVELS = (1, 2)
NUMERIC_FEATURES = (
    "svi_percentile",
    "uninsured_percentile",
    "log_population",
    "state_tick_established_share",
)
HISTOGRAM_EDGES = (-0.20, -0.10, 0.0, 0.10, 0.20)
REFERENCE_188_LOGISTIC = (0.8320, 0.9164, 0.0844, 0.0375, 0.1380)
REFERENCE_188_TREE = (0.8308, 0.9055, 0.0747, 0.0288, 0.1273)
EXCLUDED_COLUMNS = (
    "CASE_COUNT_FLOOR_2023",
    "INCIDENCE_FLOOR_2023",
    "EVIDENCE_COMPLETENESS",
    "TIER1_SCORE",
    "LAND_COVER",
    "PART_TEXT",
    "CONTEXT_LIMITATIONS",
    "GEOMETRY",
    "PAYLOAD",
)


class RegimeTickError(ValueError):
    """The comparison stopped before a pair of models existed."""


@dataclass(frozen=True)
class FitConfig:
    """Compute budget. Decision thresholds stay module constants."""

    seeds: tuple[int, ...] = (SEED_PRIMARY, SEED_SECOND)
    gbt_max_iter: int = GBT_MAX_ITER
    gbt_min_samples_leaf: int = GBT_MIN_SAMPLES_LEAF
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES


@dataclass(frozen=True)
class GeographyCounty:
    fips: str
    state: str
    population: float
    svi: float
    uninsured: float
    rucc: int
    published: int
    tick_status: str
    pathogen_status: str


@dataclass(frozen=True)
class ParsedGeography:
    counties: tuple[GeographyCounty, ...]
    svi_rescaled: bool
    uninsured_rescaled: bool


@dataclass(frozen=True)
class Score:
    roc_auc: float
    pr_auc: float
    brier: float


@dataclass(frozen=True)
class LiftInterval:
    low: float | None
    high: float | None
    estimable: bool
    failed: int


@dataclass(frozen=True)
class FamilySeedResult:
    family: str
    seed: int
    baseline: Score
    challenger: Score
    auc_lift: LiftInterval
    pr_lift: LiftInterval
    brier_lift: LiftInterval


@dataclass(frozen=True)
class StateLift:
    state: str
    county_n: int
    published_n: int
    family: str
    baseline_auc: float | None
    challenger_auc: float | None
    lift: float | None


@dataclass(frozen=True)
class StateLiftSummary:
    family: str
    estimable_n: int
    median_lift: float | None
    positive_n: int


@dataclass(frozen=True)
class CalibrationBin:
    family: str
    feature_set: str
    bin_index: int
    n: int
    probability_low: float
    probability_high: float
    mean_predicted: float
    observed_rate: float


@dataclass(frozen=True)
class PredictionRow:
    fips: str
    state: str
    published: int
    model_family: str
    seed: int
    baseline_probability: float
    challenger_probability: float
    oof_regime: int
    state_tick_share: float


@dataclass(frozen=True)
class ModelMetricRow:
    split_name: str
    metric_name: str
    metric_value: float | None
    ci_low: float | None
    ci_high: float | None
    n: int | None


@dataclass(frozen=True)
class ExperimentRow:
    experiment_id: str
    model_family: str
    hypothesis: str
    config: dict[str, object]
    split_definition: dict[str, object]
    status: str
    metrics: tuple[ModelMetricRow, ...]


@dataclass(frozen=True)
class Decision:
    method: str
    product: str
    leakage_ok: bool
    logistic_real_lift: bool
    tree_auc_positive: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Analysis:
    counties: int
    published_n: int
    absent_n: int
    states: int
    cohort_matches_expected: bool
    svi_rescaled: bool
    uninsured_rescaled: bool
    leakage_invariant: bool
    shuffled_auc_lift: float
    shuffle_baseline_gap: float
    fits: tuple[FamilySeedResult, ...]
    state_lifts: tuple[StateLift, ...]
    state_summaries: tuple[StateLiftSummary, ...]
    calibration: tuple[CalibrationBin, ...]
    predictions: tuple[PredictionRow, ...]
    decision: Decision
    sklearn_version: str


@dataclass(frozen=True)
class _SeedFit:
    family: str
    seed: int
    baseline: Vector
    challenger: Vector


def load_regime_queries(text: str) -> dict[str, str]:
    """Split the issue 194 validation file and reject unsafe SQL."""
    return load_marked_queries(text, QUERY_NAMES)


def feature_width(*, challenger: bool) -> int:
    """Return the frozen design-matrix width."""
    width = len(NUMERIC_FEATURES) + len(RUCC_LEVELS)
    width += len(TICK_LEVEL_ORDER) + len(PATHOGEN_LEVEL_ORDER)
    if challenger:
        width += len(REGIME_LEVELS)
    return width


def parse_geography(
    rows: Sequence[Mapping[str, object]],
    *,
    release_id: str,
) -> ParsedGeography:
    """Validate with the #188 parser, then keep the full tick and pathogen levels."""
    cohort = parse_counties(rows, release_id=release_id)
    statuses: dict[str, tuple[str, str]] = {}
    for row in rows:
        if _text(row.get("RELEASE_ID")) != release_id:
            raise RegimeTickError("county release id does not match the pin")
        fips = _fips(row.get("FIPS"))
        tick_status = _text(row.get("TICK_STATUS"))
        pathogen_status = _text(row.get("BURGDORFERI_STATUS"))
        if tick_status not in TICK_LEVELS or pathogen_status not in PATHOGEN_LEVELS:
            raise RegimeTickError("tick or pathogen status is outside the allowed levels")
        statuses[fips] = (tick_status, pathogen_status)
    counties: list[GeographyCounty] = []
    for county in cohort.counties:
        tick_status, pathogen_status = statuses[county.fips]
        counties.append(
            GeographyCounty(
                fips=county.fips,
                state=county.state,
                population=county.population,
                svi=county.svi,
                uninsured=county.uninsured,
                rucc=county.rucc,
                published=county.published,
                tick_status=tick_status,
                pathogen_status=pathogen_status,
            )
        )
    return ParsedGeography(
        counties=tuple(counties),
        svi_rescaled=cohort.svi_rescaled,
        uninsured_rescaled=cohort.uninsured_rescaled,
    )


def state_tick_shares(counties: Sequence[GeographyCounty]) -> dict[str, float]:
    """Return each state's established-tick share. Floors are not an input."""
    profiles = state_profiles(_as_floor(counties))
    return {profile.state: profile.tick_established_share for profile in profiles}


def shuffled_regime_maps(
    regime_maps: Mapping[str, Mapping[str, int]],
    seed: int,
) -> dict[str, dict[str, int]]:
    """Permute held-out regime ids across states and reuse each id in every fold."""
    states = tuple(sorted(regime_maps))
    if any(set(regime_maps[state]) != set(states) for state in states):
        raise RegimeTickError("regime map is missing a state")
    held_out = {state: int(regime_maps[state][state]) for state in states}
    drawn = list(states)
    random.Random(seed).shuffle(drawn)
    assigned = {states[index]: held_out[drawn[index]] for index in range(len(states))}
    return {held: {state: assigned[state] for state in states} for held in states}


def is_real_lift(
    auc: LiftInterval,
    pr_auc: LiftInterval,
    brier: LiftInterval,
    *,
    leakage_ok: bool,
) -> bool:
    """Apply the frozen pass rule for signal beyond tick geography."""
    return bool(
        leakage_ok
        and auc.estimable
        and auc.low is not None
        and auc.low > AUC_LIFT_MIN
        and pr_auc.estimable
        and pr_auc.low is not None
        and pr_auc.low > PR_LIFT_MIN
        and brier.estimable
        and brier.high is not None
        and brier.high < BRIER_WORSE_MAX
    )


def histogram_bins(lifts: Sequence[float]) -> tuple[tuple[str, int], ...]:
    """Fixed display bins. A bin with 1 to 10 states is omitted."""
    edges = HISTOGRAM_EDGES
    labels = (
        f"<= {edges[0]:.2f}",
        *[f"{edges[index]:.2f} to {edges[index + 1]:.2f}" for index in range(len(edges) - 1)],
        f"> {edges[-1]:.2f}",
    )
    counts = [0 for _ in labels]
    for lift in lifts:
        if lift <= edges[0]:
            counts[0] += 1
            continue
        placed = False
        for index in range(len(edges) - 1):
            if edges[index] < lift <= edges[index + 1]:
                counts[index + 1] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1
    return tuple(
        (label, count)
        for label, count in zip(labels, counts, strict=True)
        if count == 0 or count >= SMALL_CELL
    )


def analyze(
    counties: Sequence[GeographyCounty],
    *,
    config: FitConfig | None = None,
    expect_national: bool = True,
    svi_rescaled: bool = False,
    uninsured_rescaled: bool = False,
) -> Analysis:
    """Fit both families and apply the frozen disposition."""
    budget = FitConfig() if config is None else config
    if budget.seeds[0] != SEED_PRIMARY or SEED_SECOND not in budget.seeds:
        raise RegimeTickError("the frozen seeds are missing")
    ordered = tuple(sorted(counties, key=lambda county: county.fips))
    _require_analyzable(ordered, expect_national=expect_national)
    profiles = state_profiles(_as_floor(ordered))
    regime_maps = out_of_fold_regimes(profiles)
    invariant = _label_invariant(ordered, regime_maps)
    seed_fits = tuple(
        _fit_seed(ordered, regime_maps, family, seed, budget)
        for seed in budget.seeds
        for family in FAMILIES
    )
    shuffled_maps = shuffled_regime_maps(regime_maps, SHUFFLE_SEED)
    shuffled_fit = _fit_seed(ordered, shuffled_maps, FAMILY_LOGISTIC, SEED_PRIMARY, budget)
    labels = np.array([county.published for county in ordered], dtype=int)
    real_logistic = next(
        item for item in seed_fits if item.family == FAMILY_LOGISTIC and item.seed == SEED_PRIMARY
    )
    base_real = _score(labels, real_logistic.baseline)
    base_shuffled = _score(labels, shuffled_fit.baseline)
    chal_shuffled = _score(labels, shuffled_fit.challenger)
    shuffle_gap = abs(base_shuffled.roc_auc - base_real.roc_auc)
    shuffled_lift = chal_shuffled.roc_auc - base_shuffled.roc_auc
    by_state = _predictions_by_state(ordered, seed_fits)
    lifts = _bootstrap(by_state, budget.bootstrap_replicates)
    fits = tuple(_family_result(item, labels, lifts) for item in seed_fits)
    primary = tuple(item for item in seed_fits if item.seed == SEED_PRIMARY)
    state_lifts = _state_lifts(ordered, primary)
    summaries = _state_summaries(state_lifts)
    decision = decide(
        fits,
        leakage_invariant=invariant,
        shuffled_auc_lift=shuffled_lift,
        shuffle_baseline_gap=shuffle_gap,
    )
    shares = state_tick_shares(ordered)
    return Analysis(
        counties=len(ordered),
        published_n=int(labels.sum()),
        absent_n=len(ordered) - int(labels.sum()),
        states=len({county.state for county in ordered}),
        cohort_matches_expected=(
            len(ordered) == EXPECTED_COUNTIES
            and int(labels.sum()) == EXPECTED_PUBLISHED
            and len(ordered) - int(labels.sum()) == EXPECTED_ABSENT
        ),
        svi_rescaled=svi_rescaled,
        uninsured_rescaled=uninsured_rescaled,
        leakage_invariant=invariant,
        shuffled_auc_lift=shuffled_lift,
        shuffle_baseline_gap=shuffle_gap,
        fits=fits,
        state_lifts=state_lifts,
        state_summaries=summaries,
        calibration=_calibration(ordered, primary),
        predictions=_prediction_rows(ordered, regime_maps, shares, seed_fits),
        decision=decision,
        sklearn_version=sklearn_version(),
    )


def decide(
    fits: Sequence[FamilySeedResult],
    *,
    leakage_invariant: bool,
    shuffled_auc_lift: float,
    shuffle_baseline_gap: float,
) -> Decision:
    """Apply the frozen method and product rules."""
    leakage_ok = (
        leakage_invariant
        and abs(shuffled_auc_lift) < SHUFFLE_LIFT_MAX
        and shuffle_baseline_gap <= LOGISTIC_SEED_GAP_MAX
    )
    primary = tuple(item for item in fits if item.seed == SEED_PRIMARY)
    second = tuple(item for item in fits if item.seed == SEED_SECOND)
    reasons: list[str] = []
    if not leakage_invariant:
        reasons.append("label_invariance")
    if abs(shuffled_auc_lift) >= SHUFFLE_LIFT_MAX:
        reasons.append("shuffled_regime")
    if shuffle_baseline_gap > LOGISTIC_SEED_GAP_MAX:
        reasons.append("shuffle_baseline")
    if not _complete(primary) or not _complete(second):
        reasons.append("seeds")
    if _seed_gap(fits, FAMILY_LOGISTIC) > LOGISTIC_SEED_GAP_MAX:
        reasons.append("logistic_seed")
    if _seed_gap(fits, FAMILY_GBT, auc_only=True) > GBT_SEED_GAP_MAX:
        reasons.append("gbt_seed")
    intervals_ok = all(
        item.auc_lift.estimable and item.pr_lift.estimable and item.brier_lift.estimable
        for item in primary
    )
    if not intervals_ok:
        reasons.append("bootstrap")
    by_family = {item.family: item for item in primary}
    logistic = by_family.get(FAMILY_LOGISTIC)
    tree = by_family.get(FAMILY_GBT)
    logistic_lift = False
    if logistic is not None:
        logistic_lift = is_real_lift(
            logistic.auc_lift,
            logistic.pr_lift,
            logistic.brier_lift,
            leakage_ok=leakage_ok,
        )
    tree_positive = bool(
        tree is not None
        and tree.auc_lift.estimable
        and tree.auc_lift.low is not None
        and tree.auc_lift.low > 0.0
    )
    method = "keep" if not reasons else "revise"
    if method == "keep" and logistic_lift and tree_positive:
        product = "advance"
    elif method == "keep" and not logistic_lift:
        product = "stop"
    else:
        product = "investigate"
    return Decision(
        method=method,
        product=product,
        leakage_ok=leakage_ok,
        logistic_real_lift=logistic_lift,
        tree_auc_positive=tree_positive,
        reasons=tuple(reasons),
    )


def lab_metrics(analysis: Analysis) -> tuple[EdaMetric, ...]:
    """Aggregate metrics. A geographic denominator below 11 is suppressed by the writer."""
    rows: list[EdaMetric] = [
        _count_metric("county_n", analysis.counties),
        _count_metric("published_n", analysis.published_n),
        _count_metric("absent_n", analysis.absent_n),
        _national("shuffled_auc_lift", analysis.shuffled_auc_lift, "auc"),
        _national("shuffle_baseline_gap", analysis.shuffle_baseline_gap, "auc"),
        _national("label_invariant", 1.0 if analysis.leakage_invariant else 0.0, "indicator"),
    ]
    for fit in analysis.fits:
        for feature, score in (
            (FEATURE_BASELINE, fit.baseline),
            (FEATURE_CHALLENGER, fit.challenger),
        ):
            for name, value in (
                ("roc_auc", score.roc_auc),
                ("pr_auc", score.pr_auc),
                ("brier", score.brier),
            ):
                rows.append(
                    _dimension_metric(
                        name,
                        value,
                        analysis.counties,
                        {"family": fit.family, "feature_set": feature, "seed": fit.seed},
                    )
                )
        for name, interval, point in (
            ("auc_lift", fit.auc_lift, fit.challenger.roc_auc - fit.baseline.roc_auc),
            ("pr_auc_lift", fit.pr_lift, fit.challenger.pr_auc - fit.baseline.pr_auc),
            ("brier_lift", fit.brier_lift, fit.challenger.brier - fit.baseline.brier),
        ):
            if interval.low is None or interval.high is None:
                continue
            rows.append(
                _dimension_metric(
                    name,
                    point,
                    analysis.counties,
                    {"family": fit.family, "seed": fit.seed},
                )
            )
            rows.append(
                _dimension_metric(
                    f"{name}_low",
                    interval.low,
                    BOOTSTRAP_REPLICATES,
                    {"family": fit.family, "seed": fit.seed},
                )
            )
            rows.append(
                _dimension_metric(
                    f"{name}_high",
                    interval.high,
                    BOOTSTRAP_REPLICATES,
                    {"family": fit.family, "seed": fit.seed},
                )
            )
    for summary in analysis.state_summaries:
        if summary.median_lift is None:
            continue
        rows.append(
            _dimension_metric(
                "state_auc_lift_median",
                summary.median_lift,
                summary.estimable_n,
                {"family": summary.family, "seed": SEED_PRIMARY},
            )
        )
        rows.append(
            _count_dimension(
                "state_auc_lift_positive_n",
                summary.positive_n,
                summary.estimable_n,
                {"family": summary.family, "seed": SEED_PRIMARY},
            )
        )
    for lift in analysis.state_lifts:
        if lift.lift is None:
            continue
        rows.append(
            EdaMetric(
                metric_name="state_auc_lift",
                metric_value=lift.lift,
                n_underlying=lift.county_n,
                geography_type="state",
                geography_id=lift.state,
                dimensions={"family": lift.family, "seed": SEED_PRIMARY},
                unit="auc",
            )
        )
    for bin_row in analysis.calibration:
        if bin_row.n < SMALL_CELL:
            continue
        dimensions = {
            "family": bin_row.family,
            "feature_set": bin_row.feature_set,
            "bin": bin_row.bin_index,
            "seed": SEED_PRIMARY,
        }
        rows.append(
            _dimension_metric(
                "calibration_mean_predicted",
                bin_row.mean_predicted,
                bin_row.n,
                dimensions,
            )
        )
        rows.append(
            _dimension_metric(
                "calibration_observed_rate",
                bin_row.observed_rate,
                bin_row.n,
                dimensions,
            )
        )
    return tuple(rows)


def lab_findings(analysis: Analysis) -> tuple[FindingRecord, ...]:
    """Two aggregate findings. Evidence stays free of county identifiers."""
    logistic = _primary(analysis, FAMILY_LOGISTIC)
    point = logistic.challenger.roc_auc - logistic.baseline.roc_auc
    finding_method = FindingRecord(
        topic="regime_tick_method",
        statement=_method_statement(analysis),
        disposition=analysis.decision.method,
        n_underlying=analysis.counties,
        evidence={
            "leakage_ok": analysis.decision.leakage_ok,
            "product": analysis.decision.product,
            "reasons": list(analysis.decision.reasons),
        },
        effect_size=point,
        ci_low=logistic.auc_lift.low,
        ci_high=logistic.auc_lift.high,
        uncertainty_note=(
            "State-cluster bootstrap of out-of-fold predictions. Not a production score."
        ),
    )
    finding_product = FindingRecord(
        topic="regime_tick_product",
        statement=_product_statement(analysis),
        disposition=analysis.decision.method,
        n_underlying=analysis.counties,
        evidence={
            "logistic_real_lift": analysis.decision.logistic_real_lift,
            "tree_auc_positive": analysis.decision.tree_auc_positive,
            "shuffled_auc_lift": round(analysis.shuffled_auc_lift, 6),
        },
        effect_size=point,
        ci_low=logistic.auc_lift.low,
        ci_high=logistic.auc_lift.high,
        uncertainty_note="A pass needs the leakage tests and the frozen interval gates.",
    )
    return (finding_method, finding_product)


def lab_experiments(analysis: Analysis, run_id: str) -> tuple[ExperimentRow, ...]:
    """One experiment row per family and feature set."""
    rows: list[ExperimentRow] = []
    for family in FAMILIES:
        for feature in (FEATURE_BASELINE, FEATURE_CHALLENGER):
            metrics: list[ModelMetricRow] = []
            for fit in analysis.fits:
                if fit.family != family:
                    continue
                score = fit.baseline if feature == FEATURE_BASELINE else fit.challenger
                split = f"lso-{fit.seed}"
                metrics.extend(
                    (
                        ModelMetricRow(
                            split, "roc_auc", score.roc_auc, None, None, analysis.counties
                        ),
                        ModelMetricRow(
                            split, "pr_auc", score.pr_auc, None, None, analysis.counties
                        ),
                        ModelMetricRow(split, "brier", score.brier, None, None, analysis.counties),
                    )
                )
                if feature == FEATURE_CHALLENGER:
                    metrics.extend(
                        (
                            _lift_row(fit, "auc_lift", fit.auc_lift, analysis.counties),
                            _lift_row(fit, "pr_auc_lift", fit.pr_lift, analysis.counties),
                            _lift_row(fit, "brier_lift", fit.brier_lift, analysis.counties),
                        )
                    )
            hypothesis = (
                "Tick geography separates a published floor from its absence"
                if feature == FEATURE_BASELINE
                else "A leakage-safe state regime adds separation beyond tick geography"
            )
            rows.append(
                ExperimentRow(
                    experiment_id=f"{run_id}-{family}-{feature}",
                    model_family=family,
                    hypothesis=hypothesis,
                    config={
                        "spec": SPEC_ID,
                        "feature_set": feature,
                        "numeric_features": list(NUMERIC_FEATURES),
                        "tick_levels": list(TICK_LEVEL_ORDER),
                        "pathogen_levels": list(PATHOGEN_LEVEL_ORDER),
                        "logistic_c": LOGISTIC_C,
                        "gbt_max_iter": GBT_MAX_ITER,
                        "gbt_max_depth": GBT_MAX_DEPTH,
                        "gbt_learning_rate": GBT_LEARNING_RATE,
                        "gbt_min_samples_leaf": GBT_MIN_SAMPLES_LEAF,
                        "gbt_l2": GBT_L2,
                        "sklearn": analysis.sklearn_version,
                    },
                    split_definition={
                        "scheme": "leave_state_out",
                        "states": analysis.states,
                        "seeds": [SEED_PRIMARY, SEED_SECOND],
                        "bootstrap_seed": BOOTSTRAP_SEED,
                        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
                        "shuffle_seed": SHUFFLE_SEED,
                        "regime": "188-out-of-fold-publication-free",
                    },
                    status="succeeded",
                    metrics=tuple(metrics),
                )
            )
    return tuple(rows)


def _as_floor(counties: Sequence[GeographyCounty]) -> tuple[County, ...]:
    return tuple(
        County(
            fips=county.fips,
            state=county.state,
            population=county.population,
            svi=county.svi,
            uninsured=county.uninsured,
            rucc=county.rucc,
            published=county.published,
            tick_established=county.tick_status == TICK_ESTABLISHED,
            pathogen_present=county.pathogen_status == PATHOGEN_PRESENT,
        )
        for county in counties
    )


def _label_invariant(
    counties: Sequence[GeographyCounty],
    original: Mapping[str, Mapping[str, int]],
) -> bool:
    original_shares = state_tick_shares(counties)
    original_codes = tuple((county.tick_status, county.pathogen_status) for county in counties)
    for state in sorted({county.state for county in counties}):
        flipped = tuple(
            GeographyCounty(
                fips=county.fips,
                state=county.state,
                population=county.population,
                svi=county.svi,
                uninsured=county.uninsured,
                rucc=county.rucc,
                published=1 - county.published if county.state == state else county.published,
                tick_status=county.tick_status,
                pathogen_status=county.pathogen_status,
            )
            for county in counties
        )
        if state_tick_shares(flipped) != original_shares:
            return False
        codes = tuple((county.tick_status, county.pathogen_status) for county in flipped)
        if codes != original_codes:
            return False
        rebuilt = out_of_fold_regimes(state_profiles(_as_floor(flipped)))
        if rebuilt != original:
            return False
    return True


def _fit_seed(
    counties: Sequence[GeographyCounty],
    regimes: Mapping[str, Mapping[str, int]],
    family: str,
    seed: int,
    config: FitConfig,
) -> _SeedFit:
    index_by_state: dict[str, list[int]] = defaultdict(list)
    for index, county in enumerate(counties):
        index_by_state[county.state].append(index)
    states = sorted(index_by_state)
    shares = state_tick_shares(counties)
    numeric = _numeric_matrix(counties, shares)
    rucc = np.array([county.rucc for county in counties], dtype=int)
    tick = np.array([county.tick_status for county in counties])
    pathogen = np.array([county.pathogen_status for county in counties])
    published = np.array([county.published for county in counties], dtype=int)
    baseline = np.zeros(len(counties), dtype=np.float64)
    challenger = np.zeros(len(counties), dtype=np.float64)
    for held in states:
        test_index = np.array(index_by_state[held], dtype=int)
        train_index = np.array(
            [index for state in states if state != held for index in index_by_state[state]],
            dtype=int,
        )
        train_regime = np.array(
            [regimes[held][counties[int(index)].state] for index in train_index],
            dtype=int,
        )
        test_regime = np.array([regimes[held][held]] * len(test_index), dtype=int)
        scaler = StandardScaler()
        scaler.fit(numeric[train_index])
        train_z = np.asarray(scaler.transform(numeric[train_index]), dtype=np.float64)
        test_z = np.asarray(scaler.transform(numeric[test_index]), dtype=np.float64)
        if not np.isfinite(train_z).all() or not np.isfinite(test_z).all():
            raise RegimeTickError("scaled tick-geography features are not finite")
        y_train = published[train_index]
        if np.unique(y_train).size < 2:
            raise RegimeTickError("a training fold has one outcome class")
        train_x = _design(
            train_z,
            rucc[train_index],
            tick[train_index],
            pathogen[train_index],
            train_regime,
            challenger=False,
        )
        train_b = _design(
            train_z,
            rucc[train_index],
            tick[train_index],
            pathogen[train_index],
            train_regime,
            challenger=True,
        )
        test_x = _design(
            test_z,
            rucc[test_index],
            tick[test_index],
            pathogen[test_index],
            test_regime,
            challenger=False,
        )
        test_b = _design(
            test_z,
            rucc[test_index],
            tick[test_index],
            pathogen[test_index],
            test_regime,
            challenger=True,
        )
        base_model = _fit_model(family, seed, train_x, y_train, config)
        chal_model = _fit_model(family, seed, train_b, y_train, config)
        baseline[test_index] = _proba(base_model, test_x)
        challenger[test_index] = _proba(chal_model, test_b)
    return _SeedFit(family=family, seed=seed, baseline=baseline, challenger=challenger)


def _fit_model(
    family: str,
    seed: int,
    features: Vector,
    labels: Vector,
    config: FitConfig,
) -> Any:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if family == FAMILY_LOGISTIC:
            model = LogisticRegression(
                C=LOGISTIC_C,
                l1_ratio=0.0,
                solver="lbfgs",
                max_iter=LOGISTIC_MAX_ITER,
                random_state=seed,
            )
            model.fit(features, labels)
            if int(np.max(model.n_iter_)) >= LOGISTIC_MAX_ITER:
                raise RegimeTickError("logistic regression did not converge")
            return model
        if family == FAMILY_GBT:
            model = HistGradientBoostingClassifier(
                max_iter=config.gbt_max_iter,
                max_depth=GBT_MAX_DEPTH,
                learning_rate=GBT_LEARNING_RATE,
                min_samples_leaf=config.gbt_min_samples_leaf,
                l2_regularization=GBT_L2,
                early_stopping=False,
                random_state=seed,
            )
            model.fit(features, labels)
            return model
    raise RegimeTickError("unknown model family")


def _design(
    numeric_z: Vector,
    rucc: Vector,
    tick: Vector,
    pathogen: Vector,
    regime: Vector,
    *,
    challenger: bool,
) -> Vector:
    parts = [
        numeric_z,
        _one_hot_int(rucc, RUCC_LEVELS),
        _one_hot_text(tick, TICK_LEVEL_ORDER),
        _one_hot_text(pathogen, PATHOGEN_LEVEL_ORDER),
    ]
    if challenger:
        parts.append(_one_hot_int(regime, REGIME_LEVELS))
    return np.hstack(parts)


def _one_hot_int(values: Vector, levels: tuple[int, ...]) -> Vector:
    columns = [(values == level).astype(np.float64) for level in levels]
    return np.column_stack(columns)


def _one_hot_text(values: Vector, levels: tuple[str, ...]) -> Vector:
    columns = [(values == level).astype(np.float64) for level in levels]
    return np.column_stack(columns)


def _numeric_matrix(
    counties: Sequence[GeographyCounty],
    shares: Mapping[str, float],
) -> Vector:
    return np.column_stack(
        [
            np.array([county.svi for county in counties], dtype=np.float64),
            np.array([county.uninsured for county in counties], dtype=np.float64),
            np.log(np.array([county.population for county in counties], dtype=np.float64)),
            np.array([shares[county.state] for county in counties], dtype=np.float64),
        ]
    )


def _proba(model: Any, features: Vector) -> Vector:
    probability = np.asarray(model.predict_proba(features)[:, 1], dtype=np.float64)
    if not np.isfinite(probability).all():
        raise RegimeTickError("predicted probability is not finite")
    if np.any(probability < -1e-6) or np.any(probability > 1.0 + 1e-6):
        raise RegimeTickError("predicted probability is outside 0 to 1")
    return np.clip(probability, 0.0, 1.0)


def _score(labels: Vector, probability: Vector) -> Score:
    if np.unique(labels).size < 2:
        raise RegimeTickError("pooled outcomes have one class")
    return Score(
        roc_auc=float(roc_auc_score(labels, probability)),
        pr_auc=float(average_precision_score(labels, probability)),
        brier=float(brier_score_loss(labels, probability)),
    )


def _predictions_by_state(
    counties: Sequence[GeographyCounty],
    fits: Sequence[_SeedFit],
) -> dict[tuple[str, int], dict[str, tuple[Vector, Vector, Vector]]]:
    grouped: dict[tuple[str, int], dict[str, tuple[Vector, Vector, Vector]]] = {}
    labels = np.array([county.published for county in counties], dtype=int)
    states = np.array([county.state for county in counties])
    for fit in fits:
        by_state: dict[str, tuple[Vector, Vector, Vector]] = {}
        for state in sorted(set(states.tolist())):
            chosen = states == state
            by_state[str(state)] = (labels[chosen], fit.baseline[chosen], fit.challenger[chosen])
        grouped[(fit.family, fit.seed)] = by_state
    return grouped


def _bootstrap(
    by_state: Mapping[tuple[str, int], Mapping[str, tuple[Vector, Vector, Vector]]],
    replicates: int,
) -> dict[tuple[str, int], tuple[LiftInterval, LiftInterval, LiftInterval]]:
    sample = by_state.get((FAMILY_LOGISTIC, SEED_PRIMARY))
    if sample is None:
        raise RegimeTickError("primary logistic predictions are missing")
    states = tuple(sorted(sample))
    rng = random.Random(BOOTSTRAP_SEED)
    draws = [
        tuple(states[rng.randrange(len(states))] for _ in range(len(states)))
        for _ in range(replicates)
    ]
    results: dict[tuple[str, int], tuple[LiftInterval, LiftInterval, LiftInterval]] = {}
    for key, groups in by_state.items():
        auc_values: list[float | None] = []
        pr_values: list[float | None] = []
        brier_values: list[float | None] = []
        for draw in draws:
            pooled = _pooled(draw, groups)
            if pooled is None:
                auc_values.append(None)
                pr_values.append(None)
                brier_values.append(None)
                continue
            labels, baseline, challenger = pooled
            base = _score(labels, baseline)
            chal = _score(labels, challenger)
            auc_values.append(chal.roc_auc - base.roc_auc)
            pr_values.append(chal.pr_auc - base.pr_auc)
            brier_values.append(chal.brier - base.brier)
        results[key] = (
            _interval(auc_values, replicates),
            _interval(pr_values, replicates),
            _interval(brier_values, replicates),
        )
    return results


def _pooled(
    draw: Sequence[str],
    groups: Mapping[str, tuple[Vector, Vector, Vector]],
) -> tuple[Vector, Vector, Vector] | None:
    labels = np.concatenate([groups[state][0] for state in draw])
    if np.unique(labels).size < 2:
        return None
    baseline = np.concatenate([groups[state][1] for state in draw])
    challenger = np.concatenate([groups[state][2] for state in draw])
    return labels, baseline, challenger


def _interval(values: Sequence[float | None], replicates: int) -> LiftInterval:
    finite = [float(value) for value in values if value is not None and math.isfinite(value)]
    failed = replicates - len(finite)
    if failed * 100 > replicates * 5 or len(finite) < 2:
        return LiftInterval(None, None, False, failed)
    ordered = sorted(finite)
    return LiftInterval(_quantile(ordered, 0.025), _quantile(ordered, 0.975), True, failed)


def _quantile(ordered: Sequence[float], probability: float) -> float:
    index = (len(ordered) - 1) * probability
    low = math.floor(index)
    high = math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def _family_result(
    fit: _SeedFit,
    labels: Vector,
    lifts: Mapping[tuple[str, int], tuple[LiftInterval, LiftInterval, LiftInterval]],
) -> FamilySeedResult:
    auc, pr_auc, brier = lifts[(fit.family, fit.seed)]
    return FamilySeedResult(
        family=fit.family,
        seed=fit.seed,
        baseline=_score(labels, fit.baseline),
        challenger=_score(labels, fit.challenger),
        auc_lift=auc,
        pr_lift=pr_auc,
        brier_lift=brier,
    )


def _state_lifts(
    counties: Sequence[GeographyCounty],
    fits: Sequence[_SeedFit],
) -> tuple[StateLift, ...]:
    labels = np.array([county.published for county in counties], dtype=int)
    states = np.array([county.state for county in counties])
    rows: list[StateLift] = []
    for state in sorted(set(states.tolist())):
        chosen = states == state
        y = labels[chosen]
        both = int(np.unique(y).size) == 2
        for fit in fits:
            base = fit.baseline[chosen]
            chal = fit.challenger[chosen]
            if not both:
                rows.append(
                    StateLift(
                        state=str(state),
                        county_n=int(chosen.sum()),
                        published_n=int(y.sum()),
                        family=fit.family,
                        baseline_auc=None,
                        challenger_auc=None,
                        lift=None,
                    )
                )
                continue
            base_auc = float(roc_auc_score(y, base))
            chal_auc = float(roc_auc_score(y, chal))
            rows.append(
                StateLift(
                    state=str(state),
                    county_n=int(chosen.sum()),
                    published_n=int(y.sum()),
                    family=fit.family,
                    baseline_auc=base_auc,
                    challenger_auc=chal_auc,
                    lift=chal_auc - base_auc,
                )
            )
    return tuple(rows)


def _state_summaries(lifts: Sequence[StateLift]) -> tuple[StateLiftSummary, ...]:
    rows: list[StateLiftSummary] = []
    for family in FAMILIES:
        chosen = [
            item.lift
            for item in lifts
            if item.family == family and item.county_n >= SMALL_CELL and item.lift is not None
        ]
        if not chosen:
            rows.append(StateLiftSummary(family, 0, None, 0))
            continue
        rows.append(
            StateLiftSummary(
                family=family,
                estimable_n=len(chosen),
                median_lift=float(statistics.median(chosen)),
                positive_n=sum(item > 0 for item in chosen),
            )
        )
    return tuple(rows)


def _calibration(
    counties: Sequence[GeographyCounty],
    fits: Sequence[_SeedFit],
) -> tuple[CalibrationBin, ...]:
    labels = np.array([county.published for county in counties], dtype=int)
    rows: list[CalibrationBin] = []
    for fit in fits:
        for feature, probability in (
            (FEATURE_BASELINE, fit.baseline),
            (FEATURE_CHALLENGER, fit.challenger),
        ):
            order = np.argsort(probability, kind="mergesort")
            for index, chosen in enumerate(np.array_split(order, CALIBRATION_BINS), start=1):
                if len(chosen) == 0:
                    continue
                pp = probability[chosen]
                yy = labels[chosen]
                rows.append(
                    CalibrationBin(
                        family=fit.family,
                        feature_set=feature,
                        bin_index=index,
                        n=int(len(chosen)),
                        probability_low=float(np.min(pp)),
                        probability_high=float(np.max(pp)),
                        mean_predicted=float(np.mean(pp)),
                        observed_rate=float(np.mean(yy)),
                    )
                )
    return tuple(rows)


def _prediction_rows(
    counties: Sequence[GeographyCounty],
    regimes: Mapping[str, Mapping[str, int]],
    shares: Mapping[str, float],
    fits: Sequence[_SeedFit],
) -> tuple[PredictionRow, ...]:
    rows: list[PredictionRow] = []
    for fit in fits:
        for index, county in enumerate(counties):
            rows.append(
                PredictionRow(
                    fips=county.fips,
                    state=county.state,
                    published=county.published,
                    model_family=fit.family,
                    seed=fit.seed,
                    baseline_probability=float(fit.baseline[index]),
                    challenger_probability=float(fit.challenger[index]),
                    oof_regime=int(regimes[county.state][county.state]),
                    state_tick_share=float(shares[county.state]),
                )
            )
    return tuple(rows)


def _complete(fits: Sequence[FamilySeedResult]) -> bool:
    return {item.family for item in fits} == set(FAMILIES)


def _seed_gap(
    fits: Sequence[FamilySeedResult],
    family: str,
    *,
    auc_only: bool = False,
) -> float:
    pair = [item for item in fits if item.family == family]
    if len(pair) < 2:
        return math.inf
    first, second = pair[0], pair[1]
    names = ("roc_auc",) if auc_only else ("roc_auc", "pr_auc", "brier")
    gaps: list[float] = []
    for name in names:
        for feature in ("baseline", "challenger"):
            left = getattr(getattr(first, feature), name)
            right = getattr(getattr(second, feature), name)
            gaps.append(abs(float(left) - float(right)))
    return max(gaps)


def _primary(analysis: Analysis, family: str) -> FamilySeedResult:
    for fit in analysis.fits:
        if fit.family == family and fit.seed == SEED_PRIMARY:
            return fit
    raise RegimeTickError("primary fit is missing")


def _method_statement(analysis: Analysis) -> str:
    logistic = _primary(analysis, FAMILY_LOGISTIC)
    point = logistic.challenger.roc_auc - logistic.baseline.roc_auc
    return (
        f"Method {analysis.decision.method}. "
        f"Logistic ROC-AUC lift {point:.4f}. "
        f"Label invariance {analysis.leakage_invariant}. "
        f"Shuffled-regime lift {analysis.shuffled_auc_lift:.4f}."
    )


def _product_statement(analysis: Analysis) -> str:
    if analysis.decision.logistic_real_lift:
        claim = "The regime clears the frozen bar beyond tick geography."
    else:
        claim = _miss_sentence(analysis)
    return (
        f"Product {analysis.decision.product}. {claim} "
        "This is a reporting pattern, not a disease burden."
    )


def _miss_sentence(analysis: Analysis) -> str:
    logistic = _primary(analysis, FAMILY_LOGISTIC)
    point = logistic.challenger.roc_auc - logistic.baseline.roc_auc
    high = logistic.auc_lift.high
    low = logistic.auc_lift.low
    if high is not None and high <= 0:
        return "The regime lift disappears once tick geography is in the model."
    if abs(point) < 0.01 and (low is None or low <= 0.01):
        return "The regime lift disappears once tick geography is in the model."
    if point > 0 and (low is None or low <= AUC_LIFT_MIN):
        return "The point lift is positive and does not clear the frozen bar."
    if point < 0:
        return "The regime lift disappears once tick geography is in the model."
    return "The logistic pass rule fails."


def _count_metric(name: str, count: int) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        metric_value=float(count),
        n_underlying=max(count, SMALL_CELL),
        geography_type="national",
        unit="count",
    )


def _national(name: str, value: float, unit: str) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        metric_value=value,
        n_underlying=EXPECTED_COUNTIES,
        geography_type="national",
        unit=unit,
    )


def _dimension_metric(
    name: str,
    value: float,
    count: int,
    dimensions: dict[str, object],
) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        metric_value=value,
        n_underlying=count,
        geography_type="national",
        dimensions=dimensions,
        unit="auc" if "auc" in name or name == "roc_auc" else "value",
    )


def _count_dimension(
    name: str,
    value: int,
    count: int,
    dimensions: dict[str, object],
) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        metric_value=float(value),
        n_underlying=count,
        geography_type="national",
        dimensions=dimensions,
        unit="count",
    )


def _lift_row(
    fit: FamilySeedResult,
    name: str,
    interval: LiftInterval,
    count: int,
) -> ModelMetricRow:
    point = {
        "auc_lift": fit.challenger.roc_auc - fit.baseline.roc_auc,
        "pr_auc_lift": fit.challenger.pr_auc - fit.baseline.pr_auc,
        "brier_lift": fit.challenger.brier - fit.baseline.brier,
    }[name]
    if not interval.estimable:
        return ModelMetricRow(f"lso-{fit.seed}", name, None, None, None, count)
    return ModelMetricRow(
        f"lso-{fit.seed}",
        name,
        point,
        interval.low,
        interval.high,
        count,
    )


def _require_analyzable(
    counties: Sequence[GeographyCounty],
    *,
    expect_national: bool,
) -> None:
    if expect_national and len(counties) != EXPECTED_COUNTIES:
        raise RegimeTickError("county count is not 3144")
    states = {county.state for county in counties}
    if expect_national and len(states) != EXPECTED_STATES:
        raise RegimeTickError("state count is not 51")
    if len(states) <= 3:
        raise RegimeTickError("too few states to refit the regime")
    fips = [county.fips for county in counties]
    if len(fips) != len(set(fips)):
        raise RegimeTickError("duplicate county id")
    for county in counties:
        if county.tick_status not in TICK_LEVELS:
            raise RegimeTickError("tick status is outside the allowed levels")
        if county.pathogen_status not in PATHOGEN_LEVELS:
            raise RegimeTickError("pathogen status is outside the allowed levels")
        if county.published not in (0, 1):
            raise RegimeTickError("published indicator is not 0 or 1")
    if len({county.published for county in counties}) < 2:
        raise RegimeTickError("the cohort has one outcome class")


def _fips(value: object) -> str:
    if isinstance(value, Decimal):
        value = int(value)
    if isinstance(value, int) and not isinstance(value, bool):
        text = f"{value:05d}"
    elif isinstance(value, str) and value.strip().isdigit():
        text = value.strip().zfill(5)
    else:
        raise RegimeTickError("county id is not five digits")
    if len(text) != 5:
        raise RegimeTickError("county id is not five digits")
    return text


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RegimeTickError("required text is missing")
    return value.strip()
