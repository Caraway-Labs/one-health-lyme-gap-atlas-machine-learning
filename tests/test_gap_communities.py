"""Issue 120 gap communities, with fakes and no Snowflake connection."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from sklearn.metrics import adjusted_rand_score

from lyme_gap_atlas_ml.county_mca import FINE_POPULATION_EDGES, FINE_POPULATION_LABELS
from lyme_gap_atlas_ml.coverage_audit import PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.gap_communities import (
    BOOTSTRAP_LOW_MIN,
    K_GRID,
    REFERENCE_DOUBLE_GAP,
    SEED,
    SEED_ARI_MIN,
    SPEC_ID,
    SVI_BIN_LABELS,
    SVI_EDGES,
    AssignmentRow,
    GapCommunityError,
    KCandidate,
    build_findings,
    category_label,
    evaluate_gate,
    experiment_rows,
    fit_cohort,
    fit_k_prototypes,
    lab_metrics,
    load_gap_queries,
    minimum_cluster_size,
    rucc_label,
    scale_numeric,
    select_k,
)
from lyme_gap_atlas_ml.gap_community_report import render_comment
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import prepare_finding
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric, EdaWriteError, prepare_eda_metric
from lyme_gap_atlas_ml.snowflake.gap_community_assignments import (
    assignment_table_sql,
    write_assignment_tables,
)
from lyme_gap_atlas_ml.state_regimes import (
    EXPECTED_COUNTIES,
    HUMAN_NONE,
    HUMAN_PUBLISHED,
    TICK_ESTABLISHED,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "120_gap_communities.sql"


def test_sql_file_keeps_the_allow_list() -> None:
    queries = load_gap_queries(SQL_PATH.read_text(encoding="utf-8"))
    county = queries["county_rows"].upper()
    assert "UNINSURED_PERCENTILE" in county
    assert "UNINSURED_PERCENT," not in county
    assert "UNINSURED_PERCENT " not in county
    assert "SCAPULARIS_STATUS" in county
    assert "PACIFICUS_STATUS" in county
    assert "PAYLOAD" not in county
    assert "GEOMETRY" not in county
    assert "INCIDENCE" not in county
    assert "TIER" not in county
    with pytest.raises(EdaWriteError):
        load_gap_queries(SQL_PATH.read_text(encoding="utf-8") + "\nSELECT PAYLOAD FROM T\n")


def test_frequency_edges_match_the_mca_exhibit() -> None:
    assert FINE_POPULATION_EDGES == (10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000)
    assert len(FINE_POPULATION_LABELS) == len(FINE_POPULATION_EDGES) + 1
    assert len(SVI_BIN_LABELS) == len(SVI_EDGES) + 1


def test_blanks_stay_categories() -> None:
    assert category_label(None) == "blank"
    assert category_label("  ") == "blank"
    assert category_label("No records") == "No records"
    assert rucc_label(None) == "blank"
    assert rucc_label(8) == "8"
    assert rucc_label(0) == "unlisted"
    assert category_label(None) != "No records"


def test_gamma_is_one_half_after_the_zscore() -> None:
    raw = np.array([[1.0, 10.0, 100.0], [2.0, 20.0, 50.0], [4.0, 30.0, 20.0], [8.0, 40.0, 10.0]])
    _scaled, gamma = scale_numeric(raw)
    assert gamma == pytest.approx(0.5, abs=1e-8)


def test_separated_groups_agree_across_seeds() -> None:
    generator = np.random.default_rng(0)
    numeric = np.vstack(
        [
            generator.normal(0.0, 0.05, size=(40, 3)),
            generator.normal(5.0, 0.05, size=(40, 3)),
        ]
    )
    categorical = np.asarray([["a", "x"]] * 40 + [["b", "y"]] * 40, dtype=object)
    scaled, gamma = scale_numeric(numeric)
    primary = fit_k_prototypes(scaled, categorical, 2, SEED, gamma)
    alternate = fit_k_prototypes(scaled, categorical, 2, SEED + 1, gamma)
    assert primary.converged
    assert alternate.converged
    assert adjusted_rand_score(primary.labels, alternate.labels) == pytest.approx(1.0)


def test_select_k_prefers_the_smaller_k_inside_the_silhouette_tie() -> None:
    candidates = (
        _candidate(2, silhouette=0.40),
        _candidate(3, silhouette=0.405),
        _candidate(4, silhouette=0.20),
    )
    chosen = select_k(candidates, minimum_size=30)
    assert chosen is not None
    assert chosen.k == 2


def test_select_k_rejects_a_low_bootstrap_or_a_small_cluster() -> None:
    assert select_k((_candidate(2, bootstrap_low=BOOTSTRAP_LOW_MIN - 0.01),), 30) is None
    assert select_k((_candidate(2, seed_ari=SEED_ARI_MIN - 0.01),), 30) is None
    assert select_k((_candidate(2, min_size=29),), 30) is None
    assert minimum_cluster_size(810) == 41
    assert K_GRID == (2, 3, 4, 5, 6)


def test_small_cluster_counts_are_suppressed_in_lab_metrics() -> None:
    metric = next(item for item in _sample_metrics() if item.n_underlying < 11)
    prepared = prepare_eda_metric(metric)
    assert prepared.is_suppressed
    assert prepared.metric_value is None


def test_gate_stops_on_the_wrong_release() -> None:
    release, raw = _atlas()
    release["RELEASE_ID"] = "other-release"
    gate = evaluate_gate(release, raw)
    assert not gate.ok
    with pytest.raises(GapCommunityError):
        fit_cohort(raw, gate, run_bootstrap=False)


def test_cohort_matches_the_epic_counts_without_publishing_a_score() -> None:
    release, raw = _atlas()
    raw[443]["SCAPULARIS_STATUS"] = None
    gate = evaluate_gate(release, raw)
    assert gate.ok
    fitted = fit_cohort(raw, gate, run_bootstrap=False)
    assert fitted.cohort_n == 810
    assert fitted.double_gap_n == REFERENCE_DOUBLE_GAP
    assert fitted.double_gap_outside == 0
    assert fitted.excluded_n == 0
    assert fitted.gamma == pytest.approx(0.5, abs=1e-6)
    assert fitted.method_disposition == "revise"
    assert fitted.product_disposition == "stop"
    assert sum(row.in_double_gap for row in fitted.assignments) == REFERENCE_DOUBLE_GAP
    assert len(fitted.assignments) == 810
    assert lab_metrics(fitted)
    assert any(row.scapularis_status == "blank" for row in fitted.assignments)
    text = render_comment(fitted, run_id="120-gap-communities-test", commit="abc", charts=[])
    assert "1. Question" in text
    assert "not disease risk" in text
    assert "not incidence" in text.lower()
    assert SPEC_ID in text
    for finding in build_findings(fitted):
        prepare_finding(finding, finding_id="11111111-1111-1111-1111-111111111111")
    config = experiment_rows(fitted, "120-gap-communities-test")[0].config
    assert config["use_as_model_feature"] is False


def test_assignment_writer_is_insert_only_and_grants_once() -> None:
    sql = assignment_table_sql()
    assert "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.GAP_COMMUNITY_ASSIGNMENTS_120" in sql
    assert "DELETE" not in sql.upper()
    session = _FakeSession()
    row = AssignmentRow(
        fips="01001",
        county_name="Example",
        state="AL",
        cluster_id=1,
        in_double_gap=False,
        population=1000.0,
        svi=0.2,
        uninsured=0.3,
        rucc="8",
        scapularis_status="Established",
        pacificus_status="No records",
        burgdorferi_status="No records",
    )
    result = write_assignment_tables(session, "120-gap-communities-test", [row], ())
    assert result["granted"] is True
    assert result["assignments"] == 1
    executed = [statement for statement, _params in session.executed]
    assert any(statement.startswith("GRANT SELECT") for statement in executed)
    session.existing = True
    with pytest.raises(EdaWriteError):
        write_assignment_tables(session, "120-gap-communities-test", [row], ())


def _candidate(
    k: int,
    *,
    silhouette: float = 0.30,
    seed_ari: float = 0.90,
    bootstrap_low: float = 0.80,
    min_size: int = 50,
) -> KCandidate:
    return KCandidate(
        k=k,
        converged=True,
        alt_converged=True,
        seed_ari=seed_ari,
        silhouette=silhouette,
        min_size=min_size,
        sizes=(min_size, min_size),
        bootstrap_low=bootstrap_low,
        bootstrap_high=0.95,
        bootstrap_estimable=True,
        labels=tuple(1 for _ in range(min_size)),
    )


def _sample_metrics() -> tuple[EdaMetric, ...]:
    return (
        EdaMetric(
            metric_name="double_gap_in_cluster",
            metric_value=5,
            n_underlying=5,
            geography_type="national",
            geography_id="US",
        ),
    )


def _atlas() -> tuple[dict[str, object], list[dict[str, object]]]:
    plan = (
        [("aligned", 443)]
        + [("double_gap", 228)]
        + [("wider_only", 582)]
        + [("human_ahead", 207)]
        + [("undocumented", 1189)]
        + [("published_unknown", 1)]
        + [("other_unknown", 40)]
        + [("other_pacificus_reported", 40)]
        + [("other_reported", 414)]
    )
    labels: list[str] = []
    for name, count in plan:
        labels.extend([name] * count)
    assert len(labels) == EXPECTED_COUNTIES
    states = ["AL", "DC", "WY"]
    rows = [_row(index + 1, label, states[index % 3]) for index, label in enumerate(labels)]
    release = {
        "RELEASE_ID": PINNED_RELEASE_ID,
        "SCHEMA_VERSION": "2.0.0",
        "METHODOLOGY_VERSION": "semantic-2.0.0",
        "SCOPE": "US_COUNTIES",
        "BUNDLE_SHA256": PINNED_BUNDLE_SHA256,
    }
    return release, rows


def _row(index: int, label: str, state: str) -> dict[str, object]:
    human = (
        HUMAN_PUBLISHED if label in {"aligned", "human_ahead", "published_unknown"} else HUMAN_NONE
    )
    if label in {"aligned", "double_gap", "wider_only"}:
        tick = TICK_ESTABLISHED
        scapularis = TICK_ESTABLISHED
        pacificus = "No records"
    elif label == "other_pacificus_reported":
        tick = "Reported"
        scapularis = "No records"
        pacificus = "Reported"
    elif label in {"other_unknown", "published_unknown"}:
        tick = "Unknown"
        scapularis = "Unknown"
        pacificus = "Unknown"
    elif label == "undocumented":
        tick = "No records"
        scapularis = "No records"
        pacificus = "No records"
    else:
        tick = "Reported"
        scapularis = "Reported"
        pacificus = "No records"
    if label in {"aligned", "double_gap"}:
        pathogen = "Present"
    elif label in {"other_unknown", "published_unknown"}:
        pathogen = "Unknown"
    else:
        pathogen = "No records"
    population_cycle = (5_000, 20_000, 80_000, 400_000)
    return {
        "FIPS": f"{index:05d}",
        "COUNTY": f"Unit {index}",
        "STATE": state,
        "RELEASE_ID": PINNED_RELEASE_ID,
        "POPULATION": population_cycle[index % 4],
        "SVI_PERCENTILE": (index % 5) / 5,
        "UNINSURED_PERCENTILE": ((index + 2) % 5) / 5,
        "RUCC_2023": (index % 9) + 1,
        "HUMAN_STATUS": human,
        "TICK_STATUS": tick,
        "SCAPULARIS_STATUS": scapularis,
        "PACIFICUS_STATUS": pacificus,
        "BURGDORFERI_STATUS": pathogen,
    }


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object]] = []
        self.existing = False

    def query(self, sql: str, params: tuple[object, ...] | None = None) -> list[tuple[object, ...]]:
        del params
        if "CURRENT_ROLE" in sql:
            return [("OH_LYME_ML_AGENT", "OH_LYME_ML_LAB_XS_WH",
                "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB")]
        if "COUNT" in sql:
            return [(1 if self.existing else 0,)]
        return []

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.executed.append((sql, params))

    def executemany(self, sql: str, rows: list[tuple[object, ...]]) -> None:
        self.executed.append((sql, ("many", len(list(rows)))))
