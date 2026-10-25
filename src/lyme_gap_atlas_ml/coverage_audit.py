"""Assemble issue 109 coverage aggregates.

The functions here do not open Snowflake. They turn already-aggregated rows
into ML Lab records and chart frames. A 1-10 count is not copied into a statement.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from lyme_gap_atlas_ml.snowflake.eda_lab_writers import (
    ColumnProfileRecord,
    FindingRecord,
    MissingnessRecord,
    QueryRecord,
    prepare_missingness,
    prepare_query,
)
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric

PINNED_RELEASE_ID = "governed-2026-10-15-january-climate-prod"
PINNED_BUNDLE_SHA256 = "53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d"
REFERENCE_RELEASE_ID = "governed-2026-10-06-nlcd-demo-cohort"
REFERENCE_COUNTIES = 3144
REFERENCE_PUBLISHED_HUMAN_FLOOR = 651
REFERENCE_NO_COUNTY_LINKED_RECORD = 2493
SEED = 1092026
ATLAS = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V"
OBSERVATIONS = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V"
CLIMATE = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V"
RELEASE = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_RELEASE_V"
SOURCES = "ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_SOURCE_METADATA_V"
SOURCE_OBJECTS = (RELEASE, ATLAS, SOURCES, OBSERVATIONS, CLIMATE)
QUERY_NAMES = (
    "atlas_integrity",
    "release_identity",
    "source_vintages",
    "region_undocumented",
    "state_status",
    "joint_partition",
    "numeric_profile",
    "state_unallocated_profile",
    "categorical_levels",
    "geometry_null",
    "nlcd_coverage",
    "nlcd_county_total",
    "climate_coverage",
    "climate_status",
)
CENSUS_REGIONS = {
    "CT": "Northeast",
    "ME": "Northeast",
    "MA": "Northeast",
    "NH": "Northeast",
    "RI": "Northeast",
    "VT": "Northeast",
    "NJ": "Northeast",
    "NY": "Northeast",
    "PA": "Northeast",
    "IL": "Midwest",
    "IN": "Midwest",
    "MI": "Midwest",
    "OH": "Midwest",
    "WI": "Midwest",
    "IA": "Midwest",
    "KS": "Midwest",
    "MN": "Midwest",
    "MO": "Midwest",
    "NE": "Midwest",
    "ND": "Midwest",
    "SD": "Midwest",
    "DE": "South",
    "DC": "South",
    "FL": "South",
    "GA": "South",
    "MD": "South",
    "NC": "South",
    "SC": "South",
    "VA": "South",
    "WV": "South",
    "AL": "South",
    "KY": "South",
    "MS": "South",
    "TN": "South",
    "AR": "South",
    "LA": "South",
    "OK": "South",
    "TX": "South",
    "AZ": "West",
    "CO": "West",
    "ID": "West",
    "MT": "West",
    "NV": "West",
    "NM": "West",
    "UT": "West",
    "WY": "West",
    "AK": "West",
    "CA": "West",
    "HI": "West",
    "OR": "West",
    "WA": "West",
}
HEATMAP_REGIONS = ("Northeast", "Midwest", "South", "West")
HEATMAP_SIGNALS = (
    ("HUMAN_STATUS", "HUMAN_UNDOC_N"),
    ("CASE_COUNT_FLOOR_2023", "CASE_NULL_N"),
    ("INCIDENCE_FLOOR_2023", "INCIDENCE_NULL_N"),
    ("TICK_STATUS", "TICK_UNDOC_N"),
    ("SCAPULARIS_STATUS", "SCAPULARIS_UNDOC_N"),
    ("PACIFICUS_STATUS", "PACIFICUS_UNDOC_N"),
    ("BURGDORFERI_STATUS", "PATHOGEN_UNDOC_N"),
    ("SVI_PERCENTILE", "SVI_NULL_N"),
    ("UNINSURED_PERCENT", "UNINSURED_PERCENT_NULL_N"),
    ("UNINSURED_PERCENTILE", "UNINSURED_PERCENTILE_NULL_N"),
    ("POPULATION", "POPULATION_NULL_N"),
    ("RUCC_2023", "RUCC_NULL_N"),
)
NUMERIC_COLUMNS = (
    "POPULATION",
    "SVI_PERCENTILE",
    "UNINSURED_PERCENTILE",
    "UNINSURED_PERCENT",
    "RUCC_2023",
    "EVIDENCE_COMPLETENESS",
    "CASE_COUNT_FLOOR_2023",
    "INCIDENCE_FLOOR_2023",
)
CATEGORICAL_COLUMNS = (
    "HUMAN_STATUS",
    "TICK_STATUS",
    "SCAPULARIS_STATUS",
    "PACIFICUS_STATUS",
    "BURGDORFERI_STATUS",
    "RUCC_2023",
    "EVIDENCE_COMPLETENESS",
    "IN_CONTIGUOUS_TICK_SCOPE",
)
STATE_SIGNALS = frozenset({"HUMAN_STATUS", "TICK_STATUS", "BURGDORFERI_STATUS"})
PERCENTILE_SUFFIXES = ("P01", "P05", "P25", "P50", "P75", "P95", "P99")
_HUMAN_PERIOD = (date(2023, 1, 1), date(2023, 12, 31))
_CUMULATIVE_END = date(2025, 12, 31)
_QUERY_MARKER = re.compile(r"^-- @@ ([a-z0-9_]+)\s*$")


class CoverageAuditError(ValueError):
    """The coverage aggregates cannot be assembled."""


@dataclass(frozen=True)
class RegionRow:
    region: str
    total_n: int
    counts: Mapping[str, int]


@dataclass(frozen=True)
class FetchedCoverage:
    row_n: int
    fips_n: int
    fips_pattern_n: int
    release_n: int
    release_min: str
    release_max: str
    release_id: str
    bundle_sha256: str
    schema_version: str
    methodology_version: str
    scope: str
    sources: tuple[tuple[str, str], ...]
    levels: tuple[tuple[str, str | None, int], ...]
    regions: tuple[RegionRow, ...]
    states: tuple[tuple[str, str, str | None, int], ...]
    joints: tuple[tuple[str, str, str, int], ...]
    numeric: Mapping[str, object]
    unallocated: Mapping[str, object]
    geometry_null_n: int
    nlcd_measures: tuple[tuple[str, int, int], ...]
    nlcd_counties: int
    climate_row_n: int
    climate_county_n: int
    climate_measure_n: int
    climate_day_n: int
    climate_min: date | None
    climate_max: date | None
    climate_status: tuple[tuple[str | None, str | None, int, int], ...]


@dataclass(frozen=True)
class ChartFrames:
    heatmap_signals: tuple[str, ...]
    heatmap_regions: tuple[str, ...]
    heatmap_shares: tuple[tuple[float | None, ...], ...]
    bars: tuple[tuple[str, str, int], ...]
    vintages: tuple[tuple[str, str | None, str], ...]


@dataclass(frozen=True)
class CoverageAssembly:
    disposition: str
    metrics: tuple[EdaMetric, ...]
    missingness: tuple[MissingnessRecord, ...]
    profiles: tuple[ColumnProfileRecord, ...]
    findings: tuple[FindingRecord, ...]
    charts: ChartFrames


def load_queries(text: str) -> dict[str, str]:
    """Split the validation file on `-- @@ name` markers and reject unsafe SQL."""
    found: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = _QUERY_MARKER.match(line)
        if match is not None:
            current = match.group(1)
            if current in found:
                raise CoverageAuditError("duplicate query name")
            found[current] = []
            continue
        if current is not None and not line.startswith("--"):
            found[current].append(line)
    queries = {name: "\n".join(lines).strip() for name, lines in found.items()}
    if tuple(queries) != QUERY_NAMES:
        raise CoverageAuditError("query file does not match the registered names")
    region_sql = queries["region_undocumented"]
    for code, region in CENSUS_REGIONS.items():
        if f"WHEN '{code}' THEN '{region}'" not in region_sql:
            raise CoverageAuditError("Census region map is not in the query")
    for sql in queries.values():
        prepare_query(QueryRecord(sql_text=sql, rows_returned=1, elapsed_ms=0))
    return queries


def headline_disposition(
    *,
    counties: int,
    published_human_floor: int,
    no_county_linked_record: int,
    alignments_hold: bool,
) -> str:
    """Return keep when the October 13 headlines and the alignment checks both hold."""
    headlines = (
        counties == REFERENCE_COUNTIES
        and published_human_floor == REFERENCE_PUBLISHED_HUMAN_FLOOR
        and no_county_linked_record == REFERENCE_NO_COUNTY_LINKED_RECORD
    )
    if headlines and alignments_hold:
        return "keep"
    return "revise"


def check_integrity(fetched: FetchedCoverage) -> None:
    if fetched.release_id != PINNED_RELEASE_ID or fetched.bundle_sha256 != PINNED_BUNDLE_SHA256:
        raise CoverageAuditError("release pin mismatch")
    if fetched.release_min != PINNED_RELEASE_ID or fetched.release_max != PINNED_RELEASE_ID:
        raise CoverageAuditError("atlas release is not the pin")
    if fetched.release_n != 1 or fetched.row_n != fetched.fips_n:
        raise CoverageAuditError("county grain is not one row per FIPS")
    if fetched.fips_pattern_n != fetched.row_n:
        raise CoverageAuditError("FIPS pattern failed")
    if fetched.scope != "US_COUNTIES":
        raise CoverageAuditError("release scope is not US counties")
    regions = {row.region for row in fetched.regions}
    if "UNMAPPED" in regions or not set(HEATMAP_REGIONS).issubset(regions):
        raise CoverageAuditError("Census region bucket is incomplete")
    if sum(row.total_n for row in fetched.regions) != fetched.row_n:
        raise CoverageAuditError("regions do not partition counties")


def assemble_coverage(fetched: FetchedCoverage) -> CoverageAssembly:
    """Build lab rows from aggregates. Call check_integrity before writing them."""
    levels = _level_index(fetched.levels)
    published = _level_count(levels, "HUMAN_STATUS", "published_count_floor")
    unpublished = _level_count(levels, "HUMAN_STATUS", "no_county_linked_record")
    case_null = fetched.row_n - _required_int(fetched.numeric, "CASE_COUNT_FLOOR_2023_NON_NULL")
    incidence_null = fetched.row_n - _required_int(fetched.numeric, "INCIDENCE_FLOOR_2023_NON_NULL")
    if _sum_regions(fetched, "HUMAN_UNDOC_N") != unpublished:
        raise CoverageAuditError("region human gap does not match the status count")
    if _sum_regions(fetched, "CASE_NULL_N") != case_null:
        raise CoverageAuditError("region case-floor gap does not match the null count")
    tick_established = _level_count(levels, "TICK_STATUS", "Established")
    species_established = _level_count(levels, "SCAPULARIS_STATUS", "Established") + _level_count(
        levels, "PACIFICUS_STATUS", "Established"
    )
    alignments = (
        case_null == unpublished
        and incidence_null == unpublished
        and tick_established == species_established
    )
    disposition = headline_disposition(
        counties=fetched.row_n,
        published_human_floor=published,
        no_county_linked_record=unpublished,
        alignments_hold=alignments,
    )
    return CoverageAssembly(
        disposition=disposition,
        metrics=_metrics(fetched, levels),
        missingness=_missingness(fetched, levels),
        profiles=_profiles(fetched, levels),
        findings=_findings(
            fetched,
            disposition=disposition,
            published=published,
            unpublished=unpublished,
            case_null=case_null,
            incidence_null=incidence_null,
            tick_established=tick_established,
            species_established=species_established,
        ),
        charts=_charts(fetched, levels),
    )


def _metrics(
    fetched: FetchedCoverage,
    levels: Mapping[str, Mapping[str | None, int]],
) -> tuple[EdaMetric, ...]:
    rows: list[EdaMetric] = [_count_metric("county_count", fetched.row_n, "national", "US", {})]
    for column in CATEGORICAL_COLUMNS:
        for level, count in sorted(levels[column].items(), key=lambda item: str(item[0])):
            rows.append(
                _count_metric(
                    "status_county_count",
                    count,
                    "national",
                    "US",
                    {"signal": column, "status": _status_label(level)},
                    period=_period_for(column),
                )
            )
    for state, signal, status, count in fetched.states:
        if signal not in STATE_SIGNALS or state not in CENSUS_REGIONS:
            raise CoverageAuditError("unexpected state margin")
        rows.append(
            _count_metric(
                "status_county_count",
                count,
                "state",
                state,
                {"signal": signal, "status": _status_label(status)},
                period=_period_for(signal),
            )
        )
    for human, tick, pathogen, count in fetched.joints:
        rows.append(
            _count_metric(
                "joint_county_count",
                count,
                "national",
                "US",
                {"human_status": human, "tick_status": tick, "pathogen_status": pathogen},
            )
        )
    for signal, key in HEATMAP_SIGNALS:
        rows.append(
            _share_metric(signal, "US", _sum_regions(fetched, key), fetched.row_n, "national")
        )
        for region in fetched.regions:
            rows.append(
                _share_metric(
                    signal,
                    region.region,
                    region.counts[key],
                    region.total_n,
                    "census_region",
                )
            )
    for coverage, value_state, row_n, county_n in fetched.climate_status:
        rows.append(
            _count_metric(
                "climate_status_row_count",
                row_n,
                "national",
                "US",
                {
                    "coverage_status": coverage or "sql_null",
                    "value_state": value_state or "sql_null",
                },
            )
        )
        rows.append(
            _count_metric(
                "climate_status_county_count",
                county_n,
                "national",
                "US",
                {
                    "coverage_status": coverage or "sql_null",
                    "value_state": value_state or "sql_null",
                },
            )
        )
    return tuple(rows)


def _missingness(
    fetched: FetchedCoverage,
    levels: Mapping[str, Mapping[str | None, int]],
) -> tuple[MissingnessRecord, ...]:
    rows: list[MissingnessRecord] = []
    for column in CATEGORICAL_COLUMNS:
        rows.append(
            _gap(ATLAS, column, levels[column].get(None, 0), fetched.row_n, "national", "sql_null")
        )
    for column in NUMERIC_COLUMNS:
        null_n = fetched.row_n - _required_int(fetched.numeric, f"{column}_NON_NULL")
        rows.append(_gap(ATLAS, column, null_n, fetched.row_n, "national", "sql_null"))
    rows.append(
        _gap(
            ATLAS,
            "HUMAN_STATUS",
            _level_count(levels, "HUMAN_STATUS", "no_county_linked_record"),
            fetched.row_n,
            "national",
            "no_county_linked_record",
        )
    )
    for column in ("TICK_STATUS", "SCAPULARIS_STATUS", "PACIFICUS_STATUS", "BURGDORFERI_STATUS"):
        rows.append(
            _gap(
                ATLAS,
                column,
                _level_count(levels, column, "Unknown"),
                fetched.row_n,
                "national",
                "explicit_unknown",
            )
        )
        rows.append(
            _gap(
                ATLAS,
                column,
                _level_count(levels, column, "No records"),
                fetched.row_n,
                "national",
                "explicit_no_records",
            )
        )
    for signal, key in HEATMAP_SIGNALS:
        rows.append(
            _gap(
                ATLAS,
                signal,
                _sum_regions(fetched, key),
                fetched.row_n,
                "national",
                "undocumented",
            )
        )
        for region in fetched.regions:
            rows.append(
                _gap(
                    ATLAS,
                    signal,
                    region.counts[key],
                    region.total_n,
                    "census_region",
                    "undocumented",
                    region=region.region,
                )
            )
    rows.append(
        _gap(ATLAS, "GEOMETRY_JSON", fetched.geometry_null_n, fetched.row_n, "national", "sql_null")
    )
    rows.append(
        _gap(
            OBSERVATIONS,
            "NLCD_COUNTY",
            fetched.row_n - fetched.nlcd_counties,
            fetched.row_n,
            "national",
            "unselected",
        )
    )
    for measure, _row_n, county_n in fetched.nlcd_measures:
        rows.append(
            _gap(
                OBSERVATIONS,
                "NLCD_MEASURE",
                fetched.row_n - county_n,
                fetched.row_n,
                "national",
                "unselected",
                measure=measure,
            )
        )
    rows.append(
        _gap(
            CLIMATE,
            "COUNTY_FIPS",
            fetched.row_n - fetched.climate_county_n,
            fetched.row_n,
            "national",
            "unselected",
        )
    )
    return tuple(rows)


def _profiles(
    fetched: FetchedCoverage,
    levels: Mapping[str, Mapping[str | None, int]],
) -> tuple[ColumnProfileRecord, ...]:
    rows: list[ColumnProfileRecord] = []
    coded = {"RUCC_2023", "EVIDENCE_COMPLETENESS"}
    for column in CATEGORICAL_COLUMNS:
        if column in coded:
            continue
        present = levels[column]
        rows.append(
            ColumnProfileRecord(
                source_object=ATLAS,
                column_name=column,
                data_type="TEXT",
                row_count=fetched.row_n,
                null_count=present.get(None, 0),
                distinct_count=sum(1 for level in present if level is not None),
                top_values=tuple(
                    {"value": str(level), "n": count}
                    for level, count in present.items()
                    if level is not None
                ),
            )
        )
    for column in NUMERIC_COLUMNS:
        top = None
        if column in coded:
            top = tuple(
                {"value": str(level), "n": count}
                for level, count in levels[column].items()
                if level is not None
            )
        rows.append(
            ColumnProfileRecord(
                source_object=ATLAS,
                column_name=column,
                data_type="NUMBER",
                row_count=fetched.row_n,
                null_count=fetched.row_n - _required_int(fetched.numeric, f"{column}_NON_NULL"),
                distinct_count=_optional_int(fetched.numeric.get(f"{column}_DISTINCT")),
                min_value=_text_number(fetched.numeric.get(f"{column}_MIN")),
                max_value=_text_number(fetched.numeric.get(f"{column}_MAX")),
                mean_value=_optional_float(fetched.numeric.get(f"{column}_MEAN")),
                stddev_value=_optional_float(fetched.numeric.get(f"{column}_STDDEV")),
                percentiles={
                    suffix.lower(): _optional_float(fetched.numeric.get(f"{column}_{suffix}"))
                    for suffix in PERCENTILE_SUFFIXES
                },
                top_values=top,
            )
        )
    allocated = fetched.unallocated
    rows.append(
        ColumnProfileRecord(
            source_object=ATLAS,
            column_name="STATE_UNALLOCATED_RECORDS_2023",
            data_type="NUMBER",
            row_count=_required_int(allocated, "ROW_N"),
            null_count=_required_int(allocated, "NULL_N"),
            distinct_count=_optional_int(allocated.get("DISTINCT_N")),
            min_value=_text_number(allocated.get("MIN_VALUE")),
            max_value=_text_number(allocated.get("MAX_VALUE")),
            mean_value=_optional_float(allocated.get("MEAN_VALUE")),
            stddev_value=_optional_float(allocated.get("STDDEV_VALUE")),
            percentiles={
                suffix.lower(): _optional_float(allocated.get(suffix))
                for suffix in PERCENTILE_SUFFIXES
            },
            count_extremes=True,
        )
    )
    return tuple(rows)


def _findings(
    fetched: FetchedCoverage,
    *,
    disposition: str,
    published: int,
    unpublished: int,
    case_null: int,
    incidence_null: int,
    tick_established: int,
    species_established: int,
) -> tuple[FindingRecord, ...]:
    share = None if fetched.row_n == 0 else unpublished / fetched.row_n
    headline = FindingRecord(
        topic="headline_reproduction",
        statement=(
            f"The pinned release has {_fmt(fetched.row_n)} counties. "
            f"{_fmt(published)} have a published 2023 human count floor and "
            f"{_fmt(unpublished)} have no county-linked human record. "
            f"Epic #22 section 4.1, counted on {REFERENCE_RELEASE_ID}, reported "
            f"{_fmt(REFERENCE_COUNTIES)}, {_fmt(REFERENCE_PUBLISHED_HUMAN_FLOOR)}, and "
            f"{_fmt(REFERENCE_NO_COUNTY_LINKED_RECORD)}."
        ),
        disposition=disposition,
        n_underlying=fetched.row_n,
        effect_size=share,
        evidence={
            "counties": fetched.row_n,
            "published_human_floor": published,
            "no_county_linked_record": unpublished,
            "reference_release": REFERENCE_RELEASE_ID,
        },
        uncertainty_note=(
            "Counts are a county census. No interval is reported because counties "
            "in a state share reporting rules."
        ),
    )
    alignment = FindingRecord(
        topic="gap_alignment",
        statement=(
            f"Case-floor SQL nulls are {_fmt(case_null)} and incidence-floor SQL nulls "
            f"are {_fmt(incidence_null)}. Established tick status is {_fmt(tick_established)} "
            f"and the two species Established counts sum to {_fmt(species_established)}."
        ),
        disposition=disposition,
        n_underlying=fetched.row_n,
        evidence={
            "case_floor_null": case_null,
            "incidence_floor_null": incidence_null,
            "tick_established": tick_established,
            "species_established": species_established,
        },
        uncertainty_note="These are alignment checks, not a model of surveillance effort.",
    )
    published_joints = [
        {
            "human_status": human,
            "tick_status": tick,
            "pathogen_status": pathogen,
            "counties": count,
        }
        for human, tick, pathogen, count in fetched.joints
        if count == 0 or count >= 11
    ]
    joint = FindingRecord(
        topic="joint_partition",
        statement=(
            "Human, tick, and pathogen status together partition the counties. "
            "Cells below the small-cell minimum are omitted here and stored suppressed "
            "on the metric row. No records and Unknown are not negatives, and a human "
            "floor is a lower bound rather than a complete count."
        ),
        disposition=disposition,
        n_underlying=fetched.row_n,
        evidence={"cells": published_joints},
        uncertainty_note="The three signals do not share a time window.",
    )
    vintage_evidence: dict[str, object] = {key: vintage for key, vintage in fetched.sources}
    if fetched.climate_min is not None and fetched.climate_max is not None:
        vintage_evidence["climate_min"] = fetched.climate_min.isoformat()
        vintage_evidence["climate_max"] = fetched.climate_max.isoformat()
    vintage = FindingRecord(
        topic="vintage_mismatch",
        statement=(
            "Human surveillance is calendar year 2023. Tick and pathogen status are "
            "cumulative through 2025-12-31. Social vulnerability is the 2022 index on "
            "the 2018-2022 ACS window, and the rural-urban code is 2023. Those windows "
            "are not one time base. Population on the atlas is the 2022 county layer."
        ),
        disposition=disposition,
        n_underlying=fetched.row_n,
        evidence=vintage_evidence,
        uncertainty_note="A later story would be required to put these signals on one year.",
    )
    land = FindingRecord(
        topic="land_cover_and_climate",
        statement=_land_statement(fetched),
        disposition=disposition,
        n_underlying=fetched.row_n,
        evidence=_land_evidence(fetched),
        uncertainty_note=(
            "October 13 called the 2025 land-cover extension a tiny non-national demo. "
            "This run does not restate a geography count below 11."
        ),
    )
    return (headline, alignment, joint, vintage, land)


def _charts(
    fetched: FetchedCoverage,
    levels: Mapping[str, Mapping[str | None, int]],
) -> ChartFrames:
    by_region = {row.region: row for row in fetched.regions}
    shares: list[tuple[float | None, ...]] = []
    for _signal, key in HEATMAP_SIGNALS:
        shares.append(
            tuple(
                _publishable_share(by_region[name].counts[key], by_region[name].total_n)
                for name in HEATMAP_REGIONS
            )
        )
    bars = tuple(
        (signal, level, count)
        for signal in ("HUMAN_STATUS", "TICK_STATUS", "BURGDORFERI_STATUS")
        for level, count in levels[signal].items()
        if level is not None and (count == 0 or count >= 11)
    )
    vintages: list[tuple[str, str | None, str]] = [
        ("Human surveillance", "2023-01-01", "2023-12-31"),
        ("Population, 2022 county layer", "2018-01-01", "2022-12-31"),
        ("Social vulnerability", "2018-01-01", "2022-12-31"),
        ("Rural-urban code", "2023-01-01", "2023-12-31"),
        ("Tick status, cumulative", None, "2025-12-31"),
        ("Pathogen status, cumulative", None, "2025-12-31"),
        ("Land cover vintage", "2025-01-01", "2025-12-31"),
    ]
    if fetched.climate_min is not None and fetched.climate_max is not None:
        vintages.append(
            (
                "Climate county-day window",
                fetched.climate_min.isoformat(),
                fetched.climate_max.isoformat(),
            )
        )
    return ChartFrames(
        heatmap_signals=tuple(signal for signal, _key in HEATMAP_SIGNALS),
        heatmap_regions=HEATMAP_REGIONS,
        heatmap_shares=tuple(shares),
        bars=bars,
        vintages=tuple(vintages),
    )


def _land_statement(fetched: FetchedCoverage) -> str:
    land = _publishable_count(fetched.nlcd_counties)
    climate = _publishable_count(fetched.climate_county_n)
    climate_days = _publishable_count(fetched.climate_day_n)
    if land is None:
        land_text = (
            "Land-cover geography is below the small-cell minimum, so it is not a national layer."
        )
    else:
        land_text = f"Land-cover rows reach {_fmt(land)} counties."
    if climate is None:
        climate_text = "Climate county coverage is below the small-cell minimum."
    elif climate == 0:
        climate_text = "The climate county-day view has no county rows."
    else:
        if climate_days is None:
            day_text = "a suppressed day count"
        else:
            day_text = f"{_fmt(climate_days)} days"
        climate_text = f"Climate rows cover {_fmt(climate)} counties across {day_text}."
    return f"{land_text} {climate_text}"


def _land_evidence(fetched: FetchedCoverage) -> dict[str, object]:
    evidence: dict[str, object] = {}
    for key, count in (
        ("nlcd_counties", fetched.nlcd_counties),
        ("climate_counties", fetched.climate_county_n),
        ("climate_days", fetched.climate_day_n),
        ("climate_measures", fetched.climate_measure_n),
    ):
        published = _publishable_count(count)
        if published is not None:
            evidence[key] = published
    return evidence


def _count_metric(
    name: str,
    count: int,
    geography_type: str,
    geography_id: str,
    dimensions: Mapping[str, object],
    *,
    period: tuple[date | None, date] | None = None,
) -> EdaMetric:
    start = None if period is None else period[0]
    end = None if period is None else period[1]
    return EdaMetric(
        metric_name=name,
        n_underlying=count,
        metric_value=float(count),
        geography_type=geography_type,
        geography_id=geography_id,
        dimensions=dict(dimensions),
        unit="counties",
        period_start=start,
        period_end=end,
    )


def _share_metric(
    signal: str,
    geography_id: str,
    missing: int,
    total: int,
    geography_type: str,
) -> EdaMetric:
    period = _period_for(signal)
    start = None if period is None else period[0]
    end = None if period is None else period[1]
    share = _publishable_share(missing, total)
    dimensions = {"signal": signal, "gap": "undocumented"}
    if share is None:
        sensitive = missing if missing < 11 or total < 11 else total - missing
        return EdaMetric(
            metric_name="undocumented_share",
            n_underlying=sensitive,
            metric_value=None,
            geography_type=geography_type,
            geography_id=geography_id,
            dimensions=dimensions,
            unit="share",
            period_start=start,
            period_end=end,
        )
    return EdaMetric(
        metric_name="undocumented_share",
        n_underlying=total,
        metric_value=share,
        geography_type=geography_type,
        geography_id=geography_id,
        dimensions=dimensions,
        unit="share",
        period_start=start,
        period_end=end,
    )


def _sum_regions(fetched: FetchedCoverage, key: str) -> int:
    return sum(row.counts[key] for row in fetched.regions)


def _gap(
    source: str,
    column: str,
    missing: int,
    total: int,
    grain: str,
    gap: str,
    *,
    region: str | None = None,
    measure: str | None = None,
) -> MissingnessRecord:
    group: dict[str, object] = {"grain": grain, "gap": gap}
    if region is not None:
        group["region"] = region
    if measure is not None:
        group["measure"] = measure
    return MissingnessRecord(source, column, missing, total, group)


def _level_index(
    levels: Sequence[tuple[str, str | None, int]],
) -> dict[str, dict[str | None, int]]:
    index: dict[str, dict[str | None, int]] = defaultdict(dict)
    for column, level, count in levels:
        if column not in CATEGORICAL_COLUMNS:
            raise CoverageAuditError("unexpected categorical column")
        index[column][level] = count
    for column in CATEGORICAL_COLUMNS:
        index.setdefault(column, {})
    return index


def _level_count(
    levels: Mapping[str, Mapping[str | None, int]],
    column: str,
    level: str,
) -> int:
    return levels[column].get(level, 0)


def heatmap_cell_label(share: float | None) -> str:
    """Label a heatmap cell. A suppressed share is marked, not drawn as zero."""
    if share is None:
        return "<11"
    return f"{share * 100:.0f}"


def _publishable_share(missing: int, total: int) -> float | None:
    prepared = prepare_missingness(
        MissingnessRecord(
            ATLAS,
            "HUMAN_STATUS",
            missing,
            total,
            {"grain": "check", "gap": "undocumented"},
        )
    )
    return prepared.missing_pct


def _publishable_count(count: int) -> int | None:
    if count == 0 or count >= 11:
        return count
    return None


def _period_for(signal: str) -> tuple[date | None, date] | None:
    if signal in {"HUMAN_STATUS", "CASE_COUNT_FLOOR_2023", "INCIDENCE_FLOOR_2023"}:
        return _HUMAN_PERIOD
    if signal in {
        "TICK_STATUS",
        "SCAPULARIS_STATUS",
        "PACIFICUS_STATUS",
        "BURGDORFERI_STATUS",
    }:
        return (None, _CUMULATIVE_END)
    return None


def _status_label(level: str | None) -> str:
    if level is None:
        return "sql_null"
    if len(level) > 80 or any(ord(char) < 32 for char in level):
        raise CoverageAuditError("status label is not a short code")
    return level


def _fmt(value: int) -> str:
    if 0 < value < 11:
        return "a count below 11"
    return f"{value:,}"


def _required_int(row: Mapping[str, object], key: str) -> int:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise CoverageAuditError("aggregate is not an integer")
    return value


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise CoverageAuditError("aggregate is not an integer")
    return value


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CoverageAuditError("aggregate is not a number")
    return float(value)


def _text_number(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CoverageAuditError("aggregate is not a number")
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return format(float(value), ".6g")
