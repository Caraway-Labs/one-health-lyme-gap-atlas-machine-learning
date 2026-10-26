"""Issue 107 distributions, with fakes and no live credentials."""

from __future__ import annotations

from lyme_gap_atlas_ml.county_distribution_report import render_comment
from lyme_gap_atlas_ml.county_distributions import (
    CASE_EDGES,
    HUMAN_NONE,
    HUMAN_PUBLISHED,
    REFERENCE_COUNTIES,
    AtlasCounty,
    ClimateDay,
    TierCounty,
    analyze,
    chart_bins,
    histogram,
    lab_metrics,
    linear_quantile,
    sample_skewness,
    summarize,
    weighted_quantile,
)
from lyme_gap_atlas_ml.coverage_audit import CENSUS_REGIONS
from lyme_gap_atlas_ml.snowflake.county_adjacency import (
    INSERT_ADJACENCY_SQL,
    adjacency_sql_is_lab_only,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import EdaWriteError, QueryRecord, prepare_query
from lyme_gap_atlas_ml.snowflake.eda_writer import prepare_eda_metric


def test_histogram_uses_raw_edges_without_midpoints() -> None:
    bins = histogram([0, 1, 2, 4, 5, 9], (0, 2, 4, 8))
    assert sum(count for _label, count in bins) == 6
    assert bins[0] == ("underflow", 0)
    assert bins[-1] == ("overflow", 1)
    assert [count for _label, count in bins][1:-1] == [2, 1, 2]
    labels = [label for label, _count in bins]
    assert all("," not in label or label.startswith("[") for label in labels)
    assert len(CASE_EDGES) >= 2


def test_quantiles_and_skewness_use_the_raw_values() -> None:
    assert linear_quantile([1, 2, 3, 4], 0.5) == 2.5
    assert weighted_quantile([1, 2, 10], [1, 1, 8], 0.5) == 10
    assert sample_skewness([1, 2, 3, 4, 100]) is not None
    assert sample_skewness([1, 2, 3, 4, 100]) > 0
    summary = summarize([5, 5, 5, 5, 6, 20], [10, 10, 10, 10, 10, 10], (5, 6, 10, 20))
    assert summary.mode == 5
    assert summary.n == 6
    assert summary.iqr_high >= 1
    assert summary.minimum == 5
    assert summary.maximum == 20


def test_small_bin_is_suppressed_and_a_zero_bin_is_kept() -> None:
    visible = chart_bins((("underflow", 0), ("[0, 1)", 5), ("overflow", 20)))
    assert visible[0][1] == 0
    assert visible[1][1] is None
    assert visible[2][1] == 20


def test_reference_cohort_keeps_insufficient_separate_from_low() -> None:
    result = analyze(_counties(), _tiers(), (), nlcd_counties=2)
    assert result.disposition == "keep"
    assert result.published == 651
    assert result.unpublished == 2493
    assert result.tier.high == 315
    assert result.tier.medium == 628
    assert result.tier.low == 2201
    assert result.tier.insufficient == 2493
    assert result.tier.sufficient == 651
    assert result.tier.stored_versus_rule == 0
    assert result.tier.sufficiency_by_tier[("INSUFFICIENT", "LOW")] == 2201
    assert result.tier.sufficiency_by_tier[("INSUFFICIENT", "MEDIUM")] == 292
    assert len(lab_metrics(result)) <= 5000
    comment = render_comment(
        result,
        run_id="107-county-distributions-test",
        git_commit="abc1234",
        row_counts={"REGISTRY.RUNS": 1},
        drive_lines=("Drive upload pending",),
        adjacency_note="not run in this test",
    )
    assert "## 1. Question" in comment
    assert "not incidence, risk, or causation" in comment
    assert "**KEEP.**" in comment
    assert "INSUFFICIENT is not reported as LOW" in comment


def test_short_cohort_stops() -> None:
    county = _counties()[0]
    result = analyze((county,), _tiers()[:1], (), nlcd_counties=0)
    assert result.disposition == "stop"
    assert result.counties == 1


def test_adjacency_insert_stays_in_the_lab_and_is_not_logged() -> None:
    assert adjacency_sql_is_lab_only()
    try:
        prepare_query(QueryRecord(sql_text=INSERT_ADJACENCY_SQL, rows_returned=0, elapsed_ms=0))
    except EdaWriteError:
        return
    raise AssertionError("geometry statement was accepted by the query log")


def test_suppressed_metric_drops_a_small_cell() -> None:
    metrics = lab_metrics(analyze(_counties(), _tiers(), _climate(), nlcd_counties=2))
    prepared = [prepare_eda_metric(metric) for metric in metrics]
    assert any(metric.is_suppressed for metric in prepared) or all(
        metric.n_underlying is None or metric.n_underlying >= 11 or metric.n_underlying == 0
        for metric in prepared
    )
    assert len(metrics) <= 5000


def _counties() -> tuple[AtlasCounty, ...]:
    states = tuple(CENSUS_REGIONS)
    rows: list[AtlasCounty] = []
    for index in range(REFERENCE_COUNTIES):
        published = index < 651
        rows.append(
            AtlasCounty(
                fips=f"{index:05d}",
                county=f"County {index}",
                state=states[index % len(states)],
                population=1000.0 + index,
                human_status=HUMAN_PUBLISHED if published else HUMAN_NONE,
                case_floor=5.0 if published and index < 100 else 20.0 if published else None,
                incidence_floor=(5.0 + (index % 15)) if published else None,
                svi_percentile=(index % 100) / 100,
                uninsured_percentile=((index * 3) % 100) / 100,
                rucc=(index % 9) + 1,
            )
        )
    rows[0] = AtlasCounty(
        fips=rows[0].fips,
        county=rows[0].county,
        state=rows[0].state,
        population=rows[0].population,
        human_status=HUMAN_PUBLISHED,
        case_floor=5.0,
        incidence_floor=400.0,
        svi_percentile=rows[0].svi_percentile,
        uninsured_percentile=rows[0].uninsured_percentile,
        rucc=rows[0].rucc,
    )
    return tuple(rows)


def _tiers() -> tuple[TierCounty, ...]:
    rows: list[TierCounty] = []
    for index in range(REFERENCE_COUNTIES):
        if index < 315:
            tier, point, score, sufficiency = "HIGH", 95.0, 2.0, "SUFFICIENT"
        elif index < 651:
            tier, point, score, sufficiency = "MEDIUM", 80.0, 1.2, "SUFFICIENT"
        elif index < 943:
            tier, point, score, sufficiency = "MEDIUM", 75.0, 1.1, "INSUFFICIENT"
        else:
            tier, point, score, sufficiency = "LOW", 40.0, 0.5, "INSUFFICIENT"
        status = HUMAN_PUBLISHED if index < 651 else HUMAN_NONE
        rows.append(
            TierCounty(
                fips=f"{index:05d}",
                tier=tier,
                percentile=point,
                score=score,
                sufficiency=sufficiency,
                human_evidence_state=status,
            )
        )
    return tuple(rows)


def _climate() -> tuple[ClimateDay, ...]:
    return tuple(
        ClimateDay("nclimgrid_tavg_county_day", f"{index:05d}", float(index % 30) - 10.0)
        for index in range(30)
    )
