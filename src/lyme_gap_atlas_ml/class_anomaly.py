"""Within-class anomaly screen for issue 122.

The functions here do not open Snowflake. County rows stay in the returned
objects. Aggregate lab records suppress counts from 1 to 10. The results
write-up is allowed to name counties; chart records are not.
"""

from __future__ import annotations

import math
import warnings
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from importlib.metadata import version
from typing import Any

import numpy as np
from sklearn.covariance import MinCovDet  # type: ignore[import-untyped]
from sklearn.ensemble import IsolationForest  # type: ignore[import-untyped]

from lyme_gap_atlas_ml.coverage_audit import (
    CENSUS_REGIONS,
    PINNED_BUNDLE_SHA256,
    PINNED_RELEASE_ID,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import (
    FindingRecord,
    QueryRecord,
    prepare_query,
)
from lyme_gap_atlas_ml.snowflake.eda_writer import SMALL_CELL_MINIMUM, EdaMetric

Vector = np.ndarray[Any, Any]

SPEC_ID = "122-established-class-anomaly/v1.1"
EXPECTED_CLASS_N = 1404
EXPECTED_DOUBLE_GAP_N = 228
EXPECTED_GAP_810_N = 810
PRIMARY_SEED = 1222026
SECOND_SEED = 1222027
SEEDS = (PRIMARY_SEED, SECOND_SEED)
CONTAMINATIONS = (0.02, 0.05, 0.10)
PRIMARY_CONTAMINATION = 0.05
Z_FLAG = 3.5
Z_JOINT = 2.5
MAD_SCALE = 1.482602218505602
SUPPORT_FRACTION = 0.8
N_ESTIMATORS = 200
CHI2_975 = {
    1: 5.023886187314888,
    2: 7.377758908227871,
    3: 9.348403604496148,
    4: 11.143286781877796,
}
BOOTSTRAP_DRAWS = 400
BOOTSTRAP_MIN_DRAWS = 100
REVIEW_ALL_MAX = 40
REVIEW_TOP = 25
BASELINE_ONLY_TOP = 15
MIN_FIT_ROWS = 40
HUMAN_NO_RECORD = "no_county_linked_record"
PATHOGEN_PRESENT = "Present"
TICK_ESTABLISHED = "Established"
FEATURE_ORDER = (
    "log_population",
    "svi_percentile",
    "uninsured_percentile",
    "rucc_2023",
)
POPULATION_EDGES = (0, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 20_000_000)
LOG_POPULATION_EDGES = tuple(
    math.log(edge)
    for edge in (1_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 20_000_000)
)
PERCENTILE_EDGES = tuple(index / 10 for index in range(11))
QUERY_NAMES = ("release_identity", "class_gate", "class_rows")
REGION_ORDER = ("Northeast", "Midwest", "South", "West")
_QUERY_MARKER_PREFIX = "-- @@ "
_FOREST_ADDS_JACCARD = 0.80
_SEED_STABLE_JACCARD = 0.90
_DRIVER_FOLLOWUP_SHARE = 0.60


class ClassAnomalyError(ValueError):
    """The class screen stopped on a predeclared gate."""


@dataclass(frozen=True)
class ParsedRow:
    fips: str
    county_name: str
    state: str
    population: float | None
    svi_percentile: float | None
    uninsured_percentile: float | None
    rucc: float | None
    human_status: str
    burgdorferi_status: str
    tick_status: str


@dataclass(frozen=True)
class ExcludedRow:
    fips: str
    county_name: str
    state: str
    reason: str


@dataclass(frozen=True)
class ScoredCounty:
    fips: str
    county_name: str
    state: str
    region: str
    population: float
    log_population: float
    svi_percentile: float
    uninsured_percentile: float
    rucc: int
    human_status: str
    burgdorferi_status: str
    tick_status: str
    robust_z: tuple[tuple[str, float], ...]
    robust_z_max_abs: float
    mahalanobis_squared: float | None
    if_score_primary: float
    if_score_seed_b: float
    flag_robust_z: bool
    flag_mahalanobis: bool
    flag_if_primary: bool
    flag_if_seed_b: bool
    flag_if_c02: bool
    flag_if_c10: bool
    dominant_feature: str
    in_double_gap: bool
    in_gap_810: bool

    def z_map(self) -> dict[str, float]:
        return dict(self.robust_z)


@dataclass(frozen=True)
class GateDecision:
    ok: bool
    reasons: tuple[str, ...]
    release_id: str
    bundle_sha256: str
    schema_version: str
    methodology_version: str
    scope: str
    class_n: int
    double_gap_n: int
    gap_810_n: int
    double_gap_reproduced: bool


@dataclass(frozen=True)
class ChartBin:
    label: str
    count: int | None


@dataclass(frozen=True)
class RegionScore:
    region: str
    n: int | None
    p25: float | None
    p50: float | None
    p75: float | None


@dataclass(frozen=True)
class FlagRateBar:
    label: str
    method: str
    seed: int | None
    contamination: float | None
    count: int | None
    rate: float | None


@dataclass(frozen=True)
class DriverBar:
    method: str
    feature: str
    count: int | None
    share: float | None


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
class FitResult:
    n_class: int
    n_fit: int
    exclusions: tuple[ExcludedRow, ...]
    features_kept: tuple[str, ...]
    features_dropped: tuple[str, ...]
    scaled_columns: tuple[str, ...]
    double_gap_n: int
    gap_810_n: int
    double_gap_reproduced: bool
    mcd_ok: bool
    mcd_cutoff: float | None
    flag_counts: dict[str, int]
    seed_jaccard: float
    matched_jaccard_robust_z: float
    matched_jaccard_mcd: float
    forest_adds: bool
    driver_counts: dict[str, dict[str, int]]
    overlap_primary_228: int
    overlap_primary_810: int
    robust_z_in_228: int
    mcd_in_228: int
    flag_rate_interval: tuple[float, float] | None
    overlap_interval: tuple[float, float] | None
    region_scores: tuple[RegionScore, ...]
    population_bins: tuple[ChartBin, ...]
    log_bins: tuple[ChartBin, ...]
    svi_bins: tuple[ChartBin, ...]
    uninsured_bins: tuple[ChartBin, ...]
    rucc_bins: tuple[ChartBin, ...]
    flag_rates: tuple[FlagRateBar, ...]
    driver_bars: tuple[DriverBar, ...]
    feature_medians: dict[str, float]
    population_median: float
    disposition: str
    review: tuple[ScoredCounty, ...]
    baseline_only_z: tuple[ScoredCounty, ...]
    baseline_only_mcd: tuple[ScoredCounty, ...]
    counties: tuple[ScoredCounty, ...] = field(repr=False)
    experiments: tuple[ExperimentRow, ...] = field(repr=False)

    def __repr__(self) -> str:
        return (
            "FitResult("
            f"n_class={self.n_class}, n_fit={self.n_fit}, "
            f"disposition={self.disposition}, flags={self.flag_counts})"
        )


def load_class_queries(text: str) -> dict[str, str]:
    """Split the validation file on `-- @@ name` markers and reject unsafe SQL."""
    found: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith(_QUERY_MARKER_PREFIX):
            current = line[len(_QUERY_MARKER_PREFIX) :].strip()
            if current in found:
                raise ClassAnomalyError("duplicate query name")
            found[current] = []
            continue
        if current is not None and not line.startswith("--"):
            found[current].append(line)
    queries = {name: "\n".join(lines).strip() for name, lines in found.items()}
    if tuple(queries) != QUERY_NAMES:
        raise ClassAnomalyError("query file does not match the registered names")
    for sql in queries.values():
        prepare_query(QueryRecord(sql_text=sql, rows_returned=1, elapsed_ms=0))
    return queries


def evaluate_gate(release: Mapping[str, object], gate: Mapping[str, object]) -> GateDecision:
    """Apply the predeclared release and class-size gates. Does not fit a model."""
    release_id = _text(release.get("RELEASE_ID"))
    bundle = _text(release.get("BUNDLE_SHA256")).lower()
    schema_version = _text(release.get("SCHEMA_VERSION"))
    methodology = _text(release.get("METHODOLOGY_VERSION"))
    scope = _text(release.get("SCOPE"))
    class_n = _int(gate.get("CLASS_N"))
    fips_n = _int(gate.get("FIPS_N"))
    pattern_n = _int(gate.get("FIPS_PATTERN_N"))
    release_n = _int(gate.get("RELEASE_N"))
    release_min = _text(gate.get("RELEASE_MIN"))
    release_max = _text(gate.get("RELEASE_MAX"))
    double_gap_n = _int(gate.get("DOUBLE_GAP_N"))
    gap_810_n = _int(gate.get("GAP_810_N"))
    reasons: list[str] = []
    if release_id != PINNED_RELEASE_ID or bundle != PINNED_BUNDLE_SHA256:
        reasons.append("release pin mismatch")
    if release_n != 1 or release_min != PINNED_RELEASE_ID or release_max != PINNED_RELEASE_ID:
        reasons.append("atlas release is not a single pinned release")
    if class_n != EXPECTED_CLASS_N or fips_n != class_n or pattern_n != class_n:
        reasons.append("established class is not the predeclared county count")
    return GateDecision(
        ok=not reasons,
        reasons=tuple(reasons),
        release_id=release_id,
        bundle_sha256=bundle,
        schema_version=schema_version,
        methodology_version=methodology,
        scope=scope,
        class_n=class_n,
        double_gap_n=double_gap_n,
        gap_810_n=gap_810_n,
        double_gap_reproduced=double_gap_n == EXPECTED_DOUBLE_GAP_N,
    )


def fit_class(
    raw_rows: Sequence[Mapping[str, object]],
    *,
    enforce_class_n: int | None = None,
    reference_double_gap: int | None = EXPECTED_DOUBLE_GAP_N,
    run_id: str = "122-local",
) -> FitResult:
    """Fit the frozen baselines and forests. `run_id` is copied onto experiment ids."""
    parsed = tuple(sorted((parse_row(row) for row in raw_rows), key=lambda item: item.fips))
    _reject_identity_problems(parsed)
    if enforce_class_n is not None and len(parsed) != enforce_class_n:
        raise ClassAnomalyError("established class size is not the predeclared count")
    exclusions = tuple(
        ExcludedRow(row.fips, row.county_name, row.state, reason)
        for row in parsed
        if (reason := exclusion_reason(row)) is not None
    )
    excluded_ids = {row.fips for row in exclusions}
    kept = tuple(row for row in parsed if row.fips not in excluded_ids)
    if len(kept) < MIN_FIT_ROWS:
        raise ClassAnomalyError("too few complete class rows to fit the predeclared models")
    scaled_columns, matrix, feature_names, dropped = _design_matrix(parsed, kept)
    if len(feature_names) < 2:
        raise ClassAnomalyError("fewer than two varying features remain")
    z_matrix = _robust_z_matrix(matrix)
    feature_medians = {
        name: float(np.median(matrix[:, index])) for index, name in enumerate(feature_names)
    }
    z_flags = np.max(np.abs(z_matrix), axis=1) > Z_FLAG
    cutoff = CHI2_975[matrix.shape[1]]
    squared, mcd_ok = _robust_distances(matrix)
    mcd_flags = np.zeros(len(kept), dtype=bool) if not mcd_ok else squared > cutoff
    forest_flags, primary_scores, seed_b_scores = _forests(matrix)
    counties = _score_rows(
        kept,
        feature_names,
        scaled_columns,
        z_matrix,
        None if not mcd_ok else squared,
        primary_scores,
        seed_b_scores,
        z_flags,
        mcd_flags,
        forest_flags,
    )
    double_gap_n = sum(
        row.human_status == HUMAN_NO_RECORD and row.burgdorferi_status == PATHOGEN_PRESENT
        for row in parsed
    )
    gap_810_n = sum(row.human_status == HUMAN_NO_RECORD for row in parsed)
    reproduced = reference_double_gap is None or double_gap_n == reference_double_gap
    flag_counts = _flag_counts(counties)
    flag_counts["if_b_c02"] = int(forest_flags[(SECOND_SEED, 0.02)].sum())
    flag_counts["if_b_c10"] = int(forest_flags[(SECOND_SEED, 0.10)].sum())
    primary = _mask(counties, "flag_if_primary")
    seed_b = _mask(counties, "flag_if_seed_b")
    robust = _mask(counties, "flag_robust_z")
    mcd = _mask(counties, "flag_mahalanobis")
    scores = np.array([row.if_score_primary for row in counties], dtype=float)
    fips = np.array([row.fips for row in counties])
    seed_jaccard = _jaccard(primary, seed_b)
    matched_z = _jaccard(_top_mask(scores, fips, int(robust.sum())), robust)
    matched_mcd = _jaccard(_top_mask(scores, fips, int(mcd.sum())), mcd) if mcd_ok else 0.0
    forest_adds = (
        mcd_ok
        and seed_jaccard >= _SEED_STABLE_JACCARD
        and matched_z < _FOREST_ADDS_JACCARD
        and matched_mcd < _FOREST_ADDS_JACCARD
    )
    driver_counts = {
        "robust_z": _drivers(counties, "flag_robust_z"),
        "mahalanobis": _drivers(counties, "flag_mahalanobis"),
        "if_primary": _drivers(counties, "flag_if_primary"),
    }
    states = np.array([row.state for row in counties])
    in_228 = np.array([row.in_double_gap for row in counties])
    rate_interval = _bootstrap_rate(states, primary, PRIMARY_SEED)
    overlap_interval = _bootstrap_share(states, primary, in_228, PRIMARY_SEED)
    population = np.array([row.population for row in counties], dtype=float)
    charts = _charts(counties, feature_names, flag_counts, driver_counts, len(counties))
    max_driver = _max_share(driver_counts["if_primary"])
    disposition = decide_disposition(
        exclusions=len(exclusions),
        double_gap_reproduced=reproduced,
        mcd_ok=mcd_ok,
        seed_jaccard=seed_jaccard,
        forest_adds=forest_adds,
        max_driver_share=max_driver,
    )
    review = _review(counties)
    return FitResult(
        n_class=len(parsed),
        n_fit=len(counties),
        exclusions=exclusions,
        features_kept=feature_names,
        features_dropped=dropped,
        scaled_columns=scaled_columns,
        double_gap_n=double_gap_n,
        gap_810_n=gap_810_n,
        double_gap_reproduced=reproduced,
        mcd_ok=mcd_ok,
        mcd_cutoff=cutoff if mcd_ok else None,
        flag_counts=flag_counts,
        seed_jaccard=seed_jaccard,
        matched_jaccard_robust_z=matched_z,
        matched_jaccard_mcd=matched_mcd,
        forest_adds=forest_adds,
        driver_counts=driver_counts,
        overlap_primary_228=sum(row.flag_if_primary and row.in_double_gap for row in counties),
        overlap_primary_810=sum(row.flag_if_primary and row.in_gap_810 for row in counties),
        robust_z_in_228=sum(row.flag_robust_z and row.in_double_gap for row in counties),
        mcd_in_228=sum(row.flag_mahalanobis and row.in_double_gap for row in counties),
        flag_rate_interval=rate_interval,
        overlap_interval=overlap_interval,
        region_scores=charts[0],
        population_bins=charts[1],
        log_bins=charts[2],
        svi_bins=charts[3],
        uninsured_bins=charts[4],
        rucc_bins=charts[5],
        flag_rates=charts[6],
        driver_bars=charts[7],
        feature_medians=feature_medians,
        population_median=float(np.median(population)),
        disposition=disposition,
        review=review,
        baseline_only_z=_baseline_only(counties, "flag_robust_z", "robust_z_max_abs"),
        baseline_only_mcd=_baseline_only(counties, "flag_mahalanobis", "mahalanobis_squared"),
        counties=counties,
        experiments=_experiments(
            run_id,
            feature_names,
            flag_counts,
            len(counties),
            seed_jaccard,
            matched_z,
            matched_mcd,
            mcd_ok,
            cutoff if mcd_ok else None,
            rate_interval,
            overlap_interval,
            sum(row.flag_if_primary and row.in_double_gap for row in counties),
            sum(row.flag_if_primary and row.in_gap_810 for row in counties),
        ),
    )


def decide_disposition(
    *,
    exclusions: int,
    double_gap_reproduced: bool,
    mcd_ok: bool,
    seed_jaccard: float,
    forest_adds: bool,
    max_driver_share: float | None,
) -> str:
    """Apply the v1 disposition rule. Gates that stop the fit never reach this function."""
    if (
        exclusions > 0
        or not double_gap_reproduced
        or not mcd_ok
        or seed_jaccard < _SEED_STABLE_JACCARD
    ):
        return "revise"
    if forest_adds or (max_driver_share is not None and max_driver_share >= _DRIVER_FOLLOWUP_SHARE):
        return "follow-up"
    return "keep"


def dominant_label(z_values: Mapping[str, float]) -> str:
    """Name the feature with the largest absolute robust z, or tie or joint."""
    if not z_values:
        return "joint"
    ranked = sorted(z_values.items(), key=lambda item: (-abs(item[1]), item[0]))
    top_name, top_value = ranked[0]
    if abs(top_value) < Z_JOINT:
        return "joint"
    if len(ranked) > 1 and abs(abs(top_value) - abs(ranked[1][1])) <= 1e-12:
        return "tie"
    return top_name


def parse_row(raw: Mapping[str, object]) -> ParsedRow:
    fips = _fips(raw.get("FIPS"))
    state = _state(raw.get("STATE"))
    if state not in CENSUS_REGIONS:
        raise ClassAnomalyError("a class row has a state outside the Census map")
    tick = _status(raw.get("TICK_STATUS"), "tick status")
    if tick != TICK_ESTABLISHED:
        raise ClassAnomalyError("a class row is outside the established-tick rule")
    return ParsedRow(
        fips=fips,
        county_name=_county_name(raw.get("COUNTY")),
        state=state,
        population=_optional_float(raw.get("POPULATION")),
        svi_percentile=_optional_float(raw.get("SVI_PERCENTILE")),
        uninsured_percentile=_optional_float(raw.get("UNINSURED_PERCENTILE")),
        rucc=_optional_float(raw.get("RUCC_2023")),
        human_status=_status(raw.get("HUMAN_STATUS"), "human status"),
        burgdorferi_status=_status(raw.get("BURGDORFERI_STATUS"), "pathogen status"),
        tick_status=tick,
    )


def exclusion_reason(row: ParsedRow) -> str | None:
    values = (row.population, row.svi_percentile, row.uninsured_percentile, row.rucc)
    if any(value is None or not math.isfinite(value) for value in values):
        return "null_feature"
    population = row.population
    rucc = row.rucc
    if population is None or population <= 0:
        return "nonpositive_population"
    if rucc is None or not float(rucc).is_integer() or not 1 <= int(rucc) <= 9:
        return "rucc_out_of_range"
    return None


def lab_metrics(result: FitResult) -> list[EdaMetric]:
    """Aggregate metrics. A numerator from 1 to 10 is stored so the writer can suppress it."""
    rows: list[EdaMetric] = [
        _count_metric("class_county_count", result.n_class, {"part": "class"}),
        _count_metric("fit_county_count", result.n_fit, {"part": "fit"}),
        _count_metric("exclusion_count", len(result.exclusions), {"part": "excluded"}),
        _count_metric("double_gap_count", result.double_gap_n, {"part": "double_gap"}),
        _count_metric("gap_810_count", result.gap_810_n, {"part": "gap_810"}),
    ]
    for name, count in result.flag_counts.items():
        rows.append(
            _rate_metric(
                "flag_rate",
                count,
                result.n_fit,
                {"method": name},
                result.flag_rate_interval if name == "if_primary" else None,
            )
        )
    rows.append(
        _rate_metric(
            "overlap_share",
            result.overlap_primary_228,
            result.flag_counts["if_primary"],
            {"method": "if_primary", "list": "double_gap"},
            result.overlap_interval,
        )
    )
    rows.append(
        _rate_metric(
            "overlap_share",
            result.overlap_primary_810,
            result.flag_counts["if_primary"],
            {"method": "if_primary", "list": "gap_810"},
            None,
        )
    )
    rows.extend(_agreement_metrics(result))
    for method, counts in result.driver_counts.items():
        rows.extend(_composition_metrics("driver_share", counts, {"method": method}))
    for region in result.region_scores:
        for name, value in (("p25", region.p25), ("p50", region.p50), ("p75", region.p75)):
            rows.append(
                EdaMetric(
                    metric_name="score_percentile",
                    n_underlying=region.n if region.n is not None else 0,
                    metric_value=value,
                    geography_type="census_region",
                    geography_id=region.region,
                    dimensions={"score": "if_primary", "percentile": name},
                    unit="score",
                )
            )
    for feature, bins in (
        ("population", result.population_bins),
        ("log_population", result.log_bins),
        ("svi_percentile", result.svi_bins),
        ("uninsured_percentile", result.uninsured_bins),
        ("rucc_2023", result.rucc_bins),
    ):
        for item in bins:
            if item.count is None:
                rows.append(
                    EdaMetric(
                        metric_name="feature_bin_count",
                        n_underlying=1,
                        metric_value=None,
                        geography_type="national",
                        geography_id="US",
                        dimensions={"feature": feature, "bin": item.label},
                        unit="counties",
                    )
                )
            else:
                rows.append(
                    _count_metric(
                        "feature_bin_count",
                        item.count,
                        {"feature": feature, "bin": item.label},
                    )
                )
    return rows


def build_findings(result: FitResult) -> list[FindingRecord]:
    """Aggregate findings. County names stay in the write-up, not in these statements."""
    primary_n = result.flag_counts["if_primary"]
    rate = primary_n / result.n_fit if result.n_fit else 0.0
    low, high = _interval_fields(result.flag_rate_interval)
    overlap_low, overlap_high = _interval_fields(result.overlap_interval)
    forest_sentence = (
        "The isolation forest adds a distinct review set relative to both baselines."
        if result.forest_adds
        else "The isolation forest does not add a distinct review set beyond the baselines."
    )
    gap_sentence = (
        "The published-column double-gap predicate matches the reference count of 228."
        if result.double_gap_reproduced
        else "The published-column double-gap predicate does not match 228. Use the 810-county gap."
    )
    return [
        FindingRecord(
            topic="class screen",
            statement=(
                f"Disposition is {result.disposition}. The primary forest flag rate is "
                f"{rate:.4f} on the complete class rows. {gap_sentence}"
            ),
            disposition=result.disposition,
            n_underlying=result.n_fit,
            effect_size=rate,
            ci_low=low,
            ci_high=high,
            uncertainty_note=(
                "State-cluster bootstrap percentile interval for the primary flag rate. "
                "Counties in a state are not independent draws."
            ),
            evidence={
                "spec": SPEC_ID,
                "features_kept": list(result.features_kept),
                "features_dropped": list(result.features_dropped),
                "scaled_columns": list(result.scaled_columns),
                "mcd_ok": result.mcd_ok,
                "forest_adds": result.forest_adds,
            },
        ),
        FindingRecord(
            topic="baseline agreement",
            statement=(
                f"Seed-to-seed Jaccard at contamination 0.05 is {result.seed_jaccard:.4f}. "
                f"Matched-count Jaccard versus robust z is {result.matched_jaccard_robust_z:.4f} "
                f"and versus robust distance is {result.matched_jaccard_mcd:.4f}. {forest_sentence}"
            ),
            disposition=result.disposition,
            n_underlying=result.n_fit,
            effect_size=result.seed_jaccard,
            evidence={"forest_adds": result.forest_adds},
        ),
        FindingRecord(
            topic="double-gap overlap",
            statement=(
                "Overlap of the primary flags with the double-gap and wider gap predicates "
                "is a surveillance-list comparison. It is not a risk ranking."
            ),
            disposition=result.disposition,
            n_underlying=result.n_fit,
            effect_size=None
            if _small(result.overlap_primary_228) or _small(primary_n)
            else result.overlap_primary_228 / primary_n,
            ci_low=None if _small(result.overlap_primary_228) else overlap_low,
            ci_high=None if _small(result.overlap_primary_228) else overlap_high,
            uncertainty_note=(
                "State-cluster bootstrap percentile interval for the share of primary flags "
                "inside the double-gap predicate."
            ),
        ),
    ]


def sklearn_version() -> str:
    return version("scikit-learn")


def _design_matrix(
    parsed: Sequence[ParsedRow],
    kept: Sequence[ParsedRow],
) -> tuple[tuple[str, ...], Vector, tuple[str, ...], tuple[str, ...]]:
    scaled = _scaled_columns(parsed)
    columns = {
        "log_population": np.array([math.log(float(row.population or 0.0)) for row in kept]),
        "svi_percentile": np.array([float(row.svi_percentile or 0.0) for row in kept]),
        "uninsured_percentile": np.array([float(row.uninsured_percentile or 0.0) for row in kept]),
        "rucc_2023": np.array([float(row.rucc or 0.0) for row in kept]),
    }
    for name in scaled:
        if name in columns:
            columns[name] = columns[name] / 100.0
    kept_names: list[str] = []
    dropped: list[str] = []
    for name in FEATURE_ORDER:
        values = columns[name]
        deviation = np.abs(values - np.median(values))
        mad = float(np.median(deviation))
        if len(np.unique(values)) <= 1 or mad == 0.0:
            dropped.append(name)
            continue
        kept_names.append(name)
    if not kept_names:
        raise ClassAnomalyError("fewer than two varying features remain")
    matrix = np.column_stack([columns[name] for name in kept_names])
    return tuple(scaled), np.asarray(matrix, dtype=float), tuple(kept_names), tuple(dropped)


def _scaled_columns(parsed: Sequence[ParsedRow]) -> tuple[str, ...]:
    scaled: list[str] = []
    for name, attr in (
        ("svi_percentile", "svi_percentile"),
        ("uninsured_percentile", "uninsured_percentile"),
    ):
        values = [
            value
            for row in parsed
            if (value := getattr(row, attr)) is not None and math.isfinite(value)
        ]
        if values and max(values) > 1.5:
            scaled.append(name)
    return tuple(scaled)


def _robust_z_matrix(matrix: Vector) -> Vector:
    medians = np.median(matrix, axis=0)
    deviation = np.abs(matrix - medians)
    mad = np.median(deviation, axis=0)
    scale = MAD_SCALE * mad
    if np.any(scale == 0):
        raise ClassAnomalyError("a kept feature has a zero robust scale")
    return np.asarray((matrix - medians) / scale, dtype=float)


def _robust_distances(matrix: Vector) -> tuple[Vector, bool]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = MinCovDet(
                support_fraction=SUPPORT_FRACTION,
                random_state=PRIMARY_SEED,
                assume_centered=False,
            )
            model.fit(matrix)
            squared = np.asarray(model.mahalanobis(matrix), dtype=float)
    except Exception:
        return np.full(matrix.shape[0], np.nan), False
    if not np.all(np.isfinite(squared)):
        return squared, False
    return squared, True


def _forests(
    matrix: Vector,
) -> tuple[dict[tuple[int, float], Vector], Vector, Vector]:
    flags: dict[tuple[int, float], Vector] = {}
    primary_scores = np.zeros(matrix.shape[0], dtype=float)
    seed_b_scores = np.zeros(matrix.shape[0], dtype=float)
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
            model.fit(matrix)
            flags[(seed, contamination)] = np.asarray(model.predict(matrix) == -1, dtype=bool)
            scores = -np.asarray(model.decision_function(matrix), dtype=float)
            if seed == PRIMARY_SEED and contamination == PRIMARY_CONTAMINATION:
                primary_scores = scores
            if seed == SECOND_SEED and contamination == PRIMARY_CONTAMINATION:
                seed_b_scores = scores
    return flags, primary_scores, seed_b_scores


def _score_rows(
    kept: Sequence[ParsedRow],
    feature_names: Sequence[str],
    scaled_columns: Sequence[str],
    z_matrix: Vector,
    squared: Vector | None,
    primary_scores: Vector,
    seed_b_scores: Vector,
    z_flags: Vector,
    mcd_flags: Vector,
    forest_flags: Mapping[tuple[int, float], Vector],
) -> tuple[ScoredCounty, ...]:
    rows: list[ScoredCounty] = []
    for index, row in enumerate(kept):
        z_values = {
            feature_names[column]: float(z_matrix[index, column])
            for column in range(len(feature_names))
        }
        population = float(row.population or 0.0)
        svi = float(row.svi_percentile or 0.0)
        uninsured = float(row.uninsured_percentile or 0.0)
        if "svi_percentile" in scaled_columns:
            svi = svi / 100.0
        if "uninsured_percentile" in scaled_columns:
            uninsured = uninsured / 100.0
        rows.append(
            ScoredCounty(
                fips=row.fips,
                county_name=row.county_name,
                state=row.state,
                region=CENSUS_REGIONS[row.state],
                population=population,
                log_population=float(math.log(population)),
                svi_percentile=svi,
                uninsured_percentile=uninsured,
                rucc=int(row.rucc or 0),
                human_status=row.human_status,
                burgdorferi_status=row.burgdorferi_status,
                tick_status=row.tick_status,
                robust_z=tuple(z_values.items()),
                robust_z_max_abs=max(abs(value) for value in z_values.values()),
                mahalanobis_squared=None if squared is None else float(squared[index]),
                if_score_primary=float(primary_scores[index]),
                if_score_seed_b=float(seed_b_scores[index]),
                flag_robust_z=bool(z_flags[index]),
                flag_mahalanobis=bool(mcd_flags[index]),
                flag_if_primary=bool(forest_flags[(PRIMARY_SEED, PRIMARY_CONTAMINATION)][index]),
                flag_if_seed_b=bool(forest_flags[(SECOND_SEED, PRIMARY_CONTAMINATION)][index]),
                flag_if_c02=bool(forest_flags[(PRIMARY_SEED, 0.02)][index]),
                flag_if_c10=bool(forest_flags[(PRIMARY_SEED, 0.10)][index]),
                dominant_feature=dominant_label(z_values),
                in_double_gap=(
                    row.human_status == HUMAN_NO_RECORD
                    and row.burgdorferi_status == PATHOGEN_PRESENT
                ),
                in_gap_810=row.human_status == HUMAN_NO_RECORD,
            )
        )
    return tuple(rows)


def _charts(
    counties: Sequence[ScoredCounty],
    feature_names: Sequence[str],
    flag_counts: Mapping[str, int],
    driver_counts: Mapping[str, Mapping[str, int]],
    n_fit: int,
) -> tuple[
    tuple[RegionScore, ...],
    tuple[ChartBin, ...],
    tuple[ChartBin, ...],
    tuple[ChartBin, ...],
    tuple[ChartBin, ...],
    tuple[ChartBin, ...],
    tuple[FlagRateBar, ...],
    tuple[DriverBar, ...],
]:
    del feature_names
    regions = tuple(_region_score(counties, region) for region in REGION_ORDER)
    population = _collapse(_histogram([row.population for row in counties], POPULATION_EDGES))
    log_bins = _collapse(_histogram([row.log_population for row in counties], LOG_POPULATION_EDGES))
    svi = _collapse(_histogram([row.svi_percentile for row in counties], PERCENTILE_EDGES))
    uninsured = _collapse(
        _histogram([row.uninsured_percentile for row in counties], PERCENTILE_EDGES)
    )
    rucc_counts = [(str(code), sum(row.rucc == code for row in counties)) for code in range(1, 10)]
    rucc = _collapse(rucc_counts)
    rates = tuple(_flag_bar(name, count, n_fit) for name, count in flag_counts.items())
    bars: list[DriverBar] = []
    for method, counts in driver_counts.items():
        published = _publish_composition(counts)
        for feature, count in published.items():
            total = sum(value for value in counts.values())
            share = None if count is None or total == 0 else count / total
            bars.append(DriverBar(method=method, feature=feature, count=count, share=share))
    return regions, population, log_bins, svi, uninsured, rucc, rates, tuple(bars)


def _region_score(counties: Sequence[ScoredCounty], region: str) -> RegionScore:
    scores = [row.if_score_primary for row in counties if row.region == region]
    n = len(scores)
    if n < SMALL_CELL_MINIMUM:
        return RegionScore(region, None if _small(n) else n, None, None, None)
    quantiles = np.quantile(np.array(scores, dtype=float), [0.25, 0.5, 0.75])
    return RegionScore(region, n, float(quantiles[0]), float(quantiles[1]), float(quantiles[2]))


def _flag_bar(name: str, count: int, n_fit: int) -> FlagRateBar:
    seed, contamination = _method_parts(name)
    publish = not _small(count)
    return FlagRateBar(
        label=name,
        method=name,
        seed=seed,
        contamination=contamination,
        count=count if publish else None,
        rate=(count / n_fit) if publish and n_fit else None,
    )


def _method_parts(name: str) -> tuple[int | None, float | None]:
    if name == "robust_z" or name == "mahalanobis":
        return None, None
    if name == "if_primary":
        return PRIMARY_SEED, PRIMARY_CONTAMINATION
    if name == "if_seed_b":
        return SECOND_SEED, PRIMARY_CONTAMINATION
    if name == "if_c02":
        return PRIMARY_SEED, 0.02
    if name == "if_c10":
        return PRIMARY_SEED, 0.10
    if name == "if_b_c02":
        return SECOND_SEED, 0.02
    if name == "if_b_c10":
        return SECOND_SEED, 0.10
    return None, None


def _flag_counts(counties: Sequence[ScoredCounty]) -> dict[str, int]:
    return {
        "robust_z": sum(row.flag_robust_z for row in counties),
        "mahalanobis": sum(row.flag_mahalanobis for row in counties),
        "if_primary": sum(row.flag_if_primary for row in counties),
        "if_seed_b": sum(row.flag_if_seed_b for row in counties),
        "if_c02": sum(row.flag_if_c02 for row in counties),
        "if_c10": sum(row.flag_if_c10 for row in counties),
    }


def _drivers(counties: Sequence[ScoredCounty], flag_name: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in counties:
        if getattr(row, flag_name):
            counts[row.dominant_feature] += 1
    return dict(counts)


def _review(counties: Sequence[ScoredCounty]) -> tuple[ScoredCounty, ...]:
    flagged = sorted(
        (row for row in counties if row.flag_if_primary),
        key=lambda row: (-row.if_score_primary, row.fips),
    )
    if len(flagged) <= REVIEW_ALL_MAX:
        return tuple(flagged)
    return tuple(flagged[:REVIEW_TOP])


def _baseline_only(
    counties: Sequence[ScoredCounty],
    flag_name: str,
    score_name: str,
) -> tuple[ScoredCounty, ...]:
    rows = [row for row in counties if getattr(row, flag_name) and not row.flag_if_primary]
    rows.sort(
        key=lambda row: (
            -float(getattr(row, score_name) if getattr(row, score_name) is not None else -1.0),
            row.fips,
        )
    )
    return tuple(rows[:BASELINE_ONLY_TOP])


def _experiments(
    run_id: str,
    feature_names: Sequence[str],
    flag_counts: Mapping[str, int],
    n_fit: int,
    seed_jaccard: float,
    matched_z: float,
    matched_mcd: float,
    mcd_ok: bool,
    cutoff: float | None,
    rate_interval: tuple[float, float] | None,
    overlap_interval: tuple[float, float] | None,
    overlap_228: int,
    overlap_810: int,
) -> tuple[ExperimentRow, ...]:
    shared = {
        "spec": SPEC_ID,
        "features": list(feature_names),
        "sklearn": sklearn_version(),
    }
    rows = [
        _experiment(
            f"{run_id}-robust-z",
            "robust_z",
            "A county is unusual when its largest absolute robust z exceeds 3.5.",
            {**shared, "threshold": Z_FLAG, "mad_scale": MAD_SCALE},
            {"split": "established_tick_class"},
            "succeeded",
            _method_metrics("robust_z", flag_counts["robust_z"], n_fit, None),
        ),
        _experiment(
            f"{run_id}-mahalanobis",
            "robust_covariance",
            "A county is unusual when squared robust distance exceeds the 0.975 cutoff.",
            {
                **shared,
                "support_fraction": SUPPORT_FRACTION,
                "random_state": PRIMARY_SEED,
                "cutoff": cutoff,
            },
            {"split": "established_tick_class"},
            "succeeded" if mcd_ok else "failed",
            _method_metrics("mahalanobis", flag_counts["mahalanobis"], n_fit, None)
            if mcd_ok
            else (),
        ),
    ]
    specs = (
        ("if_c02", PRIMARY_SEED, 0.02, flag_counts["if_c02"], False),
        ("if_primary", PRIMARY_SEED, PRIMARY_CONTAMINATION, flag_counts["if_primary"], True),
        ("if_c10", PRIMARY_SEED, 0.10, flag_counts["if_c10"], False),
        ("if_b_c02", SECOND_SEED, 0.02, flag_counts["if_b_c02"], False),
        ("if_seed_b", SECOND_SEED, PRIMARY_CONTAMINATION, flag_counts["if_seed_b"], False),
        ("if_b_c10", SECOND_SEED, 0.10, flag_counts["if_b_c10"], False),
    )
    for name, seed, contamination, count, primary in specs:
        metrics = _method_metrics(
            name,
            count,
            n_fit,
            rate_interval if primary else None,
        )
        if primary:
            metrics = (
                *metrics,
                *_optional_metric("seed_jaccard", seed_jaccard, n_fit, "agreement"),
                *_optional_metric("matched_jaccard_robust_z", matched_z, n_fit, "agreement"),
                *_optional_metric("matched_jaccard_mcd", matched_mcd, n_fit, "agreement"),
                *_rate_model_metric(
                    "overlap_share_double_gap",
                    overlap_228,
                    count,
                    overlap_interval,
                    "overlap",
                ),
                *_rate_model_metric("overlap_share_gap_810", overlap_810, count, None, "overlap"),
            )
        rows.append(
            _experiment(
                f"{run_id}-if-{seed}-c{_contamination_tag(contamination)}",
                "isolation_forest",
                "A county is unusual when the isolation forest label is the outlier label.",
                {
                    **shared,
                    "n_estimators": N_ESTIMATORS,
                    "contamination": contamination,
                    "random_state": seed,
                    "max_samples": "auto",
                    "bootstrap": False,
                    "n_jobs": 1,
                    "score": "negative_decision_function",
                },
                {"split": "established_tick_class", "seed": seed},
                "succeeded",
                metrics,
            )
        )
    return tuple(rows)


def _experiment(
    experiment_id: str,
    family: str,
    hypothesis: str,
    config: dict[str, object],
    split_definition: dict[str, object],
    status: str,
    metrics: tuple[ModelMetricRow, ...],
) -> ExperimentRow:
    return ExperimentRow(
        experiment_id=experiment_id,
        model_family=family,
        hypothesis=hypothesis,
        config=config,
        split_definition=split_definition,
        status=status,
        metrics=metrics,
    )


def _method_metrics(
    name: str,
    count: int,
    n_fit: int,
    interval: tuple[float, float] | None,
) -> tuple[ModelMetricRow, ...]:
    if _small(count):
        return ()
    low, high = _interval_fields(interval)
    rate = count / n_fit if n_fit else 0.0
    return (
        ModelMetricRow(name, "flag_count", float(count), None, None, n_fit),
        ModelMetricRow(name, "flag_rate", rate, low, high, n_fit),
    )


def _optional_metric(
    name: str,
    value: float,
    n_fit: int,
    split_name: str,
) -> tuple[ModelMetricRow, ...]:
    if _small(n_fit):
        return ()
    return (ModelMetricRow(split_name, name, value, None, None, n_fit),)


def _rate_model_metric(
    name: str,
    numerator: int,
    denominator: int,
    interval: tuple[float, float] | None,
    split_name: str,
) -> tuple[ModelMetricRow, ...]:
    if denominator <= 0 or _small(numerator) or _small(denominator):
        return ()
    low, high = _interval_fields(interval)
    return (ModelMetricRow(split_name, name, numerator / denominator, low, high, denominator),)


def _agreement_metrics(result: FitResult) -> list[EdaMetric]:
    metrics = [
        ("seed_jaccard", result.seed_jaccard, result.n_fit),
        ("matched_jaccard_robust_z", result.matched_jaccard_robust_z, result.n_fit),
        ("matched_jaccard_mcd", result.matched_jaccard_mcd, result.n_fit),
    ]
    rows: list[EdaMetric] = []
    for name, value, n_value in metrics:
        rows.append(
            EdaMetric(
                metric_name=name,
                n_underlying=n_value,
                metric_value=value,
                geography_type="national",
                geography_id="US",
                dimensions={"comparison": name},
                unit="jaccard",
            )
        )
    return rows


def _count_metric(name: str, count: int, dimensions: dict[str, object]) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        n_underlying=count,
        metric_value=float(count),
        geography_type="national",
        geography_id="US",
        dimensions=dimensions,
        unit="counties",
    )


def _rate_metric(
    name: str,
    numerator: int,
    denominator: int,
    dimensions: dict[str, object],
    interval: tuple[float, float] | None,
) -> EdaMetric:
    del interval
    small = _small(numerator) or (denominator != 0 and _small(denominator))
    return EdaMetric(
        metric_name=name,
        n_underlying=numerator if small else denominator,
        metric_value=None if small or denominator == 0 else numerator / denominator,
        geography_type="national",
        geography_id="US",
        dimensions=dimensions,
        unit="rate",
    )


def _composition_metrics(
    name: str,
    counts: Mapping[str, int],
    dimensions: dict[str, object],
) -> list[EdaMetric]:
    published = _publish_composition(dict(counts))
    total = sum(counts.values())
    rows: list[EdaMetric] = []
    for feature, count in published.items():
        extra = {**dimensions, "feature": feature}
        if count is None:
            rows.append(
                EdaMetric(
                    metric_name=name,
                    n_underlying=1,
                    metric_value=None,
                    geography_type="national",
                    geography_id="US",
                    dimensions=extra,
                    unit="share",
                )
            )
            continue
        rows.append(
            EdaMetric(
                metric_name=name,
                n_underlying=total,
                metric_value=None if total == 0 else count / total,
                geography_type="national",
                geography_id="US",
                dimensions=extra,
                unit="share",
            )
        )
    return rows


def _publish_composition(counts: Mapping[str, int]) -> dict[str, int | None]:
    total = sum(counts.values())
    if total < SMALL_CELL_MINIMUM:
        return dict.fromkeys(counts, None)
    small = {key: value for key, value in counts.items() if 0 < value < SMALL_CELL_MINIMUM}
    if not small:
        return dict(counts)
    if len(small) == 1 or sum(small.values()) < SMALL_CELL_MINIMUM:
        return dict.fromkeys(counts, None)
    published: dict[str, int | None] = {
        key: value for key, value in counts.items() if value == 0 or value >= SMALL_CELL_MINIMUM
    }
    published["other"] = sum(small.values())
    return published


def _histogram(values: Sequence[float], edges: tuple[float, ...]) -> list[tuple[str, int]]:
    array = np.asarray(values, dtype=float)
    under = int(np.sum(array < edges[0]))
    over = int(np.sum(array > edges[-1]))
    inside = array[(array >= edges[0]) & (array <= edges[-1])]
    counts, _bounds = np.histogram(inside, bins=np.asarray(edges, dtype=float))
    bins = [("underflow", under)]
    for index, count in enumerate(counts):
        bins.append((f"[{edges[index]:g}, {edges[index + 1]:g})", int(count)))
    bins.append(("overflow", over))
    return bins


def _collapse(bins: Sequence[tuple[str, int]]) -> tuple[ChartBin, ...]:
    total = sum(count for _label, count in bins)
    if total < SMALL_CELL_MINIMUM:
        return tuple(ChartBin(label, None) for label, _count in bins)
    small = [(label, count) for label, count in bins if 0 < count < SMALL_CELL_MINIMUM]
    if not small:
        return tuple(ChartBin(label, count) for label, count in bins)
    small_sum = sum(count for _label, count in small)
    if len(small) == 1 or small_sum < SMALL_CELL_MINIMUM:
        return tuple(ChartBin(label, None) for label, _count in bins)
    published = [
        ChartBin(label, count) for label, count in bins if count == 0 or count >= SMALL_CELL_MINIMUM
    ]
    published.append(ChartBin("other", small_sum))
    return tuple(published)


def _bootstrap_rate(
    states: Vector,
    flags: Vector,
    seed: int,
) -> tuple[float, float] | None:
    def statistic(index: Vector) -> float:
        return float(np.mean(flags[index]))

    return _bootstrap(states, statistic, seed)


def _bootstrap_share(
    states: Vector,
    flags: Vector,
    membership: Vector,
    seed: int,
) -> tuple[float, float] | None:
    def statistic(index: Vector) -> float | None:
        chosen = flags[index]
        if int(np.sum(chosen)) == 0:
            return None
        return float(np.mean(membership[index][chosen]))

    return _bootstrap(states, statistic, seed)


def _bootstrap(
    states: Vector,
    statistic: object,
    seed: int,
) -> tuple[float, float] | None:
    if len(states) == 0:
        return None
    rng = np.random.default_rng(seed)
    unique = np.unique(states)
    groups = {state: np.flatnonzero(states == state) for state in unique}
    draws: list[float] = []
    for _ in range(BOOTSTRAP_DRAWS):
        chosen = rng.choice(unique, size=len(unique), replace=True)
        index = np.concatenate([groups[state] for state in chosen])
        value = statistic(index)  # type: ignore[operator]
        if value is None:
            continue
        draws.append(float(value))
    if len(draws) < BOOTSTRAP_MIN_DRAWS:
        return None
    low, high = np.percentile(np.asarray(draws, dtype=float), [2.5, 97.5])
    return float(low), float(high)


def _reject_identity_problems(rows: Sequence[ParsedRow]) -> None:
    seen: set[str] = set()
    for row in rows:
        if row.fips in seen:
            raise ClassAnomalyError("a class FIPS is duplicated")
        seen.add(row.fips)


def _mask(counties: Sequence[ScoredCounty], name: str) -> Vector:
    return np.array([bool(getattr(row, name)) for row in counties], dtype=bool)


def _top_mask(scores: Vector, fips: Vector, k: int) -> Vector:
    mask = np.zeros(len(scores), dtype=bool)
    if k <= 0:
        return mask
    order = np.lexsort((fips, -scores))
    mask[order[:k]] = True
    return mask


def _jaccard(left: Vector, right: Vector) -> float:
    union = int(np.logical_or(left, right).sum())
    if union == 0:
        return 1.0
    return float(np.logical_and(left, right).sum() / union)


def _max_share(counts: Mapping[str, int]) -> float | None:
    total = sum(counts.values())
    if total == 0:
        return None
    return max(counts.values()) / total


def _contamination_tag(value: float) -> str:
    return {0.02: "02", 0.05: "05", 0.10: "10"}[value]


def _interval_fields(
    interval: tuple[float, float] | None,
) -> tuple[float | None, float | None]:
    if interval is None:
        return None, None
    return interval


def _small(count: int) -> bool:
    return 0 < count < SMALL_CELL_MINIMUM


def _fips(value: object) -> str:
    if not isinstance(value, str) or len(value) != 5 or not value.isdigit():
        raise ClassAnomalyError("a class row has an unusable FIPS")
    return value


def _state(value: object) -> str:
    if not isinstance(value, str) or len(value.strip()) != 2 or not value.strip().isalpha():
        raise ClassAnomalyError("a class row has an unusable state")
    return value.strip().upper()


def _county_name(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ClassAnomalyError("a class row has an unusable county name")
    text = " ".join(value.split())
    if len(text) > 120 or any(ord(char) < 32 for char in text):
        raise ClassAnomalyError("a class row has an unusable county name")
    return text


def _status(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ClassAnomalyError(f"a class row has an unusable {label}")
    text = " ".join(value.split())
    if not text or len(text) > 80:
        raise ClassAnomalyError(f"a class row has an unusable {label}")
    return text


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ClassAnomalyError("a class row has an unusable number")
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClassAnomalyError("a gate field is missing")
    return value.strip()


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ClassAnomalyError("a gate count is missing")
    return value
