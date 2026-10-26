"""Within-state documentation outliers for issue 190.

The functions here do not open Snowflake. County rows stay in the returned
objects. Aggregate lab records suppress a denominator below 11. The results
write-up may name counties. Chart records do not.

The baseline z uses ``MAD_SCALE`` and ``Z_FLAG`` from the #113 path. A
documentation indicator is not flagged by that baseline: its MAD is 0 unless
the state is split evenly, and an even split has absolute z ``1 / MAD_SCALE``.
"""

from __future__ import annotations

import math
import warnings
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from importlib.metadata import version
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import numpy as np
from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]
from sklearn.neighbors import LocalOutlierFactor  # type: ignore[import-untyped]

from lyme_gap_atlas_ml.class_anomaly import MAD_SCALE, Z_FLAG, load_marked_queries
from lyme_gap_atlas_ml.county_mca import _situation_flags
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
)

SPEC_ID = "190-within-state-doc-outliers/v1"
ISSUE_NUMBER = 190
RUN_PREFIX = "190-within-state-doc-outliers-"
PRIMARY_SEED = 1902026
SECOND_SEED = 1902027
CLUSTER_SEED = 1902030
PERMUTATION_SEED = 1902040
MIN_STATE = 11
CAP_SHARE = 0.05
FOREST_TREES = 100
CONTAMINATION = 0.05
LOF_NEIGHBORS = 20
BOOTSTRAP_DRAWS = 20
BOOTSTRAP_KEEP = 0.8
CLUSTER_DRAWS = 400
PERMUTATION_DRAWS = 200
SEED_JACCARD_MIN = 0.80
SEED_SPEARMAN_MAX = 0.999
BOOTSTRAP_JACCARD_MIN = 0.70
PERMUTATION_JACCARD_MAX = 0.50
SIZE_SPEARMAN_MAX = 0.50
USEFUL_RATE_MIN = 0.70
USEFUL_MIN = 11
ADVANCE_JACCARD_MAX = 0.80
CONCENTRATION_FLAG = 0.80
CONCENTRATION_BASE = 0.50
TIE_EPS = 1e-12
GAP_RUN_ID = "120-gap-communities-20261026T1355Z"
QUERY_NAMES = ("release_identity", "county_rows", "gap_clusters")
SOURCE_OBJECTS = (
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.GAP_COMMUNITY_ASSIGNMENTS_120",
)
SPECIES_LEVELS = ("Established", "Reported", "No records", "Unknown")
PATHOGEN_LEVELS = (PATHOGEN_PRESENT, "No records", "Unknown")
HUMAN_LEVELS = frozenset({HUMAN_PUBLISHED, HUMAN_NONE})
SITUATIONS = ("aligned", "double_gap", "wider_gap", "human_ahead", "undocumented")
CONTEXT_COLUMNS = ("svi_percentile", "uninsured_percentile", "rucc_2023", "log_population")
Vector = np.ndarray[Any, Any]


class DocOutlierError(ValueError):
    """The county frame or a frozen rule cannot be applied."""


@dataclass(frozen=True)
class County:
    fips: str
    name: str
    state: str
    population: float | None
    svi: float | None
    uninsured: float | None
    rucc: int | None
    human_status: str | None
    scapularis: str | None
    pacificus: str | None
    burgdorferi: str | None
    tick_status: str | None

    @property
    def complete(self) -> bool:
        return (
            self.population is not None
            and self.population > 0
            and self.svi is not None
            and math.isfinite(self.svi)
            and self.uninsured is not None
            and math.isfinite(self.uninsured)
            and self.rucc is not None
            and 1 <= self.rucc <= 9
            and self.human_status in HUMAN_LEVELS
            and self.scapularis in SPECIES_LEVELS
            and self.pacificus in SPECIES_LEVELS
            and self.burgdorferi in PATHOGEN_LEVELS
        )


@dataclass(frozen=True)
class FlagRow:
    fips: str
    county_name: str
    state: str
    state_n: int
    complete_n: int
    size_band: str
    scored: bool
    incomplete: bool
    score_robust_z: float | None
    flag_robust_z: bool
    score_if_primary: float | None
    flag_if_primary: bool
    score_if_seed_b: float | None
    flag_if_seed_b: bool
    score_lof: float | None
    flag_lof: bool
    bootstrap_rate_if: float | None
    dominant_feature: str | None
    stable_useful: bool
    situation_121: str
    cluster_id_120: int | None


@dataclass(frozen=True)
class BandShare:
    band: str
    method: str
    counties: int
    flags: int


@dataclass(frozen=True)
class PairAgreement:
    left: str
    right: str
    spearman: float | None
    jaccard: float | None
    matched_jaccard: float | None


@dataclass(frozen=True)
class SituationShare:
    name: str
    scored_n: int
    flag_n: int


@dataclass(frozen=True)
class ClusterShare:
    cluster_id: int
    cohort_n: int
    flag_n: int


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
    complete_n: int
    scored_n: int
    scored_states: int
    below_11_counties: int
    below_11_states: int
    svi_rescaled: bool
    uninsured_rescaled: bool
    rows: tuple[FlagRow, ...]
    seed_jaccard: float | None
    seed_spearman: float | None
    bootstrap_z: float | None
    bootstrap_if: float | None
    bootstrap_lof: float | None
    permutation_jaccard_if: float | None
    permutation_jaccard_z: float | None
    size_spearman_z: float | None
    size_spearman_if: float | None
    size_spearman_lof: float | None
    flag_rate_if: float | None
    flag_rate_low: float | None
    flag_rate_high: float | None
    agreements: tuple[PairAgreement, ...]
    bands: tuple[BandShare, ...]
    situations: tuple[SituationShare, ...]
    clusters: tuple[ClusterShare, ...]
    method_if: str
    method_z: str
    method_lof: str
    product: str
    stable_useful_n: int
    useful_baseline_jaccard: float | None
    baseline_doc_states: int
    concentrated: bool
    examples: tuple[FlagRow, ...]
    sklearn_version: str

    @property
    def permutation_pass_if(self) -> bool:
        return _perm_pass(self.permutation_jaccard_if, self.size_spearman_if)

    @property
    def cohort_matches_expected(self) -> bool:
        return (
            self.county_n == REFERENCE_COUNTIES
            and self.published_n == REFERENCE_PUBLISHED_HUMAN_FLOOR
            and self.absent_n == REFERENCE_NO_COUNTY_LINKED_RECORD
        )


def load_doc_queries(text: str) -> dict[str, str]:
    """Split the issue 190 validation file and reject unsafe SQL."""
    return load_marked_queries(text, QUERY_NAMES)


def sklearn_version() -> str:
    return version("scikit-learn")


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
            raise DocOutlierError(f"release pin mismatch for {key}")


def parse_counties(
    rows: Sequence[Mapping[str, object]],
    *,
    release_id: str,
    enforce_gate: bool = True,
) -> tuple[County, ...]:
    """Parse atlas rows. The national gate is 3,144 counties and 51 states."""
    counties = tuple(_county(row, release_id=release_id) for row in rows)
    fips = [county.fips for county in counties]
    if len(fips) != len(set(fips)):
        raise DocOutlierError("duplicate FIPS")
    if enforce_gate:
        states = {county.state for county in counties}
        if len(counties) != REFERENCE_COUNTIES or len(states) != 51:
            raise DocOutlierError("county gate is not 3144 counties and 51 states")
    return counties


def score_counties(
    counties: Sequence[County],
    *,
    clusters: Mapping[str, int] | None = None,
) -> Analysis:
    """Score every county. States with fewer than 11 counties are not scored."""
    if len({county.fips for county in counties}) != len(counties):
        raise DocOutlierError("duplicate FIPS")
    cluster_map = {} if clusters is None else clusters
    complete = [county for county in counties if county.complete]
    svi_rescaled = bool(complete) and max(county.svi or 0 for county in complete) > 1.5
    uninsured_rescaled = bool(complete) and max(county.uninsured or 0 for county in complete) > 1.5
    grouped: dict[str, list[County]] = defaultdict(list)
    for county in counties:
        grouped[county.state].append(county)
    situations = _situations(counties)
    built: list[FlagRow] = []
    boot_z: list[float] = []
    boot_if: list[float] = []
    boot_lof: list[float] = []
    frames: list[_Frame] = []
    doc_states = 0
    for state_index, state in enumerate(sorted(grouped)):
        group = grouped[state]
        frame, state_rows, medians, saw_doc = _fit_state(
            group,
            state_index,
            situations,
            cluster_map,
            svi_rescaled=svi_rescaled,
            uninsured_rescaled=uninsured_rescaled,
        )
        built.extend(state_rows)
        if saw_doc:
            doc_states += 1
        if frame is not None:
            frames.append(frame)
        for label, bucket in (("z", boot_z), ("if", boot_if), ("lof", boot_lof)):
            median = medians[label]
            if median is not None:
                bucket.append(median)
    rows = tuple(sorted(built, key=lambda item: item.fips))
    perm_if, perm_z = _permute(frames)
    return _assemble(
        counties,
        rows,
        svi_rescaled=svi_rescaled,
        uninsured_rescaled=uninsured_rescaled,
        bootstrap_z=_median(boot_z),
        bootstrap_if=_median(boot_if),
        bootstrap_lof=_median(boot_lof),
        permutation_jaccard_if=perm_if,
        permutation_jaccard_z=perm_z,
        baseline_doc_states=doc_states,
    )


def lab_metrics(analysis: Analysis) -> list[EdaMetric]:
    """Aggregate metrics. A denominator below 11 is left for the writer to suppress."""
    scored = analysis.scored_n
    rows: list[EdaMetric] = [
        _metric("county_n", analysis.county_n, float(analysis.county_n), "count"),
        _metric("state_n", analysis.county_n, float(analysis.state_n), "count"),
        _metric("published_n", analysis.county_n, float(analysis.published_n), "count"),
        _metric("complete_n", analysis.county_n, float(analysis.complete_n), "count"),
        _metric("scored_n", analysis.county_n, float(scored), "count"),
        _metric("scored_states", analysis.county_n, float(analysis.scored_states), "count"),
        _metric(
            "below_11_counties",
            analysis.below_11_counties,
            float(analysis.below_11_states),
            "count",
        ),
        _metric("stable_useful_n", scored, float(analysis.stable_useful_n), "count"),
        _metric("baseline_doc_states", scored, float(analysis.baseline_doc_states), "count"),
    ]
    _append_rate(rows, "flag_rate_if", analysis.flag_rate_if, scored)
    _append_rate(rows, "flag_rate_if_p025", analysis.flag_rate_low, scored)
    _append_rate(rows, "flag_rate_if_p975", analysis.flag_rate_high, scored)
    _append_rate(rows, "seed_jaccard_if", analysis.seed_jaccard, scored)
    _append_rate(rows, "seed_spearman_if", analysis.seed_spearman, scored)
    _append_rate(rows, "bootstrap_jaccard_z", analysis.bootstrap_z, scored)
    _append_rate(rows, "bootstrap_jaccard_if", analysis.bootstrap_if, scored)
    _append_rate(rows, "bootstrap_jaccard_lof", analysis.bootstrap_lof, scored)
    _append_rate(rows, "permutation_jaccard_if", analysis.permutation_jaccard_if, scored)
    _append_rate(rows, "permutation_jaccard_z", analysis.permutation_jaccard_z, scored)
    _append_rate(rows, "size_spearman_z", analysis.size_spearman_z, scored)
    _append_rate(rows, "size_spearman_if", analysis.size_spearman_if, scored)
    _append_rate(rows, "size_spearman_lof", analysis.size_spearman_lof, scored)
    _append_rate(rows, "useful_baseline_jaccard", analysis.useful_baseline_jaccard, scored)
    for band in analysis.bands:
        if band.counties < MIN_STATE or 0 < band.flags < MIN_STATE:
            continue
        share = band.flags / band.counties
        rows.append(
            _metric(
                "band_flag_share",
                band.counties,
                share,
                "share",
                geography_type="size_band",
                geography_id=f"{band.band}-{band.method}",
            )
        )
    for pair in analysis.agreements:
        _append_rate(rows, f"spearman_{pair.left}_{pair.right}", pair.spearman, scored)
        _append_rate(rows, f"jaccard_{pair.left}_{pair.right}", pair.jaccard, scored)
        _append_rate(
            rows,
            f"matched_jaccard_{pair.left}_{pair.right}",
            pair.matched_jaccard,
            scored,
        )
    for item in analysis.situations:
        if item.scored_n < MIN_STATE or 0 < item.flag_n < MIN_STATE:
            continue
        rows.append(
            _metric(
                "situation_flag_share",
                item.scored_n,
                item.flag_n / item.scored_n,
                "share",
                geography_type="situation",
                geography_id=item.name,
            )
        )
    for cluster in analysis.clusters:
        if cluster.cohort_n < MIN_STATE or 0 < cluster.flag_n < MIN_STATE:
            continue
        rows.append(
            _metric(
                "community_flag_share",
                cluster.cohort_n,
                cluster.flag_n / cluster.cohort_n,
                "share",
                geography_type="community",
                geography_id=str(cluster.cluster_id),
            )
        )
    for state in sorted({row.state for row in analysis.rows if row.scored}):
        members = [row for row in analysis.rows if row.state == state and row.scored]
        if len(members) < MIN_STATE:
            continue
        flagged = sum(row.flag_if_primary for row in members)
        if 0 < flagged < MIN_STATE:
            continue
        rows.append(
            _metric(
                "state_if_flag_share",
                len(members),
                flagged / len(members),
                "share",
                geography_type="state",
                geography_id=state,
            )
        )
    _reject_detection_names(row.metric_name for row in rows)
    return rows


def lab_findings(analysis: Analysis) -> tuple[FindingRecord, ...]:
    """Method and product calls. County names stay in the write-up."""
    method = FindingRecord(
        topic="within-state documentation score",
        statement=(
            f"Primary isolation forest disposition is {analysis.method_if}. "
            f"Robust z disposition is {analysis.method_z}. "
            f"Local outlier factor disposition is {analysis.method_lof}. "
            "A flag means the county is documented differently from its state peers. "
            "No labeled detector was scored."
        ),
        disposition=_finding_disposition(analysis.method_if),
        n_underlying=max(analysis.scored_n, analysis.county_n),
        effect_size=analysis.seed_jaccard,
        uncertainty_note="State-cluster interval and within-state bootstrap. Not causal.",
        evidence={
            "seed_jaccard": analysis.seed_jaccard,
            "permutation_jaccard_if": analysis.permutation_jaccard_if,
            "stable_useful_n": analysis.stable_useful_n,
            "scored_n": analysis.scored_n,
        },
    )
    product_word = {"advance": "keep", "investigate": "follow-up", "stop": "stop"}[analysis.product]
    product = FindingRecord(
        topic="steward review list",
        statement=(
            f"Product disposition is {analysis.product}. "
            "There is no ground truth, so this is a data-review signal. "
            "State composition can still masquerade as a county signal."
        ),
        disposition=product_word,
        n_underlying=max(analysis.scored_n, analysis.county_n),
        effect_size=analysis.useful_baseline_jaccard,
        uncertainty_note="Agreement with situation groups is descriptive.",
        evidence={
            "product": analysis.product,
            "concentrated": analysis.concentrated,
            "useful_baseline_jaccard": analysis.useful_baseline_jaccard,
        },
    )
    return (method, product)


def experiment_rows(analysis: Analysis, run_id: str) -> tuple[ExperimentRow, ...]:
    """One experiment row per frozen method."""
    shared = {
        "spec": SPEC_ID,
        "mad_scale": MAD_SCALE,
        "z_flag": Z_FLAG,
        "cap_share": CAP_SHARE,
        "sklearn": analysis.sklearn_version,
    }
    split = {"unit": "county", "group": "state", "minimum_counties": MIN_STATE}
    families = (
        (
            "robust_z",
            "Within-state robust z using the issue 113 scale.",
            analysis.method_z,
            {"rule": "max_abs_z", "threshold": Z_FLAG},
            (
                _experiment_metric("bootstrap_jaccard", analysis.bootstrap_z, analysis.scored_n),
                _experiment_metric("size_spearman", analysis.size_spearman_z, analysis.scored_n),
            ),
        ),
        (
            "isolation_forest",
            "Within-state isolation forest on robust standardized features.",
            analysis.method_if,
            {
                "n_estimators": FOREST_TREES,
                "contamination": CONTAMINATION,
                "seeds": [PRIMARY_SEED, SECOND_SEED],
                "bootstrap": True,
            },
            (
                _experiment_metric(
                    "flag_rate",
                    analysis.flag_rate_if,
                    analysis.scored_n,
                    analysis.flag_rate_low,
                    analysis.flag_rate_high,
                ),
                _experiment_metric("seed_jaccard", analysis.seed_jaccard, analysis.scored_n),
                _experiment_metric("seed_spearman", analysis.seed_spearman, analysis.scored_n),
                _experiment_metric("bootstrap_jaccard", analysis.bootstrap_if, analysis.scored_n),
                _experiment_metric(
                    "permutation_jaccard",
                    analysis.permutation_jaccard_if,
                    analysis.scored_n,
                ),
            ),
        ),
        (
            "local_outlier_factor",
            "Within-state local outlier factor on robust standardized features.",
            analysis.method_lof,
            {"n_neighbors_cap": LOF_NEIGHBORS, "contamination": CONTAMINATION, "seed": None},
            (
                _experiment_metric("bootstrap_jaccard", analysis.bootstrap_lof, analysis.scored_n),
                _experiment_metric("size_spearman", analysis.size_spearman_lof, analysis.scored_n),
            ),
        ),
    )
    rows: list[ExperimentRow] = []
    for family, hypothesis, _status, config, metrics in families:
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


@dataclass
class _Frame:
    fips: tuple[str, ...]
    columns: dict[str, Vector]
    cap: int
    forest_flags: frozenset[str]
    baseline_flags: frozenset[str]


def _fit_state(
    group: Sequence[County],
    state_index: int,
    situations: Mapping[str, str],
    clusters: Mapping[str, int],
    *,
    svi_rescaled: bool,
    uninsured_rescaled: bool,
) -> tuple[_Frame | None, list[FlagRow], dict[str, float | None], bool]:
    state_n = len(group)
    band = _band(state_n)
    complete = [county for county in group if county.complete]
    complete_n = len(complete)
    scored = state_n >= MIN_STATE and complete_n >= MIN_STATE
    if not scored:
        rows = [
            _blank_row(county, state_n, complete_n, band, situations, clusters) for county in group
        ]
        return None, rows, {"z": None, "if": None, "lof": None}, False
    columns = _columns(complete, svi_rescaled=svi_rescaled, uninsured_rescaled=uninsured_rescaled)
    fips = [county.fips for county in complete]
    cap = _cap(complete_n)
    baseline_z, baseline_flags, saw_doc = _baseline(columns, fips, cap)
    challenger = _z_matrix(columns, fallback=True)
    if_scores, if_flags = _capped_forest(challenger, fips, cap, PRIMARY_SEED)
    if_scores_b, if_flags_b = _capped_forest(challenger, fips, cap, SECOND_SEED)
    lof_scores, lof_flags = _capped_lof(challenger, fips, cap)
    dominant = _dominant(challenger)
    rates, medians = _bootstrap(columns, fips, cap, state_index)
    position_of = {name: index for index, name in enumerate(fips)}
    rows = []
    for county in group:
        if county.fips not in position_of:
            rows.append(_blank_row(county, state_n, complete_n, band, situations, clusters))
            continue
        position = position_of[county.fips]
        feature = dominant[position][0] if dominant else None
        rows.append(
            FlagRow(
                fips=county.fips,
                county_name=county.name,
                state=county.state,
                state_n=state_n,
                complete_n=complete_n,
                size_band=band,
                scored=True,
                incomplete=False,
                score_robust_z=_at(baseline_z, position),
                flag_robust_z=county.fips in baseline_flags,
                score_if_primary=_at(if_scores, position),
                flag_if_primary=county.fips in if_flags,
                score_if_seed_b=_at(if_scores_b, position),
                flag_if_seed_b=county.fips in if_flags_b,
                score_lof=_at(lof_scores, position),
                flag_lof=county.fips in lof_flags,
                bootstrap_rate_if=rates.get(county.fips),
                dominant_feature=feature,
                stable_useful=False,
                situation_121=situations[county.fips],
                cluster_id_120=clusters.get(county.fips),
            )
        )
    frame = _Frame(
        fips=tuple(fips),
        columns=columns,
        cap=cap,
        forest_flags=frozenset(if_flags),
        baseline_flags=frozenset(baseline_flags),
    )
    return frame, rows, medians, saw_doc


def _assemble(
    counties: Sequence[County],
    rows: tuple[FlagRow, ...],
    *,
    svi_rescaled: bool,
    uninsured_rescaled: bool,
    bootstrap_z: float | None,
    bootstrap_if: float | None,
    bootstrap_lof: float | None,
    permutation_jaccard_if: float | None,
    permutation_jaccard_z: float | None,
    baseline_doc_states: int,
) -> Analysis:
    scored_rows = [row for row in rows if row.scored]
    seed_jaccard = _jaccard(
        {row.fips for row in scored_rows if row.flag_if_primary},
        {row.fips for row in scored_rows if row.flag_if_seed_b},
    )
    seed_spearman = _paired_spearman(
        [row.score_if_primary for row in scored_rows],
        [row.score_if_seed_b for row in scored_rows],
    )
    size_z = _size_spearman(scored_rows, "flag_robust_z")
    size_if = _size_spearman(scored_rows, "flag_if_primary")
    size_lof = _size_spearman(scored_rows, "flag_lof")
    perm_if = _perm_pass(permutation_jaccard_if, size_if)
    useful_ids = {
        row.fips
        for row in scored_rows
        if perm_if and _useful(row) and row.flag_if_primary and row.flag_if_seed_b
    }
    marked = tuple(replace(row, stable_useful=row.fips in useful_ids) for row in rows)
    scored_marked = [row for row in marked if row.scored]
    flag_if = [row for row in scored_marked if row.flag_if_primary]
    flag_rate = (len(flag_if) / len(scored_marked)) if scored_marked else None
    low, high = _cluster_interval(scored_marked)
    agreements = _agreements(scored_marked)
    bands = _bands(marked)
    situations = _situation_shares(scored_marked, flag_if)
    clusters = _cluster_shares(scored_marked, flag_if)
    useful = [row for row in scored_marked if row.stable_useful]
    useful_jaccard = _jaccard(
        {row.fips for row in useful},
        {row.fips for row in scored_marked if row.flag_robust_z},
    )
    concentrated = _concentrated(useful, scored_marked)
    method_if = _method_if(
        seed_jaccard=seed_jaccard,
        seed_spearman=seed_spearman,
        bootstrap=bootstrap_if,
        permutation=perm_if,
        useful_n=len(useful),
        flagged=len(flag_if),
    )
    method_z = _method_simple(
        bootstrap=bootstrap_z,
        permutation=_perm_pass(permutation_jaccard_if, size_z) and baseline_doc_states > 0,
        flagged=sum(row.flag_robust_z for row in scored_marked),
        extra=baseline_doc_states > 0,
    )
    method_lof = _method_simple(
        bootstrap=bootstrap_lof,
        permutation=_perm_pass(permutation_jaccard_if, size_lof),
        flagged=sum(row.flag_lof for row in scored_marked),
        extra=True,
    )
    product = _product(method_if, useful_jaccard, concentrated, perm_if, len(useful))
    examples = tuple(
        sorted(
            flag_if,
            key=lambda item: (
                -(item.score_if_primary if item.score_if_primary is not None else 0.0),
                item.fips,
            ),
        )[:8]
    )
    state_counts = _state_counts(counties)
    states = set(state_counts)
    below_states = {state for state, count in state_counts.items() if count < MIN_STATE}
    return Analysis(
        county_n=len(counties),
        state_n=len(states),
        published_n=sum(county.human_status == HUMAN_PUBLISHED for county in counties),
        absent_n=sum(county.human_status == HUMAN_NONE for county in counties),
        complete_n=sum(county.complete for county in counties),
        scored_n=len(scored_marked),
        scored_states=len({row.state for row in scored_marked}),
        below_11_counties=sum(count for count in state_counts.values() if count < MIN_STATE),
        below_11_states=len(below_states),
        svi_rescaled=svi_rescaled,
        uninsured_rescaled=uninsured_rescaled,
        rows=marked,
        seed_jaccard=seed_jaccard,
        seed_spearman=seed_spearman,
        bootstrap_z=bootstrap_z,
        bootstrap_if=bootstrap_if,
        bootstrap_lof=bootstrap_lof,
        permutation_jaccard_if=permutation_jaccard_if,
        permutation_jaccard_z=permutation_jaccard_z,
        size_spearman_z=size_z,
        size_spearman_if=size_if,
        size_spearman_lof=size_lof,
        flag_rate_if=flag_rate,
        flag_rate_low=low,
        flag_rate_high=high,
        agreements=agreements,
        bands=bands,
        situations=situations,
        clusters=clusters,
        method_if=method_if,
        method_z=method_z,
        method_lof=method_lof,
        product=product,
        stable_useful_n=len(useful),
        useful_baseline_jaccard=useful_jaccard,
        baseline_doc_states=baseline_doc_states,
        concentrated=concentrated,
        examples=examples,
        sklearn_version=sklearn_version(),
    )


def _state_counts(counties: Sequence[County]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for county in counties:
        counts[county.state] += 1
    return counts


def _method_if(
    *,
    seed_jaccard: float | None,
    seed_spearman: float | None,
    bootstrap: float | None,
    permutation: bool,
    useful_n: int,
    flagged: int,
) -> str:
    seed_ok = (
        seed_jaccard is not None
        and seed_jaccard >= SEED_JACCARD_MIN
        and seed_spearman is not None
        and seed_spearman < SEED_SPEARMAN_MAX
    )
    boot_ok = bootstrap is not None and bootstrap >= BOOTSTRAP_JACCARD_MIN
    if seed_ok and boot_ok and permutation and useful_n >= USEFUL_MIN:
        return "keep"
    if flagged > 0:
        return "revise"
    return "stop"


def _method_simple(
    *,
    bootstrap: float | None,
    permutation: bool,
    flagged: int,
    extra: bool,
) -> str:
    boot_ok = bootstrap is not None and bootstrap >= BOOTSTRAP_JACCARD_MIN
    if boot_ok and permutation and extra and flagged >= USEFUL_MIN:
        return "keep"
    if flagged > 0:
        return "revise"
    return "stop"


def _finding_disposition(value: str) -> str:
    if value in {"keep", "revise", "stop"}:
        return value
    return "stop"


def _forest_flags(columns: Mapping[str, Vector], fips: Sequence[str], cap: int) -> list[str]:
    _scores, flags = _capped_forest(_z_matrix(columns, fallback=True), fips, cap, PRIMARY_SEED)
    return flags


def _product(
    method_if: str,
    useful_jaccard: float | None,
    concentrated: bool,
    permutation: bool,
    useful_n: int,
) -> str:
    if not permutation and useful_n == 0:
        return "stop"
    if method_if == "stop":
        return "stop"
    distinct = useful_jaccard is not None and useful_jaccard < ADVANCE_JACCARD_MAX
    if method_if == "keep" and distinct and not concentrated:
        return "advance"
    if method_if in {"keep", "revise"}:
        return "investigate"
    return "stop"


def _useful(row: FlagRow) -> bool:
    rate = row.bootstrap_rate_if
    return (
        row.scored
        and rate is not None
        and rate >= USEFUL_RATE_MIN
        and _is_documentation(row.dominant_feature)
        and row.dominant_feature != "tie"
    )


def _perm_pass(jaccard: float | None, size_spearman: float | None) -> bool:
    return (
        jaccard is not None
        and jaccard <= PERMUTATION_JACCARD_MAX
        and size_spearman is not None
        and abs(size_spearman) < SIZE_SPEARMAN_MAX
    )


def _bootstrap(
    columns: Mapping[str, Vector],
    fips: Sequence[str],
    cap: int,
    state_index: int,
) -> tuple[dict[str, float], dict[str, float | None]]:
    n = len(fips)
    sub_n = int(math.floor(BOOTSTRAP_KEEP * n))
    empty: dict[str, float | None] = {"z": None, "if": None, "lof": None}
    if sub_n < MIN_STATE:
        return {}, empty
    generator = np.random.default_rng(np.random.SeedSequence([CLUSTER_SEED, state_index]))
    original_z = set(_baseline(columns, fips, cap)[1])
    original_if = set(_capped_forest(_z_matrix(columns, fallback=True), fips, cap, PRIMARY_SEED)[1])
    original_lof = set(_capped_lof(_z_matrix(columns, fallback=True), fips, cap)[1])
    kept: dict[str, list[float]] = {"z": [], "if": [], "lof": []}
    hits = dict.fromkeys(fips, 0)
    seen = dict.fromkeys(fips, 0)
    draws = 0
    while draws < BOOTSTRAP_DRAWS:
        chosen = generator.choice(n, size=sub_n, replace=False)
        draws += 1
        subset = [fips[int(index)] for index in chosen]
        sub_columns = {name: values[chosen] for name, values in columns.items()}
        flags = {
            "z": set(_baseline(sub_columns, subset, _cap(sub_n))[1]),
            "if": set(_forest_flags(sub_columns, subset, _cap(sub_n))),
            "lof": set(_capped_lof(_z_matrix(sub_columns, fallback=True), subset, _cap(sub_n))[1]),
        }
        originals = {"z": original_z, "if": original_if, "lof": original_lof}
        if_retained = False
        for label in ("z", "if", "lof"):
            reference = originals[label].intersection(subset)
            value = _jaccard(flags[label], reference)
            if value is None:
                continue
            kept[label].append(value)
            if label == "if":
                if_retained = True
        if not if_retained:
            continue
        for name in subset:
            seen[name] += 1
            if name in flags["if"]:
                hits[name] += 1
    rates = {name: hits[name] / seen[name] for name in fips if seen[name] > 0}
    medians = {
        label: _median(values) if len(values) >= 10 else None for label, values in kept.items()
    }
    return rates, medians


def _permute(frames: Sequence[_Frame]) -> tuple[float | None, float | None]:
    if not frames:
        return None, None
    generator = np.random.default_rng(PERMUTATION_SEED)
    forest_values: list[float] = []
    baseline_values: list[float] = []
    for _draw in range(PERMUTATION_DRAWS):
        forest_flags: set[str] = set()
        baseline_flags: set[str] = set()
        original_forest: set[str] = set()
        original_baseline: set[str] = set()
        for frame in frames:
            order = generator.permutation(len(frame.fips))
            shuffled = {
                name: (values[order] if _is_documentation(name) else values)
                for name, values in frame.columns.items()
            }
            forest_flags.update(
                _capped_forest(
                    _z_matrix(shuffled, fallback=True),
                    frame.fips,
                    frame.cap,
                    PRIMARY_SEED,
                )[1]
            )
            baseline_flags.update(_baseline(shuffled, frame.fips, frame.cap)[1])
            original_forest.update(frame.forest_flags)
            original_baseline.update(frame.baseline_flags)
        forest_value = _jaccard(forest_flags, original_forest)
        baseline_value = _jaccard(baseline_flags, original_baseline)
        if forest_value is not None:
            forest_values.append(forest_value)
        if baseline_value is not None:
            baseline_values.append(baseline_value)
    return _median(forest_values), _median(baseline_values)


def _baseline(
    columns: Mapping[str, Vector],
    fips: Sequence[str],
    cap: int,
) -> tuple[Vector | None, list[str], bool]:
    matrix = _z_matrix(columns, fallback=False)
    saw_doc = any(_is_documentation(name) for name in matrix)
    if not matrix:
        return None, [], saw_doc
    stacked = np.column_stack([matrix[name] for name in matrix])
    scores = np.max(np.abs(stacked), axis=1)
    flags = _apply_cap(fips, scores, scores > Z_FLAG, cap)
    return scores, flags, saw_doc


def _z_matrix(columns: Mapping[str, Vector], *, fallback: bool) -> dict[str, Vector]:
    matrix: dict[str, Vector] = {}
    for name, values in columns.items():
        column = _column_z(values, fallback=fallback)
        if column is not None:
            matrix[name] = column
    return matrix


def _column_z(values: Vector, *, fallback: bool) -> Vector | None:
    median = float(np.median(values))
    deviation = np.abs(values - median)
    mad = float(np.median(deviation))
    if mad > 0:
        scale = MAD_SCALE * mad
    elif fallback and np.unique(values).size > 1:
        mean_absolute = float(np.mean(deviation))
        if mean_absolute <= 0:
            return None
        scale = MAD_SCALE * mean_absolute
    else:
        return None
    return np.asarray((values - median) / scale, dtype=float)


def _capped_forest(
    matrix: Mapping[str, Vector],
    fips: Sequence[str],
    cap: int,
    seed: int,
) -> tuple[Vector | None, list[str]]:
    if len(matrix) < 2 or len(fips) < MIN_STATE:
        return None, []
    design = np.column_stack([matrix[name] for name in matrix])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = IsolationForest(
            n_estimators=FOREST_TREES,
            contamination=CONTAMINATION,
            bootstrap=True,
            max_samples="auto",
            max_features=1.0,
            n_jobs=1,
            random_state=seed,
        )
        model.fit(design)
        scores = -np.asarray(model.decision_function(design), dtype=float)
        marked = np.asarray(model.predict(design) == -1, dtype=bool)
    return scores, _apply_cap(fips, scores, marked, cap)


def _capped_lof(
    matrix: Mapping[str, Vector],
    fips: Sequence[str],
    cap: int,
) -> tuple[Vector | None, list[str]]:
    neighbors = min(LOF_NEIGHBORS, len(fips) - 1)
    if len(matrix) < 2 or neighbors < 5:
        return None, []
    design = np.column_stack([matrix[name] for name in matrix])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = LocalOutlierFactor(
            n_neighbors=neighbors,
            contamination=CONTAMINATION,
            metric="euclidean",
            algorithm="brute",
            novelty=False,
        )
        marked = np.asarray(model.fit_predict(design) == -1, dtype=bool)
        scores = -np.asarray(model.negative_outlier_factor_, dtype=float)
    return scores, _apply_cap(fips, scores, marked, cap)


def _dominant(matrix: Mapping[str, Vector]) -> list[tuple[str | None, bool]]:
    if not matrix:
        return []
    names = list(matrix)
    stacked = np.column_stack([matrix[name] for name in names])
    absolute = np.abs(stacked)
    rows: list[tuple[str | None, bool]] = []
    for position in range(absolute.shape[0]):
        order = np.argsort(-absolute[position], kind="mergesort")
        top = names[int(order[0])]
        if len(order) > 1:
            gap = abs(float(absolute[position, order[0]] - absolute[position, order[1]]))
            if gap <= TIE_EPS:
                rows.append(("tie", False))
                continue
        rows.append((top, _is_documentation(top)))
    return rows


def _apply_cap(
    fips: Sequence[str],
    scores: Vector,
    eligible: Vector,
    cap: int,
) -> list[str]:
    chosen = [
        index
        for index, ok in enumerate(eligible.tolist())
        if ok and math.isfinite(float(scores[index]))
    ]
    chosen.sort(key=lambda index: (-float(scores[index]), fips[index]))
    return [fips[index] for index in chosen[:cap]]


def _columns(
    counties: Sequence[County],
    *,
    svi_rescaled: bool,
    uninsured_rescaled: bool,
) -> dict[str, Vector]:
    columns: dict[str, Vector] = {
        "floor_present": np.array(
            [1.0 if county.human_status == HUMAN_PUBLISHED else 0.0 for county in counties]
        )
    }
    for prefix, attr, levels in (
        ("scapularis", "scapularis", SPECIES_LEVELS),
        ("pacificus", "pacificus", SPECIES_LEVELS),
        ("burgdorferi", "burgdorferi", PATHOGEN_LEVELS),
    ):
        for level in levels:
            name = f"{prefix}_{level.lower().replace(' ', '_')}"
            columns[name] = np.array(
                [1.0 if getattr(county, attr) == level else 0.0 for county in counties],
                dtype=float,
            )
    svi = np.array([float(county.svi or 0.0) for county in counties], dtype=float)
    uninsured = np.array([float(county.uninsured or 0.0) for county in counties], dtype=float)
    if svi_rescaled:
        svi = svi / 100.0
    if uninsured_rescaled:
        uninsured = uninsured / 100.0
    columns["svi_percentile"] = svi
    columns["uninsured_percentile"] = uninsured
    columns["rucc_2023"] = np.array([float(county.rucc or 0) for county in counties], dtype=float)
    columns["log_population"] = np.array(
        [math.log(float(county.population or 1.0)) for county in counties],
        dtype=float,
    )
    return columns


def _situations(counties: Sequence[County]) -> dict[str, str]:
    adapted = [
        _SituationCounty(
            human_status=county.human_status or "",
            tick_status=county.tick_status or "",
            burgdorferi_status=county.burgdorferi or "",
        )
        for county in counties
    ]
    raw = _situation_flags(adapted)  # type: ignore[arg-type]
    labels: dict[str, str] = {}
    for index, county in enumerate(counties):
        names = [name for name in SITUATIONS if raw[name][index]]
        labels[county.fips] = ",".join(names) if names else "other"
    return labels


@dataclass(frozen=True)
class _SituationCounty:
    human_status: str
    tick_status: str
    burgdorferi_status: str


def _blank_row(
    county: County,
    state_n: int,
    complete_n: int,
    band: str,
    situations: Mapping[str, str],
    clusters: Mapping[str, int],
) -> FlagRow:
    return FlagRow(
        fips=county.fips,
        county_name=county.name,
        state=county.state,
        state_n=state_n,
        complete_n=complete_n,
        size_band=band,
        scored=False,
        incomplete=not county.complete,
        score_robust_z=None,
        flag_robust_z=False,
        score_if_primary=None,
        flag_if_primary=False,
        score_if_seed_b=None,
        flag_if_seed_b=False,
        score_lof=None,
        flag_lof=False,
        bootstrap_rate_if=None,
        dominant_feature=None,
        stable_useful=False,
        situation_121=situations.get(county.fips, "other"),
        cluster_id_120=clusters.get(county.fips),
    )


def _agreements(rows: Sequence[FlagRow]) -> tuple[PairAgreement, ...]:
    pairs = (
        ("if", "z", "score_if_primary", "score_robust_z", "flag_if_primary", "flag_robust_z"),
        ("if", "lof", "score_if_primary", "score_lof", "flag_if_primary", "flag_lof"),
        ("z", "lof", "score_robust_z", "score_lof", "flag_robust_z", "flag_lof"),
    )
    output: list[PairAgreement] = []
    by_state: dict[str, list[FlagRow]] = defaultdict(list)
    for row in rows:
        by_state[row.state].append(row)
    for left, right, score_left, score_right, flag_left, flag_right in pairs:
        parts: list[float] = []
        weights: list[int] = []
        for group in by_state.values():
            value = _paired_spearman(
                [getattr(row, score_left) for row in group],
                [getattr(row, score_right) for row in group],
            )
            if value is None:
                continue
            parts.append(value)
            weights.append(len(group))
        spearman = float(np.average(parts, weights=weights)) if parts else None
        left_flags = {row.fips for row in rows if getattr(row, flag_left)}
        right_flags = {row.fips for row in rows if getattr(row, flag_right)}
        matched = _matched_jaccard(rows, flag_left, score_right)
        output.append(
            PairAgreement(
                left=left,
                right=right,
                spearman=spearman,
                jaccard=_jaccard(left_flags, right_flags),
                matched_jaccard=matched,
            )
        )
    return tuple(output)


def _matched_jaccard(rows: Sequence[FlagRow], flag_name: str, score_name: str) -> float | None:
    flagged = [row for row in rows if getattr(row, flag_name)]
    if not flagged:
        return _jaccard(set(), set())
    ranked = sorted(
        rows,
        key=lambda row: (
            -(getattr(row, score_name) if getattr(row, score_name) is not None else -1e18),
            row.fips,
        ),
    )
    top = {row.fips for row in ranked[: len(flagged)]}
    return _jaccard({row.fips for row in flagged}, top)


def _bands(rows: Sequence[FlagRow]) -> tuple[BandShare, ...]:
    bands = ("11_39", "40_99", "100_plus")
    methods = (
        ("robust_z", "flag_robust_z"),
        ("isolation_forest", "flag_if_primary"),
        ("local_outlier_factor", "flag_lof"),
    )
    output: list[BandShare] = []
    for band in bands:
        members = [row for row in rows if row.scored and row.size_band == band]
        for method, attr in methods:
            output.append(
                BandShare(
                    band=band,
                    method=method,
                    counties=len(members),
                    flags=sum(bool(getattr(row, attr)) for row in members),
                )
            )
    return tuple(output)


def _situation_shares(
    scored: Sequence[FlagRow],
    flagged: Sequence[FlagRow],
) -> tuple[SituationShare, ...]:
    rows: list[SituationShare] = []
    for name in (*SITUATIONS, "other"):
        rows.append(
            SituationShare(
                name=name,
                scored_n=sum(_has_situation(row, name) for row in scored),
                flag_n=sum(_has_situation(row, name) for row in flagged),
            )
        )
    return tuple(rows)


def _cluster_shares(
    scored: Sequence[FlagRow],
    flagged: Sequence[FlagRow],
) -> tuple[ClusterShare, ...]:
    ids = sorted({row.cluster_id_120 for row in scored if row.cluster_id_120 is not None})
    return tuple(
        ClusterShare(
            cluster_id=cluster_id,
            cohort_n=sum(row.cluster_id_120 == cluster_id for row in scored),
            flag_n=sum(row.cluster_id_120 == cluster_id for row in flagged),
        )
        for cluster_id in ids
    )


def _concentrated(useful: Sequence[FlagRow], scored: Sequence[FlagRow]) -> bool:
    if not useful or not scored:
        return False
    for name in SITUATIONS:
        hold = sum(_has_situation(row, name) for row in useful) / len(useful)
        cover = sum(_has_situation(row, name) for row in scored) / len(scored)
        if hold > CONCENTRATION_FLAG and cover < CONCENTRATION_BASE:
            return True
    return False


def _has_situation(row: FlagRow, name: str) -> bool:
    parts = set(row.situation_121.split(","))
    if name == "other":
        return parts == {"other"}
    return name in parts


def _cluster_interval(rows: Sequence[FlagRow]) -> tuple[float | None, float | None]:
    grouped: dict[str, tuple[int, int]] = {}
    for row in rows:
        flags, total = grouped.get(row.state, (0, 0))
        grouped[row.state] = (flags + int(row.flag_if_primary), total + 1)
    states = list(grouped.values())
    if len(states) < MIN_STATE:
        return None, None
    generator = np.random.default_rng(CLUSTER_SEED)
    draws: list[float] = []
    for _draw in range(CLUSTER_DRAWS):
        picked = generator.integers(0, len(states), size=len(states))
        flags = sum(states[int(index)][0] for index in picked)
        total = sum(states[int(index)][1] for index in picked)
        if total <= 0:
            continue
        draws.append(flags / total)
    if len(draws) < 100:
        return None, None
    low, high = np.percentile(np.array(draws), [2.5, 97.5])
    return float(low), float(high)


def _size_spearman(rows: Sequence[FlagRow], flag_name: str) -> float | None:
    grouped: dict[str, list[FlagRow]] = defaultdict(list)
    for row in rows:
        grouped[row.state].append(row)
    if len(grouped) < MIN_STATE:
        return None
    counts = []
    rates = []
    for group in grouped.values():
        counts.append(float(group[0].state_n))
        rates.append(sum(bool(getattr(row, flag_name)) for row in group) / len(group))
    return _spearman(np.array(counts), np.array(rates))


def _paired_spearman(left: Sequence[float | None], right: Sequence[float | None]) -> float | None:
    pairs = [
        (float(first), float(second))
        for first, second in zip(left, right, strict=True)
        if (
            first is not None
            and second is not None
            and math.isfinite(first)
            and math.isfinite(second)
        )
    ]
    if len(pairs) < MIN_STATE:
        return None
    return _spearman(
        np.array([item[0] for item in pairs]),
        np.array([item[1] for item in pairs]),
    )


def _spearman(left: Vector, right: Vector) -> float | None:
    if len(left) < 3 or float(np.std(left)) == 0 or float(np.std(right)) == 0:
        return None
    correlation = np.corrcoef(_rank(left), _rank(right))[0, 1]
    if not math.isfinite(float(correlation)):
        return None
    return float(correlation)


def _rank(values: Vector) -> Vector:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    start = 0
    while start < len(values):
        end = start + 1
        while end < len(values) and values[order[end]] == values[order[start]]:
            end += 1
        average = (start + end - 1) / 2.0
        for position in range(start, end):
            ranks[order[position]] = average
        start = end
    return ranks


def _jaccard(left: set[str], right: set[str]) -> float | None:
    if not left and not right:
        return None
    union = left | right
    if not union:
        return None
    return len(left & right) / len(union)


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return float(np.median(np.array(values, dtype=float)))


def _cap(count: int) -> int:
    return max(1, int(math.floor(CAP_SHARE * count)))


def _band(count: int) -> str:
    if count < MIN_STATE:
        return "below_11"
    if count < 40:
        return "11_39"
    if count < 100:
        return "40_99"
    return "100_plus"


def _is_documentation(name: str | None) -> bool:
    if name is None:
        return False
    return name == "floor_present" or name.startswith(("scapularis_", "pacificus_", "burgdorferi_"))


def _at(values: Vector | None, position: int) -> float | None:
    if values is None:
        return None
    value = float(values[position])
    if not math.isfinite(value):
        return None
    return value


def _county(row: Mapping[str, object], *, release_id: str) -> County:
    if _text(row.get("RELEASE_ID")) != release_id:
        raise DocOutlierError("county release id does not match the pin")
    fips = _text(row.get("FIPS"))
    if len(fips) != 5 or not fips.isdigit():
        raise DocOutlierError("FIPS must be five digits")
    state = _text(row.get("STATE"))
    if not state:
        raise DocOutlierError("state is missing")
    return County(
        fips=fips,
        name=_text(row.get("COUNTY")) or fips,
        state=state,
        population=_positive(row.get("POPULATION")),
        svi=_optional_float(row.get("SVI_PERCENTILE")),
        uninsured=_optional_float(row.get("UNINSURED_PERCENTILE")),
        rucc=_rucc(row.get("RUCC_2023")),
        human_status=_status(row.get("HUMAN_STATUS"), HUMAN_LEVELS, "human"),
        scapularis=_status(row.get("SCAPULARIS_STATUS"), frozenset(SPECIES_LEVELS), "scapularis"),
        pacificus=_status(row.get("PACIFICUS_STATUS"), frozenset(SPECIES_LEVELS), "pacificus"),
        burgdorferi=_status(
            row.get("BURGDORFERI_STATUS"),
            frozenset(PATHOGEN_LEVELS),
            "burgdorferi",
        ),
        tick_status=_optional_text(row.get("TICK_STATUS")),
    )


def _status(value: object, allowed: frozenset[str], label: str) -> str | None:
    if value is None:
        return None
    text = _text(value)
    if text not in allowed:
        raise DocOutlierError(f"unexpected {label} status")
    return text


def _rucc(value: object) -> int | None:
    if value is None:
        return None
    number = _optional_float(value)
    if number is None or not number.is_integer():
        raise DocOutlierError("rural-urban code is not an integer")
    code = int(number)
    if code < 1 or code > 9:
        return None
    return code


def _positive(value: object) -> float | None:
    number = _optional_float(value)
    if number is None:
        return None
    if number <= 0:
        return None
    return number


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise DocOutlierError("numeric column is not a number")
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        try:
            number = float(str(value))
        except ValueError as error:
            raise DocOutlierError("numeric column is not a number") from error
    if not math.isfinite(number):
        return None
    return number


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _text(value)


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _metric(
    name: str,
    count: int,
    value: float,
    unit: str,
    *,
    geography_type: str | None = None,
    geography_id: str | None = None,
) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        n_underlying=count,
        metric_value=value,
        geography_type=geography_type,
        geography_id=geography_id,
        unit=unit,
    )


def _append_rate(
    rows: list[EdaMetric],
    name: str,
    value: float | None,
    count: int,
) -> None:
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
    _reject_detection_names((name,))
    return ExperimentMetric(
        split_name="within_state",
        metric_name=name,
        metric_value=value,
        n=count,
        ci_low=low,
        ci_high=high,
    )


def _reject_detection_names(names: Iterable[str]) -> None:
    blocked = ("auc", "accuracy", "precision", "recall", "f1")
    for name in names:
        lowered = str(name).lower()
        if any(token in lowered for token in blocked):
            raise DocOutlierError("a label-based detection metric is not allowed")
