"""Issue 116 method selection, without a warehouse connection."""

from __future__ import annotations

from pathlib import Path

import pytest

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.coverage_audit import CENSUS_REGIONS, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.evidence_association_65 import _cluster_interval, table_statistics
from lyme_gap_atlas_ml.test_selection import (
    FAMILY,
    METHOD_DECISIONS,
    QUERY_NAMES,
    REFERENCE_COUNTIES,
    County,
    IntervalEstimate,
    SelectionError,
    SelectionResult,
    ShareCell,
    _disposition,
    _empty_interval,
    cramers_v,
    holm,
    prepare_counties,
    release_gate,
)

ROOT = Path(__file__).resolve().parents[1]
OCTOBER_JOINT = (
    ("no", "No records", "No records", 1189),
    ("no", "Established", "No records", 582),
    ("yes", "Established", "Present", 443),
    ("no", "Reported", "No records", 442),
    ("no", "Established", "Present", 228),
    ("yes", "Established", "No records", 151),
    ("no", "Unknown", "Unknown", 35),
    ("yes", "Reported", "No records", 31),
    ("yes", "No records", "No records", 25),
    ("no", "Reported", "Present", 16),
    ("yes", "Reported", "Present", 1),
    ("no", "No records", "Present", 1),
)


def _table(pairs: list[tuple[str, str, int]]) -> list[list[int]]:
    rows = sorted({item[0] for item in pairs})
    cols = sorted({item[1] for item in pairs})
    index_row = {label: index for index, label in enumerate(rows)}
    index_col = {label: index for index, label in enumerate(cols)}
    table = [[0 for _ in cols] for _ in rows]
    for row, col, count in pairs:
        table[index_row[row]][index_col[col]] += count
    return table


def test_october_table_matches_epic_displays() -> None:
    known = [row for row in OCTOBER_JOINT if row[1] != "Unknown" and row[2] != "Unknown"]
    tick = cramers_v(_table([(row[1], row[2], row[3]) for row in known]))
    human_tick = cramers_v(_table([(row[0], row[1], row[3]) for row in known]))
    human_pathogen = cramers_v(_table([(row[0], row[2], row[3]) for row in known]))
    assert tick is not None and f"{tick.v:.4f}" == "0.5607"
    assert human_tick is not None and f"{human_tick.v:.4f}" == "0.4780"
    assert human_pathogen is not None and f"{human_pathogen.v:.4f}" == "0.5705"
    assert tick.n == 3109
    full = cramers_v(_table([(row[1], row[2], row[3]) for row in OCTOBER_JOINT]))
    assert full is not None and round(full.chi2) == 4132
    assert f"{full.v:.2f}" == "0.81"


def test_issue_65_statistic_matches_cramers_v() -> None:
    known = [row for row in OCTOBER_JOINT if row[1] != "Unknown" and row[2] != "Unknown"]
    order_row = ["Established", "Reported", "No records"]
    order_col = ["Present", "No records"]
    counts = {(row[1], row[2]): row[3] for row in known}
    table = [[counts.get((row, col), 0) for col in order_col] for row in order_row]
    ours = cramers_v(table)
    theirs = table_statistics(table)
    assert ours is not None
    assert ours.v == pytest.approx(theirs["v"])
    assert ours.chi2 == pytest.approx(theirs["chi2"])


def test_state_cluster_interval_matches_issue_65() -> None:
    clusters = {f"{index:02d}": [[index + 1, 2], [1, index + 3], [4, 1]] for index in range(12)}
    theirs = _cluster_interval(clusters)
    from lyme_gap_atlas_ml.test_selection import _cluster_interval as ours
    from lyme_gap_atlas_ml.test_selection import _sum_tables, _v_of

    keys = tuple(sorted(clusters))
    estimate = ours(keys, lambda draw: _v_of(_sum_tables(clusters, draw)), 6501)
    assert theirs["interval"] is not None
    assert estimate.low == pytest.approx(theirs["interval"][0])
    assert estimate.high == pytest.approx(theirs["interval"][1])


def test_holm_is_monotone_step_down() -> None:
    adjusted = holm([("a", 0.04), ("b", 0.01), ("c", 0.03), ("d", 0.02)])
    assert adjusted == {"b": 0.04, "d": 0.06, "c": 0.06, "a": 0.06}


def test_decision_matrix_covers_the_requested_methods() -> None:
    names = {item.method for item in METHOD_DECISIONS}
    for required in (
        "Welch t",
        "Paired t",
        "Mann-Whitney",
        "Wilcoxon signed-rank",
        "ANOVA / Welch ANOVA",
        "Kruskal-Wallis",
        "Chi-square",
        "Fisher exact",
        "Spearman",
        "Pearson",
        "Regression",
    ):
        assert required in names
    chosen = {item.method for item in METHOD_DECISIONS if item.decision == "chosen"}
    assert chosen == {"Spearman"}
    assert "q1_share_diff" in FAMILY


def test_small_cell_share_is_not_publishable() -> None:
    hidden = ShareCell("rucc_5", 76, 8, 76, 8)
    visible = ShareCell("rucc_1", 443, 168, 443, 168)
    zero = ShareCell("empty", 20, 0, None, None)
    assert not hidden.publishable
    assert visible.publishable
    assert zero.publishable


def test_release_gate_rejects_a_different_pin() -> None:
    with pytest.raises(SelectionError):
        release_gate({"RELEASE_ID": "other", "BUNDLE_SHA256": "abc"})


def test_prepare_rejects_a_duplicate_fips() -> None:
    state = next(iter(CENSUS_REGIONS))
    row = {
        "FIPS": "01001",
        "COUNTY": "Example",
        "STATE": state,
        "RELEASE_ID": PINNED_RELEASE_ID,
        "HUMAN_STATUS": "published_count_floor",
        "TICK_STATUS": "Established",
        "BURGDORFERI_STATUS": "Present",
        "RUCC_2023": 1,
        "SVI_PERCENTILE": 0.2,
        "IN_CONTIGUOUS_TICK_SCOPE": True,
    }
    rows = [dict(row) for _ in range(REFERENCE_COUNTIES)]
    with pytest.raises(SelectionError):
        prepare_counties(rows, release_id=PINNED_RELEASE_ID)


def test_query_file_is_the_registered_pair() -> None:
    text = (ROOT / "sql" / "validation" / "116_test_selection.sql").read_text(encoding="utf-8")
    queries = load_marked_queries(text, QUERY_NAMES)
    assert "CURRENT_COUNTY_ATLAS_V" in queries["cohort_rows"]
    assert "GEOMETRY" not in queries["cohort_rows"].upper()
    assert "EVIDENCE_COMPLETENESS" not in queries["cohort_rows"]


def test_no_record_is_not_a_published_floor() -> None:
    county = County(
        fips="01001",
        county="Example",
        state="AL",
        release_id=PINNED_RELEASE_ID,
        human="no_county_linked_record",
        tick="No records",
        pathogen="No records",
        rucc=9,
        svi=None,
        in_scope=True,
    )
    assert county.human != "published_count_floor"
    assert county.tick == "No records"


def test_both_contrasts_not_estimable_stops() -> None:
    empty = _empty_interval(0)
    contrast = _bare_contrast("q1_share_diff", empty)
    other = _bare_contrast("q2_share_diff", empty)
    result = _bare_result((contrast, other))
    assert _disposition(result) == "stop"


def _bare_contrast(name: str, interval: IntervalEstimate) -> object:
    from lyme_gap_atlas_ml.test_selection import Contrast

    return Contrast(
        name=name,
        label=name,
        estimate=None,
        n=0,
        n_left=0,
        n_right=0,
        cluster=interval,
        naive=interval,
        width_ratio=None,
        holm=None,
    )


def _bare_result(contrasts: tuple[object, ...]) -> SelectionResult:
    from lyme_gap_atlas_ml.test_selection import Contrast, Reproduced

    typed = tuple(item for item in contrasts if isinstance(item, Contrast))
    reproduced = Reproduced(
        "tick_pathogen", None, _empty_interval(0), _empty_interval(0), None, None, "0.5607"
    )
    return SelectionResult(
        release_id=PINNED_RELEASE_ID,
        svi_rescaled=False,
        svi_max=1.0,
        counties=REFERENCE_COUNTIES,
        published_n=0,
        no_record_n=0,
        other_human_n=0,
        q1_excluded_rucc=0,
        q2_excluded_svi=0,
        contrasts=typed,
        q1_v=reproduced,
        reproduced=(reproduced,),
        tick_interval_display=None,
        tick_helper_n=None,
        tick_helper_v=None,
        collapse_v=None,
        rucc_cells=(),
        svi_cells=(),
        svi_exact_one_n=0,
        svi_exact_one_published=0,
        sensitivities=(),
        spots=(),
        q3="not_estimable",
        disposition="stop",
        family_complete=False,
        v_display_match=False,
        interval_display_match=False,
        material_sensitivity=False,
    )
