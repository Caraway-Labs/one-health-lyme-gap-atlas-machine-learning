"""K-prototypes community types inside the established-tick gap.

The functions here do not open Snowflake. County rows stay in memory. Cluster
membership is a descriptive grouping. It is not disease risk and not a score.
The distance is the Huang k-prototypes distance used by the kmodes library.
That package is not a pinned dependency, so the distance lives here.
"""

from __future__ import annotations

import math
import statistics
import uuid
import warnings
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np
from sklearn.metrics import adjusted_rand_score, silhouette_score  # type: ignore[import-untyped]

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.county_mca import (
    FINE_POPULATION_EDGES,
    FINE_POPULATION_LABELS,
    REFERENCE_DOUBLE_GAP,
    REFERENCE_WIDER,
)
from lyme_gap_atlas_ml.coverage_audit import PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.peer_clusters import sklearn_version
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import FindingRecord, QueryRecord
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric
from lyme_gap_atlas_ml.state_regimes import (
    EXPECTED_COUNTIES,
    HUMAN_NONE,
    HUMAN_PUBLISHED,
    METHODOLOGY_VERSION,
    PATHOGEN_LEVELS,
    PATHOGEN_PRESENT,
    SCHEMA_VERSION,
    SCOPE,
    TICK_ESTABLISHED,
    TICK_LEVELS,
)
from lyme_gap_atlas_ml.test_selection import resample_interval

SPEC_ID = "120-gap-communities/v1"
ISSUE_NUMBER = 120
SEED = 1202026
ALT_SEED = 1202027
BOOTSTRAP_SEED = 1202028
RUN_PREFIX = "120-gap-communities-"
SMALL_CELL = 11
K_GRID = (2, 3, 4, 5, 6)
MAX_ITER = 50
SEED_ARI_MIN = 0.80
BOOTSTRAP_LOW_MIN = 0.70
SILHOUETTE_TIE = 0.01
MIN_CLUSTER_FLOOR = 30
MIN_CLUSTER_SHARE = 0.05
PROTOTYPE_DISTANCE_MIN = 1.0
MAX_SHARE_ADVANCE = 0.70
EXPECTED_PUBLISHED = 651
EXPECTED_UNLINKED = 2493
QUERY_NAMES = ("release_identity", "county_rows")
SOURCE_OBJECTS = (
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
)
NUMERIC_FEATURES = ("log_population", "svi_percentile", "uninsured_percentile")
CATEGORICAL_FEATURES = (
    "rucc",
    "scapularis_status",
    "pacificus_status",
    "burgdorferi_status",
)
SVI_EDGES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
SVI_BIN_LABELS = (
    "le_0.1",
    "0.1_to_0.2",
    "0.2_to_0.3",
    "0.3_to_0.4",
    "0.4_to_0.5",
    "0.5_to_0.6",
    "0.6_to_0.7",
    "0.7_to_0.8",
    "0.8_to_0.9",
    "gt_0.9",
)
RUCC_TEXT = {
    "1": "large metropolitan (code 1)",
    "2": "medium metropolitan (code 2)",
    "3": "small metropolitan (code 3)",
    "4": "nonmetropolitan, urban population 20,000 or more, adjacent to a metro area (code 4)",
    "5": "nonmetropolitan, urban population 20,000 or more, not adjacent to a metro area (code 5)",
    "6": "nonmetropolitan, urban population 2,500 to 19,999, adjacent to a metro area (code 6)",
    "7": "nonmetropolitan, urban population 2,500 to 19,999, not adjacent to a metro area (code 7)",
    "8": "rural or under 2,500 urban population, adjacent to a metro area (code 8)",
    "9": "rural or under 2,500 urban population, not adjacent to a metro area (code 9)",
}
_EXPERIMENT_NAMESPACE = uuid.UUID("12000000-0000-5000-8000-000000000120")
_RURAL_CODES = frozenset({"7", "8", "9"})
Vector = np.ndarray[Any, Any]


class GapCommunityError(ValueError):
    """The county frame or the k-prototypes fit cannot be used."""


@dataclass(frozen=True)
class County:
    fips: str
    name: str
    state: str
    population: float
    svi: float
    uninsured: float
    rucc: str
    human_status: str
    tick_status: str
    scapularis_status: str
    pacificus_status: str
    burgdorferi_status: str

    @property
    def in_wider_gap(self) -> bool:
        return self.human_status == HUMAN_NONE and self.tick_status == TICK_ESTABLISHED

    @property
    def in_double_gap(self) -> bool:
        return self.in_wider_gap and self.burgdorferi_status == PATHOGEN_PRESENT


@dataclass(frozen=True)
class Gate:
    ok: bool
    reasons: tuple[str, ...]
    release_id: str
    bundle_sha256: str
    county_n: int
    published_n: int
    unlinked_n: int
    svi_scaled: bool
    uninsured_scaled: bool


@dataclass(frozen=True)
class Frequency:
    feature: str
    label: str
    n: int


@dataclass(frozen=True)
class KCandidate:
    k: int
    converged: bool
    alt_converged: bool
    seed_ari: float | None
    silhouette: float | None
    min_size: int
    sizes: tuple[int, ...]
    bootstrap_low: float | None
    bootstrap_high: float | None
    bootstrap_estimable: bool
    labels: tuple[int, ...]


@dataclass(frozen=True)
class ExampleCounty:
    fips: str
    name: str
    state: str
    population: float
    svi: float
    uninsured: float
    rucc: str
    scapularis_status: str
    pacificus_status: str
    burgdorferi_status: str
    in_double_gap: bool
    distance: float


@dataclass(frozen=True)
class ClusterProfile:
    cluster_id: int
    n: int
    population_total: float
    median_population: float
    median_svi: float
    median_uninsured: float
    median_rucc: float | None
    rural_share: float
    mode_rucc: str
    mode_scapularis: str
    mode_pacificus: str
    mode_pathogen: str
    double_gap_n: int
    nearest_prototype_distance: float | None
    distinguishable: bool
    examples: tuple[ExampleCounty, ...]


@dataclass(frozen=True)
class AssignmentRow:
    fips: str
    county_name: str
    state: str
    cluster_id: int
    in_double_gap: bool
    population: float
    svi: float
    uninsured: float
    rucc: str
    scapularis_status: str
    pacificus_status: str
    burgdorferi_status: str


@dataclass(frozen=True)
class ExperimentMetric:
    split_name: str
    metric_name: str
    metric_value: float | None
    n: int | None


@dataclass(frozen=True)
class ExperimentRow:
    experiment_id: str
    hypothesis: str
    model_family: str
    config: dict[str, object]
    split_definition: dict[str, object]
    status: str
    metrics: tuple[ExperimentMetric, ...]


@dataclass(frozen=True)
class Analysis:
    gate: Gate
    cohort_n: int
    double_gap_n: int
    double_gap_outside: int
    excluded_n: int
    gamma: float | None
    candidates: tuple[KCandidate, ...]
    selected: KCandidate | None
    reported: KCandidate | None
    profiles: tuple[ClusterProfile, ...]
    assignments: tuple[AssignmentRow, ...]
    population_bins: tuple[Frequency, ...]
    svi_bins: tuple[Frequency, ...]
    uninsured_bins: tuple[Frequency, ...]
    rucc_bins: tuple[Frequency, ...]
    most_people_cluster: int | None
    most_rural_cluster: int | None
    method_disposition: str
    product_disposition: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class _PrototypeFit:
    labels: Vector
    converged: bool
    iterations: int


def load_gap_queries(text: str) -> dict[str, str]:
    """Split the issue 120 validation file and reject unsafe SQL."""
    return load_marked_queries(text, QUERY_NAMES)


def minimum_cluster_size(n: int) -> int:
    """Return the frozen floor for a cohort of size n."""
    return max(MIN_CLUSTER_FLOOR, math.ceil(MIN_CLUSTER_SHARE * n))


def category_label(value: object) -> str:
    """Keep a blank surveillance status as its own category."""
    if value is None:
        return "blank"
    if not isinstance(value, str):
        return "blank"
    text = value.strip()
    return "blank" if text == "" else text


def rucc_label(value: object) -> str:
    """Keep a blank or non-standard rural-urban code as its own category."""
    if value is None or isinstance(value, bool):
        return "blank" if value is None else "unlisted"
    if isinstance(value, int) and value in range(1, 10):
        return str(value)
    if isinstance(value, float) and value.is_integer() and int(value) in range(1, 10):
        return str(int(value))
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return "blank"
        if text in {str(code) for code in range(1, 10)}:
            return text
    return "unlisted"


def scale_numeric(raw: Vector) -> tuple[Vector, float]:
    """Z-score columns and return the kmodes gamma on the scaled matrix."""
    if raw.ndim != 2 or raw.shape[0] == 0 or raw.shape[1] == 0:
        raise GapCommunityError("numeric matrix is empty")
    std = np.std(raw, axis=0, ddof=0)
    if not np.isfinite(std).all() or bool(np.any(std <= 0)):
        raise GapCommunityError("a numeric column has no variation")
    mean = np.mean(raw, axis=0)
    scaled = (raw - mean) / std
    gamma = 0.5 * float(np.mean(np.std(scaled, axis=0, ddof=0)))
    if not math.isfinite(gamma) or gamma <= 0:
        raise GapCommunityError("gamma is not positive")
    return np.asarray(scaled, dtype=np.float64), gamma


def fit_k_prototypes(
    numeric: Vector,
    categorical: Vector,
    k: int,
    seed: int,
    gamma: float,
) -> _PrototypeFit:
    """Fit one Huang k-prototypes start. Labels are 0..k-1 in init order."""
    n_rows = int(numeric.shape[0])
    if k < 2 or k >= n_rows:
        raise GapCommunityError("k is outside the cohort")
    if categorical.shape[0] != n_rows:
        raise GapCommunityError("categorical rows do not match the numeric rows")
    generator = np.random.default_rng(seed)
    seeds = generator.choice(n_rows, size=k, replace=False)
    centers_num = np.asarray(numeric[seeds], dtype=np.float64).copy()
    centers_cat = np.asarray(categorical[seeds]).copy()
    labels = np.full(n_rows, -1, dtype=np.int64)
    converged = False
    iterations = 0
    for iterations in range(1, MAX_ITER + 1):
        assigned = _assign(numeric, categorical, centers_num, centers_cat, gamma)
        assigned = _fill_empty(numeric, categorical, assigned, gamma, k)
        if iterations > 1 and np.array_equal(assigned, labels):
            labels = assigned
            converged = True
            break
        labels = assigned
        if int(np.min(np.bincount(labels, minlength=k))) == 0:
            converged = False
            break
        centers_num, centers_cat = _update_centers(numeric, categorical, labels, k)
    empty = int(np.min(np.bincount(labels, minlength=k))) == 0 if len(labels) else True
    return _PrototypeFit(labels=labels, converged=converged and not empty, iterations=iterations)


def select_k(candidates: Sequence[KCandidate], minimum_size: int) -> KCandidate | None:
    """Apply the frozen stability rule. The double-gap table is not an input."""
    passing = [candidate for candidate in candidates if _passes(candidate, minimum_size)]
    if not passing:
        return None
    leader = max(passing, key=lambda candidate: _silhouette_key(candidate))
    leader_score = _silhouette_key(leader)
    near = [
        candidate
        for candidate in passing
        if leader_score - _silhouette_key(candidate) <= SILHOUETTE_TIE
    ]
    return min(near, key=lambda candidate: candidate.k)


def evaluate_gate(release: Mapping[str, object], raw_rows: Sequence[Mapping[str, object]]) -> Gate:
    """Check the pin and the national counts before any cluster is named."""
    reasons: list[str] = []
    release_id = _text(release.get("RELEASE_ID"))
    schema = _text(release.get("SCHEMA_VERSION"))
    methodology = _text(release.get("METHODOLOGY_VERSION"))
    scope = _text(release.get("SCOPE"))
    bundle = _text(release.get("BUNDLE_SHA256")).lower()
    if release_id != PINNED_RELEASE_ID:
        reasons.append("release id differs from the pin")
    if schema != SCHEMA_VERSION or methodology != METHODOLOGY_VERSION or scope != SCOPE:
        reasons.append("release schema, methodology, or scope differs from the pin")
    if bundle != PINNED_BUNDLE_SHA256:
        reasons.append("bundle sha differs from the pin")
    published = 0
    unlinked = 0
    seen: set[str] = set()
    svi_values: list[float] = []
    uninsured_values: list[float] = []
    for raw in raw_rows:
        if _text(raw.get("RELEASE_ID")) != release_id:
            reasons.append("a county row has a different release id")
            break
        fips = _fips(raw.get("FIPS"))
        if fips is None or fips in seen:
            reasons.append("FIPS are not unique five-digit ids")
            break
        seen.add(fips)
        human = _text(raw.get("HUMAN_STATUS"))
        if human == HUMAN_PUBLISHED:
            published += 1
        elif human == HUMAN_NONE:
            unlinked += 1
        else:
            reasons.append("human status is outside the published levels")
            break
        if _text(raw.get("TICK_STATUS")) not in TICK_LEVELS:
            reasons.append("tick status is outside the published levels")
            break
        if _optional_status(raw.get("SCAPULARIS_STATUS"), TICK_LEVELS) is None:
            reasons.append("blacklegged tick status is outside the published levels")
            break
        if _optional_status(raw.get("PACIFICUS_STATUS"), TICK_LEVELS) is None:
            reasons.append("western blacklegged tick status is outside the published levels")
            break
        if _optional_status(raw.get("BURGDORFERI_STATUS"), PATHOGEN_LEVELS) is None:
            reasons.append("pathogen status is outside the published levels")
            break
        svi = _float(raw.get("SVI_PERCENTILE"))
        uninsured = _float(raw.get("UNINSURED_PERCENTILE"))
        if svi is None or uninsured is None:
            reasons.append("a percentile is missing")
            break
        svi_values.append(svi)
        uninsured_values.append(uninsured)
        if not _population_ok(raw.get("POPULATION")):
            reasons.append("population is missing or not positive")
            break
        if rucc_label(raw.get("RUCC_2023")) not in {str(code) for code in range(1, 10)}:
            reasons.append("rural-urban code is outside 1 through 9")
            break
        if not _text(raw.get("STATE")) or not _text(raw.get("COUNTY")):
            reasons.append("state or county name is blank")
            break
    if len(raw_rows) != EXPECTED_COUNTIES:
        reasons.append("county count is not the predeclared count")
    if published != EXPECTED_PUBLISHED or unlinked != EXPECTED_UNLINKED:
        reasons.append("published floor or no-county-linked count differs from the pin")
    svi_scaled = bool(svi_values) and max(svi_values) > 1.5
    uninsured_scaled = bool(uninsured_values) and max(uninsured_values) > 1.5
    return Gate(
        ok=not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
        release_id=release_id,
        bundle_sha256=bundle,
        county_n=len(raw_rows),
        published_n=published,
        unlinked_n=unlinked,
        svi_scaled=svi_scaled,
        uninsured_scaled=uninsured_scaled,
    )


def fit_cohort(
    raw_rows: Sequence[Mapping[str, object]],
    gate: Gate,
    *,
    run_bootstrap: bool = True,
) -> Analysis:
    """Fit the frozen k grid. Tests may skip the bootstrap and therefore cannot keep."""
    if not gate.ok:
        raise GapCommunityError("fit requires a passing gate")
    counties = tuple(_county(raw, gate) for raw in raw_rows)
    _require_unit_interval(counties)
    cohort = tuple(county for county in counties if county.in_wider_gap)
    double_gap_n = sum(county.in_double_gap for county in cohort)
    double_outside = sum(1 for county in counties if _double_outside(county))
    usable, excluded = _usable(cohort)
    population_bins = _population_bins(usable)
    svi_bins = _percentile_bins("svi_percentile", [county.svi for county in usable])
    uninsured_bins = _percentile_bins("uninsured_percentile", [county.uninsured for county in usable])  # noqa: E501
    rucc_bins = _rucc_bins(usable)
    if len(usable) <= K_GRID[-1]:
        raise GapCommunityError("the clustering cohort is smaller than the k grid")
    numeric, categorical, gamma = _matrices(usable)
    minimum = minimum_cluster_size(len(usable))
    candidates = tuple(
        _assess_k(numeric, categorical, gamma, k, [county.fips for county in usable], run_bootstrap)
        for k in K_GRID
    )
    selected = select_k(candidates, minimum)
    reported = selected if selected is not None else _fallback(candidates)
    profiles, assignments = _profiles(usable, reported, numeric, categorical, gamma)
    most_people = _most_people(profiles)
    most_rural = _most_rural(profiles)
    method, product, reasons = _disposition(
        cohort_n=len(cohort),
        double_gap_n=double_gap_n,
        double_outside=double_outside,
        excluded_n=excluded,
        selected=selected,
        profiles=profiles,
        most_people=most_people,
        most_rural=most_rural,
        bootstrap_ran=run_bootstrap,
    )
    return Analysis(
        gate=gate,
        cohort_n=len(cohort),
        double_gap_n=double_gap_n,
        double_gap_outside=double_outside,
        excluded_n=excluded,
        gamma=gamma,
        candidates=candidates,
        selected=selected,
        reported=reported,
        profiles=profiles,
        assignments=assignments,
        population_bins=population_bins,
        svi_bins=svi_bins,
        uninsured_bins=uninsured_bins,
        rucc_bins=rucc_bins,
        most_people_cluster=most_people,
        most_rural_cluster=most_rural,
        method_disposition=method,
        product_disposition=product,
        reasons=reasons,
    )


def lab_metrics(analysis: Analysis) -> tuple[EdaMetric, ...]:
    """Aggregate metrics. A caller-side count below 11 is suppressed by the writer."""
    rows: list[EdaMetric] = [
        _metric("cohort_count", analysis.cohort_n, analysis.cohort_n),
        _metric("double_gap_count", analysis.double_gap_n, analysis.double_gap_n),
        _metric("excluded_count", analysis.excluded_n, max(analysis.cohort_n, 1)),
    ]
    if analysis.gamma is not None:
        rows.append(_metric("gamma", analysis.gamma, analysis.cohort_n))
    for candidate in analysis.candidates:
        dimensions = {"k": str(candidate.k)}
        rows.append(
            _metric(
                "seed_ari",
                candidate.seed_ari,
                analysis.cohort_n,
                dimensions=dimensions,
            )
        )
        rows.append(
            _metric(
                "silhouette",
                candidate.silhouette,
                analysis.cohort_n,
                dimensions=dimensions,
            )
        )
        rows.append(
            _metric(
                "bootstrap_low",
                candidate.bootstrap_low,
                analysis.cohort_n,
                dimensions=dimensions,
            )
        )
        rows.append(
            _metric(
                "bootstrap_high",
                candidate.bootstrap_high,
                analysis.cohort_n,
                dimensions=dimensions,
            )
        )
        rows.append(_metric("min_cluster_size", candidate.min_size, candidate.min_size, dimensions))
    for profile in analysis.profiles:
        dimensions = {"cluster": str(profile.cluster_id)}
        rows.append(_metric("cluster_size", profile.n, profile.n, dimensions=dimensions))
        rows.append(
            _metric("population_total", profile.population_total, profile.n, dimensions=dimensions)
        )
        rows.append(
            _metric("median_population", profile.median_population, profile.n,
                dimensions=dimensions)
        )
        rows.append(_metric("median_svi", profile.median_svi, profile.n, dimensions=dimensions))
        rows.append(
            _metric(
                "median_uninsured",
                profile.median_uninsured,
                profile.n,
                dimensions=dimensions,
            )
        )
        rows.append(
            _metric(
                "double_gap_in_cluster",
                profile.double_gap_n,
                profile.double_gap_n,
                dimensions=dimensions,
            )
        )
        if profile.nearest_prototype_distance is not None:
            rows.append(
                _metric(
                    "prototype_distance",
                    profile.nearest_prototype_distance,
                    profile.n,
                    dimensions=dimensions,
                )
            )
    for frequency in (
        *analysis.population_bins,
        *analysis.svi_bins,
        *analysis.uninsured_bins,
        *analysis.rucc_bins,
    ):
        rows.append(
            _metric(
                "cohort_bin_count",
                frequency.n,
                frequency.n,
                dimensions={"feature": frequency.feature, "bin": frequency.label},
            )
        )
    return tuple(rows)


def build_findings(analysis: Analysis) -> tuple[FindingRecord, ...]:
    """Aggregate findings. County names and 1-10 counts stay out of these statements."""
    reported_k = "none" if analysis.reported is None else str(analysis.reported.k)
    selected_k = "none" if analysis.selected is None else str(analysis.selected.k)
    gamma = "not computed" if analysis.gamma is None else f"{analysis.gamma:.4f}"
    people = _profile(analysis.profiles, analysis.most_people_cluster)
    rural = _profile(analysis.profiles, analysis.most_rural_cluster)
    people_text = "not defined" if people is None else _people(people.population_total)
    rural_text = "not defined" if rural is None else f"type {rural.cluster_id}"
    statement = (
        f"Cohort {analysis.cohort_n}. Double gap {analysis.double_gap_n}. "
        f"Excluded numerics {analysis.excluded_n}. Gamma {gamma}. "
        f"Selected k {selected_k}. Reported k {reported_k}. "
        f"Most people {people_text}. Most rural {rural_text}. "
        f"Method {analysis.method_disposition}. Product {analysis.product_disposition}. "
        "Cluster membership is not disease risk and not a production score."
    )
    rows = [
        FindingRecord(
            topic="gap community partition",
            statement=statement,
            disposition=analysis.method_disposition,
            n_underlying=max(analysis.cohort_n, SMALL_CELL),
            effect_size=None if analysis.selected is None else analysis.selected.silhouette,
            evidence={
                "selected_k": selected_k,
                "method": analysis.method_disposition,
                "product": analysis.product_disposition,
            },
        )
    ]
    for profile in analysis.profiles:
        if profile.n < SMALL_CELL:
            continue
        rows.append(
            FindingRecord(
                topic=f"type {profile.cluster_id} profile",
                statement=_finding_profile(profile),
                disposition=analysis.method_disposition,
                n_underlying=profile.n,
                effect_size=profile.nearest_prototype_distance,
                evidence={"cluster": str(profile.cluster_id), "mode_rucc": profile.mode_rucc},
            )
        )
    return tuple(rows)


def experiment_rows(analysis: Analysis, run_id: str) -> tuple[ExperimentRow, ...]:
    """One experiment row per candidate k. The selected row is marked in the config."""
    rows: list[ExperimentRow] = []
    for candidate in analysis.candidates:
        selected = analysis.selected is not None and candidate.k == analysis.selected.k
        rows.append(
            ExperimentRow(
                experiment_id=str(uuid.uuid5(_EXPERIMENT_NAMESPACE, f"{run_id}:{candidate.k}")),
                hypothesis=(
                    "K-prototypes community types inside the established-tick gap "
                    "are a descriptive partition, not a score"
                ),
                model_family="k-prototypes",
                config={
                    "spec": SPEC_ID,
                    "k": candidate.k,
                    "seed": SEED,
                    "alt_seed": ALT_SEED,
                    "bootstrap_seed": BOOTSTRAP_SEED,
                    "gamma": analysis.gamma,
                    "selected": selected,
                    "use_as_model_feature": False,
                    "implementation": "internal_huang_kmodes_distance",
                    "sklearn": sklearn_version(),
                },
                split_definition={
                    "cohort": "established_tick_gap",
                    "exhibit_only": True,
                    "k": str(candidate.k),
                },
                status="succeeded" if candidate.converged else "failed",
                metrics=(
                    ExperimentMetric("primary", "seed_ari", candidate.seed_ari, analysis.cohort_n),
                    ExperimentMetric(
                        "primary", "silhouette", candidate.silhouette, analysis.cohort_n
                    ),
                    ExperimentMetric(
                        "bootstrap", "ari_low", candidate.bootstrap_low, analysis.cohort_n
                    ),
                    ExperimentMetric(
                        "bootstrap", "ari_high", candidate.bootstrap_high, analysis.cohort_n
                    ),
                    ExperimentMetric("primary", "min_cluster_size", candidate.min_size,
                        candidate.min_size),
                ),
            )
        )
    return tuple(rows)


def query_record(
    name: str,
    sql_text: str,
    rows_returned: int,
    elapsed_ms: int,
    snowflake_query_id: str | None,
) -> QueryRecord:
    """Build one registry query row. The name is not stored; the SQL text is."""
    del name
    return QueryRecord(
        sql_text=sql_text,
        rows_returned=rows_returned,
        elapsed_ms=elapsed_ms,
        snowflake_query_id=snowflake_query_id,
    )


def stopped_finding(gate: Gate) -> FindingRecord:
    """One finding when the national gate stops the fit."""
    reason = "; ".join(gate.reasons) if gate.reasons else "the national gate stopped the fit"
    return FindingRecord(
        topic="gap community partition",
        statement=f"Stopped before k-prototypes. {reason}.",
        disposition="stop",
        n_underlying=max(gate.county_n, SMALL_CELL),
        evidence={"status": "stopped"},
    )


def _assess_k(
    numeric: Vector,
    categorical: Vector,
    gamma: float,
    k: int,
    fips: Sequence[str],
    run_bootstrap: bool,
) -> KCandidate:
    primary = fit_k_prototypes(numeric, categorical, k, SEED, gamma)
    alternate = fit_k_prototypes(numeric, categorical, k, ALT_SEED, gamma)
    seed_ari = None
    if primary.converged and alternate.converged:
        seed_ari = _ari(primary.labels, alternate.labels)
    labels = _relabel(primary.labels, fips)
    sizes = tuple(int(np.sum(labels == cluster_id)) for cluster_id in range(1, k + 1))
    silhouette = _silhouette(numeric, categorical, primary.labels,
        gamma) if primary.converged else None
    low = high = None
    estimable = False
    if run_bootstrap and primary.converged:
        low, high, estimable = _bootstrap(numeric, categorical, primary.labels, k, gamma)
    return KCandidate(
        k=k,
        converged=primary.converged,
        alt_converged=alternate.converged,
        seed_ari=seed_ari,
        silhouette=silhouette,
        min_size=min(sizes) if sizes else 0,
        sizes=sizes,
        bootstrap_low=low,
        bootstrap_high=high,
        bootstrap_estimable=estimable,
        labels=tuple(int(label) for label in labels),
    )


def _bootstrap(
    numeric: Vector,
    categorical: Vector,
    labels: Vector,
    k: int,
    gamma: float,
) -> tuple[float | None, float | None, bool]:
    n_rows = int(numeric.shape[0])

    def statistic(draw: Sequence[int]) -> float | None:
        return _bootstrap_ari(draw, numeric, categorical, labels, k, gamma)

    interval = resample_interval(tuple(range(n_rows)), statistic, BOOTSTRAP_SEED)
    return interval.low, interval.high, interval.estimable


def _bootstrap_ari(
    draw: Sequence[int],
    numeric: Vector,
    categorical: Vector,
    labels: Vector,
    k: int,
    gamma: float,
) -> float | None:
    try:
        index = np.asarray(draw, dtype=np.int64)
        if index.size != numeric.shape[0]:
            return None
        fitted = fit_k_prototypes(numeric[index], categorical[index], k, SEED, gamma)
        if not fitted.converged:
            return None
        centers_num, centers_cat = _update_centers(numeric[index], categorical[index],
            fitted.labels, k)
        predicted = _assign(numeric, categorical, centers_num, centers_cat, gamma)
    except (ValueError, FloatingPointError, GapCommunityError):
        return None
    return _ari(labels, predicted)


def _profiles(
    counties: Sequence[County],
    reported: KCandidate | None,
    numeric: Vector,
    categorical: Vector,
    gamma: float,
) -> tuple[tuple[ClusterProfile, ...], tuple[AssignmentRow, ...]]:
    if reported is None or len(reported.labels) != len(counties):
        return (), ()
    labels = np.asarray(reported.labels, dtype=np.int64)
    gaps = _prototype_gaps(counties, labels, numeric, categorical, gamma, reported.k)
    profiles: list[ClusterProfile] = []
    assignments: list[AssignmentRow] = []
    for index, county in enumerate(counties):
        assignments.append(
            AssignmentRow(
                fips=county.fips,
                county_name=county.name,
                state=county.state,
                cluster_id=int(labels[index]),
                in_double_gap=county.in_double_gap,
                population=county.population,
                svi=county.svi,
                uninsured=county.uninsured,
                rucc=county.rucc,
                scapularis_status=county.scapularis_status,
                pacificus_status=county.pacificus_status,
                burgdorferi_status=county.burgdorferi_status,
            )
        )
    for cluster_id in range(1, reported.k + 1):
        members = [county for county, label in zip(counties, labels,
            strict=True) if label == cluster_id]
        member_index = np.flatnonzero(labels == cluster_id)
        if not members:
            continue
        rucc_numbers = [int(county.rucc) for county in members if county.rucc.isdigit()]
        distance = None if cluster_id - 1 >= len(gaps) else gaps[cluster_id - 1]
        profiles.append(
            ClusterProfile(
                cluster_id=cluster_id,
                n=len(members),
                population_total=float(sum(county.population for county in members)),
                median_population=float(statistics.median(county.population for county in members)),
                median_svi=float(statistics.median(county.svi for county in members)),
                median_uninsured=float(statistics.median(county.uninsured for county in members)),
                median_rucc=(
                    None if not rucc_numbers else float(statistics.median(rucc_numbers))
                ),
                rural_share=(
                    sum(county.rucc in _RURAL_CODES for county in members) / len(members)
                ),
                mode_rucc=_mode(county.rucc for county in members),
                mode_scapularis=_mode(county.scapularis_status for county in members),
                mode_pacificus=_mode(county.pacificus_status for county in members),
                mode_pathogen=_mode(county.burgdorferi_status for county in members),
                double_gap_n=sum(county.in_double_gap for county in members),
                nearest_prototype_distance=distance,
                distinguishable=distance is not None and distance >= PROTOTYPE_DISTANCE_MIN,
                examples=_examples(counties, member_index, numeric, categorical, gamma),
            )
        )
    return tuple(profiles), tuple(assignments)


def _examples(
    counties: Sequence[County],
    member_index: Vector,
    numeric: Vector,
    categorical: Vector,
    gamma: float,
) -> tuple[ExampleCounty, ...]:
    if len(member_index) == 0:
        return ()
    center_num = np.mean(numeric[member_index], axis=0)
    center_cat = [_mode(categorical[index, feature] for index in member_index) for feature
        in range(categorical.shape[1])]
    ranked: list[tuple[float, str, int]] = []
    for index in member_index:
        distance = _point_distance(numeric[index], categorical[index], center_num, center_cat,
            gamma)
        ranked.append((distance, counties[int(index)].fips, int(index)))
    ranked.sort()
    examples: list[ExampleCounty] = []
    for distance, _fips, index in ranked[:3]:
        county = counties[index]
        examples.append(
            ExampleCounty(
                fips=county.fips,
                name=county.name,
                state=county.state,
                population=county.population,
                svi=county.svi,
                uninsured=county.uninsured,
                rucc=county.rucc,
                scapularis_status=county.scapularis_status,
                pacificus_status=county.pacificus_status,
                burgdorferi_status=county.burgdorferi_status,
                in_double_gap=county.in_double_gap,
                distance=distance,
            )
        )
    return tuple(examples)


def _prototype_gaps(
    counties: Sequence[County],
    labels: Vector,
    numeric: Vector,
    categorical: Vector,
    gamma: float,
    k: int,
) -> tuple[float, ...]:
    del counties
    centers_num: list[Vector] = []
    centers_cat: list[tuple[str, ...]] = []
    present: list[bool] = []
    for cluster_id in range(1, k + 1):
        member_index = np.flatnonzero(labels == cluster_id)
        present.append(len(member_index) > 0)
        if len(member_index) == 0:
            centers_num.append(np.zeros(numeric.shape[1], dtype=np.float64))
            centers_cat.append(tuple("" for _ in range(categorical.shape[1])))
            continue
        centers_num.append(np.mean(numeric[member_index], axis=0))
        centers_cat.append(
            tuple(
                _mode(categorical[index, feature] for index in member_index)
                for feature in range(categorical.shape[1])
            )
        )
    gaps: list[float] = []
    for left in range(k):
        if not present[left]:
            gaps.append(0.0)
            continue
        distances = [
            _point_distance(centers_num[left], centers_cat[left], centers_num[right],
                centers_cat[right], gamma)
            for right in range(k)
            if right != left and present[right]
        ]
        gaps.append(min(distances) if distances else 0.0)
    return tuple(gaps)


def _disposition(
    *,
    cohort_n: int,
    double_gap_n: int,
    double_outside: int,
    excluded_n: int,
    selected: KCandidate | None,
    profiles: Sequence[ClusterProfile],
    most_people: int | None,
    most_rural: int | None,
    bootstrap_ran: bool,
) -> tuple[str, str, tuple[str, ...]]:
    reasons: list[str] = []
    if cohort_n != REFERENCE_WIDER:
        reasons.append("the established-tick gap count differs from 810")
    if double_gap_n != REFERENCE_DOUBLE_GAP:
        reasons.append("the double-gap count differs from 228")
    if double_outside != 0:
        reasons.append("a double-gap county sits outside the established-tick gap")
    if excluded_n != 0:
        reasons.append("a cohort county was excluded for a missing numeric")
    if not bootstrap_ran:
        reasons.append("the stability bootstrap was not run")
    if selected is None:
        reasons.append("no k passed the stability rule")
    elif any(not profile.distinguishable for profile in profiles):
        reasons.append("a chosen cluster is not distinguishable")
    method = "revise" if reasons else "keep"
    fitted_n = sum(profile.n for profile in profiles)
    shares = [profile.n / fitted_n for profile in profiles if fitted_n]
    dominated = bool(shares) and max(shares) >= MAX_SHARE_ADVANCE
    if selected is None or not bootstrap_ran:
        product = "stop"
    elif (
        method == "keep"
        and most_people is not None
        and most_rural is not None
        and not dominated
    ):
        product = "advance"
    else:
        product = "investigate"
    return method, product, tuple(reasons)


def _fallback(candidates: Sequence[KCandidate]) -> KCandidate | None:
    converged = [candidate for candidate in candidates if candidate.converged and
        candidate.seed_ari is not None]
    still_fit = [candidate for candidate in candidates if candidate.converged]
    pool = converged or still_fit or list(candidates)
    if not pool:
        return None
    return min(
        pool,
        key=lambda candidate: (
            -(candidate.seed_ari if candidate.seed_ari is not None else -2.0),
            -_silhouette_key(candidate),
            candidate.k,
        ),
    )


def _passes(candidate: KCandidate, minimum_size: int) -> bool:
    return (
        candidate.converged
        and candidate.alt_converged
        and candidate.seed_ari is not None
        and candidate.seed_ari >= SEED_ARI_MIN
        and candidate.bootstrap_estimable
        and candidate.bootstrap_low is not None
        and candidate.bootstrap_low >= BOOTSTRAP_LOW_MIN
        and candidate.silhouette is not None
        and math.isfinite(candidate.silhouette)
        and candidate.min_size >= minimum_size
    )


def _matrices(counties: Sequence[County]) -> tuple[Vector, Vector, float]:
    raw = np.asarray(
        [
            [math.log(county.population), county.svi, county.uninsured]
            for county in counties
        ],
        dtype=np.float64,
    )
    categorical = np.asarray(
        [
            [
                county.rucc,
                county.scapularis_status,
                county.pacificus_status,
                county.burgdorferi_status,
            ]
            for county in counties
        ],
        dtype=object,
    )
    scaled, gamma = scale_numeric(raw)
    return scaled, categorical, gamma


def _usable(cohort: Sequence[County]) -> tuple[tuple[County, ...], int]:
    kept = [
        county
        for county in cohort
        if county.population > 0 and math.isfinite(county.svi) and math.isfinite(county.uninsured)
    ]
    return tuple(kept), len(cohort) - len(kept)


def _assign(
    numeric: Vector,
    categorical: Vector,
    centers_num: Vector,
    centers_cat: Vector,
    gamma: float,
) -> Vector:
    diff = numeric[:, None, :] - centers_num[None, :, :]
    distance = np.sum(diff * diff, axis=2)
    for feature in range(categorical.shape[1]):
        distance += gamma * (categorical[:, feature, None] != centers_cat[None, :, feature])
    return np.asarray(np.argmin(distance, axis=1), dtype=np.int64)


def _fill_empty(
    numeric: Vector,
    categorical: Vector,
    labels: Vector,
    gamma: float,
    k: int,
) -> Vector:
    labels = np.asarray(labels, dtype=np.int64).copy()
    for _ in range(k):
        counts = np.bincount(labels, minlength=k)
        empty = np.flatnonzero(counts == 0)
        if len(empty) == 0:
            return labels
        donor = int(np.argmax(counts))
        members = np.flatnonzero(labels == donor)
        if len(members) < 2:
            return labels
        center_num = np.mean(numeric[members], axis=0)
        center_cat = np.asarray(
            [_mode(categorical[index, feature] for index in members) for feature in
                range(categorical.shape[1])],
            dtype=object,
        )
        distances = [
            _point_distance(numeric[index], categorical[index], center_num, center_cat, gamma)
            for index in members
        ]
        chosen = members[int(np.argmax(np.asarray(distances, dtype=np.float64)))]
        labels[int(chosen)] = int(empty[0])
    return labels


def _update_centers(
    numeric: Vector,
    categorical: Vector,
    labels: Vector,
    k: int,
) -> tuple[Vector, Vector]:
    centers_num = np.zeros((k, numeric.shape[1]), dtype=np.float64)
    centers_cat = np.empty((k, categorical.shape[1]), dtype=object)
    for cluster_id in range(k):
        members = np.flatnonzero(labels == cluster_id)
        if len(members) == 0:
            centers_cat[cluster_id, :] = ""
            continue
        centers_num[cluster_id] = np.mean(numeric[members], axis=0)
        for feature in range(categorical.shape[1]):
            centers_cat[cluster_id, feature] = _mode(categorical[index,
                feature] for index in members)
    return centers_num, centers_cat


def _point_distance(
    left_num: Vector,
    left_cat: Vector | Sequence[object],
    right_num: Vector,
    right_cat: Vector | Sequence[object],
    gamma: float,
) -> float:
    numeric = float(np.sum((np.asarray(left_num, dtype=np.float64) - np.asarray(right_num)) ** 2))
    mismatch = sum(str(left) != str(right) for left, right in zip(left_cat, right_cat, strict=True))
    return numeric + gamma * mismatch


def _silhouette(numeric: Vector, categorical: Vector, labels: Vector, gamma: float) -> float | None:
    if len(set(int(label) for label in labels)) < 2:
        return None
    distance = _pairwise(numeric, categorical, gamma)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            score = float(silhouette_score(distance, labels, metric="precomputed"))
    except ValueError:
        return None
    return score if math.isfinite(score) else None


def _pairwise(numeric: Vector, categorical: Vector, gamma: float) -> Vector:
    diff = numeric[:, None, :] - numeric[None, :, :]
    distance = np.sum(diff * diff, axis=2)
    for feature in range(categorical.shape[1]):
        distance += gamma * (categorical[:, feature, None] != categorical[None, :, feature])
    np.fill_diagonal(distance, 0.0)
    return np.asarray(distance, dtype=np.float64)


def _relabel(labels: Vector, fips: Sequence[str]) -> Vector:
    if len(labels) == 0:
        return np.asarray([], dtype=np.int64)
    k = int(np.max(labels)) + 1
    order = sorted(
        range(k),
        key=lambda label: (
            -int(np.sum(labels == label)),
            min((fips[index] for index in range(len(fips)) if int(labels[index]) == label),
                default=""),
        ),
    )
    mapping = {old: new for new, old in enumerate(order, start=1)}
    return np.asarray([mapping[int(label)] for label in labels], dtype=np.int64)


def _ari(left: Vector, right: Vector) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    score = float(adjusted_rand_score(left, right))
    return score if math.isfinite(score) else None


def _mode(values: Sequence[object] | Any) -> str:
    counts: Counter[str] = Counter(str(value) for value in values)
    if not counts:
        return "blank"
    best = max(counts.values())
    return min(label for label, count in counts.items() if count == best)


def _most_people(profiles: Sequence[ClusterProfile]) -> int | None:
    if not profiles:
        return None
    return min(profiles, key=lambda profile: (-profile.population_total,
        profile.cluster_id)).cluster_id


def _most_rural(profiles: Sequence[ClusterProfile]) -> int | None:
    ranked = [profile for profile in profiles if profile.median_rucc is not None]
    if not ranked:
        return None
    return min(
        ranked,
        key=lambda profile: (
            -(profile.median_rucc if profile.median_rucc is not None else -1.0),
            -profile.rural_share,
            profile.cluster_id,
        ),
    ).cluster_id


def _profile(profiles: Sequence[ClusterProfile], cluster_id: int | None) -> ClusterProfile | None:
    if cluster_id is None:
        return None
    for profile in profiles:
        if profile.cluster_id == cluster_id:
            return profile
    return None


def _finding_profile(profile: ClusterProfile) -> str:
    rural = RUCC_TEXT.get(profile.mode_rucc, profile.mode_rucc)
    return (
        f"Type {profile.cluster_id} has {_count_text(profile.n)} counties and "
        f"{_people(profile.population_total)}. Median vulnerability percentile "
        f"{profile.median_svi:.2f}. Median uninsured percentile {profile.median_uninsured:.2f}. "
        f"Modal rural-urban code is {rural}. Modal blacklegged status {profile.mode_scapularis}. "
        f"Modal western blacklegged status {profile.mode_pacificus}. "
        f"Modal pathogen status {profile.mode_pathogen}. "
        f"Double-gap counties in this type: {_count_text(profile.double_gap_n)}. "
        "This type is not a disease-risk group."
    )


def _count_text(count: int) -> str:
    if 0 < count < SMALL_CELL:
        return "a count below 11"
    return str(count)


def _people(population: float) -> str:
    if population >= 1_000_000:
        return f"{population / 1_000_000:.2f} million people"
    return f"{population / 1_000:.1f} thousand people"


def _metric(
    name: str,
    value: float | None,
    n: int,
    dimensions: Mapping[str, object] | None = None,
) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        metric_value=value,
        n_underlying=n,
        geography_type="national",
        geography_id="US",
        dimensions=dimensions,
        unit="count" if name.endswith("count") or name.endswith("size") else "value",
    )


def _population_bins(counties: Sequence[County]) -> tuple[Frequency, ...]:
    if not counties:
        return ()
    values = np.asarray([county.population for county in counties], dtype=np.float64)
    indexes = np.digitize(values, FINE_POPULATION_EDGES, right=False)
    return tuple(
        Frequency("population", label, int(np.sum(indexes == index)))
        for index, label in enumerate(FINE_POPULATION_LABELS)
    )


def _percentile_bins(feature: str, values: Sequence[float]) -> tuple[Frequency, ...]:
    if not values:
        return ()
    indexes = np.digitize(np.asarray(values, dtype=np.float64), SVI_EDGES, right=True)
    return tuple(
        Frequency(feature, label, int(np.sum(indexes == index)))
        for index, label in enumerate(SVI_BIN_LABELS)
    )


def _rucc_bins(counties: Sequence[County]) -> tuple[Frequency, ...]:
    counts = Counter(county.rucc for county in counties)
    return tuple(
        Frequency("rucc", label, counts[label]) for label in sorted(counts)
    )


def _county(raw: Mapping[str, object], gate: Gate) -> County:
    fips = _fips(raw.get("FIPS"))
    population = _float(raw.get("POPULATION"))
    svi = _float(raw.get("SVI_PERCENTILE"))
    uninsured = _float(raw.get("UNINSURED_PERCENTILE"))
    if fips is None or population is None or svi is None or uninsured is None:
        raise GapCommunityError("a gated county row is incomplete")
    if gate.svi_scaled:
        svi = svi / 100.0
    if gate.uninsured_scaled:
        uninsured = uninsured / 100.0
    scapularis = _optional_status(raw.get("SCAPULARIS_STATUS"), TICK_LEVELS)
    pacificus = _optional_status(raw.get("PACIFICUS_STATUS"), TICK_LEVELS)
    pathogen = _optional_status(raw.get("BURGDORFERI_STATUS"), PATHOGEN_LEVELS)
    if scapularis is None or pacificus is None or pathogen is None:
        raise GapCommunityError("a gated status is outside the published levels")
    return County(
        fips=fips,
        name=_text(raw.get("COUNTY")),
        state=_text(raw.get("STATE")),
        population=population,
        svi=svi,
        uninsured=uninsured,
        rucc=rucc_label(raw.get("RUCC_2023")),
        human_status=_text(raw.get("HUMAN_STATUS")),
        tick_status=_text(raw.get("TICK_STATUS")),
        scapularis_status=scapularis,
        pacificus_status=pacificus,
        burgdorferi_status=pathogen,
    )


def _require_unit_interval(counties: Sequence[County]) -> None:
    for county in counties:
        if not 0.0 <= county.svi <= 1.0 or not 0.0 <= county.uninsured <= 1.0:
            raise GapCommunityError("a percentile is outside 0 to 1 after the unit rule")


def _double_outside(county: County) -> bool:
    return (
        county.human_status == HUMAN_NONE
        and county.tick_status == TICK_ESTABLISHED
        and county.burgdorferi_status == PATHOGEN_PRESENT
        and not county.in_wider_gap
    )


def _optional_status(value: object, levels: frozenset[str]) -> str | None:
    if value is None:
        return "blank"
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text == "":
        return "blank"
    if text in levels:
        return text
    return None


def _population_ok(value: object) -> bool:
    number = _float(value)
    return number is not None and number > 0


def _silhouette_key(candidate: KCandidate) -> float:
    if candidate.silhouette is None or not math.isfinite(candidate.silhouette):
        return -2.0
    return candidate.silhouette


def _fips(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        text = f"{value:05d}"
    elif isinstance(value, float) and value.is_integer():
        text = f"{int(value):05d}"
    else:
        text = str(value).strip()
    if len(text) == 5 and text.isdigit():
        return text
    return None


def _float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(number):
        return None
    return number


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()
