"""Issue 121 correspondence map, with fakes and no Snowflake connection."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lyme_gap_atlas_ml.county_mca import (
    EXPECTED_COUNTIES,
    POPULATION_EDGES,
    SENSITIVITY_POPULATION_EDGES,
    SPEC_ID,
    SVI_EDGES,
    USE_AS_MODEL_FEATURE,
    CoordinateRow,
    County,
    CountyMcaError,
    build_findings,
    correspondence,
    evaluate_gate,
    experiment_rows,
    fit_counties,
    load_mca_queries,
    procrustes_similarity,
    spearman,
    suppress_cell_counts,
)
from lyme_gap_atlas_ml.county_mca_report import render_comment
from lyme_gap_atlas_ml.coverage_audit import PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import prepare_finding
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaWriteError
from lyme_gap_atlas_ml.snowflake.mca_coordinates import (
    coordinate_table_sql,
    write_mca_tables,
)
from lyme_gap_atlas_ml.state_regimes import HUMAN_NONE, HUMAN_PUBLISHED, TICK_ESTABLISHED

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "121_county_mca.sql"


def test_sql_file_keeps_the_allow_list() -> None:
    queries = load_mca_queries(SQL_PATH.read_text(encoding="utf-8"))
    county = queries["county_rows"].upper()
    assert "SCAPULARIS_STATUS" in county
    assert "PACIFICUS_STATUS" in county
    assert "PAYLOAD" not in county
    assert "GEOMETRY" not in county
    assert "INCIDENCE_FLOOR_2023" not in county
    with pytest.raises(EdaWriteError):
        load_mca_queries(SQL_PATH.read_text(encoding="utf-8") + "\nSELECT PAYLOAD FROM T\n")


def test_bin_edges_follow_the_spec() -> None:
    population = np.array([9999, 10000, 49999, 50000, 249999, 250000], dtype=float)
    assert np.digitize(population, POPULATION_EDGES, right=False).tolist() == [0, 1, 1, 2, 2, 3]
    shifted = np.array([99999, 100000, 249999, 250000], dtype=float)
    assert np.digitize(shifted, SENSITIVITY_POPULATION_EDGES, right=False).tolist() == [1, 2, 2, 3]
    svi = np.array([0.0, 0.25, 0.2500001, 0.5, 0.75, 1.0])
    assert np.digitize(svi, SVI_EDGES, right=True).tolist() == [0, 0, 1, 1, 2, 3]


def test_perfect_association_uses_the_greenacre_denominator() -> None:
    codes = np.column_stack([np.array([0] * 50 + [1] * 50, dtype=np.int64) for _ in range(2)])
    fit = correspondence(codes)
    assert fit.unadjusted[0] == pytest.approx(1.0, abs=1e-8)
    assert fit.greenacre_shares[0] == pytest.approx(1.0, abs=1e-8)
    assert fit.benzecri[0] == pytest.approx(fit.greenacre_total, abs=1e-8)


def test_procrustes_and_spearman_are_sign_invariant() -> None:
    base = np.array([[0.0, 0.0], [1.0, 0.2], [0.2, 1.0], [1.0, 1.1]])
    assert procrustes_similarity(base, -base) == pytest.approx(1.0, abs=1e-8)
    left = np.array([1.0, 2.0, 4.0, 8.0])
    assert spearman(left, -left) == pytest.approx(-1.0)


def test_small_hex_cells_are_suppressed() -> None:
    masked = suppress_cell_counts(np.array([0, 10, 11, 40], dtype=float))
    assert np.isnan(masked[1])
    assert masked[0] == 0
    assert masked[2] == 11


def test_situation_rules_and_exhibit_flag() -> None:
    gate_rows, raw = _atlas()
    gate = evaluate_gate(gate_rows, raw)
    assert gate.ok
    fitted = fit_counties(raw, gate)
    counts = {group.name: group.count for group in fitted.groups}
    assert counts == {
        "aligned": 443,
        "double_gap": 228,
        "wider_gap": 810,
        "human_ahead": 207,
        "undocumented": 1189,
    }
    assert all(group.reproduced for group in fitted.groups)
    assert len(fitted.contrasts) <= 3
    assert fitted.rare_leaders == ()
    assert fitted.stability is not None
    assert fitted.stability.spearman_1 >= 0.9
    text = " ".join(row.sentence for row in fitted.contrasts).lower()
    assert "incidence" not in text
    assert "risk" not in text
    experiments = experiment_rows(fitted, "121-county-contrasts-test")
    assert experiments[0].config["use_as_model_feature"] is USE_AS_MODEL_FEATURE
    assert experiments[0].split_definition["exhibit_only"] is True
    for finding in build_findings(fitted):
        prepare_finding(finding, finding_id="11111111-1111-1111-1111-111111111111")
    comment = render_comment(fitted, run_id="121-county-contrasts-test", commit="abc", charts=[])
    assert "1. Question" in comment
    assert "not a risk surface" in comment
    assert SPEC_ID in comment


def test_gate_stops_on_the_wrong_release() -> None:
    gate_rows, raw = _atlas()
    gate_rows["RELEASE_ID"] = "other-release"
    gate = evaluate_gate(gate_rows, raw)
    assert not gate.ok
    with pytest.raises(CountyMcaError):
        fit_counties(raw, gate)


def test_coordinate_writer_is_insert_only_and_grants_once() -> None:
    sql = coordinate_table_sql()
    assert "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.COUNTY_MCA_COORDINATES_121" in sql
    assert "DELETE" not in sql.upper()
    session = _FakeSession()
    row = CoordinateRow(
        fips="01001",
        county_name="Example",
        state="AL",
        axis_1=0.1,
        axis_2=-0.2,
        axis_3=0.0,
        in_aligned=True,
        in_double_gap=False,
        in_wider_gap=False,
        in_human_ahead=False,
        in_undocumented=False,
    )
    gate_rows, raw = _atlas()
    fitted = fit_counties(raw, evaluate_gate(gate_rows, raw))
    result = write_mca_tables(
        session,
        "121-county-contrasts-test",
        [row],
        experiment_rows(fitted, "121-county-contrasts-test"),
    )
    assert result["granted"] is True
    assert result["coordinates"] == 1
    executed = [statement for statement, _params in session.executed]
    assert any(statement.startswith("GRANT SELECT") for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS" in statement for statement in executed)
    session.existing = True
    with pytest.raises(EdaWriteError):
        write_mca_tables(session, "121-county-contrasts-test", [row], ())


class _FakeSession:
    def __init__(self) -> None:
        self.executed: list[tuple[str, object]] = []
        self.existing = False

    def query(self, sql: str, params: tuple[object, ...] | None = None) -> list[tuple[object, ...]]:
        del params
        if "CURRENT_ROLE" in sql:
            return [
                ("OH_LYME_ML_AGENT", "OH_LYME_ML_LAB_XS_WH", "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB")
            ]
        if "COUNT" in sql:
            return [(1 if self.existing else 0,)]
        return []

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.executed.append((sql, params))

    def executemany(self, sql: str, rows: list[tuple[object, ...]]) -> None:
        self.executed.append((sql, ("many", len(list(rows)))))


def _atlas() -> tuple[dict[str, object], list[dict[str, object]]]:
    """A complete 3,144-county fake whose situation counts match the epic references."""
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
    rows: list[dict[str, object]] = []
    for index, label in enumerate(labels):
        rows.append(_row(index + 1, label, states[index % len(states)]))
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
        "SVI_PERCENTILE": (index % 4) / 4 + 0.05,
        "RUCC_2023": (index % 9) + 1,
        "HUMAN_STATUS": human,
        "TICK_STATUS": tick,
        "SCAPULARIS_STATUS": scapularis,
        "PACIFICUS_STATUS": pacificus,
        "BURGDORFERI_STATUS": pathogen,
    }


def test_county_helper_accepts_the_template() -> None:
    county = County(
        fips="01001",
        name="Example",
        state="AL",
        population=10,
        svi=0.2,
        rucc=1,
        human_status=HUMAN_NONE,
        tick_status="No records",
        scapularis_status="No records",
        pacificus_status="No records",
        burgdorferi_status="No records",
    )
    assert county.fips == "01001"
