"""State-relative anomaly screen for issue 106.

County rows stay in memory. Aggregate lab records suppress counts from 1 to 10.
The results write-up may name counties. Charts do not.
"""

from __future__ import annotations

import math
import warnings
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]
from sklearn.neighbors import LocalOutlierFactor  # type: ignore[import-untyped]

from lyme_gap_atlas_ml.class_anomaly import (
    CHI2_975,
    MAD_SCALE,
    N_ESTIMATORS,
    Z_FLAG,
    ExperimentRow,
    ModelMetricRow,
    ParsedRow,
    Vector,
    _bootstrap,
    _county_name,
    _fips,
    _jaccard,
    _optional_float,
    _publish_composition,
    _rate_metric,
    _reject_identity_problems,
    _robust_distances,
    _robust_z_matrix,
    _state,
    _status,
    _top_mask,
    dominant_label,
    exclusion_reason,
    sklearn_version,
)
from lyme_gap_atlas_ml.coverage_audit import (
    CENSUS_REGIONS,
    PINNED_BUNDLE_SHA256,
    PINNED_RELEASE_ID,
    REFERENCE_COUNTIES,
    REFERENCE_NO_COUNTY_LINKED_RECORD,
    REFERENCE_PUBLISHED_HUMAN_FLOOR,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import FindingRecord
from lyme_gap_atlas_ml.snowflake.eda_writer import SMALL_CELL_MINIMUM, EdaMetric

SPEC_ID = "106-state-relative-anomaly/v1.1"
STATE_NATIVE_MIN = 40
SHRINK_MIN = 15
FOREST_MIN = 80
SURVEILLANCE_MIN = 44
MINORITY_SHARE_MAX = 0.25
PERCENTILE_TAIL = 0.025
SHRINK_PRIOR_N = 40
PRIMARY_SEED = 1062026
SECOND_SEED = 1062027
SEEDS = (PRIMARY_SEED, SECOND_SEED)
CONTAMINATIONS = (0.02, 0.05, 0.10)
PRIMARY_CONTAMINATION = 0.05
RANK_SHIFT_MIN = 100
JACCARD_DEFER = 0.80
SMALL_SHARE_REVISE = 0.10
URBAN_GAP_REVISE = 0.25
MCD_FAILURE_REVISE = 0.50
DETECTOR_MIN_STATES = 8
SEED_STABLE_JACCARD = 0.90
MATCHED_DISTINCT = 0.80
METRO_MAX_RUCC = 3
LOF_NEIGHBORS = 20
HUMAN_PUBLISHED = "published_count_floor"
TICK_ESTABLISHED = "Established"
PATHOGEN_PRESENT = "Present"
FEATURE_NAMES = (
    "log_population",
    "svi_percentile",
    "uninsured_percentile",
    "rucc_2023",
)
FEATURE_LABELS = {
    "log_population": "log population",
    "svi_percentile": "SVI percentile",
    "uninsured_percentile": "uninsured percentile",
    "rucc_2023": "rural-urban code",
}
SIGNAL_NAMES = ("human_published", "tick_established", "pathogen_present")
QUERY_NAMES = ("release_identity", "cohort_gate", "source_vintages", "cohort_rows")
EXPECTED_DOUBLE_GAP_N = 228
SIZE_BANDS = ("fallback", "shrunk", "state_native")
SEED_EDGES = (0.0, 0.5, 0.7, 0.8, 0.9, 1.01)


class StateAnomalyError(ValueError):
    """The state-relative screen stopped on a predeclared gate."""


@dataclass(frozen=True)
class GateDecision:
    ok: bool
    reasons: tuple[str, ...]
    release_id: str
    bundle_sha256: str
    schema_version: str
    methodology_version: str
    scope: str
    row_n: int


@dataclass(frozen=True)
class ScoredCounty:
    fips: str
    county_name: str
    state: str
    region: str
    peer_rule: str
    peer_label: str
    peer_n: int
    state_n: int
    population: float
    log_population: float
    svi_percentile: float
    uninsured_percentile: float
    rucc: int
    human_status: str
    tick_status: str
    burgdorferi_status: str
    z_state: tuple[tuple[str, float], ...]
    z_national: tuple[tuple[str, float], ...]
    max_abs_z_state: float
    max_abs_z_national: float
    rank_state: int
    rank_national: int
    flag_z_state: bool
    flag_z_national: bool
    flag_percentile: bool
    percentile_applied: bool
    flag_mcd: bool
    mcd_applied: bool
    flag_mcd_national: bool
    mahalanobis_peer: float | None
    mahalanobis_national: float | None
    flag_if_primary: bool
    flag_if_seed_b: bool
    flag_if_c02: bool
    flag_if_c10: bool
    forest_applied: bool
    if_score_primary: float | None
    flag_lof: bool
    flag_lof_c02: bool
    flag_lof_c10: bool
    lof_applied: bool
    lof_score: float | None
    flag_surveillance: bool
    surveillance_applied: bool
    surveillance_signal: str
    flag_surveillance_national: bool
    dominant_feature: str
    reason: str
    metro: bool

    def state_z(self, name: str) -> float | None:
        return _lookup(self.z_state, name)

    def national_z(self, name: str) -> float | None:
        return _lookup(self.z_national, name)


@dataclass(frozen=True)
class FitResult:
    n_rows: int
    n_fit: int
    exclusions: int
    scaled_columns: tuple[str, ...]
    disposition: str
    counties: tuple[ScoredCounty, ...]
    flag_z_state: int
    flag_z_national: int
    jaccard_national: float
    median_abs_rank_shift: float | None
    spearman: float | None
    small_share: float | None
    small_flag_n: int
    fallback_flag_n: int
    urban_gap: float | None
    urban_comparable: bool
    cohort_metro_n: int
    flag_metro_n: int
    native_feature_failure: bool
    mcd_failure_n: int
    mcd_native_n: int
    mcd_failure_share: float | None
    forest_eligible_states: int
    forest_stable_states: int
    forest_defensible: bool
    lof_defensible: bool
    seed_jaccards: tuple[float, ...]
    flag_rate_interval: tuple[float, float] | None
    review: tuple[ScoredCounty, ...]
    state_only: tuple[ScoredCounty, ...]
    national_only: tuple[ScoredCounty, ...]
    surveillance_review: tuple[ScoredCounty, ...]
    experiments: tuple[ExperimentRow, ...]
    band_state_counts: dict[str, int]
    band_county_counts: dict[str, int]
    spread: dict[str, dict[str, float | None]]
    agreement: dict[str, int | None]
    seed_split: dict[str, int | None]
    seed_bins: dict[str, int | None]


@dataclass(frozen=True)
class _ForestState:
    seed_jaccard: float
    primary_flags: int
    seed_b_flags: int
    matched_jaccard: float | None


@dataclass(frozen=True)
class _LofState:
    nested_jaccard: float | None
    matched_jaccard: float | None
    primary_flags: int


def shrunk_mad(
    state_mad: float,
    state_n: int,
    loo_mad: float,
    loo_n: int,
    full_mad: float,
) -> float:
    """Blend a small state's MAD toward the region prior from the frozen rule."""
    prior = loo_mad if loo_n >= STATE_NATIVE_MIN and loo_mad > 0 else full_mad
    if state_mad == 0:
        return prior
    if prior == 0:
        return state_mad
    weight = state_n / (state_n + SHRINK_PRIOR_N)
    return weight * state_mad + (1.0 - weight) * prior


def percentile_flags(values: Vector) -> Vector:
    """Flag tails at or beyond 2.5 percent using average ranks."""
    percentile = _average_percentile(np.asarray(values, dtype=float))
    return (percentile <= PERCENTILE_TAIL) | (percentile >= 1.0 - PERCENTILE_TAIL)


def surveillance_flags(values: Vector) -> tuple[Vector, bool]:
    """Flag a minority status when it is uncommon and not a small cell."""
    coded = np.asarray(values, dtype=float)
    count = int(coded.shape[0])
    if count < SURVEILLANCE_MIN:
        return np.zeros(count, dtype=bool), False
    ones = int(np.sum(coded == 1.0))
    minority_n = min(ones, count - ones)
    if minority_n < SMALL_CELL_MINIMUM:
        return np.zeros(count, dtype=bool), False
    if minority_n / count > MINORITY_SHARE_MAX:
        return np.zeros(count, dtype=bool), True
    minority_value = 1.0 if ones <= count - ones else 0.0
    return coded == minority_value, True


def decide_state_disposition(
    *,
    exclusions: int,
    state_flags: int,
    jaccard_national: float | None,
    median_abs_rank_shift: float | None,
    small_share: float | None,
    urban_gap: float | None,
    urban_comparable: bool,
    native_feature_failure: bool,
    mcd_failure_share: float | None,
) -> str:
    """Apply the v1.1 disposition rule. Gate failures never reach this function."""
    if exclusions > 0:
        return "revise"
    lists_agree = jaccard_national is not None and jaccard_national >= JACCARD_DEFER
    ranks_barely_move = median_abs_rank_shift is not None and median_abs_rank_shift < RANK_SHIFT_MIN
    if state_flags == 0 or lists_agree or ranks_barely_move:
        return "defer"
    small_states_dominate = small_share is not None and small_share > SMALL_SHARE_REVISE
    distance_failed = mcd_failure_share is not None and mcd_failure_share > MCD_FAILURE_REVISE
    urban_concentrated = (
        urban_comparable and urban_gap is not None and urban_gap >= URBAN_GAP_REVISE
    )
    if (
        state_flags < SMALL_CELL_MINIMUM
        or small_states_dominate
        or native_feature_failure
        or distance_failed
        or urban_concentrated
    ):
        return "revise"
    return "proceed"


def evaluate_gate(release: Mapping[str, object], gate: Mapping[str, object]) -> GateDecision:
    """Apply the predeclared release and cohort gates. Does not fit a model."""
    release_id = _text(release.get("RELEASE_ID"))
    bundle = _text(release.get("BUNDLE_SHA256")).lower()
    reasons: list[str] = []
    if release_id != PINNED_RELEASE_ID:
        reasons.append("release id is not the pinned release")
    if bundle != PINNED_BUNDLE_SHA256:
        reasons.append("bundle SHA-256 is not the pinned bundle")
    row_n = _int_field(gate.get("ROW_N"))
    checks = (
        (row_n != REFERENCE_COUNTIES, "county count is not 3144"),
        (_int_field(gate.get("FIPS_N")) != REFERENCE_COUNTIES, "distinct FIPS count is not 3144"),
        (
            _int_field(gate.get("FIPS_PATTERN_N")) != REFERENCE_COUNTIES,
            "five-digit FIPS count is not 3144",
        ),
        (_int_field(gate.get("RELEASE_N")) != 1, "release id count is not 1"),
        (
            _int_field(gate.get("HUMAN_FLOOR_N")) != REFERENCE_PUBLISHED_HUMAN_FLOOR,
            "published human floor is not 651",
        ),
        (
            _int_field(gate.get("HUMAN_NONE_N")) != REFERENCE_NO_COUNTY_LINKED_RECORD,
            "no-county-linked count is not 2493",
        ),
        (
            _int_field(gate.get("DOUBLE_GAP_N")) != EXPECTED_DOUBLE_GAP_N,
            "double-gap count is not 228",
        ),
    )
    reasons.extend(message for failed, message in checks if failed)
    return GateDecision(
        ok=not reasons,
        reasons=tuple(reasons),
        release_id=release_id,
        bundle_sha256=bundle,
        schema_version=_text(release.get("SCHEMA_VERSION")),
        methodology_version=_text(release.get("METHODOLOGY_VERSION")),
        scope=_text(release.get("SCOPE")),
        row_n=row_n,
    )


def fit_states(rows: Sequence[Mapping[str, object]], *, run_id: str) -> FitResult:
    """Fit the frozen state-relative rules. Raises on a duplicate or an unusable identity."""
    parsed = tuple(_parse(row) for row in rows)
    _reject_identity_problems(parsed)
    kept: list[ParsedRow] = []
    exclusions = 0
    for row in parsed:
        if exclusion_reason(row) is None:
            kept.append(row)
        else:
            exclusions += 1
    if len(kept) < STATE_NATIVE_MIN:
        raise StateAnomalyError("fewer than 40 complete rows remain")
    scaled = _scaled_columns(kept)
    matrix = _matrix(kept, scaled)
    national_z, national_keep = _group_z(matrix)
    if int(np.sum(national_keep)) < 2:
        raise StateAnomalyError("fewer than two national features remain")
    states = [row.state for row in kept]
    regions = [CENSUS_REGIONS[row.state] for row in kept]
    state_counts = Counter(states)
    region_counts = Counter(regions)
    cell_counts: Counter[tuple[str, str]] = Counter(
        (region, row.tick_status) for region, row in zip(regions, kept, strict=True)
    )
    peer_rule, peer_label, peer_count = _peers(
        kept, states, regions, state_counts, region_counts, cell_counts
    )
    z_state, medians, native_failure = _relative_z(
        matrix,
        states,
        regions,
        [row.tick_status for row in kept],
        peer_rule,
        state_counts,
    )
    max_state = _max_abs(z_state)
    max_national = _max_abs(national_z)
    flag_state = max_state > Z_FLAG
    flag_national = max_national > Z_FLAG
    percentile, percentile_on = _percentile_by_peer(
        matrix, kept, states, regions, peer_rule, peer_count
    )
    surveillance, surveillance_on, surveillance_name = _surveillance_by_peer(
        kept, states, regions, peer_rule
    )
    national_surveillance = _national_surveillance(kept)
    distances, distance_flags, distance_on, mcd_failures, native_groups = _distances(
        matrix, states, regions, peer_rule, [row.tick_status for row in kept]
    )
    national_distance, national_distance_flag = _national_distance(matrix, national_keep)
    fips = np.asarray([row.fips for row in kept], dtype=object)
    forest = _forests(matrix, states, state_counts, flag_state, fips)
    lof = _lofs(matrix, states, state_counts, flag_state, fips)
    counties = _assemble(
        kept,
        regions,
        peer_rule,
        peer_label,
        peer_count,
        state_counts,
        matrix,
        medians,
        z_state,
        national_z,
        max_state,
        max_national,
        _ranks(max_state, fips),
        _ranks(max_national, fips),
        flag_state,
        flag_national,
        percentile,
        percentile_on,
        distances,
        distance_flags,
        distance_on,
        national_distance,
        national_distance_flag,
        forest,
        lof,
        surveillance,
        surveillance_on,
        surveillance_name,
        national_surveillance,
    )
    summary = _summarize(
        counties,
        flag_state,
        flag_national,
        states,
        state_counts,
        mcd_failures,
        native_groups,
        forest[1],
        lof[1],
    )
    disposition = decide_state_disposition(
        exclusions=exclusions,
        state_flags=summary.flag_z_state,
        jaccard_national=summary.jaccard_national,
        median_abs_rank_shift=summary.median_abs_rank_shift,
        small_share=summary.small_share,
        urban_gap=summary.urban_gap,
        urban_comparable=summary.urban_comparable,
        native_feature_failure=native_failure,
        mcd_failure_share=summary.mcd_failure_share,
    )
    experiments = _experiments(run_id, summary.flag_rate_interval, counties)
    return FitResult(
        n_rows=len(parsed),
        n_fit=len(kept),
        exclusions=exclusions,
        scaled_columns=scaled,
        disposition=disposition,
        counties=counties,
        flag_z_state=summary.flag_z_state,
        flag_z_national=summary.flag_z_national,
        jaccard_national=summary.jaccard_national,
        median_abs_rank_shift=summary.median_abs_rank_shift,
        spearman=summary.spearman,
        small_share=summary.small_share,
        small_flag_n=summary.small_flag_n,
        fallback_flag_n=summary.fallback_flag_n,
        urban_gap=summary.urban_gap,
        urban_comparable=summary.urban_comparable,
        cohort_metro_n=summary.cohort_metro_n,
        flag_metro_n=summary.flag_metro_n,
        native_feature_failure=native_failure,
        mcd_failure_n=summary.mcd_failure_n,
        mcd_native_n=summary.mcd_native_n,
        mcd_failure_share=summary.mcd_failure_share,
        forest_eligible_states=summary.forest_eligible_states,
        forest_stable_states=summary.forest_stable_states,
        forest_defensible=summary.forest_defensible,
        lof_defensible=summary.lof_defensible,
        seed_jaccards=summary.seed_jaccards,
        flag_rate_interval=summary.flag_rate_interval,
        review=summary.review,
        state_only=summary.state_only,
        national_only=summary.national_only,
        surveillance_review=summary.surveillance_review,
        experiments=experiments,
        band_state_counts=summary.band_state_counts,
        band_county_counts=summary.band_county_counts,
        spread=summary.spread,
        agreement=summary.agreement,
        seed_split=summary.seed_split,
        seed_bins=summary.seed_bins,
    )


def lab_metrics(result: FitResult) -> list[EdaMetric]:
    """Aggregate metrics. A 1–10 numerator is suppressed by the lab writer."""
    rows = [
        EdaMetric(
            metric_name="fit_counties",
            n_underlying=result.n_fit,
            metric_value=float(result.n_fit),
            geography_type="national",
            geography_id="US",
            unit="counties",
        ),
        _rate_metric("flag_rate_z_state", result.flag_z_state, result.n_fit, {}, None),
        _rate_metric("flag_rate_z_national", result.flag_z_national, result.n_fit, {}, None),
    ]
    publish_agreement = all(value is not None for value in result.agreement.values())
    rows.append(
        EdaMetric(
            metric_name="jaccard_state_national",
            n_underlying=result.n_fit if publish_agreement else 1,
            metric_value=result.jaccard_national if publish_agreement else None,
            geography_type="national",
            geography_id="US",
            unit="jaccard",
        )
    )
    if result.spearman is not None:
        rows.append(
            EdaMetric(
                metric_name="spearman_max_abs_z",
                n_underlying=result.n_fit,
                metric_value=result.spearman,
                geography_type="national",
                geography_id="US",
                unit="correlation",
            )
        )
    if result.median_abs_rank_shift is not None and result.flag_z_state >= SMALL_CELL_MINIMUM:
        rows.append(
            EdaMetric(
                metric_name="median_abs_rank_shift",
                n_underlying=result.n_fit,
                metric_value=result.median_abs_rank_shift,
                geography_type="national",
                geography_id="US",
                unit="ranks",
            )
        )
    if result.flag_rate_interval is not None and result.flag_z_state >= SMALL_CELL_MINIMUM:
        low, high = result.flag_rate_interval
        rows.append(_interval_metric("flag_rate_z_state_bootstrap_low", low, result.n_fit))
        rows.append(_interval_metric("flag_rate_z_state_bootstrap_high", high, result.n_fit))
    band_counts = [result.band_county_counts.get(band, 0) for band in SIZE_BANDS]
    if all(count == 0 or count >= SMALL_CELL_MINIMUM for count in band_counts):
        for band, count in zip(SIZE_BANDS, band_counts, strict=True):
            if count < SMALL_CELL_MINIMUM:
                continue
            rows.append(
                EdaMetric(
                    metric_name="band_county_count",
                    n_underlying=count,
                    metric_value=float(count),
                    geography_type="state_size_band",
                    geography_id=band,
                    unit="counties",
                )
            )
    return rows


def build_findings(result: FitResult) -> list[FindingRecord]:
    """Three aggregate findings. Defer is stored as revise and named in the statement."""
    if result.flag_z_state < SMALL_CELL_MINIMUM:
        screen = "The state-relative robust-z flag count is below the publishable minimum."
    else:
        screen = (
            f"State-relative robust z flagged {result.flag_z_state} of {result.n_fit} counties. "
            f"National robust z flagged {result.flag_z_national}."
        )
    low, high = result.flag_rate_interval if result.flag_rate_interval else (None, None)
    return [
        FindingRecord(
            topic="state relative screen",
            statement=(
                f"The discovery call is {result.disposition}. {screen} "
                "Temporal detection was not fit because the pinned release is one county snapshot."
            ),
            disposition=_lab_disposition(result.disposition),
            n_underlying=result.n_fit,
            effect_size=None
            if result.flag_z_state < SMALL_CELL_MINIMUM
            else result.flag_z_state / result.n_fit,
            ci_low=low if result.flag_z_state >= SMALL_CELL_MINIMUM else None,
            ci_high=high if result.flag_z_state >= SMALL_CELL_MINIMUM else None,
            uncertainty_note="State-cluster bootstrap percentile interval for the flag rate.",
            evidence={"call": result.disposition},
        ),
        FindingRecord(
            topic="small state safeguard",
            statement=_safeguard_statement(result),
            disposition=_lab_disposition(result.disposition),
            n_underlying=result.n_fit,
            evidence={"urban_comparable": result.urban_comparable},
        ),
        FindingRecord(
            topic="detector stability",
            statement=_detector_statement(result),
            disposition=_lab_disposition(result.disposition),
            n_underlying=result.n_fit,
            evidence={
                "forest_defensible": result.forest_defensible,
                "lof_defensible": result.lof_defensible,
            },
        ),
    ]


def _lab_disposition(call: str) -> str:
    if call == "proceed":
        return "follow-up"
    if call == "stop":
        return "stop"
    return "revise"


def _safeguard_statement(result: FitResult) -> str:
    withheld = result.flag_z_state < SMALL_CELL_MINIMUM or (
        0 < result.small_flag_n < SMALL_CELL_MINIMUM
    )
    if withheld or result.small_share is None:
        small = "The count of state-relative flags from states under 40 counties is withheld."
    else:
        small = (
            "The share of state-relative flags from states under 40 counties is "
            f"{result.small_share:.3f}."
        )
    if result.urban_comparable and result.urban_gap is not None:
        urban = f"The metro share gap versus the cohort is {result.urban_gap:.3f}."
    else:
        urban = "The metro split of the flag list is withheld."
    return f"{small} {urban}"


def _detector_statement(result: FitResult) -> str:
    forest = "met" if result.forest_defensible else "missed"
    lof = "met" if result.lof_defensible else "missed"
    if result.forest_eligible_states < SMALL_CELL_MINIMUM:
        where = "Fewer than 11 states were large enough for a detector."
    else:
        where = f"{result.forest_eligible_states} states were large enough for a detector."
    return (
        f"{where} The isolation forest stability bar was {forest}. "
        f"The local outlier factor stability bar was {lof}."
    )


def _interval_metric(name: str, value: float, count: int) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        n_underlying=count,
        metric_value=value,
        geography_type="national",
        geography_id="US",
        unit="rate",
    )


def _parse(raw: Mapping[str, object]) -> ParsedRow:
    fips = raw.get("FIPS")
    if isinstance(fips, int) and not isinstance(fips, bool):
        fips = f"{fips:05d}"
    state = _state(raw.get("STATE"))
    if state not in CENSUS_REGIONS:
        raise StateAnomalyError("a row has a state outside the Census map")
    return ParsedRow(
        fips=_fips(fips),
        county_name=_county_name(raw.get("COUNTY")),
        state=state,
        population=_optional_float(raw.get("POPULATION")),
        svi_percentile=_optional_float(raw.get("SVI_PERCENTILE")),
        uninsured_percentile=_optional_float(raw.get("UNINSURED_PERCENTILE")),
        rucc=_optional_float(raw.get("RUCC_2023")),
        human_status=_status(raw.get("HUMAN_STATUS"), "human status"),
        burgdorferi_status=_status(raw.get("BURGDORFERI_STATUS"), "pathogen status"),
        tick_status=_status(raw.get("TICK_STATUS"), "tick status"),
    )


def _scaled_columns(rows: Sequence[ParsedRow]) -> tuple[str, ...]:
    scaled: list[str] = []
    for name, attr in (
        ("svi_percentile", "svi_percentile"),
        ("uninsured_percentile", "uninsured_percentile"),
    ):
        values = [float(getattr(row, attr)) for row in rows]
        if values and max(values) > 1.5:
            scaled.append(name)
    return tuple(scaled)


def _matrix(rows: Sequence[ParsedRow], scaled: Sequence[str]) -> Vector:
    columns = [
        np.asarray([math.log(float(row.population or 0.0)) for row in rows], dtype=float),
        np.asarray([float(row.svi_percentile or 0.0) for row in rows], dtype=float),
        np.asarray([float(row.uninsured_percentile or 0.0) for row in rows], dtype=float),
        np.asarray([float(row.rucc or 0.0) for row in rows], dtype=float),
    ]
    for name in scaled:
        columns[FEATURE_NAMES.index(name)] = columns[FEATURE_NAMES.index(name)] / 100.0
    return np.column_stack(columns)


def _group_z(block: Vector) -> tuple[Vector, Vector]:
    median = np.median(block, axis=0)
    mad = np.median(np.abs(block - median), axis=0)
    keep = np.asarray(mad > 0)
    scored = np.full(block.shape, np.nan)
    if int(np.sum(keep)) == 0:
        return scored, keep
    scored[:, keep] = _robust_z_matrix(np.asarray(block[:, keep], dtype=float))
    return scored, keep


def _peers(
    rows: Sequence[ParsedRow],
    states: Sequence[str],
    regions: Sequence[str],
    state_counts: Counter[str],
    region_counts: Counter[str],
    cell_counts: Counter[tuple[str, str]],
) -> tuple[list[str], list[str], list[int]]:
    rules: list[str] = []
    labels: list[str] = []
    counts: list[int] = []
    for row, state, region in zip(rows, states, regions, strict=True):
        state_size = state_counts[state]
        if state_size >= STATE_NATIVE_MIN:
            rules.append("state_native")
            labels.append(f"state {state}")
            counts.append(state_size)
            continue
        if state_size >= SHRINK_MIN:
            rules.append("state_shrunk")
            labels.append(f"state {state} with region-shrunk scale")
            counts.append(state_size)
            continue
        cell = cell_counts[(region, row.tick_status)]
        if cell >= STATE_NATIVE_MIN:
            rules.append("class_peer")
            labels.append(f"Census region {region}, tick status {row.tick_status}")
            counts.append(cell)
            continue
        rules.append("region_peer")
        labels.append(f"Census region {region}")
        counts.append(region_counts[region])
    return rules, labels, counts


def _relative_z(
    matrix: Vector,
    states: Sequence[str],
    regions: Sequence[str],
    ticks: Sequence[str],
    peer_rule: Sequence[str],
    state_counts: Counter[str],
) -> tuple[Vector, Vector, bool]:
    scored = np.full(matrix.shape, np.nan)
    medians = np.full(matrix.shape, np.nan)
    native_failure = False
    state_arr = np.asarray(states)
    region_arr = np.asarray(regions)
    for state, index in _indices(states).items():
        rule = peer_rule[int(index[0])]
        if rule == "state_native":
            block_z, keep = _group_z(matrix[index])
            scored[index] = block_z
            medians[index] = np.median(matrix[index], axis=0)
            if int(np.sum(keep)) < 2:
                native_failure = True
            continue
        if rule != "state_shrunk":
            continue
        region = regions[int(index[0])]
        loo = np.flatnonzero((region_arr == region) & (state_arr != state))
        full = np.flatnonzero(region_arr == region)
        for column in range(matrix.shape[1]):
            state_median, state_mad = _location_scale(matrix[index, column])
            _loo_median, loo_mad = _location_scale(matrix[loo, column]) if len(loo) else (0.0, 0.0)
            _full_median, full_mad = _location_scale(matrix[full, column])
            scale = shrunk_mad(state_mad, state_counts[state], loo_mad, int(loo.shape[0]), full_mad)
            medians[index, column] = state_median
            if scale > 0:
                scored[index, column] = (matrix[index, column] - state_median) / (MAD_SCALE * scale)
    for region, tick in sorted(
        {(region, tick) for region, tick in zip(regions, ticks, strict=True)}
    ):
        index = np.flatnonzero((region_arr == region) & (np.asarray(ticks) == tick))
        _write_group_z(matrix, index, peer_rule, scored, medians, "class_peer")
    for region in sorted(set(regions)):
        index = np.flatnonzero(region_arr == region)
        _write_group_z(matrix, index, peer_rule, scored, medians, "region_peer")
    return scored, medians, native_failure


def _write_group_z(
    matrix: Vector,
    index: Vector,
    peer_rule: Sequence[str],
    scored: Vector,
    medians: Vector,
    rule: str,
) -> None:
    if len(index) == 0:
        return
    block_z, _keep = _group_z(matrix[index])
    median = np.median(matrix[index], axis=0)
    for local, global_index in enumerate(index):
        if peer_rule[int(global_index)] != rule:
            continue
        scored[int(global_index)] = block_z[local]
        medians[int(global_index)] = median


def _location_scale(values: Vector) -> tuple[float, float]:
    if len(values) == 0:
        return 0.0, 0.0
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return median, mad


def _percentile_by_peer(
    matrix: Vector,
    rows: Sequence[ParsedRow],
    states: Sequence[str],
    regions: Sequence[str],
    peer_rule: Sequence[str],
    peer_count: Sequence[int],
) -> tuple[Vector, Vector]:
    flags = np.zeros(matrix.shape[0], dtype=bool)
    applied = np.zeros(matrix.shape[0], dtype=bool)
    for _state_name, index in _indices(states).items():
        if peer_rule[int(index[0])] != "state_native":
            continue
        if peer_count[int(index[0])] < STATE_NATIVE_MIN:
            continue
        _mark_percentile(matrix, index, index, flags, applied)
    ticks = [row.tick_status for row in rows]
    region_arr = np.asarray(regions)
    tick_arr = np.asarray(ticks)
    for region, tick in sorted(set(zip(regions, ticks, strict=True))):
        index = np.flatnonzero((region_arr == region) & (tick_arr == tick))
        writers = np.asarray(
            [int(item) for item in index if peer_rule[int(item)] == "class_peer"],
            dtype=int,
        )
        if len(writers):
            _mark_percentile(matrix, index, writers, flags, applied)
    _mark_fallback_percentile(matrix, regions, peer_rule, flags, applied, "region_peer")
    return flags, applied


def _mark_percentile(
    matrix: Vector,
    fit_index: Vector,
    write_index: Vector,
    flags: Vector,
    applied: Vector,
) -> None:
    if len(fit_index) < STATE_NATIVE_MIN:
        return
    position = {int(global_index): local for local, global_index in enumerate(fit_index)}
    local_flags = np.zeros(len(fit_index), dtype=bool)
    for column in range(matrix.shape[1]):
        local_flags |= percentile_flags(matrix[fit_index, column])
    for global_index in write_index:
        applied[int(global_index)] = True
        if local_flags[position[int(global_index)]]:
            flags[int(global_index)] = True


def _mark_fallback_percentile(
    matrix: Vector,
    regions: Sequence[str],
    peer_rule: Sequence[str],
    flags: Vector,
    applied: Vector,
    rule: str,
) -> None:
    for region in sorted(set(regions)):
        index = np.flatnonzero(np.asarray(regions) == region)
        writers = np.asarray(
            [int(item) for item in index if peer_rule[int(item)] == rule], dtype=int
        )
        if len(writers) == 0:
            continue
        _mark_percentile(matrix, index, writers, flags, applied)


def _surveillance_by_peer(
    rows: Sequence[ParsedRow],
    states: Sequence[str],
    regions: Sequence[str],
    peer_rule: Sequence[str],
) -> tuple[Vector, Vector, list[str]]:
    count = len(rows)
    flags = np.zeros(count, dtype=bool)
    applied = np.zeros(count, dtype=bool)
    names = [""] * count
    coded = _signal_matrix(rows)
    for _state_name, index in _indices(states).items():
        if peer_rule[int(index[0])] != "state_native":
            continue
        _mark_surveillance(coded, index, index, flags, applied, names)
    region_arr = np.asarray(regions)
    tick_arr = np.asarray([row.tick_status for row in rows])
    for region, tick in sorted(
        {(row_region, row.tick_status) for row_region, row in zip(regions, rows, strict=True)}
    ):
        index = np.flatnonzero((region_arr == region) & (tick_arr == tick))
        writers = np.asarray(
            [int(item) for item in index if peer_rule[int(item)] == "class_peer"],
            dtype=int,
        )
        if len(writers):
            _mark_surveillance(coded, index, writers, flags, applied, names)
    for region in sorted(set(regions)):
        index = np.flatnonzero(region_arr == region)
        writers = np.asarray(
            [int(item) for item in index if peer_rule[int(item)] == "region_peer"],
            dtype=int,
        )
        if len(writers):
            _mark_surveillance(coded, index, writers, flags, applied, names)
    return flags, applied, names


def _mark_surveillance(
    coded: Vector,
    fit_index: Vector,
    write_index: Vector,
    flags: Vector,
    applied: Vector,
    names: list[str],
) -> None:
    position = {int(global_index): local for local, global_index in enumerate(fit_index)}
    local_flags = np.zeros(len(fit_index), dtype=bool)
    local_names = [""] * len(fit_index)
    any_applied = False
    for column, signal in enumerate(SIGNAL_NAMES):
        chosen, estimable = surveillance_flags(coded[fit_index, column])
        if not estimable:
            continue
        any_applied = True
        for local, flagged in enumerate(chosen):
            if not flagged:
                continue
            local_flags[local] = True
            local_names[local] = _join_signal(local_names[local], signal)
    if not any_applied:
        return
    for global_index in write_index:
        local = position[int(global_index)]
        applied[int(global_index)] = True
        flags[int(global_index)] = bool(local_flags[local])
        names[int(global_index)] = local_names[local]


def _national_surveillance(rows: Sequence[ParsedRow]) -> Vector:
    coded = _signal_matrix(rows)
    flags = np.zeros(len(rows), dtype=bool)
    for column in range(coded.shape[1]):
        chosen, estimable = surveillance_flags(coded[:, column])
        if estimable:
            flags |= chosen
    return flags


def _signal_matrix(rows: Sequence[ParsedRow]) -> Vector:
    return np.column_stack(
        [
            np.asarray(
                [1.0 if row.human_status == HUMAN_PUBLISHED else 0.0 for row in rows],
                dtype=float,
            ),
            np.asarray(
                [1.0 if row.tick_status == TICK_ESTABLISHED else 0.0 for row in rows],
                dtype=float,
            ),
            np.asarray(
                [1.0 if row.burgdorferi_status == PATHOGEN_PRESENT else 0.0 for row in rows],
                dtype=float,
            ),
        ]
    )


def _join_signal(current: str, signal: str) -> str:
    if not current:
        return signal
    return f"{current}+{signal}"


def _distances(
    matrix: Vector,
    states: Sequence[str],
    regions: Sequence[str],
    peer_rule: Sequence[str],
    ticks: Sequence[str] | None = None,
) -> tuple[Vector, Vector, Vector, int, int]:
    dist = np.full(matrix.shape[0], np.nan)
    flags = np.zeros(matrix.shape[0], dtype=bool)
    applied = np.zeros(matrix.shape[0], dtype=bool)
    failures = 0
    native_groups = 0
    for _state_name, index in _indices(states).items():
        if peer_rule[int(index[0])] != "state_native":
            continue
        native_groups += 1
        if not _fit_distance(matrix, index, index, dist, flags, applied):
            failures += 1
    region_arr = np.asarray(regions)
    if ticks is not None:
        tick_arr = np.asarray(ticks)
        for region, tick in sorted(set(zip(regions, ticks, strict=True))):
            index = np.flatnonzero((region_arr == region) & (tick_arr == tick))
            writers = np.asarray(
                [int(item) for item in index if peer_rule[int(item)] == "class_peer"],
                dtype=int,
            )
            if len(writers):
                _fit_distance(matrix, index, writers, dist, flags, applied)
    for region in sorted(set(regions)):
        index = np.flatnonzero(region_arr == region)
        writers = np.asarray(
            [int(item) for item in index if peer_rule[int(item)] == "region_peer"],
            dtype=int,
        )
        if len(writers):
            _fit_distance(matrix, index, writers, dist, flags, applied)
    return dist, flags, applied, failures, native_groups


def _fit_distance(
    matrix: Vector,
    fit_index: Vector,
    write_index: Vector,
    dist: Vector,
    flags: Vector,
    applied: Vector,
) -> bool:
    block = matrix[fit_index]
    _median, mad = _column_mad(block)
    keep = mad > 0
    if int(np.sum(keep)) < 2:
        return True
    squared, ok = _robust_distances(np.asarray(block[:, keep], dtype=float), seed=PRIMARY_SEED)
    for global_index in write_index:
        applied[int(global_index)] = True
    if not ok:
        return False
    cutoff = CHI2_975[int(np.sum(keep))]
    position = {int(global_index): local for local, global_index in enumerate(fit_index)}
    for global_index in write_index:
        value = float(squared[position[int(global_index)]])
        dist[int(global_index)] = value
        flags[int(global_index)] = value > cutoff
    return True


def _column_mad(block: Vector) -> tuple[Vector, Vector]:
    median = np.median(block, axis=0)
    mad = np.median(np.abs(block - median), axis=0)
    return median, np.asarray(mad)


def _national_distance(matrix: Vector, keep: Vector) -> tuple[Vector, Vector]:
    values = np.full(matrix.shape[0], np.nan)
    flags = np.zeros(matrix.shape[0], dtype=bool)
    if int(np.sum(keep)) < 2:
        return values, flags
    squared, ok = _robust_distances(np.asarray(matrix[:, keep], dtype=float), seed=PRIMARY_SEED)
    if not ok:
        return values, flags
    cutoff = CHI2_975[int(np.sum(keep))]
    return np.asarray(squared, dtype=float), np.asarray(squared > cutoff)


def _forests(
    matrix: Vector,
    states: Sequence[str],
    state_counts: Counter[str],
    flag_state: Vector,
    fips: Vector,
) -> tuple[
    tuple[Vector, Vector, Vector, Vector, Vector, Vector],
    dict[str, _ForestState],
]:
    count = matrix.shape[0]
    applied = np.zeros(count, dtype=bool)
    primary = np.zeros(count, dtype=bool)
    seed_b = np.zeros(count, dtype=bool)
    low = np.zeros(count, dtype=bool)
    high = np.zeros(count, dtype=bool)
    score = np.full(count, np.nan)
    details: dict[str, _ForestState] = {}
    for state, index in _indices(states).items():
        if state_counts[state] < FOREST_MIN:
            continue
        block = matrix[index]
        flags: dict[tuple[int, float], Vector] = {}
        primary_score: Vector = np.zeros(block.shape[0], dtype=float)
        for seed in SEEDS:
            for contamination in CONTAMINATIONS:
                model = IsolationForest(
                    n_estimators=N_ESTIMATORS,
                    contamination=contamination,
                    random_state=seed,
                    max_samples="auto",
                    bootstrap=False,
                    n_jobs=1,
                )
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model.fit(block)
                flags[(seed, contamination)] = np.asarray(model.predict(block) == -1, dtype=bool)
                if seed == PRIMARY_SEED and contamination == PRIMARY_CONTAMINATION:
                    primary_score = -np.asarray(model.decision_function(block), dtype=float)
        applied[index] = True
        both = flags[(PRIMARY_SEED, PRIMARY_CONTAMINATION)]
        other = flags[(SECOND_SEED, PRIMARY_CONTAMINATION)]
        primary[index] = both
        seed_b[index] = other
        low[index] = flags[(PRIMARY_SEED, 0.02)]
        high[index] = flags[(PRIMARY_SEED, 0.10)]
        score[index] = primary_score
        k = int(np.sum(flag_state[index]))
        matched = None
        if k > 0:
            top = _top_mask(primary_score, fips[index], k)
            matched = float(_jaccard(top, flag_state[index]))
        details[state] = _ForestState(
            seed_jaccard=float(_jaccard(both, other)),
            primary_flags=int(np.sum(both)),
            seed_b_flags=int(np.sum(other)),
            matched_jaccard=matched,
        )
    return (applied, primary, seed_b, low, high, score), details


def _lofs(
    matrix: Vector,
    states: Sequence[str],
    state_counts: Counter[str],
    flag_state: Vector,
    fips: Vector,
) -> tuple[tuple[Vector, Vector, Vector, Vector, Vector], dict[str, _LofState]]:
    count = matrix.shape[0]
    applied = np.zeros(count, dtype=bool)
    primary = np.zeros(count, dtype=bool)
    low = np.zeros(count, dtype=bool)
    high = np.zeros(count, dtype=bool)
    score = np.full(count, np.nan)
    details: dict[str, _LofState] = {}
    for state, index in _indices(states).items():
        if state_counts[state] < FOREST_MIN:
            continue
        block = matrix[index]
        stored_score: Vector = np.zeros(block.shape[0], dtype=float)
        stored_flag: Vector = np.zeros(block.shape[0], dtype=bool)
        c02: Vector = np.zeros(block.shape[0], dtype=bool)
        c10: Vector = np.zeros(block.shape[0], dtype=bool)
        for contamination in CONTAMINATIONS:
            model = LocalOutlierFactor(
                n_neighbors=LOF_NEIGHBORS,
                contamination=contamination,
                novelty=False,
                n_jobs=1,
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                chosen = np.asarray(model.fit_predict(block) == -1, dtype=bool)
            if contamination == PRIMARY_CONTAMINATION:
                stored_flag = chosen
                stored_score = -np.asarray(model.negative_outlier_factor_, dtype=float)
            elif contamination == 0.02:
                c02 = chosen
            else:
                c10 = chosen
        applied[index] = True
        primary[index] = stored_flag
        low[index] = c02
        high[index] = c10
        score[index] = stored_score
        k_low = int(np.sum(c02))
        nested = None
        if k_low > 0:
            top = _top_mask(stored_score, fips[index], k_low)
            nested = float(_jaccard(top, c02))
        k = int(np.sum(flag_state[index]))
        matched = None
        if k > 0:
            matched = float(_jaccard(_top_mask(stored_score, fips[index], k), flag_state[index]))
        details[state] = _LofState(
            nested_jaccard=nested,
            matched_jaccard=matched,
            primary_flags=int(np.sum(stored_flag)),
        )
    return (applied, primary, low, high, score), details


def _assemble(
    rows: Sequence[ParsedRow],
    regions: Sequence[str],
    peer_rule: Sequence[str],
    peer_label: Sequence[str],
    peer_count: Sequence[int],
    state_counts: Counter[str],
    matrix: Vector,
    medians: Vector,
    z_state: Vector,
    national_z: Vector,
    max_state: Vector,
    max_national: Vector,
    rank_state: Vector,
    rank_national: Vector,
    flag_state: Vector,
    flag_national: Vector,
    percentile: Vector,
    percentile_on: Vector,
    distances: Vector,
    distance_flags: Vector,
    distance_on: Vector,
    national_distance: Vector,
    national_distance_flag: Vector,
    forest: tuple[tuple[Vector, ...], dict[str, _ForestState]],
    lof: tuple[tuple[Vector, ...], dict[str, _LofState]],
    surveillance: Vector,
    surveillance_on: Vector,
    surveillance_name: Sequence[str],
    national_surveillance: Vector,
) -> tuple[ScoredCounty, ...]:
    forest_arrays = forest[0]
    lof_arrays = lof[0]
    scored: list[ScoredCounty] = []
    for index, row in enumerate(rows):
        z_map = _finite_map(z_state[index])
        national_map = _finite_map(national_z[index])
        dominant = "not_estimable" if not z_map else dominant_label(z_map)
        population = float(row.population or 0.0)
        svi = float(matrix[index, 1])
        uninsured = float(matrix[index, 2])
        rucc = int(row.rucc or 0)
        flagged = bool(flag_state[index])
        scored.append(
            ScoredCounty(
                fips=row.fips,
                county_name=row.county_name,
                state=row.state,
                region=regions[index],
                peer_rule=peer_rule[index],
                peer_label=peer_label[index],
                peer_n=peer_count[index],
                state_n=state_counts[row.state],
                population=population,
                log_population=float(matrix[index, 0]),
                svi_percentile=svi,
                uninsured_percentile=uninsured,
                rucc=rucc,
                human_status=row.human_status,
                tick_status=row.tick_status,
                burgdorferi_status=row.burgdorferi_status,
                z_state=tuple(z_map.items()),
                z_national=tuple(national_map.items()),
                max_abs_z_state=float(max_state[index]),
                max_abs_z_national=float(max_national[index]),
                rank_state=int(rank_state[index]),
                rank_national=int(rank_national[index]),
                flag_z_state=flagged,
                flag_z_national=bool(flag_national[index]),
                flag_percentile=bool(percentile[index]),
                percentile_applied=bool(percentile_on[index]),
                flag_mcd=bool(distance_flags[index]),
                mcd_applied=bool(distance_on[index]),
                flag_mcd_national=bool(national_distance_flag[index]),
                mahalanobis_peer=_optional_number(distances[index]),
                mahalanobis_national=_optional_number(national_distance[index]),
                flag_if_primary=bool(forest_arrays[1][index]),
                flag_if_seed_b=bool(forest_arrays[2][index]),
                flag_if_c02=bool(forest_arrays[3][index]),
                flag_if_c10=bool(forest_arrays[4][index]),
                forest_applied=bool(forest_arrays[0][index]),
                if_score_primary=_optional_number(forest_arrays[5][index]),
                flag_lof=bool(lof_arrays[1][index]),
                flag_lof_c02=bool(lof_arrays[2][index]),
                flag_lof_c10=bool(lof_arrays[3][index]),
                lof_applied=bool(lof_arrays[0][index]),
                lof_score=_optional_number(lof_arrays[4][index]),
                flag_surveillance=bool(surveillance[index]),
                surveillance_applied=bool(surveillance_on[index]),
                surveillance_signal=surveillance_name[index],
                flag_surveillance_national=bool(national_surveillance[index]),
                dominant_feature=dominant,
                reason=_reason(
                    flagged,
                    dominant,
                    z_state[index],
                    medians[index],
                    matrix[index],
                    peer_label[index],
                    peer_count[index],
                    population,
                ),
                metro=rucc <= METRO_MAX_RUCC,
            )
        )
    return tuple(scored)


def _reason(
    flagged: bool,
    dominant: str,
    z_row: Vector,
    median_row: Vector,
    values: Vector,
    peer_label: str,
    peer_n: int,
    population: float,
) -> str:
    if not flagged:
        return ""
    if dominant == "joint":
        return (
            "no single continuous feature reaches 2.5 robust z units from the "
            f"{peer_label} median (n={peer_n})."
        )
    if dominant in {"tie", "not_estimable"}:
        return f"no single continuous feature leads the {peer_label} comparison (n={peer_n})."
    column = FEATURE_NAMES.index(dominant)
    z_value = float(z_row[column])
    direction = "above" if z_value > 0 else "below"
    return (
        f"{FEATURE_LABELS[dominant]} is {direction} the {peer_label} median "
        f"({_show_value(dominant, float(values[column]), population)} versus "
        f"{_show_median(dominant, float(median_row[column]))}, "
        f"robust z {z_value:.2f}, n={peer_n})."
    )


def _show_value(feature: str, value: float, population: float) -> str:
    if feature == "log_population":
        return f"population {population:,.0f}, log {value:.2f}"
    if feature == "rucc_2023":
        return str(int(round(value)))
    return f"{value:.3f}"


def _show_median(feature: str, value: float) -> str:
    if feature == "log_population":
        return f"median log {value:.2f}"
    if feature == "rucc_2023":
        return f"median {value:.1f}"
    return f"median {value:.3f}"


def _finite_map(row: Vector) -> dict[str, float]:
    return {
        name: float(row[column])
        for column, name in enumerate(FEATURE_NAMES)
        if math.isfinite(float(row[column]))
    }


def _optional_number(value: float) -> float | None:
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _max_abs(matrix: Vector) -> Vector:
    finite = np.isfinite(matrix)
    absolute = np.where(finite, np.abs(matrix), np.nan)
    reduced = np.full(matrix.shape[0], np.nan)
    present = np.any(finite, axis=1)
    if np.any(present):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reduced[present] = np.nanmax(absolute[present], axis=1)
    return reduced


def _ranks(scores: Vector, fips: Vector) -> Vector:
    key = np.nan_to_num(-scores, nan=np.inf)
    order = np.lexsort((fips, key))
    rank = np.empty(len(scores), dtype=int)
    rank[order] = np.arange(1, len(scores) + 1)
    return rank


@dataclass(frozen=True)
class _Summary:
    flag_z_state: int
    flag_z_national: int
    jaccard_national: float
    median_abs_rank_shift: float | None
    spearman: float | None
    small_share: float | None
    small_flag_n: int
    fallback_flag_n: int
    urban_gap: float | None
    urban_comparable: bool
    cohort_metro_n: int
    flag_metro_n: int
    mcd_failure_n: int
    mcd_native_n: int
    mcd_failure_share: float | None
    forest_eligible_states: int
    forest_stable_states: int
    forest_defensible: bool
    lof_defensible: bool
    seed_jaccards: tuple[float, ...]
    flag_rate_interval: tuple[float, float] | None
    review: tuple[ScoredCounty, ...]
    state_only: tuple[ScoredCounty, ...]
    national_only: tuple[ScoredCounty, ...]
    surveillance_review: tuple[ScoredCounty, ...]
    band_state_counts: dict[str, int]
    band_county_counts: dict[str, int]
    spread: dict[str, dict[str, float | None]]
    agreement: dict[str, int | None]
    seed_split: dict[str, int | None]
    seed_bins: dict[str, int | None]


def _summarize(
    counties: tuple[ScoredCounty, ...],
    flag_state: Vector,
    flag_national: Vector,
    states: Sequence[str],
    state_counts: Counter[str],
    mcd_failures: int,
    native_groups: int,
    forest: dict[str, _ForestState],
    lof: dict[str, _LofState],
) -> _Summary:
    state_flags = int(np.sum(flag_state))
    national_flags = int(np.sum(flag_national))
    union = flag_state | flag_national
    small_n = sum(1 for row in counties if row.flag_z_state and row.state_n < STATE_NATIVE_MIN)
    fallback_n = sum(1 for row in counties if row.flag_z_state and row.state_n < SHRINK_MIN)
    metro_flags = sum(1 for row in counties if row.flag_z_state and row.metro)
    cohort_metro = sum(1 for row in counties if row.metro)
    urban_comparable = state_flags >= SMALL_CELL_MINIMUM and _publishable_pair(
        metro_flags, state_flags - metro_flags
    )
    urban_gap: float | None = None
    if urban_comparable and state_flags:
        urban_gap = metro_flags / state_flags - cohort_metro / len(counties)
    stable, forest_ok = _forest_bar(forest)
    band_states, band_counties = _bands(state_counts)
    agreement = {
        "both": int(np.sum(flag_state & flag_national)),
        "state_only": int(np.sum(flag_state & ~flag_national)),
        "national_only": int(np.sum(~flag_state & flag_national)),
        "neither": int(np.sum(~flag_state & ~flag_national)),
    }
    return _Summary(
        flag_z_state=state_flags,
        flag_z_national=national_flags,
        jaccard_national=float(_jaccard(flag_state, flag_national)),
        median_abs_rank_shift=_median_shift(counties, union),
        spearman=_spearman(
            np.asarray([row.max_abs_z_state for row in counties], dtype=float),
            np.asarray([row.max_abs_z_national for row in counties], dtype=float),
        ),
        small_share=None if state_flags == 0 else small_n / state_flags,
        small_flag_n=small_n,
        fallback_flag_n=fallback_n,
        urban_gap=urban_gap,
        urban_comparable=urban_comparable,
        cohort_metro_n=cohort_metro,
        flag_metro_n=metro_flags,
        mcd_failure_n=mcd_failures,
        mcd_native_n=native_groups,
        mcd_failure_share=None if native_groups == 0 else mcd_failures / native_groups,
        forest_eligible_states=len(forest),
        forest_stable_states=stable,
        forest_defensible=forest_ok,
        lof_defensible=_lof_bar(lof),
        seed_jaccards=tuple(row.seed_jaccard for row in forest.values()),
        flag_rate_interval=_bootstrap(
            np.asarray(states, dtype=object),
            _rate_statistic(flag_state),
            PRIMARY_SEED,
        ),
        review=_review(counties, "flag_z_state", "max_abs_z_state"),
        state_only=_disagreement(counties, state_side=True),
        national_only=_disagreement(counties, state_side=False),
        surveillance_review=_review(counties, "flag_surveillance", "fips"),
        band_state_counts=band_states,
        band_county_counts=band_counties,
        spread=_spread(counties, state_counts),
        agreement=_publish_composition(agreement),
        seed_split=_seed_split(forest),
        seed_bins=_seed_bins(forest),
    )


def _rate_statistic(flags: Vector) -> object:
    def statistic(index: Vector) -> float | None:
        chosen = flags[index]
        if int(np.sum(chosen)) == 0:
            return None
        return float(np.mean(chosen))

    return statistic


def _forest_bar(details: Mapping[str, _ForestState]) -> tuple[int, bool]:
    stable = [
        row
        for row in details.values()
        if row.primary_flags >= 1
        and row.seed_b_flags >= 1
        and row.seed_jaccard >= SEED_STABLE_JACCARD
    ]
    if len(stable) < DETECTOR_MIN_STATES:
        return len(stable), False
    distinct = sum(
        1
        for row in stable
        if row.matched_jaccard is not None and row.matched_jaccard < MATCHED_DISTINCT
    )
    return len(stable), distinct * 2 >= len(stable)


def _lof_bar(details: Mapping[str, _LofState]) -> bool:
    stable = [
        row
        for row in details.values()
        if row.primary_flags >= 1
        and row.nested_jaccard is not None
        and row.nested_jaccard >= SEED_STABLE_JACCARD
    ]
    if len(stable) < DETECTOR_MIN_STATES:
        return False
    distinct = sum(
        1
        for row in stable
        if row.matched_jaccard is not None and row.matched_jaccard < MATCHED_DISTINCT
    )
    return distinct * 2 >= len(stable)


def _bands(state_counts: Counter[str]) -> tuple[dict[str, int], dict[str, int]]:
    states: Counter[str] = Counter()
    counties: Counter[str] = Counter()
    for _code, count in state_counts.items():
        band = _size_band(count)
        states[band] += 1
        counties[band] += count
    return dict(states), dict(counties)


def _size_band(count: int) -> str:
    if count >= STATE_NATIVE_MIN:
        return "state_native"
    if count >= SHRINK_MIN:
        return "shrunk"
    return "fallback"


def _spread(
    counties: Sequence[ScoredCounty],
    state_counts: Counter[str],
) -> dict[str, dict[str, float | None]]:
    grouped: dict[str, list[ScoredCounty]] = {}
    for row in counties:
        grouped.setdefault(row.state, []).append(row)
    collected: dict[str, dict[str, list[float]]] = {
        band: {"log_population": [], "svi_percentile": []} for band in SIZE_BANDS
    }
    for state, rows in grouped.items():
        band = _size_band(state_counts[state])
        collected[band]["log_population"].append(
            _location_scale(np.asarray([row.log_population for row in rows]))[1]
        )
        collected[band]["svi_percentile"].append(
            _location_scale(np.asarray([row.svi_percentile for row in rows]))[1]
        )
    published: dict[str, dict[str, float | None]] = {}
    for band, features in collected.items():
        show = len(features["log_population"]) >= SMALL_CELL_MINIMUM
        published[band] = {
            name: float(np.median(values)) if show and values else None
            for name, values in features.items()
        }
    return published


def _median_shift(counties: Sequence[ScoredCounty], union: Vector) -> float | None:
    shifts = [
        abs(row.rank_national - row.rank_state)
        for row, keep in zip(counties, union, strict=True)
        if keep
    ]
    if not shifts:
        return None
    return float(np.median(np.asarray(shifts, dtype=float)))


def _spearman(left: Vector, right: Vector) -> float | None:
    if len(left) < 3:
        return None
    left_rank = _average_percentile(left) * len(left)
    right_rank = _average_percentile(right) * len(right)
    if float(np.std(left_rank)) == 0 or float(np.std(right_rank)) == 0:
        return None
    return float(np.corrcoef(left_rank, right_rank)[0, 1])


def _publishable_pair(left: int, right: int) -> bool:
    return (left == 0 or left >= SMALL_CELL_MINIMUM) and (right == 0 or right >= SMALL_CELL_MINIMUM)


def _review(
    counties: Sequence[ScoredCounty], flag_name: str, score_name: str
) -> tuple[ScoredCounty, ...]:
    chosen = [row for row in counties if getattr(row, flag_name)]
    if score_name == "fips":
        chosen.sort(key=lambda row: row.fips)
    else:
        chosen.sort(key=lambda row: (-float(getattr(row, score_name)), row.fips))
    if len(chosen) <= 40:
        return tuple(chosen)
    return tuple(chosen[:25])


def _disagreement(
    counties: Sequence[ScoredCounty], *, state_side: bool
) -> tuple[ScoredCounty, ...]:
    if state_side:
        chosen = [row for row in counties if row.flag_z_state and not row.flag_z_national]
        chosen.sort(key=lambda row: (-row.max_abs_z_state, row.fips))
    else:
        chosen = [row for row in counties if row.flag_z_national and not row.flag_z_state]
        chosen.sort(key=lambda row: (-row.max_abs_z_national, row.fips))
    return tuple(chosen[:15])


def _seed_split(details: Mapping[str, _ForestState]) -> dict[str, int | None]:
    below = sum(1 for row in details.values() if row.seed_jaccard < SEED_STABLE_JACCARD)
    above = len(details) - below
    return _publish_composition({"below_0_90": below, "at_least_0_90": above})


def _seed_bins(details: Mapping[str, _ForestState]) -> dict[str, int | None]:
    counts: Counter[str] = Counter()
    for row in details.values():
        for start, end in zip(SEED_EDGES, SEED_EDGES[1:], strict=True):
            if start <= row.seed_jaccard < end:
                counts[f"{start:.1f}"] += 1
                break
    return _publish_composition(dict(counts))


def _experiments(
    run_id: str,
    flag_rate_interval: tuple[float, float] | None,
    counties: Sequence[ScoredCounty],
) -> tuple[ExperimentRow, ...]:
    n_fit = len(counties)
    families = (
        (
            "z-state",
            "robust_z_state",
            "State-relative median and MAD on continuous features.",
            "flag_z_state",
        ),
        (
            "z-national",
            "robust_z_national",
            "National median and MAD on the same features.",
            "flag_z_national",
        ),
        (
            "percentile",
            "percentile_peer",
            "Peer percentile tails on continuous features.",
            "flag_percentile",
        ),
        ("distance", "robust_covariance", "Peer robust-covariance distance.", "flag_mcd"),
        (
            "forest",
            "isolation_forest",
            "Isolation forest only in states with at least 80 counties.",
            "flag_if_primary",
        ),
        (
            "lof",
            "local_outlier_factor",
            "Local outlier factor only in those same states.",
            "flag_lof",
        ),
    )
    rows: list[ExperimentRow] = []
    for suffix, family, hypothesis, flag_name in families:
        count = sum(1 for row in counties if getattr(row, flag_name))
        metrics: list[ModelMetricRow] = []
        if count == 0 or count >= SMALL_CELL_MINIMUM:
            metrics.append(
                ModelMetricRow(
                    split_name="state_relative",
                    metric_name="flag_rate",
                    metric_value=0.0 if n_fit == 0 else count / n_fit,
                    ci_low=None,
                    ci_high=None,
                    n=n_fit,
                )
            )
        if (
            family == "robust_z_state"
            and flag_rate_interval is not None
            and count >= SMALL_CELL_MINIMUM
            and metrics
        ):
            metrics[0] = ModelMetricRow(
                split_name="state_relative",
                metric_name="flag_rate",
                metric_value=count / n_fit,
                ci_low=flag_rate_interval[0],
                ci_high=flag_rate_interval[1],
                n=n_fit,
            )
        rows.append(
            ExperimentRow(
                experiment_id=f"{run_id}-{suffix}",
                model_family=family,
                hypothesis=hypothesis,
                config={"spec": SPEC_ID, "sklearn": sklearn_version(), "seed": PRIMARY_SEED},
                split_definition={"split": "state_relative"},
                status="succeeded",
                metrics=tuple(metrics),
            )
        )
    return tuple(rows)


def _average_percentile(values: Vector) -> Vector:
    count = len(values)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(count, dtype=float)
    start = 0
    while start < count:
        end = start + 1
        while end < count and values[order[end]] == values[order[start]]:
            end += 1
        average = (start + 1 + end) / 2.0
        ranks[order[start:end]] = average
        start = end
    return ranks / count


def _indices(labels: Sequence[str]) -> dict[str, Vector]:
    grouped: dict[str, list[int]] = {}
    for index, label in enumerate(labels):
        grouped.setdefault(label, []).append(index)
    return {key: np.asarray(value, dtype=int) for key, value in grouped.items()}


def _lookup(pairs: tuple[tuple[str, float], ...], name: str) -> float | None:
    for key, value in pairs:
        if key == name:
            return value
    return None


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateAnomalyError("a gate field is missing")
    return value.strip()


def _int_field(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StateAnomalyError("a gate count is missing")
    return value
