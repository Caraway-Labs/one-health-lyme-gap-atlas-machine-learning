"""Visual diagnostics for issue 117.

The functions here do not open Snowflake. County rows stay in memory. Aggregate
lab records suppress a count from 1 to 10. Spearman reuses the #114 wrapper of
the #116 rank coefficient. The climate parse reuses the #107 value expression.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import numpy as np

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.county_distributions import (
    ATLAS,
    CLIMATE,
    _climate_eligible_sql,
    _climate_value_sql,
    climate_means_sql,
)
from lyme_gap_atlas_ml.coverage_audit import CENSUS_REGIONS
from lyme_gap_atlas_ml.cross_domain import (
    CROSS_FEATURES,
    County,
    _frame,
    spearman_arrays,
)
from lyme_gap_atlas_ml.cross_domain import (
    SPEC_ID as CROSS_DOMAIN_SPEC_ID,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import (
    CorrelationRecord,
    FindingRecord,
    MissingnessRecord,
)
from lyme_gap_atlas_ml.snowflake.eda_writer import SMALL_CELL_MINIMUM, EdaMetric
from lyme_gap_atlas_ml.test_selection import HUMAN_NONE, HUMAN_PUBLISHED

SPEC_ID = "117-visual-diagnostics/v1"
SEED = 1172026
MIN_DAYS = 20
MIN_COHORT = 500
HEX_SIZE = 0.12
OVERFLOW_LIMIT = 0.20
TAVG_MIN = -20.0
TAVG_MAX = 20.0
PRCP_MIN = 0.0
PRCP_MAX = 12.0
TAVG_EDGES = tuple(range(-20, 22, 2))
PRCP_EDGES = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0)
COEFFICIENT_GAP = 0.10
PANEL_T_GAP = 2.0
PANEL_P_GAP = 0.5
BLOCK_ABS = 0.40
BLOCK_LENGTH = 3
WIDE_RANGE = 10.0
WIDE_DAYS = 15
MIN_STATES_PER_DAY = 10
NATIONAL_RANGE = 5.0
COLDEST_STATES = 3
MIN_DAYS_IN_SERIES = 2
TAVG_MEASURE = "nclimgrid_tavg_county_day"
PRCP_MEASURE = "nclimgrid_prcp_county_day"
QUERY_NAMES = ("release_identity", "cohort_rows", "climate_means", "state_day_temperature")
SOURCE_OBJECTS = (
    "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V",
    ATLAS,
    CLIMATE,
)
_SQRT3 = math.sqrt(3)
Vector = np.ndarray[Any, Any]


class VisualDiagnosticsError(ValueError):
    """A frozen gate or an input shape is not usable."""


@dataclass(frozen=True)
class HexCell:
    q: int
    r: int
    n: int
    center_t: float
    center_p: float


@dataclass(frozen=True)
class HexPanel:
    label: str
    n: int
    modal: HexCell | None


@dataclass(frozen=True)
class HistogramBin:
    left: float
    right: float
    n: int


@dataclass(frozen=True)
class HexResult:
    estimable: bool
    reason: str
    n: int
    overflow_n: int
    spearman: float | None
    pearson: float | None
    temperature_bins: tuple[HistogramBin, ...]
    precipitation_bins: tuple[HistogramBin, ...]
    joint_mode_differs: bool
    coefficient_gap: bool
    panel_shift: bool
    useful: bool
    cohort: HexPanel
    published: HexPanel
    unpublished: HexPanel
    cells: tuple[HexCell, ...]
    published_cells: tuple[HexCell, ...]
    unpublished_cells: tuple[HexCell, ...]


@dataclass(frozen=True)
class HeatResult:
    estimable: bool
    order: tuple[str, ...]
    rho: tuple[tuple[float | None, ...], ...]
    pair_n: tuple[tuple[int, ...], ...]
    block: tuple[str, ...]
    useful: bool
    missing: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class StateDay:
    state: str
    region: str
    day: date
    mean: float
    n: int


@dataclass(frozen=True)
class TimeResult:
    estimable: bool
    reason: str
    day_count: int
    wide_days: int
    national_range: float | None
    coldest_states: tuple[str, ...]
    useful: bool
    rows: tuple[StateDay, ...]
    national: tuple[tuple[date, float, int], ...]


@dataclass(frozen=True)
class Spot:
    label: str
    fips: str
    name: str
    state: str
    human: str
    tick: str
    pathogen: str
    tavg_days: int | None
    prcp_days: int | None


@dataclass(frozen=True)
class Analysis:
    hexbin: HexResult
    heatmap: HeatResult
    time: TimeResult
    importance_estimable: bool
    importance_reason: str
    disposition: str
    spots: tuple[Spot, ...]
    cohort_n: int
    published_n: int
    unpublished_n: int
    tavg_ready_n: int
    prcp_ready_n: int


def state_day_sql() -> str:
    """Aggregate eligible January temperature to state and day. No county name."""
    value = _climate_value_sql()
    eligible = _climate_eligible_sql()
    return f"""
SELECT
    ATLAS.STATE AS STATE,
    CAST(DAYS.PERIOD_START AS DATE) AS DAY,
    AVG(DAYS.VAL) AS MEAN_VALUE,
    COUNT(*) AS N
FROM (
    SELECT
        COUNTY_FIPS,
        PERIOD_START,
        {value} AS VAL
    FROM {CLIMATE}
    WHERE MEASURE_ID = '{TAVG_MEASURE}'
      AND VALUE_STATE IN ('OBSERVED', 'ZERO')
      AND {eligible}
) AS DAYS
JOIN {ATLAS} AS ATLAS
    ON ATLAS.FIPS = DAYS.COUNTY_FIPS
GROUP BY ATLAS.STATE, CAST(DAYS.PERIOD_START AS DATE)
""".strip()


def load_visual_queries(text: str) -> dict[str, str]:
    """Split the issue 117 validation file and reject unsafe SQL."""
    queries = load_marked_queries(text, QUERY_NAMES)
    if queries["climate_means"] != climate_means_sql():
        raise VisualDiagnosticsError("climate mean SQL drifted from the #107 helper")
    if queries["state_day_temperature"] != state_day_sql():
        raise VisualDiagnosticsError("state-day SQL drifted from the registered helper")
    return queries


def axial_round(q: float, r: float) -> tuple[int, int]:
    """Round fractional axial coordinates to the nearest hex."""
    x = q
    z = r
    y = -x - z
    rx = int(round(x))
    ry = int(round(y))
    rz = int(round(z))
    x_diff = abs(rx - x)
    y_diff = abs(ry - y)
    z_diff = abs(rz - z)
    if x_diff > y_diff and x_diff > z_diff:
        rx = -ry - rz
    elif y_diff > z_diff:
        ry = -rx - rz
    else:
        rz = -rx - ry
    return rx, rz


def pixel_to_axial(x: float, y: float, size: float = HEX_SIZE) -> tuple[int, int]:
    """Map a point in the unit square to a pointy-top hex."""
    q = ((_SQRT3 / 3.0) * x - (1.0 / 3.0) * y) / size
    r = ((2.0 / 3.0) * y) / size
    return axial_round(q, r)


def axial_to_pixel(q: int, r: int, size: float = HEX_SIZE) -> tuple[float, float]:
    """Map a hex back to the unit square."""
    x = size * (_SQRT3 * q + (_SQRT3 / 2.0) * r)
    y = size * (1.5 * r)
    return x, y


def average_linkage_order(distance: Vector) -> tuple[int, ...]:
    """UPGMA leaf order. Ties merge the lower cluster id first."""
    width = int(distance.shape[0])
    if distance.shape != (width, width):
        raise VisualDiagnosticsError("distance matrix is not square")
    clusters: dict[int, tuple[int, ...]] = {index: (index,) for index in range(width)}
    active = list(range(width))
    dist: dict[tuple[int, int], float] = {}
    for left in range(width):
        for right in range(left + 1, width):
            dist[(left, right)] = float(distance[left, right])

    def paired(left: int, right: int) -> float:
        key = (left, right) if left < right else (right, left)
        return dist[key]

    next_id = width
    while len(active) > 1:
        best: tuple[int, int] | None = None
        best_key: tuple[float, int, int] | None = None
        for index, left in enumerate(active):
            for right in active[index + 1 :]:
                low, high = (left, right) if left < right else (right, left)
                key = (paired(left, right), low, high)
                if best_key is None or key < best_key:
                    best_key = key
                    best = (low, high)
        if best is None:
            break
        left, right = best
        left_n = len(clusters[left])
        right_n = len(clusters[right])
        merged = clusters[left] + clusters[right]
        new_id = next_id
        next_id += 1
        for other in active:
            if other in (left, right):
                continue
            value = (paired(left, other) * left_n + paired(right, other) * right_n) / (
                left_n + right_n
            )
            pair = (new_id, other) if new_id < other else (other, new_id)
            dist[pair] = value
        clusters[new_id] = merged
        active = [item for item in active if item not in (left, right)]
        active.append(new_id)
    return clusters[active[0]]


def outside_product_mode(modal_q: int, modal_r: int, margin_q: int, margin_r: int) -> bool:
    """True when the joint modal hex is not the product of the axial margins."""
    return (modal_q, modal_r) != (margin_q, margin_r)


def analyze(
    counties: Sequence[County],
    climate_means: Sequence[Mapping[str, object]],
    state_days: Sequence[Mapping[str, object]],
) -> Analysis:
    """Apply the frozen visual rules. Do not change a threshold from a result."""
    if not counties:
        raise VisualDiagnosticsError("county cohort is empty")
    days = _climate_days(climate_means)
    hexbin = _hexbin(counties, days)
    heatmap = _heatmap(counties)
    time = _time(state_days)
    disposition = _disposition(hexbin, heatmap, time)
    return Analysis(
        hexbin=hexbin,
        heatmap=heatmap,
        time=time,
        importance_estimable=False,
        importance_reason=(
            "No approved fitted model with a valid held-out evaluation is in scope. "
            f"{CROSS_DOMAIN_SPEC_ID} PCA is an in-sample variance split, not held-out "
            "feature contribution. The stored tier review batch is not used."
        ),
        disposition=disposition,
        spots=_spots(counties, days),
        cohort_n=len(counties),
        published_n=sum(county.human == HUMAN_PUBLISHED for county in counties),
        unpublished_n=sum(county.human == HUMAN_NONE for county in counties),
        tavg_ready_n=sum(_ready(days.get(county.fips, {}), TAVG_MEASURE) for county in counties),
        prcp_ready_n=sum(_ready(days.get(county.fips, {}), PRCP_MEASURE) for county in counties),
    )


def lab_metrics(result: Analysis) -> tuple[EdaMetric, ...]:
    """Aggregate metrics only. A state-day under 11 counties is suppressed by the writer."""
    rows: list[EdaMetric] = [
        _metric("hex_cohort_n", result.cohort_n, result.hexbin.n, unit="counties"),
        _metric("hex_overflow_n", result.cohort_n, result.hexbin.overflow_n, unit="counties"),
        _metric("hex_spearman", result.cohort_n, result.hexbin.spearman, unit="coefficient"),
        _metric("hex_pearson", result.cohort_n, result.hexbin.pearson, unit="coefficient"),
        _metric("hex_useful", result.cohort_n, 1 if result.hexbin.useful else 0, unit="flag"),
        _metric("heat_useful", result.cohort_n, 1 if result.heatmap.useful else 0, unit="flag"),
        _metric("time_useful", result.cohort_n, 1 if result.time.useful else 0, unit="flag"),
        _metric("time_wide_days", result.cohort_n, result.time.wide_days, unit="days"),
        _metric(
            "time_national_range_c",
            result.cohort_n,
            result.time.national_range,
            unit="celsius",
        ),
        _metric(
            "time_coldest_state_count",
            result.cohort_n,
            len(result.time.coldest_states),
            unit="states",
        ),
        _metric("importance_estimable", result.cohort_n, 0, unit="flag"),
    ]
    for row in result.time.rows:
        rows.append(
            EdaMetric(
                metric_name="state_day_tavg_c",
                n_underlying=row.n,
                metric_value=row.mean,
                geography_type="state",
                geography_id=row.state,
                period_start=row.day,
                period_end=row.day,
                unit="celsius",
            )
        )
    for day, mean, count in result.time.national:
        rows.append(
            EdaMetric(
                metric_name="national_day_tavg_c",
                n_underlying=count,
                metric_value=mean,
                geography_type="national",
                geography_id="US",
                period_start=day,
                period_end=day,
                unit="celsius",
            )
        )
    return tuple(rows)


def lab_correlations(result: Analysis) -> tuple[CorrelationRecord, ...]:
    """Pairwise Spearman for the #114 columns, plus the climate-pair baselines."""
    rows: list[CorrelationRecord] = []
    names = CROSS_FEATURES
    for left in range(len(names)):
        for right in range(left + 1, len(names)):
            rows.append(
                CorrelationRecord(
                    var_a=names[left],
                    var_b=names[right],
                    method="spearman",
                    n=result.heatmap.pair_n[left][right],
                    coefficient=result.heatmap.rho[left][right],
                )
            )
    rows.append(
        CorrelationRecord(
            var_a="january_tavg_c",
            var_b="january_prcp_mm",
            method="spearman",
            n=result.hexbin.n,
            coefficient=result.hexbin.spearman,
        )
    )
    rows.append(
        CorrelationRecord(
            var_a="january_tavg_c",
            var_b="january_prcp_mm",
            method="pearson_baseline",
            n=result.hexbin.n,
            coefficient=result.hexbin.pearson,
        )
    )
    return tuple(rows)


def lab_missingness(result: Analysis) -> tuple[MissingnessRecord, ...]:
    """Null counts for the #114 columns. Climate shortfalls use the atlas denominator."""
    rows = [
        MissingnessRecord(
            source_object=ATLAS,
            column_name=name,
            missing_n=count,
            total_n=result.cohort_n,
        )
        for name, count in result.heatmap.missing
    ]
    short_t = result.cohort_n - result.tavg_ready_n
    short_p = result.cohort_n - result.prcp_ready_n
    rows.append(
        MissingnessRecord(
            source_object=CLIMATE,
            column_name="JANUARY_TAVG_C",
            missing_n=max(short_t, 0),
            total_n=result.cohort_n,
        )
    )
    rows.append(
        MissingnessRecord(
            source_object=CLIMATE,
            column_name="JANUARY_PRCP_MM",
            missing_n=max(short_p, 0),
            total_n=result.cohort_n,
        )
    )
    return tuple(rows)


def lab_findings(result: Analysis) -> tuple[FindingRecord, ...]:
    """Aggregate statements. County identifiers stay out of these sentences."""
    return (
        FindingRecord(
            topic="climate hexbin",
            statement=_hex_statement(result.hexbin),
            disposition="keep" if result.hexbin.useful else "revise",
            n_underlying=result.cohort_n,
            effect_size=result.hexbin.spearman,
            evidence={
                "estimable": result.hexbin.estimable,
                "useful": result.hexbin.useful,
                "joint_mode_differs": result.hexbin.joint_mode_differs,
                "coefficient_gap": result.hexbin.coefficient_gap,
                "panel_shift": result.hexbin.panel_shift,
            },
        ),
        FindingRecord(
            topic="correlation heatmap",
            statement=_heat_statement(result.heatmap),
            disposition="keep" if result.heatmap.useful else "revise",
            n_underlying=result.cohort_n,
            evidence={"useful": result.heatmap.useful, "block_length": len(result.heatmap.block)},
        ),
        FindingRecord(
            topic="state day temperature",
            statement=_time_statement(result.time),
            disposition="keep" if result.time.useful else "revise",
            n_underlying=result.cohort_n,
            effect_size=result.time.national_range,
            evidence={
                "estimable": result.time.estimable,
                "useful": result.time.useful,
                "wide_days": result.time.wide_days,
                "coldest_state_count": len(result.time.coldest_states),
            },
        ),
        FindingRecord(
            topic="feature contribution",
            statement=result.importance_reason,
            disposition="stop",
            n_underlying=result.cohort_n,
            evidence={"estimable": False},
        ),
        FindingRecord(
            topic="visual panel",
            statement=_panel_statement(result),
            disposition=result.disposition,
            n_underlying=result.cohort_n,
            evidence={
                "hex_useful": result.hexbin.useful,
                "heat_useful": result.heatmap.useful,
                "time_useful": result.time.useful,
            },
        ),
    )


def _metric(
    name: str,
    n: int,
    value: float | int | None,
    *,
    unit: str,
) -> EdaMetric:
    return EdaMetric(
        metric_name=name,
        n_underlying=n,
        metric_value=value,
        geography_type="national",
        geography_id="US",
        unit=unit,
    )


def _disposition(hexbin: HexResult, heatmap: HeatResult, time: TimeResult) -> str:
    estimable = (hexbin.estimable, heatmap.estimable, time.estimable)
    if not any(estimable):
        return "stop"
    useful = sum((hexbin.useful, heatmap.useful, time.useful))
    if useful >= 2:
        return "keep"
    return "revise"


def _climate_days(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, tuple[float, int]]]:
    found: dict[str, dict[str, tuple[float, int]]] = defaultdict(dict)
    for row in rows:
        fips = _fips(row.get("COUNTY_FIPS"))
        measure = _text(row.get("MEASURE_ID"))
        if measure not in (TAVG_MEASURE, PRCP_MEASURE):
            continue
        found[fips][measure] = (_number(row.get("MEAN_VALUE")), _whole(row.get("N")))
    return found


def _hexbin(
    counties: Sequence[County],
    days: Mapping[str, Mapping[str, tuple[float, int]]],
) -> HexResult:
    eligible = [
        county
        for county in counties
        if _ready(days.get(county.fips, {}), TAVG_MEASURE)
        and _ready(days.get(county.fips, {}), PRCP_MEASURE)
    ]
    temperatures = np.array(
        [days[county.fips][TAVG_MEASURE][0] for county in eligible], dtype=float
    )
    precipitation = np.array(
        [days[county.fips][PRCP_MEASURE][0] for county in eligible], dtype=float
    )
    labels = [county.human for county in eligible]
    n = len(eligible)
    inside = _inside(temperatures, precipitation)
    overflow_n = n - int(inside.sum())
    reason = "estimable"
    estimable = True
    if n < MIN_COHORT:
        estimable = False
        reason = "fewer than 500 counties have 20 eligible days on both measures"
    elif n > 0 and overflow_n / n > OVERFLOW_LIMIT:
        estimable = False
        reason = "more than 20 percent of the county means fall outside the frozen extent"
    spearman = _pair_spearman(temperatures, precipitation)
    pearson = _pearson(temperatures, precipitation)
    cells = _cells(temperatures[inside], precipitation[inside])
    cohort = HexPanel("all eligible", n, _modal(cells))
    published_mask = np.array([label == HUMAN_PUBLISHED for label in labels], dtype=bool) & inside
    unpublished_mask = np.array([label == HUMAN_NONE for label in labels], dtype=bool) & inside
    published_cells = _cells(temperatures[published_mask], precipitation[published_mask])
    unpublished_cells = _cells(temperatures[unpublished_mask], precipitation[unpublished_mask])
    published = HexPanel(
        "published floor",
        int(np.array([label == HUMAN_PUBLISHED for label in labels]).sum()),
        _modal(published_cells),
    )
    unpublished = HexPanel(
        "no county-linked record",
        int(np.array([label == HUMAN_NONE for label in labels]).sum()),
        _modal(unpublished_cells),
    )
    joint = False
    if cohort.modal is not None:
        margin_q, margin_r = _axial_margins(cells)
        joint = outside_product_mode(cohort.modal.q, cohort.modal.r, margin_q, margin_r)
    gap = (
        spearman is not None and pearson is not None and abs(spearman - pearson) >= COEFFICIENT_GAP
    )
    shift = _panel_shift(published.modal, unpublished.modal)
    useful = estimable and (joint or gap or shift)
    return HexResult(
        estimable=estimable,
        reason=reason,
        n=n,
        overflow_n=overflow_n,
        spearman=spearman,
        pearson=pearson,
        temperature_bins=_histogram(temperatures[inside], TAVG_EDGES),
        precipitation_bins=_histogram(precipitation[inside], PRCP_EDGES),
        joint_mode_differs=joint,
        coefficient_gap=gap,
        panel_shift=shift,
        useful=useful,
        cohort=cohort,
        published=published,
        unpublished=unpublished,
        cells=tuple(cells),
        published_cells=tuple(published_cells),
        unpublished_cells=tuple(unpublished_cells),
    )


def _ready(measures: Mapping[str, tuple[float, int]], measure: str) -> bool:
    found = measures.get(measure)
    return found is not None and found[1] >= MIN_DAYS and math.isfinite(found[0])


def _inside(temperatures: Vector, precipitation: Vector) -> Vector:
    if temperatures.size == 0:
        return np.zeros(0, dtype=bool)
    return (
        (temperatures >= TAVG_MIN)
        & (temperatures <= TAVG_MAX)
        & (precipitation >= PRCP_MIN)
        & (precipitation <= PRCP_MAX)
    )


def _cells(temperatures: Vector, precipitation: Vector) -> list[HexCell]:
    counts: dict[tuple[int, int], int] = defaultdict(int)
    for temperature, rain in zip(temperatures.tolist(), precipitation.tolist(), strict=True):
        x = (float(temperature) - TAVG_MIN) / (TAVG_MAX - TAVG_MIN)
        y = (float(rain) - PRCP_MIN) / (PRCP_MAX - PRCP_MIN)
        counts[pixel_to_axial(x, y)] += 1
    cells: list[HexCell] = []
    for (q, r), count in sorted(counts.items()):
        x, y = axial_to_pixel(q, r)
        cells.append(
            HexCell(
                q=q,
                r=r,
                n=count,
                center_t=TAVG_MIN + x * (TAVG_MAX - TAVG_MIN),
                center_p=PRCP_MIN + y * (PRCP_MAX - PRCP_MIN),
            )
        )
    return cells


def _modal(cells: Sequence[HexCell]) -> HexCell | None:
    publishable = [cell for cell in cells if cell.n >= SMALL_CELL_MINIMUM]
    if not publishable:
        return None
    return min(publishable, key=lambda cell: (-cell.n, cell.q, cell.r))


def _axial_margins(cells: Sequence[HexCell]) -> tuple[int, int]:
    q_counts: dict[int, int] = defaultdict(int)
    r_counts: dict[int, int] = defaultdict(int)
    for cell in cells:
        if cell.n < SMALL_CELL_MINIMUM:
            continue
        q_counts[cell.q] += cell.n
        r_counts[cell.r] += cell.n
    if not q_counts or not r_counts:
        raise VisualDiagnosticsError("axial margins require a publishable hex")
    margin_q = min(q_counts.items(), key=lambda item: (-item[1], item[0]))[0]
    margin_r = min(r_counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return margin_q, margin_r


def _panel_shift(published: HexCell | None, unpublished: HexCell | None) -> bool:
    if published is None or unpublished is None:
        return False
    return (
        abs(published.center_t - unpublished.center_t) >= PANEL_T_GAP
        or abs(published.center_p - unpublished.center_p) >= PANEL_P_GAP
    )


def _histogram(values: Vector, edges: Sequence[float]) -> tuple[HistogramBin, ...]:
    bins: list[HistogramBin] = []
    for index, left in enumerate(edges[:-1]):
        right = float(edges[index + 1])
        if index == len(edges) - 2:
            count = int(((values >= left) & (values <= right)).sum())
        else:
            count = int(((values >= left) & (values < right)).sum())
        bins.append(HistogramBin(left=float(left), right=right, n=count))
    return tuple(bins)


def _pair_spearman(left: Vector, right: Vector) -> float | None:
    if left.size < 3:
        return None
    return spearman_arrays(left, right)


def _pearson(left: Vector, right: Vector) -> float | None:
    if left.size < 3 or np.unique(left).size < 2 or np.unique(right).size < 2:
        return None
    centered_left = left - float(left.mean())
    centered_right = right - float(right.mean())
    denom = math.sqrt(float((centered_left**2).sum()) * float((centered_right**2).sum()))
    if denom == 0:
        return None
    return float((centered_left * centered_right).sum() / denom)


def _heatmap(counties: Sequence[County]) -> HeatResult:
    frame = _frame(counties)
    names = CROSS_FEATURES
    width = len(names)
    rho = np.full((width, width), np.nan)
    pair_n = np.zeros((width, width), dtype=int)
    columns = [frame.columns[name] for name in names]
    for left in range(width):
        for right in range(left, width):
            mask = np.isfinite(columns[left]) & np.isfinite(columns[right])
            count = int(mask.sum())
            pair_n[left, right] = count
            pair_n[right, left] = count
            if left == right:
                rho[left, left] = 1.0 if count >= 3 else np.nan
                continue
            value = spearman_arrays(columns[left][mask], columns[right][mask])
            if value is not None:
                rho[left, right] = value
                rho[right, left] = value
    distance = np.ones((width, width), dtype=float)
    np.fill_diagonal(distance, 0.0)
    for left in range(width):
        for right in range(left + 1, width):
            value = rho[left, right]
            if pair_n[left, right] >= SMALL_CELL_MINIMUM and math.isfinite(float(value)):
                distance[left, right] = distance[right, left] = 1.0 - abs(float(value))
    order_index = average_linkage_order(distance)
    order = tuple(names[index] for index in order_index)
    block = _new_block(order_index, rho, pair_n)
    missing = tuple((name, int((~np.isfinite(frame.columns[name])).sum())) for name in names)
    estimable = bool(np.any(np.triu(pair_n, k=1) >= SMALL_CELL_MINIMUM))
    return HeatResult(
        estimable=estimable,
        order=order,
        rho=_matrix(rho),
        pair_n=tuple(tuple(int(value) for value in row) for row in pair_n),
        block=tuple(names[index] for index in block),
        useful=estimable and len(block) >= BLOCK_LENGTH,
        missing=missing,
    )


def _new_block(order: Sequence[int], rho: Vector, pair_n: Vector) -> tuple[int, ...]:
    width = len(order)
    definition = list(range(width))
    for length in range(width, BLOCK_LENGTH - 1, -1):
        for start in range(width - length + 1):
            block = tuple(order[start : start + length])
            if not _tight(block, rho, pair_n):
                continue
            if _contiguous(definition, set(block)) or _contiguous(
                list(reversed(definition)), set(block)
            ):
                continue
            return block
    return ()


def _tight(block: Sequence[int], rho: Vector, pair_n: Vector) -> bool:
    for index, left in enumerate(block):
        for right in block[index + 1 :]:
            value = float(rho[left, right])
            if pair_n[left, right] < SMALL_CELL_MINIMUM or not math.isfinite(value):
                return False
            if abs(value) < BLOCK_ABS:
                return False
    return True


def _contiguous(order: Sequence[int], wanted: set[int]) -> bool:
    for start in range(len(order)):
        for end in range(start + 1, len(order) + 1):
            if set(order[start:end]) == wanted:
                return True
    return False


def _matrix(values: Vector) -> tuple[tuple[float | None, ...], ...]:
    rows: list[tuple[float | None, ...]] = []
    for row in values.tolist():
        rows.append(
            tuple(None if not math.isfinite(float(value)) else float(value) for value in row)
        )
    return tuple(rows)


def _time(rows: Sequence[Mapping[str, object]]) -> TimeResult:
    merged = _merge_state_days(rows)
    days = sorted({row.day for row in merged})
    if len(days) < MIN_DAYS_IN_SERIES:
        return TimeResult(
            estimable=False,
            reason="fewer than two distinct climate days support a county-by-time view",
            day_count=len(days),
            wide_days=0,
            national_range=None,
            coldest_states=(),
            useful=False,
            rows=tuple(merged),
            national=(),
        )
    wide = 0
    coldest: list[str] = []
    national: list[tuple[date, float, int]] = []
    for day in days:
        publishable = [row for row in merged if row.day == day and row.n >= SMALL_CELL_MINIMUM]
        if len(publishable) < MIN_STATES_PER_DAY:
            continue
        means = [row.mean for row in publishable]
        if max(means) - min(means) > WIDE_RANGE:
            wide += 1
        coldest.append(min(publishable, key=lambda row: (row.mean, row.state)).state)
        count = sum(row.n for row in publishable)
        mean = sum(row.mean * row.n for row in publishable) / count
        national.append((day, mean, count))
    national_range = None
    if len(national) >= MIN_DAYS_IN_SERIES:
        series = [mean for _day, mean, _count in national]
        national_range = max(series) - min(series)
    distinct = tuple(sorted(set(coldest)))
    useful = (
        wide >= WIDE_DAYS
        and national_range is not None
        and national_range > NATIONAL_RANGE
        and len(distinct) >= COLDEST_STATES
    )
    return TimeResult(
        estimable=True,
        reason="estimable",
        day_count=len(days),
        wide_days=wide,
        national_range=national_range,
        coldest_states=distinct,
        useful=useful,
        rows=tuple(merged),
        national=tuple(national),
    )


def _merge_state_days(rows: Sequence[Mapping[str, object]]) -> list[StateDay]:
    totals: dict[tuple[str, date], tuple[float, int]] = {}
    for row in rows:
        state = _text(row.get("STATE"))
        if state not in CENSUS_REGIONS:
            raise VisualDiagnosticsError("state is outside the Census map")
        day = _as_date(row.get("DAY"))
        count = _whole(row.get("N"))
        mean = _number(row.get("MEAN_VALUE"))
        total, seen = totals.get((state, day), (0.0, 0))
        totals[(state, day)] = (total + mean * count, seen + count)
    merged: list[StateDay] = []
    for (state, day), (total, count) in sorted(totals.items()):
        if count <= 0:
            continue
        merged.append(
            StateDay(
                state=state,
                region=CENSUS_REGIONS[state],
                day=day,
                mean=total / count,
                n=int(count),
            )
        )
    return merged


def _spots(
    counties: Sequence[County],
    days: Mapping[str, Mapping[str, tuple[float, int]]],
) -> tuple[Spot, ...]:
    return (
        _spot("published_floor", counties, days, lambda county: county.human == HUMAN_PUBLISHED),
        _spot("no_county_record", counties, days, lambda county: county.human == HUMAN_NONE),
        _spot("outside_tick_scope", counties, days, lambda county: not county.in_scope),
    )


def _spot(
    label: str,
    counties: Sequence[County],
    days: Mapping[str, Mapping[str, tuple[float, int]]],
    predicate: Callable[[County], bool],
) -> Spot:
    chosen = [county for county in counties if predicate(county)]
    if not chosen:
        raise VisualDiagnosticsError(f"spot check {label} has no county")
    county = min(chosen, key=lambda item: item.fips)
    measures = days.get(county.fips, {})
    return Spot(
        label=label,
        fips=county.fips,
        name=county.name,
        state=county.state,
        human=county.human,
        tick=county.tick,
        pathogen=county.pathogen,
        tavg_days=measures[TAVG_MEASURE][1] if TAVG_MEASURE in measures else None,
        prcp_days=measures[PRCP_MEASURE][1] if PRCP_MEASURE in measures else None,
    )


def _hex_statement(result: HexResult) -> str:
    if not result.estimable:
        return (
            "The January temperature and precipitation hexbin is not estimable. "
            + result.reason
            + ". No missing climate day was filled with zero."
        )
    flag = "meets" if result.useful else "does not meet"
    return (
        "The January county-mean temperature and precipitation hexbin "
        f"{flag} the frozen usefulness rule. "
        f"Spearman is {_fmt(result.spearman)} and the Pearson baseline is {_fmt(result.pearson)}. "
        "A published human floor remains a surveillance lower bound beside this climate month."
    )


def _heat_statement(result: HeatResult) -> str:
    if result.useful:
        names = ", ".join(result.block)
        return (
            "Average linkage on one minus absolute Spearman groups a block that is not "
            f"contiguous in the frozen feature order: {names}. "
            "Pairwise n is on the heatmap. This does not refit the cross-domain PCA."
        )
    return (
        "Average linkage on one minus absolute Spearman does not reveal a block of three "
        "or more features that the frozen definition order does not already place together. "
        "The cross-domain table remains the baseline."
    )


def _time_statement(result: TimeResult) -> str:
    if not result.estimable:
        return (
            "No county-by-time surveillance panel is available. "
            + result.reason
            + ". Historical CDC objects were not read. Issue 112 was not run."
        )
    flag = "meets" if result.useful else "does not meet"
    return (
        "The state-by-day January temperature heatmap "
        f"{flag} the frozen usefulness rule against the national daily mean "
        "and against a single monthly state mean. "
        f"Publishable days with a cross-state range above 10 C: {result.wide_days}. "
        "Cells under 11 counties are omitted. County names are not drawn."
    )


def _panel_statement(result: Analysis) -> str:
    return (
        f"Disposition is {result.disposition}. "
        "Feature contribution stays not estimable because no approved held-out model was fit. "
        "Counts are surveillance signals. No records and Unknown are not negatives. "
        "Missing is not zero."
    )


def _fmt(value: float | None) -> str:
    if value is None:
        return "not estimable"
    return f"{value:.4f}"


def _fips(value: object) -> str:
    if isinstance(value, str) and len(value.strip()) == 5 and value.strip().isdigit():
        return value.strip()
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 99999:
        return f"{value:05d}"
    raise VisualDiagnosticsError("county fips is missing")


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VisualDiagnosticsError("a required label is missing")
    return value.strip()


def _whole(value: object) -> int:
    if isinstance(value, bool):
        raise VisualDiagnosticsError("a count is missing")
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise VisualDiagnosticsError("a count is missing")


def _number(value: object) -> float:
    if value is None or isinstance(value, (bool, str, bytes)):
        raise VisualDiagnosticsError("a numeric value is missing")
    if isinstance(value, (int, float, Decimal)):
        number = float(value)
        if math.isfinite(number):
            return number
    raise VisualDiagnosticsError("a numeric value is missing")


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if type(value) is date:
        return value
    if isinstance(value, str) and len(value) >= 10:
        return date.fromisoformat(value[:10])
    raise VisualDiagnosticsError("state day is missing")
