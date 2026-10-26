"""Peer-county cluster baselines for issue 110.

The functions here do not open Snowflake. County rows stay in memory. Aggregate
lab metrics suppress a count from 1 to 10. The results write-up may name counties.
"""

from __future__ import annotations

import math
import statistics
import warnings
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from importlib.metadata import version
from typing import Any

import numpy as np
from sklearn.cluster import (  # type: ignore[import-untyped]
    DBSCAN,
    HDBSCAN,
    AgglomerativeClustering,
    KMeans,
)
from sklearn.metrics import adjusted_rand_score, silhouette_score  # type: ignore[import-untyped]
from sklearn.mixture import GaussianMixture  # type: ignore[import-untyped]
from sklearn.preprocessing import StandardScaler  # type: ignore[import-untyped]

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.coverage_audit import (
    CENSUS_REGIONS,
    HEATMAP_REGIONS,
    PINNED_BUNDLE_SHA256,
    PINNED_RELEASE_ID,
)
from lyme_gap_atlas_ml.snowflake.eda_writer import SMALL_CELL_MINIMUM, EdaMetric
from lyme_gap_atlas_ml.test_selection import (
    HUMAN_NONE,
    HUMAN_PUBLISHED,
    PATHOGEN_ALLOWED,
    TICK_ALLOWED,
    cramers_v,
    resample_interval,
    state_cluster_interval,
)

SPEC_ID = "110-peer-county-clusters/v1"
PRIMARY_SEED = 1102026
ALT_SEED = 1102027
K_PRIMARY = 4
K_GRID = (2, 3, 4, 5, 6, 7, 8)
EXPECTED_COUNTIES = 3144
OCT13_SIZES = (461, 703, 828, 1152)
OCT13_SILHOUETTE = 0.389
OCT13_WEIGHT_ARI = 0.365
SILHOUETTE_TOLERANCE = 0.010
WEIGHT_ARI_TOLERANCE = 0.020
SILHOUETTE_FLOOR = 0.25
SEED_ARI_BAR = 0.90
STATE_ARI_LOW_BAR = 0.80
REGION_ARI_BAR = 0.70
STATE_HOLDOUT_MEDIAN_BAR = 0.90
WARD_ARI_BAR = 0.50
WEIGHT_ARI_BAR = 0.80
K_SILHOUETTE_GAP = 0.05
CRAMER_BAR = 0.50
NONPUBLISH_SHARE_BAR = 0.80
COVERAGE_FLOOR = 0.90
CLIMATE_MIN_DAYS = 20
MIN_COMPLETE = 500
N_INIT_PRIMARY = 10
N_INIT_BOOTSTRAP = 1
MAX_ITER = 300
SCHEMA_VERSION = "2.0.0"
METHODOLOGY_VERSION = "semantic-2.0.0"
SCOPE = "US_COUNTIES"
QUERY_NAMES = ("release_identity", "atlas_rows", "climate_county", "nlcd_county_total")
BOOTSTRAP_SLICES = frozenset({"context", "multidomain"})
CONTEXT_FEATURES = ("log_population", "svi_percentile")
EXTENDED_FEATURES = (
    "log_population",
    "svi_percentile",
    "uninsured_percentile",
    "rucc_2023",
)
CLIMATE_FEATURES = ("january_tavg_c", "january_prcp_mm")
MULTI_FEATURES = (*EXTENDED_FEATURES, *CLIMATE_FEATURES)
COVERAGE_FEATURES = (
    "human_published",
    "tick_established",
    "tick_reported",
    "tick_unknown",
    "pathogen_present",
    "pathogen_unknown",
)
SLICE_FEATURES = {
    "context": CONTEXT_FEATURES,
    "extended": EXTENDED_FEATURES,
    "climate": CLIMATE_FEATURES,
    "coverage": COVERAGE_FEATURES,
    "multidomain": MULTI_FEATURES,
}
_PERCENTILE_FEATURES = frozenset({"svi_percentile", "uninsured_percentile"})

Vector = np.ndarray[Any, Any]


class PeerClusterError(ValueError):
    """The county table cannot be clustered under the frozen spec."""


@dataclass(frozen=True)
class County:
    fips: str
    name: str
    state: str
    region: str
    population: float
    svi: float | None
    uninsured: float | None
    rucc: int | None
    human: str
    tick: str
    pathogen: str
    tavg: float | None = None
    tavg_days: int = 0
    prcp: float | None = None
    prcp_days: int = 0


@dataclass(frozen=True)
class Representative:
    slice_name: str
    cluster_id: int
    rank: int
    fips: str
    name: str
    state: str
    distance: float
    population: float
    svi: float | None
    uninsured: float | None
    rucc: int | None
    human: str
    tick: str
    pathogen: str


@dataclass(frozen=True)
class DensityFit:
    opened: bool
    gmm_ari: float | None = None
    gmm_silhouette: float | None = None
    dbscan_clusters: int | None = None
    dbscan_noise: int | None = None
    hdbscan_clusters: int | None = None
    hdbscan_noise: int | None = None


@dataclass(frozen=True)
class SliceFit:
    name: str
    estimable: bool
    note: str
    n: int
    excluded: int
    features: tuple[str, ...]
    percentile_divided: tuple[str, ...]
    labels: tuple[int | None, ...]
    silhouette: float | None
    sizes: tuple[int, ...]
    seed_ari: float | None
    ward_ari: float | None
    weight_ari: float | None
    unscaled_ari: float | None
    k_silhouettes: tuple[tuple[int, float], ...]
    region_held_in: tuple[tuple[str, float], ...]
    region_held_out: tuple[tuple[str, float], ...]
    region_min: float | None
    state_holdout_median: float | None
    state_holdout_min: float | None
    state_low: float | None
    state_high: float | None
    state_estimable: bool
    county_low: float | None
    county_high: float | None
    county_estimable: bool
    cramer_publishing: float | None
    cramer_region: float | None
    cramer_human: float | None
    cramer_tick: float | None
    max_nonpublish_share: float | None
    max_nonpublish_count: int | None
    centers: tuple[tuple[float, ...], ...]
    representatives: tuple[Representative, ...]
    density: DensityFit | None


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
    cluster: str
    product: str
    reasons: tuple[str, ...]
    product_reasons: tuple[str, ...]
    sizes_reproduced: bool
    silhouette_reproduced: bool
    weight_reproduced: bool


@dataclass(frozen=True)
class Analysis:
    counties: tuple[County, ...]
    publishing_states: frozenset[str]
    slices: tuple[SliceFit, ...]
    decision: Decision
    nlcd_counties: int | None
    climate_loaded: bool
    experiments: tuple[ExperimentRow, ...]

    def slice(self, name: str) -> SliceFit:
        for item in self.slices:
            if item.name == name:
                return item
        raise PeerClusterError(f"missing slice {name}")


def sklearn_version() -> str:
    return version("scikit-learn")


def load_peer_queries(text: str) -> dict[str, str]:
    """Split the issue 110 validation file and reject unsafe SQL."""
    return load_marked_queries(text, QUERY_NAMES)


def build_counties(
    atlas_rows: Sequence[Mapping[str, object]],
    climate_rows: Sequence[Mapping[str, object]] | None,
) -> tuple[County, ...]:
    """Validate the atlas census and attach climate means. Does not impute."""
    if len(atlas_rows) != EXPECTED_COUNTIES:
        raise PeerClusterError("county count is not 3144")
    climate = _climate_index(climate_rows)
    counties: list[County] = []
    seen: set[str] = set()
    for row in atlas_rows:
        county = _county(row, climate)
        if county.fips in seen:
            raise PeerClusterError("duplicate county id")
        seen.add(county.fips)
        counties.append(county)
    if [county.fips for county in counties] != sorted(seen):
        counties.sort(key=lambda county: county.fips)
    return tuple(counties)


def analyze(
    counties: Sequence[County],
    *,
    nlcd_counties: int | None = None,
    climate_loaded: bool = True,
    bootstrap: bool = True,
    enforce_count: bool = True,
    log: Callable[[str], None] | None = None,
) -> Analysis:
    """Fit the frozen slices. Bootstrap intervals run only for context and multi-domain.

    ``enforce_count`` is false only in unit tests. The live runner keeps the default.
    """
    if enforce_count and len(counties) != EXPECTED_COUNTIES:
        raise PeerClusterError("county count is not 3144")

    def _log(message: str) -> None:
        if log is not None:
            log(message)

    publishing = frozenset(county.state for county in counties if county.human == HUMAN_PUBLISHED)
    nonpublishing = np.asarray([county.state not in publishing for county in counties], dtype=bool)
    fits: list[SliceFit] = []
    for name, use_density in (
        ("context", True),
        ("extended", False),
        ("climate", False),
        ("coverage", False),
        ("multidomain", False),
    ):
        _log(f"fitting {name}")
        fits.append(
            _fit_named(
                name,
                counties,
                nonpublishing,
                climate_loaded=climate_loaded,
                bootstrap=bootstrap,
                density=use_density,
            )
        )
    decision = decide(fits[0], fits[4], len(counties))
    analysis = Analysis(
        counties=tuple(counties),
        publishing_states=publishing,
        slices=tuple(fits),
        decision=decision,
        nlcd_counties=nlcd_counties,
        climate_loaded=climate_loaded,
        experiments=(),
    )
    return Analysis(
        counties=analysis.counties,
        publishing_states=analysis.publishing_states,
        slices=analysis.slices,
        decision=analysis.decision,
        nlcd_counties=analysis.nlcd_counties,
        climate_loaded=analysis.climate_loaded,
        experiments=tuple(_experiments(analysis)),
    )


def decide(context: SliceFit, multi: SliceFit, cohort_n: int) -> Decision:
    """Apply the frozen keep and product rules."""
    sizes_reproduced = tuple(sorted(context.sizes)) == OCT13_SIZES
    silhouette_reproduced = (
        context.silhouette is not None
        and abs(context.silhouette - OCT13_SILHOUETTE) <= SILHOUETTE_TOLERANCE
    )
    weight_reproduced = (
        context.weight_ari is not None
        and abs(context.weight_ari - OCT13_WEIGHT_ARI) <= WEIGHT_ARI_TOLERANCE
    )
    if not context.estimable:
        return Decision(
            "stop",
            "stop",
            ("context_not_estimable",),
            ("context_not_estimable",),
            sizes_reproduced,
            silhouette_reproduced,
            weight_reproduced,
        )
    reasons = _stability_failures(
        context,
        reproduction=True,
        sizes_reproduced=sizes_reproduced,
        silhouette_reproduced=silhouette_reproduced,
        zero_exclusion=True,
    )
    product_reasons = _product_failures(multi, cohort_n)
    cluster = "keep" if not reasons else "revise"
    product = "advance" if not product_reasons else "investigate"
    return Decision(
        cluster,
        product,
        reasons,
        product_reasons,
        sizes_reproduced,
        silhouette_reproduced,
        weight_reproduced,
    )


def lab_metrics(analysis: Analysis) -> tuple[EdaMetric, ...]:
    """Aggregate metrics. A 1-10 composition is omitted rather than partially stored."""
    rows: list[EdaMetric] = []
    for fit in analysis.slices:
        if not fit.estimable:
            continue
        _append_metric(rows, "silhouette", fit.silhouette, fit.n, {"slice": fit.name})
        _append_metric(rows, "seed_ari", fit.seed_ari, fit.n, {"slice": fit.name})
        _append_metric(rows, "ward_ari", fit.ward_ari, fit.n, {"slice": fit.name})
        _append_metric(rows, "weight_ari", fit.weight_ari, fit.n, {"slice": fit.name})
        _append_metric(rows, "unscaled_ari", fit.unscaled_ari, fit.n, {"slice": fit.name})
        _append_metric(
            rows,
            "state_bootstrap_ari_low",
            fit.state_low,
            fit.n,
            {"slice": fit.name},
        )
        _append_metric(
            rows,
            "county_bootstrap_ari_low",
            fit.county_low,
            fit.n,
            {"slice": fit.name},
        )
        _append_metric(rows, "region_holdout_min", fit.region_min, fit.n, {"slice": fit.name})
        _append_metric(
            rows,
            "state_holdout_median",
            fit.state_holdout_median,
            fit.n,
            {"slice": fit.name},
        )
        _append_metric(
            rows, "cramers_v_publishing", fit.cramer_publishing, fit.n, {"slice": fit.name}
        )
        _append_metric(rows, "cramers_v_region", fit.cramer_region, fit.n, {"slice": fit.name})
        _append_metric(rows, "cramers_v_human", fit.cramer_human, fit.n, {"slice": fit.name})
        _append_metric(rows, "cramers_v_tick", fit.cramer_tick, fit.n, {"slice": fit.name})
        if _share_publishable(fit.max_nonpublish_share, fit.max_nonpublish_count):
            _append_metric(
                rows,
                "nonpublishing_share",
                fit.max_nonpublish_share,
                fit.n,
                {"slice": fit.name},
            )
        for k, score in fit.k_silhouettes:
            _append_metric(rows, "silhouette_grid", score, fit.n, {"slice": fit.name, "k": str(k)})
        if _composition_publishable(fit.sizes):
            for cluster_id, size in enumerate(fit.sizes, start=1):
                _append_metric(
                    rows,
                    "cluster_size",
                    float(size),
                    fit.n if size == 0 else size,
                    {"slice": fit.name, "cluster": str(cluster_id)},
                )
                if cluster_id - 1 >= len(fit.centers):
                    continue
                for feature, mean in zip(fit.features, fit.centers[cluster_id - 1], strict=True):
                    _append_metric(
                        rows,
                        "cluster_feature_mean",
                        mean,
                        size,
                        {"slice": fit.name, "cluster": str(cluster_id), "feature": feature},
                    )
    return tuple(rows)


def release_matches(row: Mapping[str, object]) -> tuple[bool, tuple[str, ...]]:
    """Return whether the live release row is the frozen pin."""
    checks = {
        "RELEASE_ID": PINNED_RELEASE_ID,
        "SCHEMA_VERSION": SCHEMA_VERSION,
        "METHODOLOGY_VERSION": METHODOLOGY_VERSION,
        "SCOPE": SCOPE,
        "BUNDLE_SHA256": PINNED_BUNDLE_SHA256,
    }
    reasons = tuple(
        key.lower()
        for key, expected in checks.items()
        if str(row.get(key, "")).strip().lower() != expected.lower()
    )
    return not reasons, reasons


def _fit_named(
    name: str,
    counties: Sequence[County],
    nonpublishing: Vector,
    *,
    climate_loaded: bool,
    bootstrap: bool,
    density: bool,
) -> SliceFit:
    if name in {"climate", "multidomain"} and not climate_loaded:
        return _empty_slice(name, len(counties), "climate aggregate was not available")
    features = SLICE_FEATURES[name]
    qualified, raw, divided = _matrix(counties, features)
    n = int(qualified.sum())
    excluded = len(counties) - n
    if n < MIN_COMPLETE or raw.shape[1] < 2:
        return _empty_slice(
            name, len(counties), "complete case is below the frozen minimum", excluded
        )
    try:
        scaled, scaler = _scale(raw)
        model = _kmeans(scaled, K_PRIMARY, PRIMARY_SEED, N_INIT_PRIMARY)
        fips = [counties[int(i)].fips for i in np.flatnonzero(qualified)]
        labels = _relabel(np.asarray(model.labels_, dtype=int), fips)
        centers = _centers(scaled, labels)
    except (ValueError, FloatingPointError):
        return _empty_slice(name, len(counties), "primary fit failed", excluded)
    full_labels = _place(qualified, labels, len(counties))
    sil = _silhouette(scaled, labels)
    seed_labels = _labels_only(scaled, K_PRIMARY, ALT_SEED, N_INIT_PRIMARY)
    seed_ari = _ari(labels, seed_labels) if seed_labels is not None else None
    ward_labels = _ward_labels(scaled)
    ward_ari = _ari(labels, ward_labels) if ward_labels is not None else None
    weight_ari = _weight_ari(scaled, features, labels)
    unscaled_labels = _labels_only(raw, K_PRIMARY, PRIMARY_SEED, N_INIT_PRIMARY)
    unscaled_ari = _ari(labels, unscaled_labels) if unscaled_labels is not None else None
    k_silhouettes = _k_grid(scaled)
    region_in, region_out, region_min = _region_holdouts(
        raw, labels, [counties[i].region for i in np.flatnonzero(qualified)]
    )
    state_median, state_min = _state_holdouts(
        raw, labels, [counties[i].state for i in np.flatnonzero(qualified)]
    )
    state_low = state_high = None
    state_estimable = False
    county_low = county_high = None
    county_estimable = False
    if bootstrap and name in BOOTSTRAP_SLICES:
        state_low, state_high, state_estimable = _state_interval(
            raw,
            labels,
            [counties[i].state for i in np.flatnonzero(qualified)],
        )
        county_low, county_high, county_estimable = _county_interval(raw, labels)
    member_index = np.flatnonzero(qualified)
    publishing_groups = [
        "nonpublishing" if nonpublishing[int(i)] else "publishing" for i in member_index
    ]
    cramer_publishing = _cramer(labels, publishing_groups)
    cramer_region = _cramer(labels, [counties[i].region for i in member_index])
    cramer_human = _cramer(labels, [counties[i].human for i in member_index])
    cramer_tick = _cramer(labels, [counties[i].tick for i in member_index])
    share, share_count = _max_nonpublish(labels, nonpublishing[member_index])
    representatives = _representatives(name, counties, member_index, scaled, labels, centers)
    density_fit = _density(scaled, labels, sil) if density else None
    sizes = tuple(int(np.sum(labels == cluster_id)) for cluster_id in range(1, K_PRIMARY + 1))
    return SliceFit(
        name=name,
        estimable=True,
        note="fit",
        n=n,
        excluded=excluded,
        features=features,
        percentile_divided=divided,
        labels=full_labels,
        silhouette=sil,
        sizes=sizes,
        seed_ari=seed_ari,
        ward_ari=ward_ari,
        weight_ari=weight_ari,
        unscaled_ari=unscaled_ari,
        k_silhouettes=k_silhouettes,
        region_held_in=region_in,
        region_held_out=region_out,
        region_min=region_min,
        state_holdout_median=state_median,
        state_holdout_min=state_min,
        state_low=state_low,
        state_high=state_high,
        state_estimable=state_estimable,
        county_low=county_low,
        county_high=county_high,
        county_estimable=county_estimable,
        cramer_publishing=cramer_publishing,
        cramer_region=cramer_region,
        cramer_human=cramer_human,
        cramer_tick=cramer_tick,
        max_nonpublish_share=share,
        max_nonpublish_count=share_count,
        centers=centers,
        representatives=representatives,
        density=density_fit,
    )


def _matrix(
    counties: Sequence[County], features: Sequence[str]
) -> tuple[Vector, Vector, tuple[str, ...]]:
    qualified = np.asarray([_qualifies(county, features) for county in counties], dtype=bool)
    included = [county for county, keep in zip(counties, qualified, strict=True) if keep]
    divisors = _divisors(included, features)
    rows = []
    for county in included:
        values = [_feature_value(county, feature, divisors) for feature in features]
        rows.append(values)
    raw = np.asarray(rows, dtype=np.float64) if rows else np.empty((0, len(features)))
    divided = tuple(feature for feature, divisor in divisors.items() if divisor == 100.0)
    return qualified, raw, divided


def _qualifies(county: County, features: Sequence[str]) -> bool:
    needed = set(features)
    if "log_population" in needed and county.population <= 0:
        return False
    if "svi_percentile" in needed and county.svi is None:
        return False
    if "uninsured_percentile" in needed and county.uninsured is None:
        return False
    if "rucc_2023" in needed and county.rucc is None:
        return False
    if "january_tavg_c" in needed and (county.tavg is None or county.tavg_days < CLIMATE_MIN_DAYS):
        return False
    return not (
        "january_prcp_mm" in needed and (county.prcp is None or county.prcp_days < CLIMATE_MIN_DAYS)
    )


def _divisors(counties: Sequence[County], features: Sequence[str]) -> dict[str, float]:
    divisors: dict[str, float] = {}
    for feature in features:
        if feature not in _PERCENTILE_FEATURES:
            continue
        values = [
            county.svi if feature == "svi_percentile" else county.uninsured for county in counties
        ]
        observed = [value for value in values if value is not None]
        divisors[feature] = 100.0 if observed and max(observed) > 1.5 else 1.0
    return divisors


def _feature_value(county: County, feature: str, divisors: Mapping[str, float]) -> float:
    if feature == "log_population":
        return math.log(county.population)
    if feature == "svi_percentile":
        if county.svi is None:
            raise PeerClusterError("missing svi entered the matrix")
        return county.svi / divisors.get(feature, 1.0)
    if feature == "uninsured_percentile":
        if county.uninsured is None:
            raise PeerClusterError("missing uninsured entered the matrix")
        return county.uninsured / divisors.get(feature, 1.0)
    if feature == "rucc_2023":
        if county.rucc is None:
            raise PeerClusterError("missing rural-urban code entered the matrix")
        return float(county.rucc)
    if feature == "january_tavg_c":
        if county.tavg is None:
            raise PeerClusterError("missing temperature entered the matrix")
        return county.tavg
    if feature == "january_prcp_mm":
        if county.prcp is None:
            raise PeerClusterError("missing precipitation entered the matrix")
        return county.prcp
    if feature == "human_published":
        return 1.0 if county.human == HUMAN_PUBLISHED else 0.0
    if feature == "tick_established":
        return 1.0 if county.tick == "Established" else 0.0
    if feature == "tick_reported":
        return 1.0 if county.tick == "Reported" else 0.0
    if feature == "tick_unknown":
        return 1.0 if county.tick == "Unknown" else 0.0
    if feature == "pathogen_present":
        return 1.0 if county.pathogen == "Present" else 0.0
    if feature == "pathogen_unknown":
        return 1.0 if county.pathogen == "Unknown" else 0.0
    raise PeerClusterError("unknown feature")


def _scale(raw: Vector) -> tuple[Vector, StandardScaler]:
    scaler = StandardScaler()
    scaled = np.asarray(scaler.fit_transform(raw), dtype=np.float64)
    return scaled, scaler


def _kmeans(scaled: Vector, k: int, seed: int, n_init: int) -> KMeans:
    model = KMeans(
        n_clusters=k,
        init="k-means++",
        n_init=n_init,
        max_iter=MAX_ITER,
        random_state=seed,
        algorithm="lloyd",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(scaled)
    return model


def _labels_only(scaled: Vector, k: int, seed: int, n_init: int) -> Vector | None:
    if len(scaled) <= k:
        return None
    try:
        model = _kmeans(scaled, k, seed, n_init)
    except ValueError:
        return None
    return np.asarray(model.labels_, dtype=int)


def _relabel(labels: Vector, fips: Sequence[str]) -> Vector:
    order = sorted(
        range(K_PRIMARY),
        key=lambda label: (
            -int(np.sum(labels == label)),
            min((fips[i] for i in range(len(fips)) if labels[i] == label), default=""),
        ),
    )
    mapping = {old: new for new, old in enumerate(order, start=1)}
    return np.asarray([mapping[int(label)] for label in labels], dtype=int)


def _centers(scaled: Vector, labels: Vector) -> tuple[tuple[float, ...], ...]:
    centers: list[tuple[float, ...]] = []
    for cluster_id in range(1, K_PRIMARY + 1):
        members = scaled[labels == cluster_id]
        if len(members) == 0:
            centers.append(tuple(float("nan") for _ in range(scaled.shape[1])))
        else:
            centers.append(tuple(float(value) for value in members.mean(axis=0)))
    return tuple(centers)


def _place(qualified: Vector, labels: Vector, n: int) -> tuple[int | None, ...]:
    placed: list[int | None] = [None] * n
    cursor = 0
    for index, keep in enumerate(qualified):
        if keep:
            placed[index] = int(labels[cursor])
            cursor += 1
    return tuple(placed)


def _silhouette(scaled: Vector, labels: Vector) -> float | None:
    if len(set(labels.tolist())) < 2 or len(labels) <= K_PRIMARY:
        return None
    try:
        score = float(silhouette_score(scaled, labels, metric="euclidean"))
    except ValueError:
        return None
    return score if math.isfinite(score) else None


def _ward_labels(scaled: Vector) -> Vector | None:
    if len(scaled) <= K_PRIMARY:
        return None
    try:
        model = AgglomerativeClustering(n_clusters=K_PRIMARY, linkage="ward")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fitted = model.fit_predict(scaled)
    except ValueError:
        return None
    return np.asarray(fitted, dtype=int)


def _weight_ari(scaled: Vector, features: Sequence[str], labels: Vector) -> float | None:
    if "svi_percentile" not in features:
        return None
    weighted = np.array(scaled, copy=True)
    weighted[:, features.index("svi_percentile")] *= 2.0
    refit = _labels_only(weighted, K_PRIMARY, PRIMARY_SEED, N_INIT_PRIMARY)
    return _ari(labels, refit) if refit is not None else None


def _k_grid(scaled: Vector) -> tuple[tuple[int, float], ...]:
    scores: list[tuple[int, float]] = []
    for k in K_GRID:
        labels = _labels_only(scaled, k, PRIMARY_SEED, N_INIT_PRIMARY)
        if labels is None:
            continue
        score = _silhouette(scaled, labels)
        if score is not None:
            scores.append((k, score))
    return tuple(scores)


def _region_holdouts(
    raw: Vector, labels: Vector, regions: Sequence[str]
) -> tuple[tuple[tuple[str, float], ...], tuple[tuple[str, float], ...], float | None]:
    present = [region for region in HEATMAP_REGIONS if region in set(regions)]
    held_in: list[tuple[str, float]] = []
    held_out: list[tuple[str, float]] = []
    for region in present:
        inside = np.asarray([item == region for item in regions], dtype=bool)
        ari_in, ari_out = _holdout(raw, labels, ~inside)
        if ari_in is None:
            return tuple(held_in), tuple(held_out), None
        held_in.append((region, ari_in))
        if ari_out is not None:
            held_out.append((region, ari_out))
    if len(held_in) != len(present) or not held_in:
        return tuple(held_in), tuple(held_out), None
    return tuple(held_in), tuple(held_out), min(value for _region, value in held_in)


def _state_holdouts(
    raw: Vector, labels: Vector, states: Sequence[str]
) -> tuple[float | None, float | None]:
    values: list[float] = []
    for state in sorted(set(states)):
        inside = np.asarray([item == state for item in states], dtype=bool)
        ari_in, _ari_out = _holdout(raw, labels, ~inside)
        if ari_in is not None:
            values.append(ari_in)
    if not values:
        return None, None
    return float(statistics.median(values)), min(values)


def _holdout(raw: Vector, labels: Vector, kept: Vector) -> tuple[float | None, float | None]:
    if int(kept.sum()) <= K_PRIMARY or int((~kept).sum()) == 0:
        return None, None
    try:
        scaled, scaler = _scale(raw[kept])
        model = _kmeans(scaled, K_PRIMARY, PRIMARY_SEED, N_INIT_PRIMARY)
    except (ValueError, FloatingPointError):
        return None, None
    ari_in = _ari(labels[kept], np.asarray(model.labels_, dtype=int))
    held = ~kept
    try:
        transformed = np.asarray(scaler.transform(raw[held]), dtype=np.float64)
        predicted = _assign(transformed, np.asarray(model.cluster_centers_, dtype=np.float64))
    except ValueError:
        return ari_in, None
    return ari_in, _ari(labels[held], predicted)


def _state_interval(
    raw: Vector, labels: Vector, states: Sequence[str]
) -> tuple[float | None, float | None, bool]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, state in enumerate(states):
        grouped[state].append(index)
    keys = tuple(sorted(grouped))

    def statistic(drawn: Sequence[str]) -> float | None:
        positions: list[int] = []
        for state in drawn:
            positions.extend(grouped[state])
        return _bootstrap_ari(raw, labels, positions)

    interval = state_cluster_interval(keys, statistic, PRIMARY_SEED)
    return interval.low, interval.high, interval.estimable


def _county_interval(raw: Vector, labels: Vector) -> tuple[float | None, float | None, bool]:
    positions = tuple(range(len(labels)))

    def statistic(drawn: Sequence[int]) -> float | None:
        return _bootstrap_ari(raw, labels, drawn)

    interval = resample_interval(positions, statistic, ALT_SEED)
    return interval.low, interval.high, interval.estimable


def _bootstrap_ari(raw: Vector, labels: Vector, positions: Sequence[int]) -> float | None:
    if len(positions) <= K_PRIMARY:
        return None
    index = np.asarray(positions, dtype=int)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            scaled, scaler = _scale(raw[index])
            model = _kmeans(scaled, K_PRIMARY, PRIMARY_SEED, N_INIT_BOOTSTRAP)
            full = np.asarray(scaler.transform(raw), dtype=np.float64)
            if not np.isfinite(full).all():
                return None
            predicted = _assign(full, np.asarray(model.cluster_centers_, dtype=np.float64))
    except (ValueError, FloatingPointError):
        return None
    return _ari(labels, predicted)


def _assign(scaled: Vector, centers: Vector) -> Vector:
    distances = ((scaled[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
    return np.asarray(distances.argmin(axis=1), dtype=int)


def _ari(left: Vector | None, right: Vector | None) -> float | None:
    if left is None or right is None or len(left) != len(right) or len(left) < 2:
        return None
    score = float(adjusted_rand_score(left, right))
    return score if math.isfinite(score) else None


def _cramer(labels: Vector, groups: Sequence[str]) -> float | None:
    label_levels = sorted(set(int(label) for label in labels))
    group_levels = sorted(set(groups))
    if len(label_levels) < 2 or len(group_levels) < 2:
        return None
    label_index = {label: index for index, label in enumerate(label_levels)}
    group_index = {group: index for index, group in enumerate(group_levels)}
    table = [[0 for _ in group_levels] for _ in label_levels]
    for label, group in zip(labels, groups, strict=True):
        table[label_index[int(label)]][group_index[group]] += 1
    association = cramers_v(table)
    return None if association is None else association.v


def _max_nonpublish(labels: Vector, nonpublishing: Vector) -> tuple[float | None, int | None]:
    best_share: float | None = None
    best_count: int | None = None
    for cluster_id in range(1, K_PRIMARY + 1):
        members = labels == cluster_id
        size = int(members.sum())
        if size < SMALL_CELL_MINIMUM:
            continue
        count = int(nonpublishing[members].sum())
        share = count / size
        if best_share is None or share > best_share:
            best_share = share
            best_count = count
    return best_share, best_count


def _representatives(
    slice_name: str,
    counties: Sequence[County],
    member_index: Vector,
    scaled: Vector,
    labels: Vector,
    centers: Sequence[Sequence[float]],
) -> tuple[Representative, ...]:
    chosen: list[Representative] = []
    for cluster_id in range(1, K_PRIMARY + 1):
        members = np.flatnonzero(labels == cluster_id)
        if len(members) == 0 or cluster_id - 1 >= len(centers):
            continue
        center = np.asarray(centers[cluster_id - 1], dtype=np.float64)
        if not np.isfinite(center).all():
            continue
        distances = np.sqrt(((scaled[members] - center) ** 2).sum(axis=1))
        order = sorted(
            range(len(members)),
            key=lambda index: (
                float(distances[index]),
                counties[int(member_index[members[index]])].fips,
            ),
        )
        for rank, index in enumerate(order[:3], start=1):
            county = counties[int(member_index[members[index]])]
            chosen.append(
                Representative(
                    slice_name=slice_name,
                    cluster_id=cluster_id,
                    rank=rank,
                    fips=county.fips,
                    name=county.name,
                    state=county.state,
                    distance=float(distances[index]),
                    population=county.population,
                    svi=county.svi,
                    uninsured=county.uninsured,
                    rucc=county.rucc,
                    human=county.human,
                    tick=county.tick,
                    pathogen=county.pathogen,
                )
            )
    return tuple(chosen)


def _density(scaled: Vector, labels: Vector, silhouette: float | None) -> DensityFit:
    sizes = [int(np.sum(labels == cluster_id)) for cluster_id in range(1, K_PRIMARY + 1)]
    share = min(sizes) / len(labels) if labels.size else 1.0
    opened = (silhouette is not None and silhouette < SILHOUETTE_FLOOR) or share < 0.05
    if not opened:
        return DensityFit(False)
    gmm_ari = None
    gmm_sil = None
    try:
        mixture = GaussianMixture(
            n_components=K_PRIMARY,
            covariance_type="diag",
            n_init=3,
            max_iter=200,
            random_state=PRIMARY_SEED,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            gmm_labels = np.asarray(mixture.fit_predict(scaled), dtype=int)
        gmm_ari = _ari(labels, gmm_labels)
        gmm_sil = _silhouette(scaled, gmm_labels)
    except (ValueError, FloatingPointError):
        gmm_ari = None
    db_clusters, db_noise = _noise_counts(
        DBSCAN(eps=0.9, min_samples=40, metric="euclidean").fit_predict(scaled)
    )
    hb_clusters, hb_noise = _noise_counts(
        HDBSCAN(
            min_cluster_size=80,
            min_samples=15,
            cluster_selection_method="eom",
            n_jobs=1,
            copy=True,
        ).fit_predict(scaled)
    )
    return DensityFit(True, gmm_ari, gmm_sil, db_clusters, db_noise, hb_clusters, hb_noise)


def _noise_counts(labels: Vector) -> tuple[int, int]:
    array = np.asarray(labels)
    noise = int(np.sum(array == -1))
    clusters = len({int(label) for label in array if int(label) != -1})
    return clusters, noise


def _stability_failures(
    fit: SliceFit,
    *,
    reproduction: bool,
    sizes_reproduced: bool,
    silhouette_reproduced: bool,
    zero_exclusion: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if reproduction and not sizes_reproduced:
        reasons.append("sizes")
    if reproduction and not silhouette_reproduced:
        reasons.append("silhouette_tolerance")
    if fit.silhouette is None or fit.silhouette < SILHOUETTE_FLOOR:
        reasons.append("silhouette_floor")
    if fit.seed_ari is None or fit.seed_ari < SEED_ARI_BAR:
        reasons.append("seed")
    if not fit.state_estimable or fit.state_low is None or fit.state_low < STATE_ARI_LOW_BAR:
        reasons.append("state_bootstrap")
    if fit.region_min is None or fit.region_min < REGION_ARI_BAR:
        reasons.append("region_holdout")
    if fit.state_holdout_median is None or fit.state_holdout_median < STATE_HOLDOUT_MEDIAN_BAR:
        reasons.append("state_holdout")
    if fit.ward_ari is None or fit.ward_ari < WARD_ARI_BAR:
        reasons.append("ward")
    if fit.weight_ari is None or fit.weight_ari < WEIGHT_ARI_BAR:
        reasons.append("svi_weight")
    if _k_gap(fit):
        reasons.append("k_grid")
    if fit.max_nonpublish_share is not None and fit.max_nonpublish_share >= NONPUBLISH_SHARE_BAR:
        reasons.append("nonpublishing_share")
    if fit.cramer_publishing is not None and fit.cramer_publishing >= CRAMER_BAR:
        reasons.append("publishing_cramer")
    if zero_exclusion and fit.excluded != 0:
        reasons.append("exclusions")
    return tuple(reasons)


def _product_failures(fit: SliceFit, cohort_n: int) -> tuple[str, ...]:
    if not fit.estimable:
        return ("multidomain_not_estimable",)
    coverage = fit.n / cohort_n if cohort_n else 0.0
    reasons = list(
        _stability_failures(
            fit,
            reproduction=False,
            sizes_reproduced=True,
            silhouette_reproduced=True,
            zero_exclusion=False,
        )
    )
    if coverage < COVERAGE_FLOOR:
        reasons.append("climate_coverage")
    if fit.cramer_region is None or fit.cramer_region >= CRAMER_BAR:
        reasons.append("region_cramer")
    return tuple(reasons)


def _k_gap(fit: SliceFit) -> bool:
    if fit.silhouette is None:
        return False
    for k, score in fit.k_silhouettes:
        if k != K_PRIMARY and score >= fit.silhouette + K_SILHOUETTE_GAP:
            return True
    return False


def _empty_slice(name: str, n: int, note: str, excluded: int | None = None) -> SliceFit:
    return SliceFit(
        name=name,
        estimable=False,
        note=note,
        n=0,
        excluded=n if excluded is None else excluded,
        features=SLICE_FEATURES[name],
        percentile_divided=(),
        labels=tuple(None for _ in range(n)),
        silhouette=None,
        sizes=(),
        seed_ari=None,
        ward_ari=None,
        weight_ari=None,
        unscaled_ari=None,
        k_silhouettes=(),
        region_held_in=(),
        region_held_out=(),
        region_min=None,
        state_holdout_median=None,
        state_holdout_min=None,
        state_low=None,
        state_high=None,
        state_estimable=False,
        county_low=None,
        county_high=None,
        county_estimable=False,
        cramer_publishing=None,
        cramer_region=None,
        cramer_human=None,
        cramer_tick=None,
        max_nonpublish_share=None,
        max_nonpublish_count=None,
        centers=(),
        representatives=(),
        density=None,
    )


def _experiments(analysis: Analysis) -> list[ExperimentRow]:
    rows: list[ExperimentRow] = []
    for fit in analysis.slices:
        if not fit.estimable:
            rows.append(
                ExperimentRow(
                    experiment_id=f"110-{fit.name}-not-estimable",
                    model_family="kmeans",
                    hypothesis=f"{fit.name} peer groups were not estimable",
                    config={"spec": SPEC_ID, "note": fit.note},
                    split_definition={"slice": fit.name, "n": 0},
                    status="failed",
                    metrics=(),
                )
            )
            continue
        metrics = [
            _metric("full", "silhouette", fit.silhouette, None, None, fit.n),
            _metric("full", "seed_ari", fit.seed_ari, None, None, fit.n),
            _metric("full", "ward_ari", fit.ward_ari, None, None, fit.n),
            _metric("full", "weight_ari", fit.weight_ari, None, None, fit.n),
            _metric("full", "unscaled_ari", fit.unscaled_ari, None, None, fit.n),
            _metric(
                "state_bootstrap", "ari_low", fit.state_low, fit.state_low, fit.state_high, fit.n
            ),
            _metric(
                "county_bootstrap",
                "ari_low",
                fit.county_low,
                fit.county_low,
                fit.county_high,
                fit.n,
            ),
            _metric("region_holdout", "ari_min", fit.region_min, None, None, fit.n),
            _metric("state_holdout", "ari_median", fit.state_holdout_median, None, None, fit.n),
        ]
        if _composition_publishable(fit.sizes):
            for cluster_id, size in enumerate(fit.sizes, start=1):
                metrics.append(
                    _metric(
                        "full",
                        f"cluster_{cluster_id}_n",
                        float(size),
                        None,
                        None,
                        fit.n if size == 0 else size,
                    )
                )
        rows.append(
            ExperimentRow(
                experiment_id=f"110-{fit.name}-kmeans",
                model_family="kmeans",
                hypothesis=f"Standardized Euclidean K-means peer groups for {fit.name}",
                config={
                    "spec": SPEC_ID,
                    "k": K_PRIMARY,
                    "seed": PRIMARY_SEED,
                    "alt_seed": ALT_SEED,
                    "n_init": N_INIT_PRIMARY,
                    "features": list(fit.features),
                    "percentile_divided": list(fit.percentile_divided),
                },
                split_definition={"slice": fit.name, "n": fit.n, "excluded": fit.excluded},
                status="succeeded",
                metrics=tuple(metric for metric in metrics if metric.metric_value is not None),
            )
        )
    return rows


def _metric(
    split_name: str,
    metric_name: str,
    metric_value: float | None,
    ci_low: float | None,
    ci_high: float | None,
    n: int | None,
) -> ModelMetricRow:
    if n is not None and 0 < n < SMALL_CELL_MINIMUM:
        return ModelMetricRow(split_name, metric_name, None, None, None, None)
    return ModelMetricRow(split_name, metric_name, metric_value, ci_low, ci_high, n)


def _append_metric(
    rows: list[EdaMetric],
    name: str,
    value: float | None,
    n: int,
    dimensions: dict[str, str],
) -> None:
    if value is None or not math.isfinite(value):
        return
    if 0 < n < SMALL_CELL_MINIMUM:
        return
    rows.append(
        EdaMetric(
            metric_name=name,
            metric_value=value,
            n_underlying=n,
            geography_type="national",
            geography_id="US",
            dimensions=dimensions,
            unit="index" if name != "cluster_size" else "counties",
        )
    )


def _composition_publishable(sizes: Sequence[int]) -> bool:
    if not sizes:
        return False
    small = [size for size in sizes if 0 < size < SMALL_CELL_MINIMUM]
    if not small:
        return True
    return not (len(small) == 1 or sum(small) < SMALL_CELL_MINIMUM)


def _share_publishable(share: float | None, count: int | None) -> bool:
    if share is None or count is None:
        return False
    return count == 0 or count >= SMALL_CELL_MINIMUM


def _climate_index(
    rows: Sequence[Mapping[str, object]] | None,
) -> dict[str, tuple[float | None, int, float | None, int]]:
    if rows is None:
        return {}
    index: dict[str, tuple[float | None, int, float | None, int]] = {}
    for row in rows:
        fips = _fips(row.get("COUNTY_FIPS"))
        index[fips] = (
            _optional_float(row.get("TAVG_C")),
            _day_count(row.get("TAVG_DAYS")),
            _optional_float(row.get("PRCP_MM")),
            _day_count(row.get("PRCP_DAYS")),
        )
    return index


def _county(
    row: Mapping[str, object],
    climate: Mapping[str, tuple[float | None, int, float | None, int]],
) -> County:
    fips = _fips(row.get("FIPS"))
    state = _text(row.get("STATE"))
    if state not in CENSUS_REGIONS:
        raise PeerClusterError("state is outside the Census map")
    human = _text(row.get("HUMAN_STATUS"))
    tick = _text(row.get("TICK_STATUS"))
    pathogen = _text(row.get("BURGDORFERI_STATUS"))
    if human not in {HUMAN_PUBLISHED, HUMAN_NONE}:
        raise PeerClusterError("human status is outside the frozen levels")
    if tick not in TICK_ALLOWED:
        raise PeerClusterError("tick status is outside the frozen levels")
    if pathogen not in PATHOGEN_ALLOWED:
        raise PeerClusterError("pathogen status is outside the frozen levels")
    population = _required_float(row.get("POPULATION"))
    attached = climate.get(fips, (None, 0, None, 0))
    return County(
        fips=fips,
        name=_text(row.get("COUNTY")),
        state=state,
        region=CENSUS_REGIONS[state],
        population=population,
        svi=_optional_float(row.get("SVI_PERCENTILE")),
        uninsured=_optional_float(row.get("UNINSURED_PERCENTILE")),
        rucc=_rucc(row.get("RUCC_2023")),
        human=human,
        tick=tick,
        pathogen=pathogen,
        tavg=attached[0],
        tavg_days=attached[1],
        prcp=attached[2],
        prcp_days=attached[3],
    )


def _fips(value: object) -> str:
    if isinstance(value, Decimal):
        value = int(value)
    if isinstance(value, int) and not isinstance(value, bool):
        text = f"{value:05d}"
    elif isinstance(value, str) and value.strip().isdigit():
        text = value.strip().zfill(5)
    else:
        raise PeerClusterError("county id is not five digits")
    if len(text) != 5:
        raise PeerClusterError("county id is not five digits")
    return text


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PeerClusterError("required text is missing")
    return value.strip()


def _required_float(value: object) -> float:
    number = _optional_float(value)
    if number is None:
        raise PeerClusterError("required number is missing")
    return number


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise PeerClusterError("number is not numeric")
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _day_count(value: object) -> int:
    number = _optional_float(value)
    if number is None:
        return 0
    return int(number)


def _rucc(value: object) -> int | None:
    number = _optional_float(value)
    if number is None:
        return None
    if not number.is_integer():
        return None
    code = int(number)
    if code < 1 or code > 9:
        return None
    return code
