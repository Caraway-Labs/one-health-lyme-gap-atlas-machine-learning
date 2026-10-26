"""Leave-state-out models of published-floor presence for issue 188.

The functions here do not open Snowflake. County rows stay in memory. The regime
feature reuses the issue 123 publication-free matrix and is rebuilt without the
held-out state's county outcomes. The descriptive regime is not fit.
"""

from __future__ import annotations

import math
import random
import warnings
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

import numpy as np
from sklearn.cluster import AgglomerativeClustering  # type: ignore[import-untyped]
from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import (  # type: ignore[import-untyped]
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.coverage_audit import PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.peer_clusters import sklearn_version
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import FindingRecord
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric
from lyme_gap_atlas_ml.state_regimes import (
    HUMAN_NONE,
    HUMAN_PUBLISHED,
    PATHOGEN_LEVELS,
    PATHOGEN_PRESENT,
    RURAL_CODES,
    TICK_ESTABLISHED,
    TICK_LEVELS,
    StateProfile,
    publication_free_raw,
)

Vector = np.ndarray[Any, Any]

SPEC_ID = "188-floor-presence-regime/v1"
ISSUE_NUMBER = 188
SCHEMA_VERSION = "2.0.0"
METHODOLOGY_VERSION = "semantic-2.0.0"
SCOPE = "US_COUNTIES"
EXPECTED_COUNTIES = 3144
EXPECTED_STATES = 51
EXPECTED_PUBLISHED = 651
EXPECTED_ABSENT = 2493
REGIME_K = 2
SEED_PRIMARY = 1882026
SEED_SECOND = 1882027
BOOTSTRAP_SEED = 1882030
PERMUTATION_SEED = 1882031
SHUFFLE_SEED = 1889001
BOOTSTRAP_REPLICATES = 2000
PERMUTATION_DRAWS = 30
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
PROBABILITY_CUT = 0.5
SMALL_CELL = 11
RUN_PREFIX = "188-floor-presence-regime-"
QUERY_NAMES = ("release_identity", "cohort_rows")
SOURCE_OBJECTS = (
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
)
FAMILY_LOGISTIC = "logistic"
FAMILY_GBT = "gradient_boosting"
FAMILIES = (FAMILY_LOGISTIC, FAMILY_GBT)
FEATURE_BASELINE = "baseline"
FEATURE_CHALLENGER = "challenger"
RUCC_LEVELS = (1, 2, 3, 4, 5, 6, 7, 8, 9)
REGIME_LEVELS = (1, 2)
BASELINE_FEATURES = (
    "svi_percentile",
    "uninsured_percentile",
    "log_population",
    "rucc",
)
CHALLENGER_FEATURES = (*BASELINE_FEATURES, "regime")
EXCLUDED_COLUMNS = (
    "CASE_COUNT_FLOOR_2023",
    "INCIDENCE_FLOOR_2023",
    "EVIDENCE_COMPLETENESS",
    "TIER1_SCORE",
    "LAND_COVER",
)


class FloorPresenceError(ValueError):
    """The floor-presence fit stopped before a comparable pair of models existed."""


@dataclass(frozen=True)
class FitConfig:
    """Compute budget. Decision thresholds stay module constants."""

    seeds: tuple[int, ...] = (SEED_PRIMARY, SEED_SECOND)
    gbt_max_iter: int = GBT_MAX_ITER
    gbt_min_samples_leaf: int = GBT_MIN_SAMPLES_LEAF
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES
    permutation_draws: int = PERMUTATION_DRAWS


@dataclass(frozen=True)
class ParsedCohort:
    counties: tuple[County, ...]
    svi_rescaled: bool
    uninsured_rescaled: bool


@dataclass(frozen=True)
class County:
    fips: str
    state: str
    population: float
    svi: float
    uninsured: float
    rucc: int
    published: int
    tick_established: bool
    pathogen_present: bool


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
class StateModelError:
    family: str
    feature_set: str
    brier: float
    mean_predicted: float
    errors_at_half: int


@dataclass(frozen=True)
class StateError:
    state: str
    county_n: int
    published_n: int
    models: tuple[StateModelError, ...]


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
class Importance:
    family: str
    feature_set: str
    feature: str
    auc_drop: float


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
class ModelMetricRow:
    split_name: str
    metric_name: str
    metric_value: float | None
    ci_low: float | None
    ci_high: float | None
    n: int | None


@dataclass(frozen=True)
class Decision:
    method: str
    product: str
    leakage_ok: bool
    logistic_real_lift: bool
    gbt_real_lift: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class _FoldModel:
    state: str
    baseline: Any
    challenger: Any
    scaler: Any
    test_index: tuple[int, ...]


@dataclass(frozen=True)
class _SeedFit:
    family: str
    seed: int
    baseline: Vector
    challenger: Vector
    folds: tuple[_FoldModel, ...]


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
    fits: tuple[FamilySeedResult, ...]
    state_errors: tuple[StateError, ...]
    calibration: tuple[CalibrationBin, ...]
    importance: tuple[Importance, ...]
    predictions: tuple[PredictionRow, ...]
    decision: Decision
    sklearn_version: str


def load_floor_queries(text: str) -> dict[str, str]:
    """Split the issue 188 validation file and reject unsafe SQL."""
    return load_marked_queries(text, QUERY_NAMES)


def release_matches(row: Mapping[str, object]) -> tuple[bool, tuple[str, ...]]:
    """Return whether the live release row is the pin frozen in the spec."""
    checks = (
        ("release_id", _text(row.get("RELEASE_ID")), PINNED_RELEASE_ID),
        ("schema_version", _text(row.get("SCHEMA_VERSION")), SCHEMA_VERSION),
        ("methodology_version", _text(row.get("METHODOLOGY_VERSION")), METHODOLOGY_VERSION),
        ("scope", _text(row.get("SCOPE")), SCOPE),
        ("bundle_sha256", _text(row.get("BUNDLE_SHA256")).lower(), PINNED_BUNDLE_SHA256),
    )
    reasons = tuple(name for name, found, expected in checks if found != expected)
    return not reasons, reasons


def parse_counties(
    rows: Sequence[Mapping[str, object]],
    *,
    release_id: str,
) -> ParsedCohort:
    """Validate the allow-listed columns and return counties sorted by FIPS."""
    seen: set[str] = set()
    parsed: list[County] = []
    for row in rows:
        if _text(row.get("RELEASE_ID")) != release_id:
            raise FloorPresenceError("county release id does not match the pin")
        fips = _fips(row.get("FIPS"))
        if fips in seen:
            raise FloorPresenceError("duplicate county id")
        seen.add(fips)
        human = _text(row.get("HUMAN_STATUS"))
        if human not in {HUMAN_PUBLISHED, HUMAN_NONE}:
            raise FloorPresenceError("human status is outside the allowed levels")
        tick_status = _text(row.get("TICK_STATUS"))
        pathogen_status = _text(row.get("BURGDORFERI_STATUS"))
        if tick_status not in TICK_LEVELS:
            raise FloorPresenceError("tick status is outside the allowed levels")
        if pathogen_status not in PATHOGEN_LEVELS:
            raise FloorPresenceError("pathogen status is outside the allowed levels")
        population = _positive(row.get("POPULATION"), "population")
        parsed.append(
            County(
                fips=fips,
                state=_state_code(row.get("STATE")),
                population=population,
                svi=_unit_interval(row.get("SVI_PERCENTILE"), "svi"),
                uninsured=_unit_interval(row.get("UNINSURED_PERCENTILE"), "uninsured"),
                rucc=_rucc(row.get("RUCC_2023")),
                published=1 if human == HUMAN_PUBLISHED else 0,
                tick_established=tick_status == TICK_ESTABLISHED,
                pathogen_present=pathogen_status == PATHOGEN_PRESENT,
            )
        )
    counties = tuple(sorted(parsed, key=lambda county: county.fips))
    _require_shape(counties)
    scaled, svi_rescaled, uninsured_rescaled = _rescale(counties)
    return ParsedCohort(
        counties=scaled,
        svi_rescaled=svi_rescaled,
        uninsured_rescaled=uninsured_rescaled,
    )


def analyze(
    counties: Sequence[County],
    *,
    config: FitConfig | None = None,
    expect_national: bool = True,
    svi_rescaled: bool = False,
    uninsured_rescaled: bool = False,
) -> Analysis:
    """Fit both families under the frozen leakage rule and apply the disposition."""
    budget = FitConfig() if config is None else config
    if budget.seeds[0] != SEED_PRIMARY or SEED_SECOND not in budget.seeds:
        raise FloorPresenceError("the frozen seeds are missing")
    ordered = tuple(sorted(counties, key=lambda county: county.fips))
    _require_analyzable(ordered, expect_national=expect_national)
    profiles = state_profiles(ordered)
    regime_maps = out_of_fold_regimes(profiles)
    invariant = _label_invariant(ordered, regime_maps)
    shuffled_lift = _shuffled_lift(ordered, budget)
    seed_fits = tuple(
        _fit_seed(ordered, regime_maps, family, seed, budget)
        for seed in budget.seeds
        for family in FAMILIES
    )
    by_state = _predictions_by_state(ordered, seed_fits)
    lifts = _bootstrap(by_state, budget.bootstrap_replicates)
    labels = np.array([county.published for county in ordered], dtype=int)
    fits = tuple(_family_result_from_probabilities(item, labels, lifts) for item in seed_fits)
    primary = tuple(item for item in seed_fits if item.seed == SEED_PRIMARY)
    importance = _importance(ordered, regime_maps, primary, budget.permutation_draws)
    published = sum(county.published for county in ordered)
    decision = decide(fits, leakage_invariant=invariant, shuffled_auc_lift=shuffled_lift)
    return Analysis(
        counties=len(ordered),
        published_n=published,
        absent_n=len(ordered) - published,
        states=len({county.state for county in ordered}),
        cohort_matches_expected=published == EXPECTED_PUBLISHED
        and len(ordered) - published == EXPECTED_ABSENT,
        svi_rescaled=svi_rescaled,
        uninsured_rescaled=uninsured_rescaled,
        leakage_invariant=invariant,
        shuffled_auc_lift=shuffled_lift,
        fits=fits,
        state_errors=_state_errors(ordered, primary),
        calibration=_calibration(ordered, primary),
        importance=importance,
        predictions=_prediction_rows(ordered, regime_maps, seed_fits),
        decision=decision,
        sklearn_version=sklearn_version(),
    )


def state_profiles(counties: Sequence[County]) -> tuple[StateProfile, ...]:
    """Roll counties to the #123 state profile. The stored median is not read."""
    grouped: dict[str, list[County]] = defaultdict(list)
    for county in counties:
        grouped[county.state].append(county)
    profiles: list[StateProfile] = []
    for state in sorted(grouped):
        rows = grouped[state]
        county_n = len(rows)
        published = sum(county.published for county in rows)
        tick = sum(county.tick_established for county in rows)
        pathogen = sum(county.pathogen_present for county in rows)
        rural = sum(county.rucc in RURAL_CODES for county in rows)
        profiles.append(
            StateProfile(
                state=state,
                county_n=county_n,
                published_n=published,
                tick_established_n=tick,
                pathogen_present_n=pathogen,
                rural_nonmetro_n=rural,
                published_share=published / county_n,
                tick_established_share=tick / county_n,
                pathogen_present_share=pathogen / county_n,
                rural_nonmetro_share=rural / county_n,
                median_published_floor=None,
                zero_published=published == 0,
            )
        )
    return tuple(profiles)


def out_of_fold_regimes(profiles: Sequence[StateProfile]) -> dict[str, dict[str, int]]:
    """Map held-out state to the group id used for every state in that fold.

    Training ids come from Ward on the other states. The held-out id is the
    nearest training centroid. The matrix is the #123 publication-free profile.
    """
    ordered = tuple(sorted(profiles, key=lambda profile: profile.state))
    if len(ordered) <= REGIME_K:
        raise FloorPresenceError("too few states to refit the regime")
    folds: dict[str, dict[str, int]] = {}
    for index, held in enumerate(ordered):
        train = ordered[:index] + ordered[index + 1 :]
        folds[held.state] = _assign_fold(train, held)
    return folds


def is_real_lift(
    auc: LiftInterval,
    pr_auc: LiftInterval,
    brier: LiftInterval,
    *,
    leakage_ok: bool,
) -> bool:
    """Apply the frozen lift rule. A failed leakage test cannot be a real lift."""
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


def decide(
    fits: Sequence[FamilySeedResult],
    *,
    leakage_invariant: bool,
    shuffled_auc_lift: float,
) -> Decision:
    """Apply the frozen method and product rules."""
    leakage_ok = leakage_invariant and abs(shuffled_auc_lift) < SHUFFLE_LIFT_MAX
    primary = tuple(item for item in fits if item.seed == SEED_PRIMARY)
    second = tuple(item for item in fits if item.seed == SEED_SECOND)
    reasons: list[str] = []
    if not leakage_invariant:
        reasons.append("label_invariance")
    if abs(shuffled_auc_lift) >= SHUFFLE_LIFT_MAX:
        reasons.append("shuffled_label")
    if not _complete(primary) or not _complete(second):
        reasons.append("seeds")
    logistic_gap = _seed_gap(fits, FAMILY_LOGISTIC, metrics=("roc_auc", "pr_auc", "brier"))
    gbt_gap = _seed_gap(fits, FAMILY_GBT, metrics=("roc_auc",))
    if logistic_gap > LOGISTIC_SEED_GAP_MAX:
        reasons.append("logistic_seed")
    if gbt_gap > GBT_SEED_GAP_MAX:
        reasons.append("gbt_seed")
    intervals_ok = all(
        item.auc_lift.estimable and item.pr_lift.estimable and item.brier_lift.estimable
        for item in primary
    )
    if not intervals_ok:
        reasons.append("bootstrap")
    by_family = {item.family: item for item in primary}
    logistic_lift = _family_lift(by_family.get(FAMILY_LOGISTIC), leakage_ok)
    gbt_lift = _family_lift(by_family.get(FAMILY_GBT), leakage_ok)
    method = "keep" if not reasons else "revise"
    real = int(logistic_lift) + int(gbt_lift)
    if method == "keep" and real == 2:
        product = "advance"
    elif method == "keep" and real == 0:
        product = "stop"
    else:
        product = "investigate"
    return Decision(
        method=method,
        product=product,
        leakage_ok=leakage_ok,
        logistic_real_lift=logistic_lift,
        gbt_real_lift=gbt_lift,
        reasons=tuple(reasons),
    )


def lab_metrics(analysis: Analysis) -> tuple[EdaMetric, ...]:
    """Aggregate metrics. A state with fewer than 11 counties is suppressed later."""
    rows: list[EdaMetric] = [
        _count_metric("county_n", analysis.counties),
        _count_metric("published_n", analysis.published_n),
        _count_metric("absent_n", analysis.absent_n),
        _national("shuffled_auc_lift", analysis.shuffled_auc_lift, "auc"),
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
                        {
                            "family": fit.family,
                            "feature_set": feature,
                            "seed": fit.seed,
                        },
                    )
                )
        for name, interval in (
            ("auc_lift", fit.auc_lift),
            ("pr_auc_lift", fit.pr_lift),
            ("brier_lift", fit.brier_lift),
        ):
            if interval.low is None or interval.high is None:
                continue
            point = (interval.low + interval.high) / 2.0
            rows.append(
                _dimension_metric(
                    name,
                    point,
                    analysis.counties,
                    {"family": fit.family, "seed": fit.seed, "endpoint": "mid"},
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
    for state in analysis.state_errors:
        for model in state.models:
            dimensions = {
                "family": model.family,
                "feature_set": model.feature_set,
                "seed": SEED_PRIMARY,
            }
            rows.append(
                EdaMetric(
                    metric_name="state_brier",
                    metric_value=model.brier,
                    n_underlying=state.county_n,
                    geography_type="state",
                    geography_id=state.state,
                    dimensions=dimensions,
                    unit="brier",
                )
            )
            rows.append(
                EdaMetric(
                    metric_name="state_mean_predicted",
                    metric_value=model.mean_predicted,
                    n_underlying=state.county_n,
                    geography_type="state",
                    geography_id=state.state,
                    dimensions=dimensions,
                    unit="probability",
                )
            )
            rows.append(
                EdaMetric(
                    metric_name="state_error_rate",
                    metric_value=model.errors_at_half / state.county_n,
                    n_underlying=state.county_n,
                    geography_type="state",
                    geography_id=state.state,
                    dimensions=dimensions,
                    unit="share",
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
    for item in analysis.importance:
        rows.append(
            _dimension_metric(
                "permutation_auc_drop",
                item.auc_drop,
                analysis.counties,
                {
                    "family": item.family,
                    "feature_set": item.feature_set,
                    "feature": item.feature,
                    "seed": SEED_PRIMARY,
                },
            )
        )
    return tuple(rows)


def lab_findings(analysis: Analysis) -> tuple[FindingRecord, ...]:
    """Two aggregate findings. Evidence stays free of county identifiers."""
    logistic = _primary(analysis, FAMILY_LOGISTIC)
    auc_lift = _point_lift(logistic.challenger.roc_auc, logistic.baseline.roc_auc)
    finding_method = FindingRecord(
        topic="floor_presence_method",
        statement=_method_statement(analysis),
        disposition=analysis.decision.method,
        n_underlying=analysis.counties,
        evidence={
            "leakage_ok": analysis.decision.leakage_ok,
            "product": analysis.decision.product,
            "reasons": list(analysis.decision.reasons),
        },
        effect_size=auc_lift,
        ci_low=logistic.auc_lift.low,
        ci_high=logistic.auc_lift.high,
        uncertainty_note=(
            "State-cluster bootstrap of out-of-fold predictions. Not a production score."
        ),
    )
    finding_product = FindingRecord(
        topic="floor_presence_product",
        statement=_product_statement(analysis),
        disposition=analysis.decision.method,
        n_underlying=analysis.counties,
        evidence={
            "logistic_real_lift": analysis.decision.logistic_real_lift,
            "gbt_real_lift": analysis.decision.gbt_real_lift,
            "shuffled_auc_lift": round(analysis.shuffled_auc_lift, 6),
        },
        effect_size=auc_lift,
        ci_low=logistic.auc_lift.low,
        ci_high=logistic.auc_lift.high,
        uncertainty_note="A real lift needs both leakage tests and the frozen interval gates.",
    )
    return (finding_method, finding_product)


def lab_experiments(analysis: Analysis, run_id: str) -> tuple[ExperimentRow, ...]:
    """One experiment row per family and feature set. The id includes the run id."""
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
            rows.append(
                ExperimentRow(
                    experiment_id=f"{run_id}-{family}-{feature}",
                    model_family=family,
                    hypothesis=(
                        "Demographics separate a published floor from its absence"
                        if feature == FEATURE_BASELINE
                        else "A leakage-safe state regime adds separation beyond demographics"
                    ),
                    config={
                        "spec": SPEC_ID,
                        "feature_set": feature,
                        "logistic_c": LOGISTIC_C,
                        "gbt_max_iter": GBT_MAX_ITER,
                        "gbt_max_depth": GBT_MAX_DEPTH,
                        "gbt_learning_rate": GBT_LEARNING_RATE,
                        "gbt_min_samples_leaf": GBT_MIN_SAMPLES_LEAF,
                        "gbt_l2": GBT_L2,
                        "regime_k": REGIME_K,
                        "sklearn": analysis.sklearn_version,
                    },
                    split_definition={
                        "scheme": "leave_state_out",
                        "states": EXPECTED_STATES,
                        "seeds": [SEED_PRIMARY, SEED_SECOND],
                        "bootstrap_seed": BOOTSTRAP_SEED,
                        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
                    },
                    status="succeeded",
                    metrics=tuple(metrics),
                )
            )
    return tuple(rows)


def _assign_fold(train: Sequence[StateProfile], held: StateProfile) -> dict[str, int]:
    if len(train) <= REGIME_K:
        raise FloorPresenceError("too few states to refit the regime")
    raw = publication_free_raw(train)
    scaler = StandardScaler()
    scaled = np.asarray(scaler.fit_transform(raw), dtype=np.float64)
    if not np.isfinite(scaled).all():
        raise FloorPresenceError("standardized regime matrix is not finite")
    labels = _relabel(_ward(scaled), tuple(profile.state for profile in train))
    centers: list[Vector] = []
    for group in REGIME_LEVELS:
        members = scaled[labels == group]
        if len(members) == 0:
            raise FloorPresenceError("regime group is empty")
        centers.append(np.asarray(members.mean(axis=0), dtype=np.float64))
    center_matrix = np.vstack(centers)
    held_raw = publication_free_raw((held,))
    held_scaled = np.asarray(scaler.transform(held_raw), dtype=np.float64)
    distances = ((held_scaled[:, None, :] - center_matrix[None, :, :]) ** 2).sum(axis=2)
    assigned = int(np.asarray(distances).argmin()) + 1
    mapping = {profile.state: int(labels[index]) for index, profile in enumerate(train)}
    mapping[held.state] = assigned
    return mapping


def _ward(scaled: Vector) -> Vector:
    model = AgglomerativeClustering(n_clusters=REGIME_K, linkage="ward")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = model.fit_predict(scaled)
    return np.asarray(fitted, dtype=int)


def _relabel(labels: Vector, names: Sequence[str]) -> Vector:
    raw_ids = sorted({int(label) for label in labels.tolist()})
    order = sorted(
        raw_ids,
        key=lambda label: (
            -int(np.sum(labels == label)),
            min(names[index] for index in range(len(names)) if int(labels[index]) == label),
        ),
    )
    mapping = {old: new for new, old in enumerate(order, start=1)}
    return np.asarray([mapping[int(label)] for label in labels], dtype=int)


def _label_invariant(
    counties: Sequence[County],
    original: Mapping[str, Mapping[str, int]],
) -> bool:
    for state in sorted({county.state for county in counties}):
        flipped = tuple(
            replace(county, published=1 - county.published) if county.state == state else county
            for county in counties
        )
        rebuilt = out_of_fold_regimes(state_profiles(flipped))
        if rebuilt != original:
            return False
    return True


def _shuffled_lift(counties: Sequence[County], config: FitConfig) -> float:
    shuffled = _shuffle_published(counties, SHUFFLE_SEED)
    profiles = state_profiles(shuffled)
    regimes = out_of_fold_regimes(profiles)
    fit = _fit_seed(shuffled, regimes, FAMILY_LOGISTIC, SEED_PRIMARY, config)
    base = _score(np.array([county.published for county in shuffled]), fit.baseline)
    challenger = _score(np.array([county.published for county in shuffled]), fit.challenger)
    return challenger.roc_auc - base.roc_auc


def _shuffle_published(counties: Sequence[County], seed: int) -> tuple[County, ...]:
    labels = [county.published for county in counties]
    random.Random(seed).shuffle(labels)
    return tuple(
        replace(county, published=label) for county, label in zip(counties, labels, strict=True)
    )


def _fit_seed(
    counties: Sequence[County],
    regimes: Mapping[str, Mapping[str, int]],
    family: str,
    seed: int,
    config: FitConfig,
) -> _SeedFit:
    index_by_state: dict[str, list[int]] = defaultdict(list)
    for index, county in enumerate(counties):
        index_by_state[county.state].append(index)
    states = sorted(index_by_state)
    numeric = _numeric_matrix(counties)
    rucc = np.array([county.rucc for county in counties], dtype=int)
    published = np.array([county.published for county in counties], dtype=int)
    baseline = np.zeros(len(counties), dtype=np.float64)
    challenger = np.zeros(len(counties), dtype=np.float64)
    folds: list[_FoldModel] = []
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
        y_train = published[train_index]
        if np.unique(y_train).size < 2:
            raise FloorPresenceError("a training fold has one outcome class")
        base_model = _fit_model(
            family,
            seed,
            _design(train_z, rucc[train_index], train_regime, challenger=False),
            y_train,
            config,
        )
        chal_model = _fit_model(
            family,
            seed,
            _design(train_z, rucc[train_index], train_regime, challenger=True),
            y_train,
            config,
        )
        baseline[test_index] = _proba(
            base_model,
            _design(test_z, rucc[test_index], test_regime, challenger=False),
        )
        challenger[test_index] = _proba(
            chal_model,
            _design(test_z, rucc[test_index], test_regime, challenger=True),
        )
        folds.append(
            _FoldModel(
                state=held,
                baseline=base_model,
                challenger=chal_model,
                scaler=scaler,
                test_index=tuple(int(index) for index in test_index),
            )
        )
    return _SeedFit(
        family=family,
        seed=seed,
        baseline=baseline,
        challenger=challenger,
        folds=tuple(folds),
    )


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
                raise FloorPresenceError("logistic regression did not converge")
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
    raise FloorPresenceError("unknown model family")


def _design(numeric_z: Vector, rucc: Vector, regime: Vector, *, challenger: bool) -> Vector:
    parts = [numeric_z, _one_hot(rucc, RUCC_LEVELS)]
    if challenger:
        parts.append(_one_hot(regime, REGIME_LEVELS))
    return np.hstack(parts)


def _one_hot(values: Vector, levels: tuple[int, ...]) -> Vector:
    columns = [(values == level).astype(np.float64) for level in levels]
    return np.column_stack(columns)


def _numeric_matrix(counties: Sequence[County]) -> Vector:
    return np.column_stack(
        [
            np.array([county.svi for county in counties], dtype=np.float64),
            np.array([county.uninsured for county in counties], dtype=np.float64),
            np.log(np.array([county.population for county in counties], dtype=np.float64)),
        ]
    )


def _proba(model: Any, features: Vector) -> Vector:
    probability = np.asarray(model.predict_proba(features)[:, 1], dtype=np.float64)
    if not np.isfinite(probability).all():
        raise FloorPresenceError("predicted probability is not finite")
    if np.any(probability < -1e-6) or np.any(probability > 1.0 + 1e-6):
        raise FloorPresenceError("predicted probability is outside 0 to 1")
    return np.clip(probability, 0.0, 1.0)


def _score(labels: Vector, probability: Vector) -> Score:
    if np.unique(labels).size < 2:
        raise FloorPresenceError("pooled outcomes have one class")
    return Score(
        roc_auc=float(roc_auc_score(labels, probability)),
        pr_auc=float(average_precision_score(labels, probability)),
        brier=float(brier_score_loss(labels, probability)),
    )


def _predictions_by_state(
    counties: Sequence[County],
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
        raise FloorPresenceError("primary logistic predictions are missing")
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


def _state_errors(counties: Sequence[County], fits: Sequence[_SeedFit]) -> tuple[StateError, ...]:
    labels = np.array([county.published for county in counties], dtype=int)
    states = np.array([county.state for county in counties])
    rows: list[StateError] = []
    for state in sorted(set(states.tolist())):
        chosen = states == state
        y = labels[chosen]
        models: list[StateModelError] = []
        for fit in fits:
            for feature, probability in (
                (FEATURE_BASELINE, fit.baseline[chosen]),
                (FEATURE_CHALLENGER, fit.challenger[chosen]),
            ):
                models.append(
                    StateModelError(
                        family=fit.family,
                        feature_set=feature,
                        brier=float(np.mean((probability - y) ** 2)),
                        mean_predicted=float(np.mean(probability)),
                        errors_at_half=int(np.sum((probability >= PROBABILITY_CUT) != (y == 1))),
                    )
                )
        rows.append(
            StateError(
                state=str(state),
                county_n=int(chosen.sum()),
                published_n=int(y.sum()),
                models=tuple(models),
            )
        )
    return tuple(rows)


def _calibration(
    counties: Sequence[County],
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


def _importance(
    counties: Sequence[County],
    regimes: Mapping[str, Mapping[str, int]],
    fits: Sequence[_SeedFit],
    draws: int,
) -> tuple[Importance, ...]:
    numeric = _numeric_matrix(counties)
    rucc = np.array([county.rucc for county in counties], dtype=int)
    regime = np.array(
        [regimes[county.state][county.state] for county in counties],
        dtype=int,
    )
    labels = np.array([county.published for county in counties], dtype=int)
    rng = random.Random(PERMUTATION_SEED)
    rows: list[Importance] = []
    columns = {
        FEATURE_BASELINE: BASELINE_FEATURES,
        FEATURE_CHALLENGER: CHALLENGER_FEATURES,
    }
    for fit in fits:
        for feature_set, names in columns.items():
            original = fit.baseline if feature_set == FEATURE_BASELINE else fit.challenger
            base_auc = float(roc_auc_score(labels, original))
            for name in names:
                drops: list[float] = []
                for _ in range(draws):
                    order = list(range(len(counties)))
                    rng.shuffle(order)
                    permuted = _permuted_probability(
                        fit,
                        feature_set,
                        name,
                        numeric,
                        rucc,
                        regime,
                        np.array(order, dtype=int),
                    )
                    drops.append(base_auc - float(roc_auc_score(labels, permuted)))
                rows.append(
                    Importance(
                        family=fit.family,
                        feature_set=feature_set,
                        feature=name,
                        auc_drop=float(np.mean(drops)),
                    )
                )
    return tuple(rows)


def _permuted_probability(
    fit: _SeedFit,
    feature_set: str,
    column: str,
    numeric: Vector,
    rucc: Vector,
    regime: Vector,
    order: Vector,
) -> Vector:
    numeric_p = np.array(numeric, copy=True)
    rucc_p = np.array(rucc, copy=True)
    regime_p = np.array(regime, copy=True)
    if column == "svi_percentile":
        numeric_p[:, 0] = numeric[order, 0]
    elif column == "uninsured_percentile":
        numeric_p[:, 1] = numeric[order, 1]
    elif column == "log_population":
        numeric_p[:, 2] = numeric[order, 2]
    elif column == "rucc":
        rucc_p = rucc[order]
    elif column == "regime":
        regime_p = regime[order]
    else:
        raise FloorPresenceError("unknown permutation column")
    probability = np.zeros(len(numeric), dtype=np.float64)
    challenger = feature_set == FEATURE_CHALLENGER
    for fold in fit.folds:
        test_index = np.array(fold.test_index, dtype=int)
        test_z = np.asarray(fold.scaler.transform(numeric_p[test_index]), dtype=np.float64)
        model = fold.challenger if challenger else fold.baseline
        probability[test_index] = _proba(
            model,
            _design(test_z, rucc_p[test_index], regime_p[test_index], challenger=challenger),
        )
    return probability


def _prediction_rows(
    counties: Sequence[County],
    regimes: Mapping[str, Mapping[str, int]],
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
                )
            )
    return tuple(rows)


def _family_result_from_probabilities(
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


def _complete(fits: Sequence[FamilySeedResult]) -> bool:
    return {item.family for item in fits} == set(FAMILIES)


def _seed_gap(fits: Sequence[FamilySeedResult], family: str, *, metrics: tuple[str, ...]) -> float:
    primary = next(
        (item for item in fits if item.family == family and item.seed == SEED_PRIMARY),
        None,
    )
    second = next(
        (item for item in fits if item.family == family and item.seed == SEED_SECOND),
        None,
    )
    if primary is None or second is None:
        return math.inf
    gap = 0.0
    for metric in metrics:
        for side in ("baseline", "challenger"):
            left = getattr(getattr(primary, side), metric)
            right = getattr(getattr(second, side), metric)
            gap = max(gap, abs(float(left) - float(right)))
    return gap


def _family_lift(fit: FamilySeedResult | None, leakage_ok: bool) -> bool:
    if fit is None:
        return False
    return is_real_lift(fit.auc_lift, fit.pr_lift, fit.brier_lift, leakage_ok=leakage_ok)


def _primary(analysis: Analysis, family: str) -> FamilySeedResult:
    for fit in analysis.fits:
        if fit.family == family and fit.seed == SEED_PRIMARY:
            return fit
    raise FloorPresenceError("primary fit is missing")


def _point_lift(challenger: float, baseline: float) -> float:
    return challenger - baseline


def _method_statement(analysis: Analysis) -> str:
    logistic = _primary(analysis, FAMILY_LOGISTIC)
    return (
        f"Method {analysis.decision.method}. "
        f"Logistic published-floor AUC baseline {logistic.baseline.roc_auc:.4f}, "
        f"challenger {logistic.challenger.roc_auc:.4f}. "
        f"Leakage invariant {analysis.leakage_invariant}. "
        "Not a production score."
    )


def _product_statement(analysis: Analysis) -> str:
    return (
        f"Product {analysis.decision.product}. "
        f"Logistic real lift {analysis.decision.logistic_real_lift}. "
        f"Tree real lift {analysis.decision.gbt_real_lift}. "
        "Predictions stay in the ML Lab."
    )


def _count_metric(name: str, count: int) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        metric_value=count,
        n_underlying=count,
        geography_type="national",
        geography_id="US",
        unit="count",
    )


def _national(name: str, value: float, unit: str) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        metric_value=value,
        n_underlying=EXPECTED_COUNTIES,
        geography_type="national",
        geography_id="US",
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
        geography_id="US",
        dimensions=dimensions,
        unit=name,
    )


def _lift_row(
    fit: FamilySeedResult,
    name: str,
    interval: LiftInterval,
    count: int,
) -> ModelMetricRow:
    point = None
    if interval.low is not None and interval.high is not None:
        if name == "auc_lift":
            point = fit.challenger.roc_auc - fit.baseline.roc_auc
        elif name == "pr_auc_lift":
            point = fit.challenger.pr_auc - fit.baseline.pr_auc
        else:
            point = fit.challenger.brier - fit.baseline.brier
    return ModelMetricRow(
        f"lso-{fit.seed}",
        name,
        point,
        interval.low,
        interval.high,
        count,
    )


def _require_shape(counties: Sequence[County]) -> None:
    if len(counties) != EXPECTED_COUNTIES:
        raise FloorPresenceError("county count is not 3144")
    states = {county.state for county in counties}
    if len(states) != EXPECTED_STATES:
        raise FloorPresenceError("state count is not 51")


def _require_analyzable(counties: Sequence[County], *, expect_national: bool) -> None:
    if expect_national:
        _require_shape(counties)
        return
    states = {county.state for county in counties}
    if len(states) <= REGIME_K + 1:
        raise FloorPresenceError("too few states to refit the regime")
    if len({county.published for county in counties}) < 2:
        raise FloorPresenceError("pooled outcomes have one class")


def _rescale(counties: tuple[County, ...]) -> tuple[tuple[County, ...], bool, bool]:
    svi_max = max(county.svi for county in counties)
    uninsured_max = max(county.uninsured for county in counties)
    svi_rescaled = svi_max > 1.5
    uninsured_rescaled = uninsured_max > 1.5
    svi_scale = 100.0 if svi_rescaled else 1.0
    uninsured_scale = 100.0 if uninsured_rescaled else 1.0
    scaled = tuple(
        replace(
            county,
            svi=county.svi / svi_scale,
            uninsured=county.uninsured / uninsured_scale,
        )
        for county in counties
    )
    for county in scaled:
        if not 0.0 <= county.svi <= 1.0 or not 0.0 <= county.uninsured <= 1.0:
            raise FloorPresenceError("a percentile is outside 0 to 1")
    return scaled, svi_rescaled, uninsured_rescaled


def _fips(value: object) -> str:
    if isinstance(value, Decimal):
        value = int(value)
    if isinstance(value, int) and not isinstance(value, bool):
        text = f"{value:05d}"
    elif isinstance(value, str) and value.strip().isdigit():
        text = value.strip().zfill(5)
    else:
        raise FloorPresenceError("county id is not five digits")
    if len(text) != 5:
        raise FloorPresenceError("county id is not five digits")
    return text


def _state_code(value: object) -> str:
    if not isinstance(value, str) or len(value.strip()) != 2 or not value.strip().isalpha():
        raise FloorPresenceError("state code is not two letters")
    return value.strip().upper()


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FloorPresenceError("required text is missing")
    return value.strip()


def _positive(value: object, label: str) -> float:
    number = _float(value, label)
    if number <= 0:
        raise FloorPresenceError(f"{label} is not positive")
    return number


def _unit_interval(value: object, label: str) -> float:
    number = _float(value, label)
    if number < 0:
        raise FloorPresenceError(f"{label} is negative")
    return number


def _float(value: object, label: str) -> float:
    if value is None or isinstance(value, bool):
        raise FloorPresenceError(f"{label} is missing")
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError as error:
            raise FloorPresenceError(f"{label} is not numeric") from error
    else:
        raise FloorPresenceError(f"{label} is not numeric")
    if not math.isfinite(number):
        raise FloorPresenceError(f"{label} is not finite")
    return number


def _rucc(value: object) -> int:
    if isinstance(value, bool) or value is None:
        raise FloorPresenceError("rural-urban code is missing")
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise FloorPresenceError("rural-urban code is not an integer")
        value = int(value)
    if isinstance(value, float):
        if not value.is_integer():
            raise FloorPresenceError("rural-urban code is not an integer")
        value = int(value)
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, int) and value in RUCC_LEVELS:
        return value
    raise FloorPresenceError("rural-urban code is outside 1 through 9")
