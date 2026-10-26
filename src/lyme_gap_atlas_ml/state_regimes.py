"""State reporting-regime groups for issue 123.

The functions here do not open Snowflake. County rows stay in memory long enough
to become 51 state profiles. A missing published floor is never stored as zero.
"""

from __future__ import annotations

import math
import statistics
import warnings
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np
from sklearn.cluster import AgglomerativeClustering  # type: ignore[import-untyped]
from sklearn.metrics import adjusted_rand_score, silhouette_score  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.coverage_audit import PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.peer_clusters import sklearn_version
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import FindingRecord
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric
from lyme_gap_atlas_ml.test_selection import REPLICATES, IntervalEstimate, resample_interval

Vector = np.ndarray[Any, Any]

SPEC_ID = "123-state-reporting-regimes/v1"
ISSUE_NUMBER = 123
SCHEMA_VERSION = "2.0.0"
METHODOLOGY_VERSION = "semantic-2.0.0"
SCOPE = "US_COUNTIES"
EXPECTED_COUNTIES = 3144
EXPECTED_STATES = 51
EXPECTED_ZERO_STATES = 19
EXPECTED_ZERO_COUNTIES = 1437
K_GRID = (2, 3, 4, 5, 6)
SEED_DESCRIPTIVE = 1232026
SEED_PUBLICATION_FREE = 1232027
SMALL_CELL = 11
SILHOUETTE_KEEP = 0.25
LOSO_ADMISSIBLE = 0.70
LOSO_KEEP = 0.80
BOOT_LOW_ADMISSIBLE = 0.40
BOOT_LOW_KEEP = 0.50
ARI_FEATURE_MAX = 0.50
HIGH_PUBLISHED_SHARE = 0.5
RUN_PREFIX = "123-state-reporting-regimes-"
QUERY_NAMES = ("release_identity", "state_rows")
SOURCE_OBJECTS = (
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
)
HUMAN_PUBLISHED = "published_count_floor"
HUMAN_NONE = "no_county_linked_record"
TICK_ESTABLISHED = "Established"
PATHOGEN_PRESENT = "Present"
TICK_LEVELS = frozenset({TICK_ESTABLISHED, "Reported", "No records", "Unknown"})
PATHOGEN_LEVELS = frozenset({PATHOGEN_PRESENT, "No records", "Unknown"})
RURAL_CODES = frozenset({4, 5, 6, 7, 8, 9})
NORTHEAST_STATES = frozenset({"CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"})
DESCRIPTIVE_FEATURES = (
    "published_share",
    "tick_established_share",
    "pathogen_present_share",
    "median_observed",
    "median_coordinate",
)
PUBLICATION_FREE_FEATURES = (
    "tick_established_share",
    "pathogen_present_share",
    "rural_nonmetro_share",
)
PROFILE_SEEDS = {
    "descriptive": SEED_DESCRIPTIVE,
    "publication_free": SEED_PUBLICATION_FREE,
}


class StateRegimeError(ValueError):
    """The state-regime fit stopped before a partition was accepted."""


@dataclass(frozen=True)
class StateProfile:
    state: str
    county_n: int
    published_n: int
    tick_established_n: int
    pathogen_present_n: int
    rural_nonmetro_n: int
    published_share: float
    tick_established_share: float
    pathogen_present_share: float
    rural_nonmetro_share: float
    median_published_floor: float | None
    zero_published: bool


@dataclass(frozen=True)
class KFit:
    k: int
    labels: tuple[int, ...]
    silhouette: float | None
    loso_median: float | None
    loso_min: float | None
    loso_failed: int
    bootstrap_low: float | None
    bootstrap_high: float | None
    bootstrap_estimable: bool
    bootstrap_failed: int
    admissible: bool


@dataclass(frozen=True)
class ProfileFit:
    name: str
    features: tuple[str, ...]
    seed: int
    chosen: KFit
    fits: tuple[KFit, ...]
    labels: tuple[int, ...]
    cut_stable: bool
    average_ari: float
    complete_ari: float
    share_only_ari: float | None
    tree_ari: float
    cut_height: float
    leaf_order: tuple[int, ...]
    children: tuple[tuple[int, int], ...]
    distances: tuple[float, ...]
    median_contrast: bool


@dataclass(frozen=True)
class QuestionLabels:
    northeast_high_group: int | None
    northeast_high_states: tuple[str, ...]
    zero_published_group: int | None
    zero_published_states: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    method: str
    product: str
    feature_profile: str | None
    reasons: tuple[str, ...]


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
class AssignmentRow:
    state: str
    county_n: int | None
    published_share: float | None
    tick_established_share: float | None
    pathogen_present_share: float | None
    median_published_floor: float | None
    rural_nonmetro_share: float | None
    descriptive_group: int
    publication_free_group: int
    zero_published: bool | None


@dataclass(frozen=True)
class Analysis:
    states: tuple[StateProfile, ...]
    descriptive: ProfileFit
    publication_free: ProfileFit
    cross_ari: float
    contingency: tuple[tuple[int, ...], ...]
    descriptive_ids: tuple[int, ...]
    publication_free_ids: tuple[int, ...]
    zero_states: int
    zero_counties: int
    matches_107: bool
    questions: QuestionLabels
    decision: Decision
    sklearn_version: str


def load_state_queries(text: str) -> dict[str, str]:
    """Split the issue 123 validation file and reject unsafe SQL."""
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


def aggregate_states(
    rows: Sequence[Mapping[str, object]],
    *,
    release_id: str,
) -> tuple[StateProfile, ...]:
    """Build one profile per state. A county with no floor does not contribute a zero."""
    seen: set[str] = set()
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if _text(row.get("RELEASE_ID")) != release_id:
            raise StateRegimeError("county release id does not match the pin")
        fips = _fips(row.get("FIPS"))
        if fips in seen:
            raise StateRegimeError("duplicate county id")
        seen.add(fips)
        grouped[_state_code(row.get("STATE"))].append(row)
    if len(seen) != len(rows):
        raise StateRegimeError("county id check did not cover every row")
    return tuple(_profile(state, grouped[state]) for state in sorted(grouped))


def require_cohort(states: Sequence[StateProfile]) -> None:
    """Stop unless the atlas still has 3,144 counties and 51 states."""
    if len(states) != EXPECTED_STATES or len({state.state for state in states}) != EXPECTED_STATES:
        raise StateRegimeError("state count is not 51")
    if sum(state.county_n for state in states) != EXPECTED_COUNTIES:
        raise StateRegimeError("county count is not 3144")


def descriptive_raw(states: Sequence[StateProfile]) -> tuple[Vector, bool]:
    """Return the five-column descriptive matrix and whether medians vary.

    Column 5 is 0 when the median is missing because the observation indicator
    is 0. The stored median on the state stays missing.
    """
    share_names = ("published_share", "tick_established_share", "pathogen_present_share")
    shares = _share_block(states, share_names)
    observed = np.array(
        [state.median_published_floor is not None for state in states],
        dtype=bool,
    )
    indicator = observed.astype(np.float64)
    coordinate = np.zeros(len(states), dtype=np.float64)
    contrast = False
    observed_n = int(observed.sum())
    if observed_n < 2:
        raise StateRegimeError("fewer than two states have a published floor median")
    values = np.array(
        [
            state.median_published_floor
            for state in states
            if state.median_published_floor is not None
        ],
        dtype=np.float64,
    ).reshape(-1, 1)
    if float(values.std(ddof=0)) > 0:
        coordinate[observed] = StandardScaler().fit_transform(values).ravel()
        contrast = True
    raw = np.column_stack([shares, indicator, coordinate])
    return np.asarray(raw, dtype=np.float64), contrast


def publication_free_raw(states: Sequence[StateProfile]) -> Vector:
    """Return tick, pathogen, and rural shares only."""
    return _share_block(
        states,
        ("tick_established_share", "pathogen_present_share", "rural_nonmetro_share"),
    )


def analyze(states: Sequence[StateProfile]) -> Analysis:
    """Fit both Ward profiles and apply the frozen disposition rule."""
    ordered = tuple(sorted(states, key=lambda state: state.state))
    unique = {state.state for state in ordered}
    if len(ordered) != EXPECTED_STATES or len(unique) != EXPECTED_STATES:
        raise StateRegimeError("state count is not 51")
    descriptive_matrix, contrast = descriptive_raw(ordered)
    free_matrix = publication_free_raw(ordered)
    descriptive = _fit_profile(
        "descriptive",
        DESCRIPTIVE_FEATURES,
        descriptive_matrix,
        ordered,
        contrast,
        share_only=descriptive_matrix[:, :3],
    )
    publication_free = _fit_profile(
        "publication_free",
        PUBLICATION_FREE_FEATURES,
        free_matrix,
        ordered,
        False,
        share_only=None,
    )
    cross_ari = _ari(np.asarray(descriptive.labels), np.asarray(publication_free.labels))
    descriptive_ids = tuple(range(1, descriptive.chosen.k + 1))
    free_ids = tuple(range(1, publication_free.chosen.k + 1))
    contingency = _contingency(
        descriptive.labels,
        publication_free.labels,
        descriptive_ids,
        free_ids,
    )
    zero = tuple(state for state in ordered if state.zero_published)
    zero_states = len(zero)
    zero_counties = sum(state.county_n for state in zero)
    questions = _questions(ordered, descriptive.labels)
    partial = Analysis(
        states=ordered,
        descriptive=descriptive,
        publication_free=publication_free,
        cross_ari=cross_ari,
        contingency=contingency,
        descriptive_ids=descriptive_ids,
        publication_free_ids=free_ids,
        zero_states=zero_states,
        zero_counties=zero_counties,
        matches_107=zero_states == EXPECTED_ZERO_STATES and zero_counties == EXPECTED_ZERO_COUNTIES,
        questions=questions,
        decision=Decision("revise", "investigate", None, ()),
        sklearn_version=sklearn_version(),
    )
    return Analysis(
        states=partial.states,
        descriptive=partial.descriptive,
        publication_free=partial.publication_free,
        cross_ari=partial.cross_ari,
        contingency=partial.contingency,
        descriptive_ids=partial.descriptive_ids,
        publication_free_ids=partial.publication_free_ids,
        zero_states=partial.zero_states,
        zero_counties=partial.zero_counties,
        matches_107=partial.matches_107,
        questions=partial.questions,
        decision=decide(partial),
        sklearn_version=partial.sklearn_version,
    )


def decide(analysis: Analysis) -> Decision:
    """Apply the frozen keep and advance rules. Do not retune them."""
    reasons: list[str] = []
    if len(analysis.states) != EXPECTED_STATES:
        reasons.append("state_count")
    if analysis.descriptive.features != DESCRIPTIVE_FEATURES:
        reasons.append("descriptive_features")
    if analysis.publication_free.features != PUBLICATION_FREE_FEATURES:
        reasons.append("publication_free_features")
    for profile in (analysis.descriptive, analysis.publication_free):
        reasons.extend(_profile_reasons(profile))
    if not _complete_partition(analysis.descriptive.labels, analysis.descriptive.chosen.k):
        reasons.append("descriptive_partition")
    free_labels = analysis.publication_free.labels
    free_k = analysis.publication_free.chosen.k
    if not _complete_partition(free_labels, free_k):
        reasons.append("publication_free_partition")
    for state, label in zip(analysis.states, analysis.descriptive.labels, strict=True):
        if state.zero_published and state.median_published_floor is not None:
            reasons.append("median_filled")
        if state.zero_published and label < 1:
            reasons.append("zero_hidden")
    if not analysis.matches_107:
        reasons.append("issue_107_comparison")
    method = "keep" if not reasons else "revise"
    if method == "keep" and analysis.cross_ari < ARI_FEATURE_MAX:
        product = "advance"
        feature: str | None = "publication_free"
    else:
        product = "investigate"
        feature = None
    return Decision(method, product, feature, tuple(dict.fromkeys(reasons)))


def feature_sentence(decision: Decision) -> str:
    """State which profile a later county model may use."""
    if decision.product == "advance" and decision.feature_profile == "publication_free":
        return (
            "The publication-free profile may be used as a categorical county-model feature. "
            "The descriptive profile stays a briefing result."
        )
    return (
        "No profile may be used as a county-model feature on this run. "
        "The descriptive profile stays a briefing result. "
        "The publication-free profile stays a candidate until a later run meets the advance rule."
    )


def assignment_rows(analysis: Analysis) -> tuple[AssignmentRow, ...]:
    """Lab rows. States with fewer than 11 counties keep a group and lose their shares."""
    rows: list[AssignmentRow] = []
    for index, state in enumerate(analysis.states):
        suppressed = state.county_n < SMALL_CELL
        rows.append(
            AssignmentRow(
                state=state.state,
                county_n=None if suppressed else state.county_n,
                published_share=None if suppressed else state.published_share,
                tick_established_share=None if suppressed else state.tick_established_share,
                pathogen_present_share=None if suppressed else state.pathogen_present_share,
                median_published_floor=None if suppressed else state.median_published_floor,
                rural_nonmetro_share=None if suppressed else state.rural_nonmetro_share,
                descriptive_group=analysis.descriptive.labels[index],
                publication_free_group=analysis.publication_free.labels[index],
                zero_published=None if suppressed else state.zero_published,
            )
        )
    return tuple(rows)


def lab_metrics(analysis: Analysis) -> tuple[EdaMetric, ...]:
    """Aggregate metrics. A state-count from 1 to 10 is stored so the writer can suppress it."""
    rows: list[EdaMetric | None] = []
    for profile in (analysis.descriptive, analysis.publication_free):
        chosen = profile.chosen
        rows.extend(
            (
                _national(f"{profile.name}_chosen_k", chosen.k, "groups"),
                _optional_national(f"{profile.name}_silhouette", chosen.silhouette, "index"),
                _optional_national(f"{profile.name}_loso_median", chosen.loso_median, "index"),
                _optional_national(f"{profile.name}_loso_min", chosen.loso_min, "index"),
                _optional_national(f"{profile.name}_bootstrap_low", chosen.bootstrap_low, "index"),
                _optional_national(
                    f"{profile.name}_bootstrap_high",
                    chosen.bootstrap_high,
                    "index",
                ),
                _national(
                    f"{profile.name}_cut_stable",
                    1 if profile.cut_stable else 0,
                    "indicator",
                ),
                _national(f"{profile.name}_average_ari", profile.average_ari, "index"),
                _national(f"{profile.name}_complete_ari", profile.complete_ari, "index"),
                _national(f"{profile.name}_tree_ari", profile.tree_ari, "index"),
            )
        )
        if profile.share_only_ari is not None:
            rows.append(
                _national(f"{profile.name}_share_only_ari", profile.share_only_ari, "index")
            )
        for fit in profile.fits:
            prefix = f"{profile.name}_k{fit.k}"
            rows.append(_optional_national(f"{prefix}_silhouette", fit.silhouette, "index"))
            rows.append(_optional_national(f"{prefix}_loso_median", fit.loso_median, "index"))
            rows.append(_optional_national(f"{prefix}_bootstrap_low", fit.bootstrap_low, "index"))
        for group_id in range(1, chosen.k + 1):
            count = sum(label == group_id for label in profile.labels)
            rows.append(_cell(f"{profile.name}_group_size", f"g{group_id}", count))
    rows.append(_national("cross_profile_ari", analysis.cross_ari, "index"))
    rows.append(_count_metric("zero_published_states", analysis.zero_states))
    rows.append(_count_metric("zero_published_counties", analysis.zero_counties))
    rows.append(_national("matches_107", 1 if analysis.matches_107 else 0, "indicator"))
    for row_index, descriptive_id in enumerate(analysis.descriptive_ids):
        for column_index, free_id in enumerate(analysis.publication_free_ids):
            count = analysis.contingency[row_index][column_index]
            rows.append(_cell("contingency_count", f"d{descriptive_id}-f{free_id}", count))
    return tuple(metric for metric in rows if metric is not None)


def lab_findings(analysis: Analysis) -> tuple[FindingRecord, ...]:
    """Two aggregate findings. State names stay in the write-up."""
    decision = analysis.decision
    method = FindingRecord(
        topic="state reporting regimes",
        statement=(
            f"Method {decision.method}. Product call {decision.product}. "
            f"Descriptive k is {analysis.descriptive.chosen.k}. "
            f"Publication-free k is {analysis.publication_free.chosen.k}. "
            f"Cross-profile adjusted Rand is {analysis.cross_ari:.4f}. "
            f"States with no published floor are in the descriptive partition. "
            f"{feature_sentence(decision)}"
        ),
        disposition=decision.method,
        n_underlying=EXPECTED_STATES,
        evidence={
            "descriptive_k": analysis.descriptive.chosen.k,
            "publication_free_k": analysis.publication_free.chosen.k,
            "cross_ari": analysis.cross_ari,
            "zero_published_states": analysis.zero_states,
            "matches_107": analysis.matches_107,
            "reason_count": len(decision.reasons),
        },
        effect_size=analysis.cross_ari,
        uncertainty_note="Bootstrap intervals resample states. No p-value is reported.",
    )
    feature = FindingRecord(
        topic="county model feature",
        statement=feature_sentence(decision),
        disposition="keep" if decision.product == "advance" else "follow-up",
        n_underlying=EXPECTED_STATES,
        evidence={
            "product": decision.product,
            "feature_profile": decision.feature_profile or "none",
        },
        effect_size=analysis.cross_ari,
        uncertainty_note="Advance is the only call that allows the publication-free group id.",
    )
    return (method, feature)


def lab_experiments(analysis: Analysis, run_id: str) -> tuple[ExperimentRow, ...]:
    """One experiment row per profile. The id includes the run id."""
    profiles = (analysis.descriptive, analysis.publication_free)
    return tuple(_experiment(run_id, profile) for profile in profiles)


def _experiment(run_id: str, profile: ProfileFit) -> ExperimentRow:
    chosen = profile.chosen
    metrics = [
        _model_metric("chosen", "silhouette", chosen.silhouette, None, None, EXPECTED_STATES),
        _model_metric("chosen", "loso_median_ari", chosen.loso_median, None, None, EXPECTED_STATES),
        _model_metric(
            "bootstrap",
            "ari",
            chosen.bootstrap_low,
            chosen.bootstrap_low,
            chosen.bootstrap_high,
            REPLICATES,
        ),
        _model_metric(
            "chosen",
            "average_linkage_ari",
            profile.average_ari,
            None,
            None,
            EXPECTED_STATES,
        ),
        _model_metric(
            "chosen",
            "complete_linkage_ari",
            profile.complete_ari,
            None,
            None,
            EXPECTED_STATES,
        ),
        _model_metric("chosen", "tree_ari", profile.tree_ari, None, None, EXPECTED_STATES),
    ]
    if profile.share_only_ari is not None:
        metrics.append(
            _model_metric(
                "sensitivity",
                "share_only_ari",
                profile.share_only_ari,
                None,
                None,
                EXPECTED_STATES,
            )
        )
    for fit in profile.fits:
        metrics.append(
            _model_metric(f"k{fit.k}", "silhouette", fit.silhouette, None, None, EXPECTED_STATES)
        )
    return ExperimentRow(
        experiment_id=f"{run_id}-{profile.name}",
        model_family="ward_hierarchical",
        hypothesis=f"{profile.name} Ward groups describe state surveillance regimes",
        config={
            "spec": SPEC_ID,
            "linkage": "ward",
            "distance": "euclidean",
            "features": list(profile.features),
            "seed": profile.seed,
            "k": chosen.k,
            "scaler": "standard",
        },
        split_definition={
            "profile": profile.name,
            "n_states": EXPECTED_STATES,
            "k_grid": list(K_GRID),
        },
        status="succeeded",
        metrics=tuple(metrics),
    )


def _fit_profile(
    name: str,
    features: tuple[str, ...],
    raw: Vector,
    states: Sequence[StateProfile],
    median_contrast: bool,
    *,
    share_only: Vector | None,
) -> ProfileFit:
    names = tuple(state.state for state in states)
    fits = tuple(_fit_k(raw, names, k, PROFILE_SEEDS[name]) for k in K_GRID)
    chosen, stable = _choose(fits)
    scaled = _scale(raw)
    average_ari = _ari(np.asarray(chosen.labels), _linkage(scaled, chosen.k, "average"))
    complete_ari = _ari(np.asarray(chosen.labels), _linkage(scaled, chosen.k, "complete"))
    share_ari = None
    if share_only is not None:
        share_labels = _relabel(_ward(_scale(share_only), chosen.k), names)
        share_ari = _ari(np.asarray(chosen.labels), share_labels)
    children, distances = _tree(scaled)
    tree_labels = _tree_labels(children, len(states), chosen.k)
    tree_ari = _ari(np.asarray(chosen.labels), tree_labels)
    return ProfileFit(
        name=name,
        features=features,
        seed=PROFILE_SEEDS[name],
        chosen=chosen,
        fits=fits,
        labels=chosen.labels,
        cut_stable=stable,
        average_ari=average_ari,
        complete_ari=complete_ari,
        share_only_ari=share_ari,
        tree_ari=tree_ari,
        cut_height=_cut_height(distances, len(states), chosen.k),
        leaf_order=_leaf_order(children, len(states)),
        children=tuple((int(left), int(right)) for left, right in children),
        distances=tuple(float(value) for value in distances),
        median_contrast=median_contrast,
    )


def _fit_k(raw: Vector, names: Sequence[str], k: int, seed: int) -> KFit:
    scaled = _scale(raw)
    raw_labels = _ward(scaled, k)
    labels = _relabel(raw_labels, names)
    silhouette = _silhouette(scaled, raw_labels)
    loso_median, loso_min, loso_failed = _loso(raw, labels, k)
    interval = _bootstrap(raw, labels, k, seed)
    admissible = (
        silhouette is not None
        and loso_median is not None
        and loso_median >= LOSO_ADMISSIBLE
        and interval.estimable
        and interval.low is not None
        and interval.low >= BOOT_LOW_ADMISSIBLE
    )
    return KFit(
        k=k,
        labels=tuple(int(label) for label in labels),
        silhouette=silhouette,
        loso_median=loso_median,
        loso_min=loso_min,
        loso_failed=loso_failed,
        bootstrap_low=interval.low,
        bootstrap_high=interval.high,
        bootstrap_estimable=interval.estimable,
        bootstrap_failed=interval.failed,
        admissible=admissible,
    )


def _choose(fits: Sequence[KFit]) -> tuple[KFit, bool]:
    admissible = [fit for fit in fits if fit.admissible]
    pool = admissible or list(fits)

    def key(fit: KFit) -> tuple[float, float, int]:
        silhouette = fit.silhouette if fit.silhouette is not None else -math.inf
        loso = fit.loso_median if fit.loso_median is not None else -math.inf
        return (silhouette, loso, -fit.k)

    return max(pool, key=key), bool(admissible)


def _profile_reasons(profile: ProfileFit) -> tuple[str, ...]:
    chosen = profile.chosen
    reasons: list[str] = []
    if not profile.cut_stable:
        reasons.append(f"{profile.name}_unstable")
    if chosen.silhouette is None or chosen.silhouette < SILHOUETTE_KEEP:
        reasons.append(f"{profile.name}_silhouette")
    if chosen.loso_median is None or chosen.loso_median < LOSO_KEEP:
        reasons.append(f"{profile.name}_loso")
    if (
        not chosen.bootstrap_estimable
        or chosen.bootstrap_low is None
        or chosen.bootstrap_low < BOOT_LOW_KEEP
    ):
        reasons.append(f"{profile.name}_bootstrap")
    if profile.tree_ari != 1.0:
        reasons.append(f"{profile.name}_tree")
    return tuple(reasons)


def _complete_partition(labels: Sequence[int], k: int) -> bool:
    return len(labels) == EXPECTED_STATES and set(labels) == set(range(1, k + 1))


def _questions(states: Sequence[StateProfile], labels: Sequence[int]) -> QuestionLabels:
    high = tuple(
        state.state
        for state in states
        if state.state in NORTHEAST_STATES and state.published_share >= HIGH_PUBLISHED_SHARE
    )
    zero = tuple(state.state for state in states if state.zero_published)
    return QuestionLabels(
        northeast_high_group=_modal_group(states, labels, set(high)),
        northeast_high_states=high,
        zero_published_group=_modal_group(states, labels, set(zero)),
        zero_published_states=zero,
    )


def _modal_group(
    states: Sequence[StateProfile],
    labels: Sequence[int],
    members: set[str],
) -> int | None:
    counts: dict[int, int] = defaultdict(int)
    for state, label in zip(states, labels, strict=True):
        if state.state in members:
            counts[label] += 1
    if not counts:
        return None
    return sorted(counts, key=lambda group: (-counts[group], group))[0]


def _loso(raw: Vector, labels: Vector, k: int) -> tuple[float | None, float | None, int]:
    values: list[float] = []
    failed = 0
    total = len(labels)
    for index in range(total):
        kept = np.ones(total, dtype=bool)
        kept[index] = False
        try:
            refit = _ward(_scale(raw[kept]), k)
            score = float(adjusted_rand_score(labels[kept], refit))
        except (StateRegimeError, ValueError, FloatingPointError):
            failed += 1
            continue
        if math.isfinite(score):
            values.append(score)
        else:
            failed += 1
    if failed * 100 > total * 5 or len(values) < 2:
        return None, None, failed
    return float(statistics.median(values)), min(values), failed


def _bootstrap(raw: Vector, labels: Vector, k: int, seed: int) -> IntervalEstimate:
    positions = tuple(range(len(labels)))

    def statistic(drawn: Sequence[int]) -> float | None:
        return _bootstrap_ari(raw, labels, drawn, k)

    return resample_interval(positions, statistic, seed)


def _bootstrap_ari(raw: Vector, labels: Vector, drawn: Sequence[int], k: int) -> float | None:
    if len(drawn) <= k:
        return None
    try:
        sample = raw[np.asarray(drawn, dtype=int)]
        scaler = StandardScaler()
        scaled = np.asarray(scaler.fit_transform(sample), dtype=np.float64)
        if not np.isfinite(scaled).all():
            return None
        boot_labels = _ward(scaled, k)
        ids = sorted({int(label) for label in boot_labels.tolist()})
        if len(ids) < k:
            return None
        centers = np.vstack([scaled[boot_labels == label].mean(axis=0) for label in ids])
        full = np.asarray(scaler.transform(raw), dtype=np.float64)
        if not np.isfinite(full).all() or not np.isfinite(centers).all():
            return None
        predicted = _assign(full, centers)
    except (StateRegimeError, ValueError, FloatingPointError):
        return None
    score = float(adjusted_rand_score(labels, predicted))
    return score if math.isfinite(score) else None


def _assign(scaled: Vector, centers: Vector) -> Vector:
    distances = ((scaled[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    return np.asarray(distances.argmin(axis=1), dtype=int)


def _scale(raw: Vector) -> Vector:
    scaled = np.asarray(StandardScaler().fit_transform(raw), dtype=np.float64)
    if not np.isfinite(scaled).all():
        raise StateRegimeError("standardized matrix is not finite")
    return scaled


def _ward(scaled: Vector, k: int) -> Vector:
    if len(scaled) <= k:
        raise StateRegimeError("too few rows for the group count")
    model = AgglomerativeClustering(n_clusters=k, linkage="ward")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = model.fit_predict(scaled)
    return np.asarray(fitted, dtype=int)


def _linkage(scaled: Vector, k: int, linkage: str) -> Vector:
    model = AgglomerativeClustering(n_clusters=k, linkage=linkage)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = model.fit_predict(scaled)
    return np.asarray(fitted, dtype=int)


def _tree(scaled: Vector) -> tuple[Vector, Vector]:
    model = AgglomerativeClustering(n_clusters=None, distance_threshold=0, linkage="ward")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(scaled)
    children = np.asarray(model.children_, dtype=int)
    distances = np.asarray(model.distances_, dtype=np.float64)
    return children, distances


def _tree_labels(children: Vector, n_leaves: int, k: int) -> Vector:
    members: dict[int, list[int]] = {index: [index] for index in range(n_leaves)}
    leaf_cluster = np.arange(n_leaves)
    next_id = n_leaves
    for index in range(n_leaves - k):
        left = int(children[index, 0])
        right = int(children[index, 1])
        combined = members[left] + members[right]
        members[next_id] = combined
        for leaf in combined:
            leaf_cluster[leaf] = next_id
        next_id += 1
    return leaf_cluster


def _leaf_order(children: Vector, n_leaves: int) -> tuple[int, ...]:
    order: dict[int, tuple[int, ...]] = {index: (index,) for index in range(n_leaves)}
    for index, pair in enumerate(children):
        left = int(pair[0])
        right = int(pair[1])
        order[n_leaves + index] = order[left] + order[right]
    return order[n_leaves + len(children) - 1]


def _cut_height(distances: Vector, n_leaves: int, k: int) -> float:
    done = n_leaves - k - 1
    nxt = n_leaves - k
    if nxt >= len(distances):
        return float(distances[-1])
    if done < 0:
        return float(distances[0]) / 2.0
    return float(distances[done] + distances[nxt]) / 2.0


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


def _silhouette(scaled: Vector, labels: Vector) -> float | None:
    if len(set(labels.tolist())) < 2:
        return None
    try:
        score = float(silhouette_score(scaled, labels, metric="euclidean"))
    except ValueError:
        return None
    return score if math.isfinite(score) else None


def _ari(left: Vector, right: Vector) -> float:
    score = float(adjusted_rand_score(left, right))
    if not math.isfinite(score):
        raise StateRegimeError("adjusted Rand index is not finite")
    return score


def _contingency(
    left: Sequence[int],
    right: Sequence[int],
    left_ids: Sequence[int],
    right_ids: Sequence[int],
) -> tuple[tuple[int, ...], ...]:
    table = [[0 for _ in right_ids] for _ in left_ids]
    left_index = {group: index for index, group in enumerate(left_ids)}
    right_index = {group: index for index, group in enumerate(right_ids)}
    for left_group, right_group in zip(left, right, strict=True):
        table[left_index[left_group]][right_index[right_group]] += 1
    return tuple(tuple(row) for row in table)


def _share_block(states: Sequence[StateProfile], names: tuple[str, ...]) -> Vector:
    columns = [[float(getattr(state, name)) for state in states] for name in names]
    return np.asarray(np.column_stack(columns), dtype=np.float64)


def _profile(state: str, items: Sequence[Mapping[str, object]]) -> StateProfile:
    published = 0
    tick = 0
    pathogen = 0
    rural = 0
    floors: list[float] = []
    for item in items:
        human = _text(item.get("HUMAN_STATUS"))
        tick_status = _text(item.get("TICK_STATUS"))
        pathogen_status = _text(item.get("BURGDORFERI_STATUS"))
        if human not in {HUMAN_PUBLISHED, HUMAN_NONE}:
            raise StateRegimeError("human status is outside the allowed levels")
        if tick_status not in TICK_LEVELS:
            raise StateRegimeError("tick status is outside the allowed levels")
        if pathogen_status not in PATHOGEN_LEVELS:
            raise StateRegimeError("pathogen status is outside the allowed levels")
        code = _rucc(item.get("RUCC_2023"))
        floor = _optional_float(item.get("INCIDENCE_FLOOR_2023"))
        if human == HUMAN_PUBLISHED:
            if floor is None:
                raise StateRegimeError("published floor is missing")
            published += 1
            floors.append(floor)
        elif floor is not None:
            raise StateRegimeError("unpublished county has a floor")
        if tick_status == TICK_ESTABLISHED:
            tick += 1
        if pathogen_status == PATHOGEN_PRESENT:
            pathogen += 1
        if code in RURAL_CODES:
            rural += 1
    county_n = len(items)
    median = None if not floors else float(statistics.median(floors))
    if published == 0 and median is not None:
        raise StateRegimeError("a state with no published floor received a median")
    if published > 0 and median is None:
        raise StateRegimeError("a publishing state is missing its median")
    return StateProfile(
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
        median_published_floor=median,
        zero_published=published == 0,
    )


def _national(name: str, value: float, unit: str) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        metric_value=value,
        n_underlying=EXPECTED_STATES,
        geography_type="national",
        geography_id="US",
        unit=unit,
    )


def _optional_national(name: str, value: float | None, unit: str) -> EdaMetric | None:
    if value is None:
        return None
    return _national(name, value, unit)


def _count_metric(name: str, count: int) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        metric_value=count,
        n_underlying=count,
        geography_type="national",
        geography_id="US",
        unit="count",
    )


def _cell(name: str, geography_id: str, count: int) -> EdaMetric:
    if count == 0:
        return EdaMetric(
            metric_name=name,
            metric_value=0,
            n_underlying=EXPECTED_STATES,
            geography_type="state_group",
            geography_id=geography_id,
            unit="count",
        )
    if count < SMALL_CELL:
        return EdaMetric(
            metric_name=name,
            metric_value=count,
            n_underlying=count,
            geography_type="state_group",
            geography_id=geography_id,
            unit="count",
        )
    return EdaMetric(
        metric_name=name,
        metric_value=count,
        n_underlying=EXPECTED_STATES,
        geography_type="state_group",
        geography_id=geography_id,
        unit="count",
    )


def _model_metric(
    split_name: str,
    metric_name: str,
    value: float | None,
    low: float | None,
    high: float | None,
    n: int,
) -> ModelMetricRow:
    return ModelMetricRow(split_name, metric_name, value, low, high, n)


def _fips(value: object) -> str:
    if isinstance(value, Decimal):
        value = int(value)
    if isinstance(value, int) and not isinstance(value, bool):
        text = f"{value:05d}"
    elif isinstance(value, str) and value.strip().isdigit():
        text = value.strip().zfill(5)
    else:
        raise StateRegimeError("county id is not five digits")
    if len(text) != 5:
        raise StateRegimeError("county id is not five digits")
    return text


def _state_code(value: object) -> str:
    if not isinstance(value, str) or len(value.strip()) != 2 or not value.strip().isalpha():
        raise StateRegimeError("state code is not two letters")
    return value.strip().upper()


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateRegimeError("required text is missing")
    return value.strip()


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise StateRegimeError("number is not numeric")
    number = float(value)
    if not math.isfinite(number):
        raise StateRegimeError("number is not finite")
    return number


def _rucc(value: object) -> int:
    if isinstance(value, (bool, str)):
        raise StateRegimeError("rural-urban code is outside 1 through 9")
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise StateRegimeError("rural-urban code is outside 1 through 9")
        value = int(value)
    if isinstance(value, float):
        if not value.is_integer():
            raise StateRegimeError("rural-urban code is outside 1 through 9")
        value = int(value)
    if isinstance(value, int) and 1 <= value <= 9:
        return value
    raise StateRegimeError("rural-urban code is outside 1 through 9")
