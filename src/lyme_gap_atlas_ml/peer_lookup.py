"""Nearest-county lookup on the issue 120 feature set.

The functions here do not open Snowflake. County rows stay in the returned
objects. Aggregate lab records suppress a denominator below 11. The results
write-up may name counties. Chart records do not.

Squared Euclidean distance on the embedding equals the issue 120 mixed
distance at gamma 0.5. Cosine uses that same embedding. Neighbor search is
exact. There is no random start.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import numpy as np
from sklearn.metrics import silhouette_score  # type: ignore[import-untyped]

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.coverage_audit import (
    PINNED_BUNDLE_SHA256,
    PINNED_RELEASE_ID,
    REFERENCE_COUNTIES,
    REFERENCE_NO_COUNTY_LINKED_RECORD,
    REFERENCE_PUBLISHED_HUMAN_FLOOR,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import FindingRecord
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric
from lyme_gap_atlas_ml.state_regimes import (
    HUMAN_NONE,
    HUMAN_PUBLISHED,
    METHODOLOGY_VERSION,
    PATHOGEN_PRESENT,
    SCHEMA_VERSION,
    SCOPE,
    TICK_ESTABLISHED,
    TICK_LEVELS,
)

SPEC_ID = "192-peer-county-lookup/v1"
ISSUE_NUMBER = 192
RUN_PREFIX = "192-peer-county-lookup-"
PRIMARY_SEED = 1922026
SECOND_SEED = 1922027
K_PRIMARY = 5
K_SENSITIVITY = 15
GAMMA = 0.5
CATEGORY_SCALE = math.sqrt(GAMMA / 2.0)
TIE_EPS = 1e-12
BOOTSTRAP_REPLICATES = 200
MIN_CONTRIBUTING = 500
BOOTSTRAP_MEDIAN_MIN = 0.50
BOOTSTRAP_LOW_MIN = 0.30
SEED_MEDIAN_GAP_MAX = 0.05
COSINE_JACCARD_MIN = 0.40
LSO_AGREEMENT_MIN = 0.50
LSO_BASELINE_GAP_MIN = 0.10
LSO_JACCARD_MIN = 0.10
SINGLE_BLOCK_MAX = 0.60
DROP_ALL_MIN = 0.80
RECOVERY_MIN = 0.95
CROSS_STATE_MIN = 0.50
LSO_JACCARD_ADVANCE = 0.20
IN_SAMPLE_GAP_MIN = 0.05
REFERENCE_WIDER = 810
REFERENCE_DOUBLE = 228
ASSIGNMENT_N = 810
GAP_RUN_ID = "120-gap-communities-20261026T1355Z"
N_STATES = 51
QUERY_NAMES = ("release_identity", "county_rows", "gap_clusters")
SOURCE_OBJECTS = (
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.GAP_COMMUNITY_ASSIGNMENTS_120",
)
RUCC_LEVELS = tuple(str(code) for code in range(1, 10)) + ("blank", "unlisted")
SPECIES_LEVELS = ("Established", "Reported", "No records", "Unknown", "blank")
PATHOGEN_LEVELS = ("Present", "No records", "Unknown", "blank")
SPECIES_ALLOWED = frozenset(SPECIES_LEVELS) - {"blank"}
PATHOGEN_ALLOWED = frozenset(PATHOGEN_LEVELS) - {"blank"}
HUMAN_LEVELS = frozenset({HUMAN_PUBLISHED, HUMAN_NONE})
BLOCKS = (
    "svi_percentile",
    "uninsured_percentile",
    "log_population",
    "rucc",
    "scapularis_status",
    "pacificus_status",
    "burgdorferi_status",
)
NUMERIC_BLOCKS = ("svi_percentile", "uninsured_percentile", "log_population")
Vector = np.ndarray[Any, Any]


class PeerLookupError(ValueError):
    """The county frame or a frozen gate cannot be applied."""


@dataclass(frozen=True)
class County:
    fips: str
    name: str
    state: str
    population: float
    svi: float
    uninsured: float
    rucc: int
    human_status: str
    scapularis: str
    pacificus: str
    burgdorferi: str
    tick_status: str


@dataclass(frozen=True)
class NeighborRow:
    fips: str
    county_name: str
    state: str
    cluster_id: int | None
    situation: str
    prototype_cluster_id: int
    euclidean_neighbors: str
    cosine_neighbors: str
    euclidean_distance_k: float
    baseline_peer_n: int
    leave_state_type_agreement: float | None


@dataclass(frozen=True)
class Example:
    fips: str
    county_name: str
    state: str
    distance: float
    neighbors: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True)
class Ablation:
    block: str
    dropped_jaccard: float
    alone_jaccard: float


@dataclass(frozen=True)
class ExperimentMetric:
    split_name: str
    metric_name: str
    metric_value: float | None
    n: int | None
    ci_low: float | None = None
    ci_high: float | None = None


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
    county_n: int
    state_n: int
    published_n: int
    absent_n: int
    wider_n: int
    double_n: int
    assignment_n: int
    sklearn_version: str
    determinism_jaccard: float
    cosine_jaccard: float
    type_agreement_euclidean: float | None
    type_agreement_euclidean_n: int
    type_agreement_cosine: float | None
    type_agreement_baseline: float | None
    type_agreement_baseline_n: int
    type_agreement_lso: float | None
    type_agreement_lso_n: int
    type_agreement_lso_cosine: float | None
    type_agreement_lso_baseline: float | None
    type_agreement_lso_baseline_n: int
    lso_jaccard: float
    cross_state_share: float
    bootstrap_median: float | None
    bootstrap_low: float | None
    bootstrap_high: float | None
    bootstrap_estimable: bool
    bootstrap_median_b: float | None
    bootstrap_failed: int
    silhouette: float | None
    recovery: float
    situation_agreement: float | None
    k15_bootstrap_median: float | None
    k15_lso_agreement: float | None
    distance_deciles: tuple[float, ...]
    cosine_deciles: tuple[float, ...]
    ablations: tuple[Ablation, ...]
    in_sample_gap: float | None
    lso_baseline_gap: float | None
    rows: tuple[NeighborRow, ...]
    examples_near: tuple[Example, ...]
    examples_far: tuple[Example, ...]
    method: str
    product: str
    failures: tuple[str, ...]
    distance_values: tuple[float, ...]


def load_peer_queries(text: str) -> dict[str, str]:
    """Split the issue 192 validation file and reject unsafe SQL."""
    return load_marked_queries(text, QUERY_NAMES)


def release_gate(row: Mapping[str, object]) -> None:
    """Stop unless the pinned release identity is unchanged."""
    checks = {
        "RELEASE_ID": PINNED_RELEASE_ID,
        "SCHEMA_VERSION": SCHEMA_VERSION,
        "METHODOLOGY_VERSION": METHODOLOGY_VERSION,
        "SCOPE": SCOPE,
        "BUNDLE_SHA256": PINNED_BUNDLE_SHA256,
    }
    for key, expected in checks.items():
        if _text(row.get(key)) != expected:
            raise PeerLookupError(f"release pin mismatch for {key}")


def parse_counties(
    rows: Sequence[Mapping[str, object]],
    *,
    release_id: str,
    enforce_gate: bool = True,
) -> tuple[County, ...]:
    """Parse atlas rows. The national gate is the pinned county and status counts."""
    counties = tuple(_county(row, release_id=release_id) for row in rows)
    fips = [county.fips for county in counties]
    if len(fips) != len(set(fips)):
        raise PeerLookupError("duplicate FIPS")
    if not enforce_gate:
        return tuple(sorted(counties, key=lambda county: county.fips))
    states = {county.state for county in counties}
    published = sum(county.human_status == HUMAN_PUBLISHED for county in counties)
    absent = sum(county.human_status == HUMAN_NONE for county in counties)
    if len(counties) != REFERENCE_COUNTIES or len(states) != N_STATES:
        raise PeerLookupError("county gate is not 3144 counties and 51 states")
    if published != REFERENCE_PUBLISHED_HUMAN_FLOOR or absent != REFERENCE_NO_COUNTY_LINKED_RECORD:
        raise PeerLookupError("published-floor gate is not 651 and 2493")
    return tuple(sorted(counties, key=lambda county: county.fips))


def parse_clusters(
    rows: Sequence[Mapping[str, object]],
    *,
    national: bool = True,
) -> dict[str, int]:
    """Read the pinned issue 120 assignments. National runs require 810 rows."""
    clusters: dict[str, int] = {}
    for row in rows:
        raw_fips = _text(row.get("FIPS"))
        fips = raw_fips.zfill(5) if raw_fips.isdigit() else raw_fips
        if len(fips) != 5 or not fips.isdigit():
            raise PeerLookupError("assignment FIPS must be five digits")
        if fips in clusters:
            raise PeerLookupError("duplicate assignment FIPS")
        cluster_id = _cluster_id(row.get("CLUSTER_ID"))
        if cluster_id not in (1, 2):
            raise PeerLookupError("assignment cluster ids are not 1 and 2")
        clusters[fips] = cluster_id
    if national and len(clusters) != ASSIGNMENT_N:
        raise PeerLookupError("assignment table does not have 810 rows")
    if set(clusters.values()) != {1, 2}:
        raise PeerLookupError("assignment cluster ids are not 1 and 2")
    return clusters


def score_counties(
    counties: Sequence[County],
    clusters: Mapping[str, int],
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    min_contributing: int = MIN_CONTRIBUTING,
) -> Analysis:
    """Fit the frozen lookup. The script uses the default replicate count."""
    ordered = tuple(sorted(counties, key=lambda county: county.fips))
    if len({county.fips for county in ordered}) != len(ordered):
        raise PeerLookupError("duplicate FIPS")
    missing = [fips for fips in clusters if fips not in {county.fips for county in ordered}]
    if missing:
        raise PeerLookupError("assignment FIPS is not in the atlas")
    n = len(ordered)
    if n <= K_SENSITIVITY:
        raise PeerLookupError("county count is not above k")
    raw, blocks = _design(ordered)
    numeric = _scale_numeric(raw, np.arange(n))
    embedding = _embedding(numeric, blocks, BLOCKS[3:])
    euclid_15, _wide_dist = _neighbors(embedding, np.arange(n), K_SENSITIVITY, "euclidean")
    euclid_5, euclid_dist = _neighbors(embedding, np.arange(n), K_PRIMARY, "euclidean")
    if not np.array_equal(euclid_5, euclid_15[:, :K_PRIMARY]):
        raise PeerLookupError("k=5 list is not the prefix of k=15")
    cosine_5, cosine_dist = _neighbors(embedding, np.arange(n), K_PRIMARY, "cosine")
    determinism = _mean_jaccard(
        euclid_5,
        _neighbors(embedding, np.arange(n), K_PRIMARY, "euclidean")[0],
    )
    labels = np.array(
        [clusters.get(county.fips, -1) for county in ordered],
        dtype=int,
    )
    situations = np.array([_situation_code(county) for county in ordered], dtype=int)
    states = np.array([county.state for county in ordered])
    proto_labels, recovery = _prototypes(ordered, labels, raw, blocks)
    type_euclid, type_euclid_n, type_rates = _type_rates(euclid_5, labels)
    type_cosine, _cosine_n, _cosine_rates = _type_rates(cosine_5, labels)
    baseline_n = _baseline_counts(ordered)
    type_base, type_base_n = _baseline_agreement(ordered, labels, held_out=False)
    lso_15, lso_cosine_15 = _leave_state(raw, blocks, states, K_SENSITIVITY)
    lso_5 = lso_15[:, :K_PRIMARY]
    lso_cosine = lso_cosine_15[:, :K_PRIMARY]
    type_lso, type_lso_n, lso_rates = _type_rates(lso_5, labels)
    type_lso_cosine, _, _ = _type_rates(lso_cosine, labels)
    type_lso_k15, _, _ = _type_rates(lso_15, labels)
    type_lso_base, type_lso_base_n = _baseline_agreement(ordered, labels, held_out=True)
    lso_jaccard = _mean_jaccard(euclid_5, lso_5)
    cross_state = _cross_state_share(euclid_5, states)
    cosine_jaccard = _mean_jaccard(euclid_5, cosine_5)
    situation_agreement, _, _ = _type_rates(euclid_5, situations)
    boot_5, boot_15, boot_low, boot_high, boot_ok, boot_failed = _bootstrap_pair(
        embedding,
        euclid_5,
        euclid_15,
        PRIMARY_SEED,
        replicates,
        min_contributing,
    )
    boot_b, _, _, _, _, _ = _bootstrap_pair(
        embedding,
        euclid_5,
        euclid_5,
        SECOND_SEED,
        replicates,
        min_contributing,
    )
    ablations = _ablations(raw, blocks, euclid_5)
    silhouette = _silhouette(embedding, proto_labels)
    in_gap = _gap(type_euclid, type_base)
    lso_gap = _gap(type_lso, type_lso_base)
    failures = _failures(
        determinism=determinism,
        cosine_jaccard=cosine_jaccard,
        type_lso=type_lso,
        lso_gap=lso_gap,
        lso_jaccard=lso_jaccard,
        bootstrap_median=boot_5,
        bootstrap_low=boot_low,
        bootstrap_estimable=boot_ok,
        bootstrap_median_b=boot_b,
        silhouette=silhouette,
        recovery=recovery,
        ablations=ablations,
    )
    method = "keep" if not failures else "revise"
    product = _product(
        method,
        cross_state=cross_state,
        lso_jaccard=lso_jaccard,
        in_gap=in_gap,
    )
    rows, near, far = _rows(
        ordered,
        labels,
        situations,
        proto_labels,
        euclid_5,
        cosine_5,
        euclid_dist,
        baseline_n,
        lso_rates,
    )
    return Analysis(
        county_n=n,
        state_n=len({county.state for county in ordered}),
        published_n=sum(county.human_status == HUMAN_PUBLISHED for county in ordered),
        absent_n=sum(county.human_status == HUMAN_NONE for county in ordered),
        wider_n=sum(_wider(county) for county in ordered),
        double_n=sum(_double(county) for county in ordered),
        assignment_n=int(np.sum(labels >= 0)),
        sklearn_version=version("scikit-learn"),
        determinism_jaccard=determinism,
        cosine_jaccard=cosine_jaccard,
        type_agreement_euclidean=type_euclid,
        type_agreement_euclidean_n=type_euclid_n,
        type_agreement_cosine=type_cosine,
        type_agreement_baseline=type_base,
        type_agreement_baseline_n=type_base_n,
        type_agreement_lso=type_lso,
        type_agreement_lso_n=type_lso_n,
        type_agreement_lso_cosine=type_lso_cosine,
        type_agreement_lso_baseline=type_lso_base,
        type_agreement_lso_baseline_n=type_lso_base_n,
        lso_jaccard=lso_jaccard,
        cross_state_share=cross_state,
        bootstrap_median=boot_5,
        bootstrap_low=boot_low,
        bootstrap_high=boot_high,
        bootstrap_estimable=boot_ok,
        bootstrap_median_b=boot_b,
        bootstrap_failed=boot_failed,
        silhouette=silhouette,
        recovery=recovery,
        situation_agreement=situation_agreement,
        k15_bootstrap_median=boot_15,
        k15_lso_agreement=type_lso_k15,
        distance_deciles=_deciles(euclid_dist),
        cosine_deciles=_deciles(cosine_dist),
        ablations=ablations,
        in_sample_gap=in_gap,
        lso_baseline_gap=lso_gap,
        rows=rows,
        examples_near=near,
        examples_far=far,
        method=method,
        product=product,
        failures=failures,
        distance_values=tuple(float(value) for value in euclid_dist),
    )


def lab_metrics(analysis: Analysis) -> list[EdaMetric]:
    """Aggregate metrics. A denominator below 11 is left for the writer to suppress."""
    rows: list[EdaMetric] = [
        _metric("county_n", analysis.county_n, float(analysis.county_n), "count"),
        _metric("assignment_n", analysis.assignment_n, float(analysis.assignment_n), "count"),
        _metric("wider_gap_n", analysis.wider_n, float(analysis.wider_n), "count"),
        _metric("double_gap_n", analysis.double_n, float(analysis.double_n), "count"),
    ]
    _rate(rows, "determinism_jaccard", analysis.determinism_jaccard, analysis.county_n)
    _rate(rows, "cosine_euclidean_jaccard", analysis.cosine_jaccard, analysis.county_n)
    _rate(
        rows,
        "type_agreement_euclidean",
        analysis.type_agreement_euclidean,
        analysis.type_agreement_euclidean_n,
    )
    _rate(
        rows,
        "type_agreement_cosine",
        analysis.type_agreement_cosine,
        analysis.type_agreement_euclidean_n,
    )
    _rate(
        rows,
        "type_agreement_baseline",
        analysis.type_agreement_baseline,
        analysis.type_agreement_baseline_n,
    )
    _rate(
        rows,
        "type_agreement_lso_euclidean",
        analysis.type_agreement_lso,
        analysis.type_agreement_lso_n,
    )
    _rate(
        rows,
        "type_agreement_lso_cosine",
        analysis.type_agreement_lso_cosine,
        analysis.type_agreement_lso_n,
    )
    _rate(
        rows,
        "type_agreement_lso_baseline",
        analysis.type_agreement_lso_baseline,
        analysis.type_agreement_lso_baseline_n,
    )
    _rate(rows, "lso_neighbor_jaccard", analysis.lso_jaccard, analysis.county_n)
    _rate(rows, "cross_state_share", analysis.cross_state_share, analysis.county_n)
    _rate(rows, "bootstrap_median_jaccard", analysis.bootstrap_median, analysis.county_n)
    _rate(rows, "bootstrap_low_jaccard", analysis.bootstrap_low, analysis.county_n)
    _rate(rows, "bootstrap_high_jaccard", analysis.bootstrap_high, analysis.county_n)
    _rate(rows, "bootstrap_median_seed_b", analysis.bootstrap_median_b, analysis.county_n)
    _rate(rows, "prototype_recovery", analysis.recovery, analysis.assignment_n)
    _rate(rows, "prototype_silhouette", analysis.silhouette, analysis.county_n)
    _rate(rows, "situation_agreement", analysis.situation_agreement, analysis.county_n)
    _rate(rows, "k15_bootstrap_median", analysis.k15_bootstrap_median, analysis.county_n)
    _rate(rows, "k15_lso_type_agreement", analysis.k15_lso_agreement, analysis.type_agreement_lso_n)
    _rate(
        rows,
        "in_sample_agreement_gap",
        analysis.in_sample_gap,
        analysis.type_agreement_euclidean_n,
    )
    _rate(rows, "lso_agreement_gap", analysis.lso_baseline_gap, analysis.type_agreement_lso_n)
    for index, value in enumerate(analysis.distance_deciles, start=1):
        rows.append(
            _metric(f"euclidean_distance_decile_{index}", analysis.county_n, value, "distance")
        )
    for block in analysis.ablations:
        _rate(rows, f"ablation_drop_{block.block}", block.dropped_jaccard, analysis.county_n)
        _rate(rows, f"ablation_alone_{block.block}", block.alone_jaccard, analysis.county_n)
    return rows


def lab_findings(analysis: Analysis) -> tuple[FindingRecord, ...]:
    """Method and product calls. County names stay in the write-up."""
    failed = ", ".join(analysis.failures) if analysis.failures else "none"
    method = FindingRecord(
        topic="peer county lookup",
        statement=(
            f"Euclidean nearest-neighbor disposition is {analysis.method}. "
            f"Gate failures: {failed}. "
            "A neighbor is similar on the listed context features only. "
            "No ground truth exists, so this is a lookup aid."
        ),
        disposition=analysis.method if analysis.method in {"keep", "revise", "stop"} else "revise",
        n_underlying=analysis.county_n,
        effect_size=analysis.lso_jaccard,
        ci_low=analysis.bootstrap_low,
        ci_high=analysis.bootstrap_high,
        uncertainty_note="Bootstrap band for neighbor lists. Not a disease-rate interval.",
        evidence={
            "cosine_jaccard": analysis.cosine_jaccard,
            "lso_jaccard": analysis.lso_jaccard,
            "recovery": analysis.recovery,
            "bootstrap_median": analysis.bootstrap_median,
        },
    )
    product_word = {"advance": "keep", "investigate": "follow-up", "stop": "stop"}[analysis.product]
    product = FindingRecord(
        topic="steward peer list",
        statement=(
            f"Product disposition is {analysis.product}. "
            "There is no ground truth. "
            "Situation agreement is partly circular because tick and pathogen "
            "statuses are also distance features. Human status is not."
        ),
        disposition=product_word,
        n_underlying=analysis.county_n,
        effect_size=analysis.type_agreement_lso,
        uncertainty_note="Leave-state-out type agreement against stored community types.",
        evidence={
            "product": analysis.product,
            "cross_state_share": analysis.cross_state_share,
            "type_agreement_lso": analysis.type_agreement_lso,
        },
    )
    return (method, product)


def experiment_rows(analysis: Analysis, run_id: str) -> tuple[ExperimentRow, ...]:
    """One experiment row for each frozen comparison."""
    split = {"unit": "county", "k": K_PRIMARY, "sensitivity_k": K_SENSITIVITY}
    shared = {"spec": SPEC_ID, "gamma": GAMMA, "sklearn": analysis.sklearn_version}
    families = (
        (
            "euclidean_knn",
            "Exact Euclidean neighbors on the issue 120 embedding.",
            {
                "k": K_PRIMARY,
                "seeds": [PRIMARY_SEED, SECOND_SEED],
                "replicates": BOOTSTRAP_REPLICATES,
            },
            (
                _experiment_metric(
                    "bootstrap_jaccard",
                    analysis.bootstrap_median,
                    analysis.county_n,
                    analysis.bootstrap_low,
                    analysis.bootstrap_high,
                ),
                _experiment_metric("lso_jaccard", analysis.lso_jaccard, analysis.county_n),
                _experiment_metric(
                    "lso_type_agreement",
                    analysis.type_agreement_lso,
                    analysis.type_agreement_lso_n,
                ),
            ),
        ),
        (
            "cosine_knn",
            "Cosine neighbors on the same embedding.",
            {"k": K_PRIMARY},
            (
                _experiment_metric(
                    "cosine_euclidean_jaccard",
                    analysis.cosine_jaccard,
                    analysis.county_n,
                ),
                _experiment_metric(
                    "lso_type_agreement",
                    analysis.type_agreement_lso_cosine,
                    analysis.type_agreement_lso_n,
                ),
            ),
        ),
        (
            "same_state_rucc",
            "Baseline peers share a state and a rural-urban code.",
            {"leave_state": "same_rucc_other_states"},
            (
                _experiment_metric(
                    "type_agreement",
                    analysis.type_agreement_baseline,
                    analysis.type_agreement_baseline_n,
                ),
                _experiment_metric(
                    "lso_type_agreement",
                    analysis.type_agreement_lso_baseline,
                    analysis.type_agreement_lso_baseline_n,
                ),
            ),
        ),
        (
            "nearest_prototype",
            "Nearest stored issue 120 prototype at gamma 0.5.",
            {"source_run": GAP_RUN_ID},
            (
                _experiment_metric("recovery", analysis.recovery, analysis.assignment_n),
                _experiment_metric("silhouette", analysis.silhouette, analysis.county_n),
            ),
        ),
    )
    rows: list[ExperimentRow] = []
    for family, hypothesis, config, metrics in families:
        rows.append(
            ExperimentRow(
                experiment_id=str(uuid5(NAMESPACE_URL, f"{run_id}:{family}")),
                hypothesis=hypothesis,
                model_family=family,
                config={**shared, **config},
                split_definition=split,
                status="succeeded",
                metrics=metrics,
            )
        )
    return tuple(rows)


def _design(counties: Sequence[County]) -> tuple[Vector, dict[str, Vector]]:
    raw = np.column_stack(
        [
            np.array([county.svi for county in counties], dtype=float),
            np.array([county.uninsured for county in counties], dtype=float),
            np.log(np.array([county.population for county in counties], dtype=float)),
        ]
    )
    blocks = {
        "rucc": _one_hot([str(county.rucc) for county in counties], RUCC_LEVELS),
        "scapularis_status": _one_hot([county.scapularis for county in counties], SPECIES_LEVELS),
        "pacificus_status": _one_hot([county.pacificus for county in counties], SPECIES_LEVELS),
        "burgdorferi_status": _one_hot(
            [county.burgdorferi for county in counties],
            PATHOGEN_LEVELS,
        ),
    }
    return raw, blocks


def _scale_numeric(
    raw: Vector,
    train_idx: Vector,
    *,
    percentile_columns: tuple[int, ...] = (0, 1),
) -> Vector:
    data = np.array(raw, dtype=float, copy=True)
    train = data[train_idx]
    for column in percentile_columns:
        if float(np.max(train[:, column])) > 1.5:
            data[:, column] = data[:, column] / 100.0
        if np.any(data[:, column] < 0) or np.any(data[:, column] > 1):
            raise PeerLookupError("percentile outside 0 to 1")
    fit = data[train_idx]
    mean = fit.mean(axis=0)
    std = fit.std(axis=0, ddof=0)
    if np.any(std == 0):
        raise PeerLookupError("numeric standard deviation is 0")
    return np.asarray((data - mean) / std, dtype=float)


def _one_hot(values: Sequence[str], levels: tuple[str, ...]) -> Vector:
    index = {level: position for position, level in enumerate(levels)}
    out = np.zeros((len(values), len(levels)), dtype=float)
    for row, value in enumerate(values):
        if value not in index:
            raise PeerLookupError("categorical level is outside the frozen list")
        out[row, index[value]] = CATEGORY_SCALE
    return out


def _embedding(numeric: Vector, blocks: Mapping[str, Vector], categorical: Sequence[str]) -> Vector:
    parts: list[Vector] = []
    if numeric.size and numeric.shape[1] > 0:
        parts.append(numeric)
    parts.extend(blocks[name] for name in categorical)
    if not parts:
        raise PeerLookupError("embedding has no columns")
    matrix = parts[0] if len(parts) == 1 else np.hstack(parts)
    if np.any(np.linalg.norm(matrix, axis=1) == 0):
        raise PeerLookupError("embedding vector has length 0")
    return matrix


def _neighbors(
    embedding: Vector,
    pool: Vector,
    k: int,
    metric: str,
) -> tuple[Vector, Vector]:
    """Return neighbor indexes and the distance to the kth neighbor."""
    pool = np.asarray(pool, dtype=int)
    n = embedding.shape[0]
    if pool.size < k:
        empty = np.full((n, k), -1, dtype=int)
        return empty, np.full(n, np.nan)
    if metric == "euclidean":
        sq = np.einsum("ij,ij->i", embedding, embedding)
        pooled = embedding[pool]
        sqp = np.einsum("ij,ij->i", pooled, pooled)
        dist = sq[:, None] + sqp[None, :] - 2.0 * (embedding @ pooled.T)
        np.maximum(dist, 0.0, out=dist)
        dist = np.sqrt(dist)
    elif metric == "cosine":
        norms = np.linalg.norm(embedding, axis=1)
        normal = embedding / norms[:, None]
        dist = 1.0 - (normal @ normal[pool].T)
        np.maximum(dist, 0.0, out=dist)
    else:
        raise PeerLookupError("metric is not euclidean or cosine")
    position = np.full(n, -1, dtype=int)
    position[pool] = np.arange(pool.size)
    self_rows = np.flatnonzero(position >= 0)
    dist[self_rows, position[self_rows]] = np.inf
    indexes = _take_k(dist, pool, k)
    kth = np.full(n, np.nan)
    ok = indexes[:, 0] >= 0
    if np.any(ok):
        row_ids = np.arange(n)[ok]
        kth[ok] = dist[row_ids, position[indexes[ok, k - 1]]]
    return indexes, kth


def _take_k(dist: Vector, pool: Vector, k: int) -> Vector:
    n = dist.shape[0]
    out = np.full((n, k), -1, dtype=int)
    if dist.shape[1] < k:
        return out
    ok = np.isfinite(dist).sum(axis=1) >= k
    if not np.any(ok):
        return out
    part = np.argpartition(dist, kth=k - 1, axis=1)[:, :k]
    chosen = np.take_along_axis(dist, part, axis=1)
    snapped = np.round(chosen / TIE_EPS)
    order = np.lexsort((part, snapped), axis=1)
    part = np.take_along_axis(part, order, axis=1)
    mapped = pool[part]
    out[ok] = mapped[ok]
    return out


def _mean_jaccard(left: Vector, right: Vector) -> float:
    scores = _row_jaccard(left, right)
    finite = scores[np.isfinite(scores)]
    if finite.size == 0:
        raise PeerLookupError("neighbor Jaccard is not estimable")
    return float(finite.mean())


def _row_jaccard(left: Vector, right: Vector) -> Vector:
    scores = np.full(left.shape[0], np.nan)
    for index in range(left.shape[0]):
        if left[index, 0] < 0 or right[index, 0] < 0:
            continue
        first = set(int(item) for item in left[index])
        second = set(int(item) for item in right[index])
        union = first | second
        if not union:
            continue
        scores[index] = len(first & second) / len(union)
    return scores


def _type_rates(neighbors: Vector, labels: Vector) -> tuple[float | None, int, Vector]:
    rates = np.full(labels.shape[0], np.nan)
    for index in range(labels.shape[0]):
        if labels[index] < 0 or neighbors[index, 0] < 0:
            continue
        typed = [int(labels[item]) for item in neighbors[index] if labels[item] >= 0]
        if not typed:
            continue
        rates[index] = sum(value == int(labels[index]) for value in typed) / len(typed)
    finite = rates[np.isfinite(rates)]
    if finite.size == 0:
        return None, 0, rates
    return float(finite.mean()), int(finite.size), rates


def _baseline_counts(counties: Sequence[County]) -> tuple[int, ...]:
    grouped: dict[tuple[str, int], int] = defaultdict(int)
    keys = [(county.state, county.rucc) for county in counties]
    for key in keys:
        grouped[key] += 1
    return tuple(grouped[key] - 1 for key in keys)


def _baseline_agreement(
    counties: Sequence[County],
    labels: Vector,
    *,
    held_out: bool,
) -> tuple[float | None, int]:
    rates: list[float] = []
    if held_out:
        by_rucc: dict[int, list[int]] = defaultdict(list)
        for index, county in enumerate(counties):
            by_rucc[county.rucc].append(index)
        for index, county in enumerate(counties):
            if labels[index] < 0:
                continue
            peers = [
                peer
                for peer in by_rucc[county.rucc]
                if peer != index and counties[peer].state != county.state and labels[peer] >= 0
            ]
            if not peers:
                continue
            matched = sum(int(labels[peer]) == int(labels[index]) for peer in peers)
            rates.append(matched / len(peers))
    else:
        groups: dict[tuple[str, int], list[int]] = defaultdict(list)
        for index, county in enumerate(counties):
            groups[(county.state, county.rucc)].append(index)
        for indexes in groups.values():
            typed = [index for index in indexes if labels[index] >= 0]
            if len(typed) < 2:
                continue
            for index in typed:
                peers = [peer for peer in typed if peer != index]
                rates.append(
                    sum(int(labels[peer]) == int(labels[index]) for peer in peers) / len(peers)
                )
    if not rates:
        return None, 0
    return float(np.mean(rates)), len(rates)


def _leave_state(
    raw: Vector,
    blocks: Mapping[str, Vector],
    states: Vector,
    k: int,
) -> tuple[Vector, Vector]:
    n = states.shape[0]
    euclid = np.full((n, k), -1, dtype=int)
    cosine = np.full((n, k), -1, dtype=int)
    categorical = tuple(BLOCKS[3:])
    for state in sorted(set(states.tolist())):
        held = np.flatnonzero(states == state)
        train = np.flatnonzero(states != state)
        if train.size <= k:
            raise PeerLookupError("leave-state-out pool is smaller than k")
        embedding = _embedding(_scale_numeric(raw, train), blocks, categorical)
        euclid_part, _ = _neighbors(embedding, train, k, "euclidean")
        cosine_part, _ = _neighbors(embedding, train, k, "cosine")
        euclid[held] = euclid_part[held]
        cosine[held] = cosine_part[held]
    if np.any(euclid < 0) or np.any(cosine < 0):
        raise PeerLookupError("leave-state-out neighbor list is incomplete")
    return euclid, cosine


def _bootstrap_pair(
    embedding: Vector,
    base_5: Vector,
    base_15: Vector,
    seed: int,
    replicates: int,
    min_contributing: int,
) -> tuple[float | None, float | None, float | None, float | None, bool, int]:
    rng = np.random.Generator(np.random.PCG64(seed))
    n = embedding.shape[0]
    primary: list[float] = []
    sensitivity: list[float] = []
    for _ in range(replicates):
        pool = np.unique(rng.choice(n, size=n, replace=True))
        width = K_SENSITIVITY if base_15.shape[1] == K_SENSITIVITY else K_PRIMARY
        found, _ = _neighbors(embedding, pool, width, "euclidean")
        _keep_stat(primary, _row_jaccard(base_5, found[:, :K_PRIMARY]), min_contributing)
        if width == K_SENSITIVITY:
            _keep_stat(sensitivity, _row_jaccard(base_15, found), min_contributing)
    low, high, estimable, failed = _interval(primary, replicates)
    median = float(np.median(np.array(primary))) if primary else None
    median_15 = float(np.median(np.array(sensitivity))) if sensitivity else None
    if median_15 is not None and not math.isfinite(median_15):
        median_15 = None
    return median, median_15, low, high, estimable, failed


def _keep_stat(bucket: list[float], scores: Vector, min_contributing: int) -> None:
    finite = scores[np.isfinite(scores)]
    if finite.size >= min_contributing:
        bucket.append(float(finite.mean()))


def _interval(
    values: Sequence[float],
    replicates: int,
) -> tuple[float | None, float | None, bool, int]:
    failed = replicates - len(values)
    if failed * 100 > replicates * 5 or len(values) < 2:
        return None, None, False, failed
    ordered = sorted(values)
    return _quantile(ordered, 0.025), _quantile(ordered, 0.975), True, failed


def _quantile(ordered: Sequence[float], probability: float) -> float:
    index = (len(ordered) - 1) * probability
    low = math.floor(index)
    high = math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def _ablations(
    raw: Vector,
    blocks: Mapping[str, Vector],
    base: Vector,
) -> tuple[Ablation, ...]:
    n = raw.shape[0]
    train = np.arange(n)
    rows: list[Ablation] = []
    numeric_index = {name: index for index, name in enumerate(NUMERIC_BLOCKS)}
    for block in BLOCKS:
        if block in numeric_index:
            keep_numeric = [name for name in NUMERIC_BLOCKS if name != block]
            dropped_numeric = _scale_numeric(
                raw[:, [numeric_index[name] for name in keep_numeric]],
                train,
                percentile_columns=_percentile_columns(keep_numeric),
            )
            alone_numeric = _scale_numeric(
                raw[:, [numeric_index[block]]],
                train,
                percentile_columns=() if block == "log_population" else (0,),
            )
            dropped = _embedding(dropped_numeric, blocks, BLOCKS[3:])
            alone = _embedding(alone_numeric, blocks, ())
        else:
            kept = tuple(name for name in BLOCKS[3:] if name != block)
            dropped = _embedding(_scale_numeric(raw, train), blocks, kept)
            alone = _embedding(np.zeros((n, 0)), blocks, (block,))
        dropped_neighbors, _ = _neighbors(dropped, train, K_PRIMARY, "euclidean")
        alone_neighbors, _ = _neighbors(alone, train, K_PRIMARY, "euclidean")
        rows.append(
            Ablation(
                block=block,
                dropped_jaccard=_mean_jaccard(base, dropped_neighbors),
                alone_jaccard=_mean_jaccard(base, alone_neighbors),
            )
        )
    return tuple(rows)


def _percentile_columns(names: Sequence[str]) -> tuple[int, ...]:
    return tuple(index for index, name in enumerate(names) if name != "log_population")


def _prototypes(
    counties: Sequence[County],
    labels: Vector,
    raw: Vector,
    blocks: Mapping[str, Vector],
) -> tuple[Vector, float]:
    assigned = np.flatnonzero(labels >= 0)
    if assigned.size < 2:
        raise PeerLookupError("prototype cohort is empty")
    scaled = _scale_numeric(raw, assigned)
    categories = {
        "rucc": [str(county.rucc) for county in counties],
        "scapularis_status": [county.scapularis for county in counties],
        "pacificus_status": [county.pacificus for county in counties],
        "burgdorferi_status": [county.burgdorferi for county in counties],
    }
    distances: list[Vector] = []
    ids: list[int] = []
    for cluster_id in (1, 2):
        members = np.flatnonzero(labels == cluster_id)
        if members.size == 0:
            raise PeerLookupError("a stored community type is empty")
        center = scaled[members].mean(axis=0)
        numeric = np.sum((scaled - center) ** 2, axis=1)
        mismatch = np.zeros(len(counties))
        for values in categories.values():
            mode = _mode([values[index] for index in members])
            mismatch += np.array([0.0 if value == mode else 1.0 for value in values])
        distances.append(numeric + GAMMA * mismatch)
        ids.append(cluster_id)
    stacked = np.column_stack(distances)
    choice = np.argmin(stacked, axis=1)
    ties = np.isclose(stacked[:, 0], stacked[:, 1], rtol=0.0, atol=TIE_EPS)
    choice[ties] = 0 if ids[0] < ids[1] else 1
    proto = np.array([ids[int(item)] for item in choice], dtype=int)
    recovery = float(np.mean(proto[assigned] == labels[assigned]))
    return proto, recovery


def _mode(values: Sequence[str]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    best = max(counts.values())
    return min(value for value, count in counts.items() if count == best)


def _silhouette(embedding: Vector, labels: Vector) -> float | None:
    if len(set(int(item) for item in labels)) < 2:
        return None
    try:
        score = float(silhouette_score(embedding, labels, metric="euclidean"))
    except ValueError:
        return None
    if not math.isfinite(score):
        return None
    return score


def _cross_state_share(neighbors: Vector, states: Vector) -> float:
    hits = 0
    for index in range(states.shape[0]):
        if neighbors[index, 0] < 0:
            continue
        if any(states[item] != states[index] for item in neighbors[index]):
            hits += 1
    return float(hits) / float(states.shape[0])


def _failures(
    *,
    determinism: float,
    cosine_jaccard: float,
    type_lso: float | None,
    lso_gap: float | None,
    lso_jaccard: float,
    bootstrap_median: float | None,
    bootstrap_low: float | None,
    bootstrap_estimable: bool,
    bootstrap_median_b: float | None,
    silhouette: float | None,
    recovery: float,
    ablations: Sequence[Ablation],
) -> tuple[str, ...]:
    failed: list[str] = []
    if not math.isclose(determinism, 1.0, abs_tol=TIE_EPS):
        failed.append("determinism")
    if (
        not bootstrap_estimable
        or bootstrap_median is None
        or bootstrap_low is None
        or bootstrap_median < BOOTSTRAP_MEDIAN_MIN
        or bootstrap_low < BOOTSTRAP_LOW_MIN
    ):
        failed.append("bootstrap")
    if (
        bootstrap_median is None
        or bootstrap_median_b is None
        or abs(bootstrap_median - bootstrap_median_b) > SEED_MEDIAN_GAP_MAX
    ):
        failed.append("bootstrap_seeds")
    if cosine_jaccard < COSINE_JACCARD_MIN:
        failed.append("cosine_jaccard")
    if type_lso is None or type_lso < LSO_AGREEMENT_MIN:
        failed.append("lso_type_agreement")
    if lso_gap is None or lso_gap < LSO_BASELINE_GAP_MIN:
        failed.append("lso_baseline_gap")
    if lso_jaccard < LSO_JACCARD_MIN:
        failed.append("lso_jaccard")
    if ablations and max(row.alone_jaccard for row in ablations) >= SINGLE_BLOCK_MAX:
        failed.append("single_block")
    if ablations and min(row.dropped_jaccard for row in ablations) >= DROP_ALL_MIN:
        failed.append("drop_block")
    if silhouette is None or silhouette < 0:
        failed.append("silhouette")
    if recovery < RECOVERY_MIN:
        failed.append("prototype_recovery")
    return tuple(failed)


def _product(
    method: str,
    *,
    cross_state: float,
    lso_jaccard: float,
    in_gap: float | None,
) -> str:
    if method == "stop":
        return "stop"
    if (
        method == "keep"
        and cross_state >= CROSS_STATE_MIN
        and lso_jaccard >= LSO_JACCARD_ADVANCE
        and in_gap is not None
        and in_gap >= IN_SAMPLE_GAP_MIN
    ):
        return "advance"
    return "investigate"


def _rows(
    counties: Sequence[County],
    labels: Vector,
    situations: Vector,
    prototypes: Vector,
    euclid: Vector,
    cosine: Vector,
    distances: Vector,
    baseline_n: Sequence[int],
    lso_rates: Vector,
) -> tuple[tuple[NeighborRow, ...], tuple[Example, ...], tuple[Example, ...]]:
    names = [(county.fips, county.name, county.state) for county in counties]
    rows: list[NeighborRow] = []
    for index, county in enumerate(counties):
        rate = float(lso_rates[index])
        rows.append(
            NeighborRow(
                fips=county.fips,
                county_name=county.name,
                state=county.state,
                cluster_id=None if labels[index] < 0 else int(labels[index]),
                situation=_SITUATION_NAMES[int(situations[index])],
                prototype_cluster_id=int(prototypes[index]),
                euclidean_neighbors=",".join(names[int(item)][0] for item in euclid[index]),
                cosine_neighbors=",".join(names[int(item)][0] for item in cosine[index]),
                euclidean_distance_k=float(distances[index]),
                baseline_peer_n=int(baseline_n[index]),
                leave_state_type_agreement=None if not math.isfinite(rate) else rate,
            )
        )
    order = np.lexsort((np.arange(len(counties)), distances))
    far_order = np.lexsort((np.arange(len(counties)), -distances))
    near = tuple(_example(int(index), names, distances, euclid) for index in order[:3])
    far = tuple(_example(int(index), names, distances, euclid) for index in far_order[:3])
    return tuple(rows), near, far


def _example(
    index: int,
    names: Sequence[tuple[str, str, str]],
    distances: Vector,
    neighbors: Vector,
) -> Example:
    fips, name, state = names[index]
    return Example(
        fips=fips,
        county_name=name,
        state=state,
        distance=float(distances[index]),
        neighbors=tuple(names[int(item)] for item in neighbors[index]),
    )


def _gap(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return left - right


def _deciles(values: Vector) -> tuple[float, ...]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return ()
    points = [float(np.quantile(finite, step / 10)) for step in range(1, 10)]
    return tuple(points)


def _situation_code(county: County) -> int:
    published = county.human_status == HUMAN_PUBLISHED
    absent = county.human_status == HUMAN_NONE
    established = county.tick_status == TICK_ESTABLISHED
    present = county.burgdorferi == PATHOGEN_PRESENT
    if published and established and present:
        return 0
    if absent and established and present:
        return 1
    if absent and established and not present:
        return 2
    if published and county.burgdorferi == "No records":
        return 3
    if absent and county.tick_status == "No records" and county.burgdorferi == "No records":
        return 4
    return 5


_SITUATION_NAMES = (
    "aligned",
    "double_gap",
    "wider_gap_only",
    "human_ahead",
    "undocumented",
    "other",
)


def _wider(county: County) -> bool:
    return county.human_status == HUMAN_NONE and county.tick_status == TICK_ESTABLISHED


def _double(county: County) -> bool:
    return _wider(county) and county.burgdorferi == PATHOGEN_PRESENT


def _county(row: Mapping[str, object], *, release_id: str) -> County:
    if _text(row.get("RELEASE_ID")) != release_id:
        raise PeerLookupError("county release id does not match the pin")
    fips = _text(row.get("FIPS"))
    if len(fips) != 5 or not fips.isdigit():
        raise PeerLookupError("FIPS must be five digits")
    state = _text(row.get("STATE"))
    if not state:
        raise PeerLookupError("state is missing")
    population = _required_float(row.get("POPULATION"), "population")
    if population <= 0:
        raise PeerLookupError("population is not positive")
    rucc = _required_float(row.get("RUCC_2023"), "rural-urban code")
    if not rucc.is_integer() or int(rucc) < 1 or int(rucc) > 9:
        raise PeerLookupError("rural-urban code is outside 1 through 9")
    return County(
        fips=fips,
        name=_text(row.get("COUNTY")) or fips,
        state=state,
        population=population,
        svi=_required_float(row.get("SVI_PERCENTILE"), "svi"),
        uninsured=_required_float(row.get("UNINSURED_PERCENTILE"), "uninsured"),
        rucc=int(rucc),
        human_status=_required_status(row.get("HUMAN_STATUS"), HUMAN_LEVELS, "human"),
        scapularis=_required_status(row.get("SCAPULARIS_STATUS"), SPECIES_ALLOWED, "scapularis"),
        pacificus=_required_status(row.get("PACIFICUS_STATUS"), SPECIES_ALLOWED, "pacificus"),
        burgdorferi=_required_status(
            row.get("BURGDORFERI_STATUS"),
            PATHOGEN_ALLOWED,
            "burgdorferi",
        ),
        tick_status=_required_status(row.get("TICK_STATUS"), TICK_LEVELS, "tick"),
    )


def _cluster_id(value: object) -> int:
    number = _required_float(value, "cluster id")
    if not number.is_integer():
        raise PeerLookupError("cluster id is not an integer")
    return int(number)


def _required_status(value: object, allowed: frozenset[str], label: str) -> str:
    text = _text(value)
    if text not in allowed:
        raise PeerLookupError(f"unexpected {label} status")
    return text


def _required_float(value: object, label: str) -> float:
    if value is None or isinstance(value, bool):
        raise PeerLookupError(f"{label} is missing")
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        try:
            number = float(str(value))
        except ValueError as error:
            raise PeerLookupError(f"{label} is not a number") from error
    if not math.isfinite(number):
        raise PeerLookupError(f"{label} is missing")
    return number


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _metric(name: str, count: int, value: float, unit: str) -> EdaMetric:
    return EdaMetric(metric_name=name, n_underlying=count, metric_value=value, unit=unit)


def _rate(rows: list[EdaMetric], name: str, value: float | None, count: int) -> None:
    if value is None:
        return
    rows.append(_metric(name, count, value, "ratio"))


def _experiment_metric(
    name: str,
    value: float | None,
    count: int,
    low: float | None = None,
    high: float | None = None,
) -> ExperimentMetric:
    return ExperimentMetric(
        split_name="national",
        metric_name=name,
        metric_value=value,
        n=count,
        ci_low=low,
        ci_high=high,
    )
