"""Multiple correspondence analysis of county surveillance categories.

The functions here do not open Snowflake. County rows stay in memory. Axes are
an exploratory exhibit. They are not features for another model.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.coverage_audit import PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import FindingRecord, QueryRecord
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric
from lyme_gap_atlas_ml.state_regimes import (
    EXPECTED_COUNTIES,
    HUMAN_NONE,
    HUMAN_PUBLISHED,
    METHODOLOGY_VERSION,
    PATHOGEN_PRESENT,
    SCHEMA_VERSION,
    SCOPE,
    TICK_ESTABLISHED,
)

SPEC_ID = "121-county-contrasts/v1"
ISSUE_NUMBER = 121
SEED = 1212026
RUN_PREFIX = "121-county-contrasts-"
SMALL_CELL = 11
RARE_BELOW = 30
QUERY_NAMES = ("release_identity", "county_rows")
SOURCE_OBJECTS = (
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V",
)
EXPECTED_PUBLISHED = 651
EXPECTED_UNLINKED = 2493
REFERENCE_ALIGNED = 443
REFERENCE_DOUBLE_GAP = 228
REFERENCE_WIDER = 810
REFERENCE_HUMAN_AHEAD = 207
REFERENCE_UNDOCUMENTED = 1189
SVI_EDGES = (0.25, 0.50, 0.75)
POPULATION_EDGES = (10_000, 50_000, 250_000)
SENSITIVITY_POPULATION_EDGES = (10_000, 100_000, 250_000)
FINE_POPULATION_EDGES = (10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000)
FINE_SVI_EDGES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
SVI_LABELS = ("q1_low", "q2", "q3", "q4_high")
POPULATION_LABELS = ("lt_10k", "10k_to_50k", "50k_to_250k", "ge_250k")
SENSITIVITY_POPULATION_LABELS = ("lt_10k", "10k_to_100k", "100k_to_250k", "ge_250k")
FINE_POPULATION_LABELS = (
    "under_10k",
    "10k_to_25k",
    "25k_to_50k",
    "50k_to_100k",
    "100k_to_250k",
    "250k_to_500k",
    "500k_to_1m",
    "1m_or_more",
)
CHI2_95_DF2 = 5.991464547107979
SPEARMAN_MIN = 0.90
PROCRUSTES_MIN = 0.90
SEPARATION_ADVANCE = 0.50
CONTRIBUTION_CLOSE = 0.02
CONTRIBUTION_THIRD = 0.10
EIGENVALUE_FLOOR = 1e-12
Q_VARIABLES = 7
TICK_LEVELS = frozenset({TICK_ESTABLISHED, "Reported", "No records", "Unknown"})
PATHOGEN_LEVELS = frozenset({PATHOGEN_PRESENT, "No records", "Unknown"})
HUMAN_LEVELS = frozenset({HUMAN_PUBLISHED, HUMAN_NONE})
NO_RECORDS = "No records"
VARIABLES = (
    "svi_bin",
    "population_bin",
    "rucc",
    "human_status",
    "scapularis_status",
    "pacificus_status",
    "burgdorferi_status",
)
SHARED_VARIABLES = frozenset(VARIABLES[2:])
USE_AS_MODEL_FEATURE = False

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]


class CountyMcaError(ValueError):
    """The county frame or the MCA fit cannot be used."""


@dataclass(frozen=True)
class County:
    fips: str
    name: str
    state: str
    population: float
    svi: float
    rucc: int
    human_status: str
    tick_status: str
    scapularis_status: str
    pacificus_status: str
    burgdorferi_status: str


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


@dataclass(frozen=True)
class CategoryCount:
    variable: str
    level: str
    count: int
    stage: str


@dataclass(frozen=True)
class Contribution:
    category_id: str
    variable: str
    level: str
    axis: int
    contribution: float
    coordinate: float
    count: int


@dataclass(frozen=True)
class AxisContrast:
    axis: int
    positive_ids: tuple[str, ...]
    negative_ids: tuple[str, ...]
    sentence: str
    greenacre_share: float


@dataclass(frozen=True)
class GroupLocation:
    name: str
    count: int
    reference: int
    centroid_1: float
    centroid_2: float
    reproduced: bool


@dataclass(frozen=True)
class Stability:
    spearman_1: float
    spearman_2: float
    spearman_3: float
    procrustes: float
    shared_categories: int
    stable: bool


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
class CoordinateRow:
    fips: str
    county_name: str
    state: str
    axis_1: float
    axis_2: float
    axis_3: float
    in_aligned: bool
    in_double_gap: bool
    in_wider_gap: bool
    in_human_ahead: bool
    in_undocumented: bool


@dataclass(frozen=True)
class Analysis:
    gate: Gate
    counties: tuple[County, ...]
    greenacre_shares: tuple[float, ...]
    benzecri: tuple[float, ...]
    unadjusted: tuple[float, ...]
    greenacre_total: float
    contributions: tuple[Contribution, ...]
    contrasts: tuple[AxisContrast, ...]
    groups: tuple[GroupLocation, ...]
    other_n: int
    stability: Stability | None
    rare_leaders: tuple[str, ...]
    separation_ratio: float | None
    frequencies: tuple[CategoryCount, ...]
    row_coordinates: FloatArray
    method_disposition: str
    product_disposition: str
    reasons: tuple[str, ...]

    @property
    def coordinates(self) -> tuple[CoordinateRow, ...]:
        flags = _situation_flags(self.counties)
        rows: list[CoordinateRow] = []
        for index, county in enumerate(self.counties):
            rows.append(
                CoordinateRow(
                    fips=county.fips,
                    county_name=county.name,
                    state=county.state,
                    axis_1=float(self.row_coordinates[index, 0]),
                    axis_2=float(self.row_coordinates[index, 1]),
                    axis_3=float(self.row_coordinates[index, 2]),
                    in_aligned=flags["aligned"][index],
                    in_double_gap=flags["double_gap"][index],
                    in_wider_gap=flags["wider_gap"][index],
                    in_human_ahead=flags["human_ahead"][index],
                    in_undocumented=flags["undocumented"][index],
                )
            )
        return tuple(rows)


def load_mca_queries(text: str) -> dict[str, str]:
    """Split the issue 121 validation file and reject unsafe SQL."""
    return load_marked_queries(text, QUERY_NAMES)


def evaluate_gate(release: Mapping[str, object], raw_rows: Sequence[Mapping[str, object]]) -> Gate:
    """Check the pin and the headline counts before any axis is named."""
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
        svi = _float(raw.get("SVI_PERCENTILE"))
        if svi is None:
            reasons.append("SVI percentile is missing")
            break
        svi_values.append(svi)
        if not _population_ok(raw.get("POPULATION")):
            reasons.append("population is missing or not positive")
            break
        if _rucc(raw.get("RUCC_2023")) is None:
            reasons.append("rural-urban code is outside 1 through 9")
            break
        if not _text(raw.get("STATE")) or not _text(raw.get("COUNTY")):
            reasons.append("state or county name is blank")
            break
        for column, levels in (
            ("TICK_STATUS", TICK_LEVELS),
            ("SCAPULARIS_STATUS", TICK_LEVELS),
            ("PACIFICUS_STATUS", TICK_LEVELS),
            ("BURGDORFERI_STATUS", PATHOGEN_LEVELS),
        ):
            if _text(raw.get(column)) not in levels:
                reasons.append(f"{column} is outside the published levels")
                break
        else:
            continue
        break
    if len(raw_rows) != EXPECTED_COUNTIES:
        reasons.append("county count is not the predeclared count")
    if published != EXPECTED_PUBLISHED or unlinked != EXPECTED_UNLINKED:
        reasons.append("published floor or no-county-linked count differs from the pin")
    scaled = bool(svi_values) and max(svi_values) > 1.5
    return Gate(
        ok=not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
        release_id=release_id,
        bundle_sha256=bundle,
        county_n=len(raw_rows),
        published_n=published,
        unlinked_n=unlinked,
        svi_scaled=scaled,
    )


def fit_counties(raw_rows: Sequence[Mapping[str, object]], gate: Gate) -> Analysis:
    """Fit the primary MCA and the one-edge sensitivity. The gate must already be ok."""
    if not gate.ok:
        raise CountyMcaError("fit requires a passing gate")
    counties = tuple(_county(raw, scale_svi=gate.svi_scaled) for raw in raw_rows)
    _require_unit_interval(counties)
    primary = _fit_codes(counties, POPULATION_EDGES, POPULATION_LABELS)
    sensitivity = _fit_codes(counties, SENSITIVITY_POPULATION_EDGES, SENSITIVITY_POPULATION_LABELS)
    stability = _stability(primary, sensitivity)
    groups, other_n = _groups(counties, primary.row_coordinates)
    ratio = _separation(counties, primary.row_coordinates)
    rare = _rare_leaders(primary.contributions)
    reproduced = all(group.reproduced for group in groups)
    reasons: list[str] = []
    if not reproduced:
        reasons.append("a situation count differs from the epic reference")
    if rare:
        reasons.append("a rare category leads axis 1 or axis 2")
    if not stability.stable:
        reasons.append("the population-edge sensitivity misses the stability gate")
    method = "revise" if reasons else "keep"
    product = _product(method, ratio)
    return Analysis(
        gate=gate,
        counties=counties,
        greenacre_shares=primary.greenacre_shares,
        benzecri=primary.benzecri,
        unadjusted=primary.unadjusted,
        greenacre_total=primary.greenacre_total,
        contributions=primary.contributions,
        contrasts=primary.contrasts,
        groups=groups,
        other_n=other_n,
        stability=stability,
        rare_leaders=rare,
        separation_ratio=ratio,
        frequencies=_frequencies(counties),
        row_coordinates=primary.row_coordinates,
        method_disposition=method,
        product_disposition=product,
        reasons=tuple(reasons),
    )


def chart_contributions(
    contributions: Sequence[Contribution], axis: int
) -> tuple[Contribution, ...]:
    """Categories that may be drawn. Counts below 11 stay off the chart."""
    rows = [row for row in contributions if row.axis == axis and row.count >= SMALL_CELL]
    rows.sort(key=lambda row: (-row.contribution, row.category_id))
    return tuple(rows[:8])


def suppress_cell_counts(counts: FloatArray) -> FloatArray:
    """Hide hex or grid cells whose count is from 1 to 10."""
    masked = np.array(counts, dtype=float, copy=True)
    small = (masked > 0) & (masked < SMALL_CELL)
    masked[small] = math.nan
    return masked


def lab_metrics(analysis: Analysis) -> tuple[EdaMetric, ...]:
    """Aggregate metrics. The writer removes counts below 11."""
    metrics: list[EdaMetric] = []
    n = analysis.gate.county_n
    for index, share in enumerate(analysis.greenacre_shares[:3], start=1):
        metrics.append(_metric(f"greenacre_share_axis_{index}", share, n, {"axis": str(index)}))
    for stage_rows in analysis.frequencies:
        metrics.append(
            _metric(
                "category_count",
                float(stage_rows.count),
                stage_rows.count,
                {
                    "variable": stage_rows.variable,
                    "level": stage_rows.level,
                    "stage": stage_rows.stage,
                },
            )
        )
    for row in analysis.contributions:
        if row.axis > 3:
            continue
        metrics.append(
            _metric(
                "category_contribution",
                row.contribution,
                row.count,
                {"category": row.category_id, "axis": str(row.axis)},
            )
        )
    for group in analysis.groups:
        dimensions = {"situation": group.name}
        metrics.append(_metric("situation_count", float(group.count), group.count, dimensions))
        metrics.append(_metric("centroid_axis_1", group.centroid_1, group.count, dimensions))
        metrics.append(_metric("centroid_axis_2", group.centroid_2, group.count, dimensions))
    if analysis.separation_ratio is not None:
        metrics.append(
            _metric(
                "separation_ratio", analysis.separation_ratio, n, {"groups": "aligned_double_gap"}
            )
        )
    if analysis.stability is not None:
        stability = analysis.stability
        metrics.append(
            _metric("spearman_axis_1", stability.spearman_1, n, {"check": "sensitivity"})
        )
        metrics.append(
            _metric("spearman_axis_2", stability.spearman_2, n, {"check": "sensitivity"})
        )
        metrics.append(
            _metric("spearman_axis_3", stability.spearman_3, n, {"check": "sensitivity"})
        )
        metrics.append(
            _metric(
                "procrustes_similarity",
                stability.procrustes,
                stability.shared_categories,
                {"check": "shared_categories"},
            )
        )
    return tuple(metrics)


def experiment_rows(analysis: Analysis, run_id: str) -> tuple[ExperimentRow, ...]:
    """Two exhibit rows. The config forbids reuse as a model feature."""
    base = {
        "spec": SPEC_ID,
        "seed": SEED,
        "correction": "greenacre",
        "use_as_model_feature": USE_AS_MODEL_FEATURE,
        "risk_surface": False,
        "svi_edges": list(SVI_EDGES),
        "q_variables": Q_VARIABLES,
    }
    n = analysis.gate.county_n
    primary_metrics = [
        ExperimentMetric(f"axis_{index}", "greenacre_share", share, n)
        for index, share in enumerate(analysis.greenacre_shares[:3], start=1)
    ]
    if analysis.separation_ratio is not None:
        primary_metrics.append(
            ExperimentMetric("groups", "separation_ratio", analysis.separation_ratio, n)
        )
    sensitivity_metrics: list[ExperimentMetric] = []
    if analysis.stability is not None:
        stability = analysis.stability
        sensitivity_metrics = [
            ExperimentMetric("axis_1", "spearman", stability.spearman_1, n),
            ExperimentMetric("axis_2", "spearman", stability.spearman_2, n),
            ExperimentMetric("axis_3", "spearman", stability.spearman_3, n),
            ExperimentMetric(
                "shared_categories",
                "procrustes_similarity",
                stability.procrustes,
                stability.shared_categories,
            ),
        ]
    hypothesis = (
        "Multiple correspondence analysis of binned county surveillance attributes. "
        "Axes are an exploratory exhibit and are not features for another model."
    )
    return (
        ExperimentRow(
            experiment_id=f"{run_id}-primary",
            hypothesis=hypothesis,
            model_family="multiple_correspondence_analysis",
            config={**base, "population_edges": list(POPULATION_EDGES), "fit": "primary"},
            split_definition={"cohort": "pinned_release_counties", "exhibit_only": True},
            status="succeeded",
            metrics=tuple(primary_metrics),
        ),
        ExperimentRow(
            experiment_id=f"{run_id}-sensitivity",
            hypothesis=hypothesis,
            model_family="multiple_correspondence_analysis",
            config={
                **base,
                "population_edges": list(SENSITIVITY_POPULATION_EDGES),
                "fit": "one_edge_population_shift",
            },
            split_definition={"cohort": "pinned_release_counties", "exhibit_only": True},
            status="succeeded",
            metrics=tuple(sensitivity_metrics),
        ),
    )


def build_findings(analysis: Analysis) -> tuple[FindingRecord, ...]:
    """Aggregate findings. Statements do not carry a five-digit county id."""
    shares = ", ".join(f"{share:.4f}" for share in analysis.greenacre_shares[:3])
    contrast_text = " ".join(row.sentence for row in analysis.contrasts) or "No positive share."
    group_text = "; ".join(
        (
            f"{group.name} count {group.count} "
            f"centroid ({group.centroid_1:.3f}, {group.centroid_2:.3f})"
        )
        for group in analysis.groups
    )
    stability = analysis.stability
    stability_text = "not estimable"
    if stability is not None:
        stability_text = (
            f"Spearman axis 1 {stability.spearman_1:.4f}, axis 2 {stability.spearman_2:.4f}, "
            f"axis 3 {stability.spearman_3:.4f}, Procrustes {stability.procrustes:.4f}"
        )
    ratio = (
        "not estimable" if analysis.separation_ratio is None else f"{analysis.separation_ratio:.4f}"
    )
    rare = ", ".join(analysis.rare_leaders) if analysis.rare_leaders else "none"
    n = analysis.gate.county_n
    return (
        FindingRecord(
            topic="greenacre inertia",
            statement=(
                f"Greenacre-adjusted shares on the first three axes are {shares}. "
                "These axes are an exploratory exhibit, not a risk surface and not a model feature."
            ),
            disposition=analysis.method_disposition,
            n_underlying=n,
            effect_size=analysis.greenacre_shares[0] if analysis.greenacre_shares else None,
        ),
        FindingRecord(
            topic="category contrasts",
            statement=contrast_text,
            disposition=analysis.method_disposition,
            n_underlying=n,
        ),
        FindingRecord(
            topic="situation centroids",
            statement=(
                f"Group summaries: {group_text}. "
                f"Counties outside the five situations: {analysis.other_n}. "
                f"Aligned versus double-gap separation ratio {ratio}. "
                "The double-gap set sits inside the wider established-tick gap."
            ),
            disposition=analysis.method_disposition,
            n_underlying=n,
        ),
        FindingRecord(
            topic="edge sensitivity",
            statement=(
                f"One population-edge shift. {stability_text}. Rare axis leaders: {rare}. "
                f"Method {analysis.method_disposition}. Product {analysis.product_disposition}."
            ),
            disposition=analysis.method_disposition,
            n_underlying=n,
            effect_size=None if stability is None else stability.procrustes,
        ),
    )


def stopped_finding(gate: Gate) -> FindingRecord:
    reason = "; ".join(gate.reasons) if gate.reasons else "gate failed"
    return FindingRecord(
        topic="gate",
        statement=f"The fit stopped before any axis was interpreted. {reason}.",
        disposition="stop",
        n_underlying=max(gate.county_n, SMALL_CELL),
    )


@dataclass(frozen=True)
class _McaFit:
    greenacre_shares: tuple[float, ...]
    benzecri: tuple[float, ...]
    unadjusted: tuple[float, ...]
    greenacre_total: float
    contributions: tuple[Contribution, ...]
    contrasts: tuple[AxisContrast, ...]
    row_coordinates: FloatArray
    column_coordinates: FloatArray
    category_ids: tuple[str, ...]
    category_variables: tuple[str, ...]


def _fit_codes(
    counties: Sequence[County],
    population_edges: tuple[int, ...],
    population_labels: tuple[str, ...],
) -> _McaFit:
    codes, ids, variables, levels, counts = _indicator_codes(
        counties, population_edges, population_labels
    )
    fit = correspondence(codes)
    coordinates = np.array(fit.row_coordinates[:, :3], copy=True)
    if coordinates.shape[1] < 3:
        pad = np.zeros((coordinates.shape[0], 3 - coordinates.shape[1]))
        coordinates = np.hstack((coordinates, pad))
    contributions = _contributions(fit, ids, variables, levels, counts)
    _apply_signs(coordinates, fit.column_coordinates, contributions)
    contrasts = _contrasts(contributions, fit.greenacre_shares)
    return _McaFit(
        greenacre_shares=fit.greenacre_shares,
        benzecri=fit.benzecri,
        unadjusted=fit.unadjusted,
        greenacre_total=fit.greenacre_total,
        contributions=tuple(contributions),
        contrasts=contrasts,
        row_coordinates=coordinates,
        column_coordinates=np.array(fit.column_coordinates, copy=True),
        category_ids=ids,
        category_variables=variables,
    )


@dataclass(frozen=True)
class Correspondence:
    row_coordinates: FloatArray
    column_coordinates: FloatArray
    unadjusted: tuple[float, ...]
    benzecri: tuple[float, ...]
    greenacre_shares: tuple[float, ...]
    greenacre_total: float
    column_mass: FloatArray


def correspondence(codes: IntArray) -> Correspondence:
    """CA of a complete disjunctive code matrix. ``codes`` is n by Q."""
    if codes.ndim != 2 or codes.shape[1] < 2:
        raise CountyMcaError("correspondence analysis needs at least two variables")
    n_rows, q_variables = codes.shape
    levels = [int(codes[:, column].max()) + 1 for column in range(q_variables)]
    if any(len(set(codes[:, column].tolist())) < 2 for column in range(q_variables)):
        raise CountyMcaError("a variable has fewer than two observed levels")
    j_categories = sum(levels)
    indicator = np.zeros((n_rows, j_categories), dtype=np.float64)
    offset = 0
    for column, width in enumerate(levels):
        indicator[np.arange(n_rows), offset + codes[:, column]] = 1.0
        offset += width
    total = float(n_rows * q_variables)
    correspondence_matrix = indicator / total
    row_mass = correspondence_matrix.sum(axis=1)
    column_mass = correspondence_matrix.sum(axis=0)
    residuals = correspondence_matrix - np.outer(row_mass, column_mass)
    standardized = residuals / np.sqrt(np.outer(row_mass, column_mass))
    _left, singular, vt = np.linalg.svd(standardized, full_matrices=False)
    eigenvalues = singular**2
    keep = singular > EIGENVALUE_FLOOR
    singular = singular[keep]
    eigenvalues = eigenvalues[keep]
    left = _left[:, keep]
    vt = vt[keep, :]
    row_coordinates = (left * singular) / np.sqrt(row_mass)[:, None]
    column_coordinates = (vt.T * singular) / np.sqrt(column_mass)[:, None]
    gram = standardized.T @ standardized
    sum_squares = float(np.sum(gram * gram))
    benzecri = _benzecri(eigenvalues, q_variables)
    greenacre_total = (q_variables / (q_variables - 1)) * (
        sum_squares - (j_categories - q_variables) / q_variables**2
    )
    if not math.isfinite(greenacre_total) or greenacre_total <= 0:
        raise CountyMcaError("Greenacre denominator is not positive")
    shares = tuple(float(value / greenacre_total) for value in benzecri)
    return Correspondence(
        row_coordinates=row_coordinates,
        column_coordinates=column_coordinates,
        unadjusted=tuple(float(value) for value in eigenvalues),
        benzecri=tuple(float(value) for value in benzecri),
        greenacre_shares=shares,
        greenacre_total=float(greenacre_total),
        column_mass=column_mass,
    )


def procrustes_similarity(left: FloatArray, right: FloatArray) -> float:
    """Orthogonal Procrustes similarity after centering and Frobenius scaling."""
    if left.shape != right.shape or left.ndim != 2 or left.shape[0] < 2:
        raise CountyMcaError("Procrustes inputs must be matching matrices")
    first = left - left.mean(axis=0)
    second = right - right.mean(axis=0)
    first_norm = float(np.linalg.norm(first))
    second_norm = float(np.linalg.norm(second))
    if first_norm == 0 or second_norm == 0:
        raise CountyMcaError("Procrustes input has no spread")
    first /= first_norm
    second /= second_norm
    _u, singular, _vt = np.linalg.svd(first.T @ second)
    disparity = 1.0 - float(np.sum(singular) ** 2)
    return 1.0 - disparity


def spearman(left: FloatArray, right: FloatArray) -> float:
    """Spearman rank correlation with average ranks for ties."""
    if left.shape != right.shape or left.ndim != 1 or left.size < 3:
        raise CountyMcaError("Spearman inputs must be matching vectors")
    ranked_left = _rank(left)
    ranked_right = _rank(right)
    if float(np.std(ranked_left)) == 0 or float(np.std(ranked_right)) == 0:
        return 0.0
    coefficient = np.corrcoef(ranked_left, ranked_right)[0, 1]
    return float(coefficient)


def _benzecri(eigenvalues: FloatArray, q_variables: int) -> FloatArray:
    threshold = 1.0 / q_variables
    factor = q_variables / (q_variables - 1)
    corrected = np.zeros(eigenvalues.shape, dtype=np.float64)
    for index, value in enumerate(eigenvalues):
        if value > threshold:
            corrected[index] = (factor * (value - threshold)) ** 2
    return corrected


def _indicator_codes(
    counties: Sequence[County],
    population_edges: tuple[int, ...],
    population_labels: tuple[str, ...],
) -> tuple[IntArray, tuple[str, ...], tuple[str, ...], tuple[str, ...], tuple[int, ...]]:
    svi = _digitize(np.array([row.svi for row in counties]), SVI_EDGES, right=True)
    population = _digitize(
        np.array([row.population for row in counties]),
        np.array(population_edges, dtype=float),
        right=False,
    )
    rucc = np.array([row.rucc - 1 for row in counties], dtype=np.int64)
    human = _code([row.human_status for row in counties], (HUMAN_PUBLISHED, HUMAN_NONE))
    scapularis = _code(
        [row.scapularis_status for row in counties],
        ("Established", "Reported", "No records", "Unknown"),
    )
    pacificus = _code(
        [row.pacificus_status for row in counties],
        ("Established", "Reported", "No records", "Unknown"),
    )
    pathogen = _code(
        [row.burgdorferi_status for row in counties],
        (PATHOGEN_PRESENT, "No records", "Unknown"),
    )
    raw_codes = (svi, population, rucc, human[0], scapularis[0], pacificus[0], pathogen[0])
    label_sets = (
        SVI_LABELS,
        population_labels,
        tuple(str(code) for code in range(1, 10)),
        human[1],
        scapularis[1],
        pacificus[1],
        pathogen[1],
    )
    packed: list[IntArray] = []
    ids: list[str] = []
    variables: list[str] = []
    levels: list[str] = []
    counts: list[int] = []
    for variable, column, labels in zip(VARIABLES, raw_codes, label_sets, strict=True):
        observed = sorted(set(int(value) for value in column.tolist()))
        remap = {old: new for new, old in enumerate(observed)}
        packed.append(np.array([remap[int(value)] for value in column.tolist()], dtype=np.int64))
        tally = Counter(int(value) for value in column.tolist())
        for old in observed:
            level = labels[old]
            ids.append(f"{variable}={level}")
            variables.append(variable)
            levels.append(level)
            counts.append(tally[old])
    return np.column_stack(packed), tuple(ids), tuple(variables), tuple(levels), tuple(counts)


def _contributions(
    fit: Correspondence,
    ids: Sequence[str],
    variables: Sequence[str],
    levels: Sequence[str],
    counts: Sequence[int],
) -> list[Contribution]:
    rows: list[Contribution] = []
    width = min(3, fit.column_coordinates.shape[1], len(fit.unadjusted))
    for axis in range(width):
        eigenvalue = fit.unadjusted[axis]
        if eigenvalue <= EIGENVALUE_FLOOR:
            continue
        for index, category_id in enumerate(ids):
            coordinate = float(fit.column_coordinates[index, axis])
            contribution = float(fit.column_mass[index] * coordinate**2 / eigenvalue)
            rows.append(
                Contribution(
                    category_id=category_id,
                    variable=variables[index],
                    level=levels[index],
                    axis=axis + 1,
                    contribution=contribution,
                    coordinate=coordinate,
                    count=counts[index],
                )
            )
    return rows


def _apply_signs(
    row_coordinates: FloatArray,
    column_coordinates: FloatArray,
    contributions: list[Contribution],
) -> None:
    by_axis: dict[int, list[Contribution]] = {}
    for row in contributions:
        by_axis.setdefault(row.axis, []).append(row)
    updated: list[Contribution] = []
    for axis, rows in by_axis.items():
        leader = min(rows, key=lambda row: (-row.contribution, row.category_id))
        sign = -1.0 if leader.coordinate < 0 else 1.0
        column = axis - 1
        row_coordinates[:, column] *= sign
        if column < column_coordinates.shape[1]:
            column_coordinates[:, column] *= sign
        for row in rows:
            updated.append(
                Contribution(
                    category_id=row.category_id,
                    variable=row.variable,
                    level=row.level,
                    axis=row.axis,
                    contribution=row.contribution,
                    coordinate=row.coordinate * sign,
                    count=row.count,
                )
            )
    contributions[:] = updated


def _contrasts(
    contributions: Sequence[Contribution], shares: Sequence[float]
) -> tuple[AxisContrast, ...]:
    named: list[AxisContrast] = []
    for axis in (1, 2, 3):
        if axis - 1 >= len(shares) or shares[axis - 1] <= 0:
            continue
        rows = [row for row in contributions if row.axis == axis]
        positive = sorted(
            (row for row in rows if row.coordinate > 0),
            key=lambda row: (-row.contribution, row.category_id),
        )
        negative = sorted(
            (row for row in rows if row.coordinate < 0),
            key=lambda row: (-row.contribution, row.category_id),
        )
        if not positive or not negative:
            continue
        positive_ids = [positive[0].category_id]
        negative_ids = [negative[0].category_id]
        if (
            len(positive) > 1
            and positive[1].contribution >= CONTRIBUTION_THIRD
            and positive[0].contribution - positive[1].contribution <= CONTRIBUTION_CLOSE
        ):
            positive_ids.append(positive[1].category_id)
        elif (
            len(negative) > 1
            and negative[1].contribution >= CONTRIBUTION_THIRD
            and negative[0].contribution - negative[1].contribution <= CONTRIBUTION_CLOSE
        ):
            negative_ids.append(negative[1].category_id)
        sentence = f"Axis {axis} contrasts {_phrase(positive_ids)} with {_phrase(negative_ids)}."
        named.append(
            AxisContrast(
                axis=axis,
                positive_ids=tuple(positive_ids),
                negative_ids=tuple(negative_ids),
                sentence=sentence,
                greenacre_share=float(shares[axis - 1]),
            )
        )
        if len(named) == 3:
            break
    return tuple(named)


def _stability(primary: _McaFit, sensitivity: _McaFit) -> Stability:
    scores_1 = _aligned_spearman(primary.row_coordinates[:, 0], sensitivity.row_coordinates[:, 0])
    scores_2 = _aligned_spearman(primary.row_coordinates[:, 1], sensitivity.row_coordinates[:, 1])
    scores_3 = _aligned_spearman(primary.row_coordinates[:, 2], sensitivity.row_coordinates[:, 2])
    shared = [
        category_id
        for category_id, variable in zip(
            primary.category_ids, primary.category_variables, strict=True
        )
        if variable in SHARED_VARIABLES and category_id in sensitivity.category_ids
    ]
    left_index = {category_id: index for index, category_id in enumerate(primary.category_ids)}
    right_index = {category_id: index for index, category_id in enumerate(sensitivity.category_ids)}
    order = sorted(shared)
    if len(order) < SMALL_CELL:
        return Stability(scores_1, scores_2, scores_3, 0.0, len(order), False)
    left = np.array(
        [primary.column_coordinates[left_index[category_id], :2] for category_id in order]
    )
    right = np.array(
        [sensitivity.column_coordinates[right_index[category_id], :2] for category_id in order]
    )
    try:
        similarity = procrustes_similarity(left, right)
    except CountyMcaError:
        similarity = 0.0
    stable = scores_1 >= SPEARMAN_MIN and scores_2 >= SPEARMAN_MIN and similarity >= PROCRUSTES_MIN
    return Stability(scores_1, scores_2, scores_3, similarity, len(order), stable)


def _aligned_spearman(primary: FloatArray, sensitivity: FloatArray) -> float:
    if float(np.std(primary)) == 0 or float(np.std(sensitivity)) == 0:
        return 0.0
    coefficient = float(np.corrcoef(primary, sensitivity)[0, 1])
    sign = 1.0 if not math.isfinite(coefficient) or coefficient >= 0 else -1.0
    return spearman(primary, sensitivity * sign)


def _groups(
    counties: Sequence[County], coordinates: FloatArray
) -> tuple[tuple[GroupLocation, ...], int]:
    flags = _situation_flags(counties)
    catalog = (
        ("aligned", REFERENCE_ALIGNED),
        ("double_gap", REFERENCE_DOUBLE_GAP),
        ("wider_gap", REFERENCE_WIDER),
        ("human_ahead", REFERENCE_HUMAN_AHEAD),
        ("undocumented", REFERENCE_UNDOCUMENTED),
    )
    groups: list[GroupLocation] = []
    for name, reference in catalog:
        mask = np.array(flags[name], dtype=bool)
        count = int(mask.sum())
        if count == 0:
            centroid = (0.0, 0.0)
        else:
            centroid = (
                float(coordinates[mask, 0].mean()),
                float(coordinates[mask, 1].mean()),
            )
        groups.append(
            GroupLocation(
                name=name,
                count=count,
                reference=reference,
                centroid_1=centroid[0],
                centroid_2=centroid[1],
                reproduced=count == reference,
            )
        )
    stacked = np.column_stack([np.asarray(mask, dtype=bool) for mask in flags.values()])
    outside = int(np.count_nonzero(~stacked.any(axis=1)))
    return tuple(groups), outside


def _separation(counties: Sequence[County], coordinates: FloatArray) -> float | None:
    flags = _situation_flags(counties)
    aligned = coordinates[np.array(flags["aligned"], dtype=bool), :2]
    double_gap = coordinates[np.array(flags["double_gap"], dtype=bool), :2]
    if len(aligned) < SMALL_CELL or len(double_gap) < SMALL_CELL:
        return None
    center_aligned = aligned.mean(axis=0)
    center_double = double_gap.mean(axis=0)
    distance = float(np.linalg.norm(center_aligned - center_double))
    rms_aligned = float(np.sqrt(np.mean(np.sum((aligned - center_aligned) ** 2, axis=1))))
    rms_double = float(np.sqrt(np.mean(np.sum((double_gap - center_double) ** 2, axis=1))))
    pooled = math.sqrt(
        (len(aligned) * rms_aligned**2 + len(double_gap) * rms_double**2)
        / (len(aligned) + len(double_gap))
    )
    if pooled == 0:
        return math.inf if distance > 0 else 0.0
    return distance / pooled


def _rare_leaders(contributions: Sequence[Contribution]) -> tuple[str, ...]:
    leaders: list[str] = []
    for axis in (1, 2):
        rows = [row for row in contributions if row.axis == axis]
        if not rows:
            continue
        leader = min(rows, key=lambda row: (-row.contribution, row.category_id))
        if leader.count < RARE_BELOW:
            leaders.append(leader.category_id)
    return tuple(leaders)


def _product(method: str, ratio: float | None) -> str:
    if method == "stop":
        return "stop"
    if method == "keep" and ratio is not None and ratio >= SEPARATION_ADVANCE:
        return "advance"
    return "investigate"


def _situation_flags(counties: Sequence[County]) -> dict[str, list[bool]]:
    flags: dict[str, list[bool]] = {
        "aligned": [],
        "double_gap": [],
        "wider_gap": [],
        "human_ahead": [],
        "undocumented": [],
    }
    for county in counties:
        published = county.human_status == HUMAN_PUBLISHED
        absent = county.human_status == HUMAN_NONE
        established = county.tick_status == TICK_ESTABLISHED
        present = county.burgdorferi_status == PATHOGEN_PRESENT
        pathogen_blank = county.burgdorferi_status == NO_RECORDS
        tick_blank = county.tick_status == NO_RECORDS
        flags["aligned"].append(published and established and present)
        flags["double_gap"].append(absent and established and present)
        flags["wider_gap"].append(absent and established)
        flags["human_ahead"].append(published and pathogen_blank)
        flags["undocumented"].append(absent and tick_blank and pathogen_blank)
    return flags


def _frequencies(counties: Sequence[County]) -> tuple[CategoryCount, ...]:
    rows: list[CategoryCount] = []
    fields = (
        ("rucc", [str(row.rucc) for row in counties]),
        ("human_status", [row.human_status for row in counties]),
        ("scapularis_status", [row.scapularis_status for row in counties]),
        ("pacificus_status", [row.pacificus_status for row in counties]),
        ("burgdorferi_status", [row.burgdorferi_status for row in counties]),
        ("tick_status", [row.tick_status for row in counties]),
    )
    for variable, values in fields:
        for level, count in sorted(Counter(values).items()):
            rows.append(CategoryCount(variable, level, count, "before_binning"))
    population = _digitize(
        np.array([row.population for row in counties]),
        np.array(FINE_POPULATION_EDGES, dtype=float),
        right=False,
    )
    svi = _digitize(np.array([row.svi for row in counties]), FINE_SVI_EDGES, right=True)
    rows.extend(_bin_counts("population", FINE_POPULATION_LABELS, population, "before_binning"))
    svi_labels = tuple(f"through_{edge:.1f}" for edge in FINE_SVI_EDGES) + ("through_1.0",)
    rows.extend(_bin_counts("svi_percentile", svi_labels, svi, "before_binning"))
    mca_population = _digitize(
        np.array([row.population for row in counties]),
        np.array(POPULATION_EDGES, dtype=float),
        right=False,
    )
    mca_svi = _digitize(np.array([row.svi for row in counties]), SVI_EDGES, right=True)
    rows.extend(_bin_counts("population_bin", POPULATION_LABELS, mca_population, "mca_bin"))
    rows.extend(_bin_counts("svi_bin", SVI_LABELS, mca_svi, "mca_bin"))
    return tuple(rows)


def _bin_counts(
    variable: str, labels: Sequence[str], codes: IntArray, stage: str
) -> list[CategoryCount]:
    tally = Counter(int(value) for value in codes.tolist())
    return [
        CategoryCount(variable, labels[index], tally.get(index, 0), stage)
        for index in range(len(labels))
    ]


def _phrase(category_ids: Sequence[str]) -> str:
    return " and ".join(PHRASES[category_id] for category_id in category_ids)


PHRASES = {
    "svi_bin=q1_low": "the low social-vulnerability quartile",
    "svi_bin=q2": "the second social-vulnerability quartile",
    "svi_bin=q3": "the third social-vulnerability quartile",
    "svi_bin=q4_high": "the high social-vulnerability quartile",
    "population_bin=lt_10k": "counties under 10 thousand people",
    "population_bin=10k_to_50k": "counties from 10 thousand to under 50 thousand people",
    "population_bin=50k_to_250k": "counties from 50 thousand to under 250 thousand people",
    "population_bin=ge_250k": "counties of 250 thousand people or more",
    "population_bin=10k_to_100k": "counties from 10 thousand to under 100 thousand people",
    "population_bin=100k_to_250k": "counties from 100 thousand to under 250 thousand people",
    "rucc=1": "rural-urban code 1, the largest metro counties",
    "rucc=2": "rural-urban code 2",
    "rucc=3": "rural-urban code 3",
    "rucc=4": "rural-urban code 4",
    "rucc=5": "rural-urban code 5",
    "rucc=6": "rural-urban code 6",
    "rucc=7": "rural-urban code 7",
    "rucc=8": "rural-urban code 8",
    "rucc=9": "rural-urban code 9, the most rural counties",
    "human_status=published_count_floor": "a published human floor",
    "human_status=no_county_linked_record": "no county-linked human record",
    "scapularis_status=Established": "an established blacklegged tick",
    "scapularis_status=Reported": "a reported blacklegged tick",
    "scapularis_status=No records": "no blacklegged-tick record",
    "scapularis_status=Unknown": "unknown blacklegged-tick status",
    "pacificus_status=Established": "an established western blacklegged tick",
    "pacificus_status=Reported": "a reported western blacklegged tick",
    "pacificus_status=No records": "no western-blacklegged-tick record",
    "pacificus_status=Unknown": "unknown western-blacklegged-tick status",
    "burgdorferi_status=Present": "a published pathogen record",
    "burgdorferi_status=No records": "no pathogen record",
    "burgdorferi_status=Unknown": "unknown pathogen status",
}


def _metric(name: str, value: float, count: int, dimensions: dict[str, str]) -> EdaMetric:
    if name.startswith("centroid"):
        unit = "coordinate"
    elif (
        "share" in name
        or name.endswith("ratio")
        or "spearman" in name
        or "procrustes" in name
        or name == "category_contribution"
    ):
        unit = "share"
    else:
        unit = "counties"
    return EdaMetric(
        metric_name=name,
        metric_value=value,
        n_underlying=count,
        geography_type="national",
        geography_id="US",
        dimensions=dimensions,
        unit=unit,
    )


def _county(raw: Mapping[str, object], *, scale_svi: bool) -> County:
    population = _float(raw.get("POPULATION"))
    svi = _float(raw.get("SVI_PERCENTILE"))
    rucc = _rucc(raw.get("RUCC_2023"))
    fips = _fips(raw.get("FIPS"))
    if population is None or svi is None or rucc is None or fips is None:
        raise CountyMcaError("a county field failed after the gate")
    if scale_svi:
        svi = svi / 100.0
    if not 0.0 <= svi <= 1.0:
        raise CountyMcaError("SVI percentile is outside the unit interval")
    return County(
        fips=fips,
        name=_text(raw.get("COUNTY")),
        state=_text(raw.get("STATE")),
        population=population,
        svi=svi,
        rucc=rucc,
        human_status=_text(raw.get("HUMAN_STATUS")),
        tick_status=_text(raw.get("TICK_STATUS")),
        scapularis_status=_text(raw.get("SCAPULARIS_STATUS")),
        pacificus_status=_text(raw.get("PACIFICUS_STATUS")),
        burgdorferi_status=_text(raw.get("BURGDORFERI_STATUS")),
    )


def _require_unit_interval(counties: Sequence[County]) -> None:
    if any(not 0.0 <= county.svi <= 1.0 for county in counties):
        raise CountyMcaError("SVI percentile is outside the unit interval")


def _digitize(
    values: FloatArray, edges: tuple[float, ...] | FloatArray, *, right: bool
) -> IntArray:
    return np.digitize(values, np.array(edges, dtype=float), right=right).astype(np.int64)


def _code(values: Sequence[str], ordered: Sequence[str]) -> tuple[IntArray, tuple[str, ...]]:
    index = {level: position for position, level in enumerate(ordered)}
    return np.array([index[value] for value in values], dtype=np.int64), tuple(ordered)


def _rank(values: FloatArray) -> FloatArray:
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(values.shape, dtype=np.float64)
    sorted_values = values[order]
    start = 0
    while start < values.size:
        stop = start + 1
        while stop < values.size and sorted_values[stop] == sorted_values[start]:
            stop += 1
        ranks[order[start:stop]] = 0.5 * (start + stop - 1)
        start = stop
    return ranks


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        try:
            number = float(str(value))
        except ValueError:
            return None
    if not math.isfinite(number):
        return None
    return number


def _population_ok(value: object) -> bool:
    number = _float(value)
    return number is not None and number > 0


def _rucc(value: object) -> int | None:
    number = _float(value)
    if number is None or not number.is_integer():
        return None
    code = int(number)
    if code < 1 or code > 9:
        return None
    return code


def _fips(value: object) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        text = f"{value:05d}"
    else:
        text = str(value).strip()
        if text.isdigit() and len(text) < 5:
            text = text.zfill(5)
    if len(text) != 5 or not text.isdigit():
        return None
    return text


def query_record(
    name: str, sql_text: str, rows: int, elapsed_ms: int, query_id: str | None
) -> QueryRecord:
    """Build one query-log row. ``name`` is accepted so callers can label the capture."""
    del name
    return QueryRecord(
        sql_text=sql_text,
        rows_returned=rows,
        elapsed_ms=elapsed_ms,
        snowflake_query_id=query_id,
    )
