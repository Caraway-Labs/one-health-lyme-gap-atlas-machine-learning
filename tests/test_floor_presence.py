"""Issue 188 published-floor models. No live warehouse connection."""

from __future__ import annotations

from pathlib import Path

import pytest

from lyme_gap_atlas_ml.coverage_audit import PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.floor_presence import (
    AUC_LIFT_MIN,
    BRIER_WORSE_MAX,
    EXCLUDED_COLUMNS,
    EXPECTED_COUNTIES,
    FAMILY_GBT,
    FAMILY_LOGISTIC,
    PR_LIFT_MIN,
    SEED_PRIMARY,
    SEED_SECOND,
    SHUFFLE_LIFT_MAX,
    SPEC_ID,
    County,
    FamilySeedResult,
    FitConfig,
    FloorPresenceError,
    LiftInterval,
    PredictionRow,
    Score,
    analyze,
    decide,
    is_real_lift,
    lab_experiments,
    lab_findings,
    load_floor_queries,
    out_of_fold_regimes,
    parse_counties,
    release_matches,
    state_profiles,
)
from lyme_gap_atlas_ml.floor_presence_report import render_comment
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import prepare_finding
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaWriteError
from lyme_gap_atlas_ml.snowflake.floor_presence_predictions import (
    PREDICTION_TABLE,
    prediction_table_sql,
    write_prediction_tables,
)

SQL_PATH = Path("sql/validation/188_floor_presence.sql")
FAST = FitConfig(
    seeds=(SEED_PRIMARY, SEED_SECOND),
    gbt_max_iter=8,
    gbt_min_samples_leaf=8,
    bootstrap_replicates=30,
    permutation_draws=2,
)


def test_sql_stays_on_the_allow_list() -> None:
    text = SQL_PATH.read_text(encoding="utf-8")
    queries = load_floor_queries(text)
    assert tuple(queries) == ("release_identity", "cohort_rows")
    joined = "\n".join(queries.values()).upper()
    for column in EXCLUDED_COLUMNS:
        assert column not in joined
    assert "GEOMETRY" not in joined
    assert "PAYLOAD" not in joined


def test_release_pin_and_bad_status() -> None:
    assert release_matches(
        {
            "RELEASE_ID": PINNED_RELEASE_ID,
            "SCHEMA_VERSION": "2.0.0",
            "METHODOLOGY_VERSION": "semantic-2.0.0",
            "SCOPE": "US_COUNTIES",
            "BUNDLE_SHA256": PINNED_BUNDLE_SHA256,
        }
    ) == (True, ())
    with pytest.raises(FloorPresenceError):
        parse_counties([_row(1, human="other")], release_id=PINNED_RELEASE_ID)


def test_regime_ignores_flipped_labels() -> None:
    counties = _counties()
    original = out_of_fold_regimes(state_profiles(counties))
    flipped = tuple(
        County(
            fips=county.fips,
            state=county.state,
            population=county.population,
            svi=county.svi,
            uninsured=county.uninsured,
            rucc=county.rucc,
            published=1 - county.published,
            tick_established=county.tick_established,
            pathogen_present=county.pathogen_present,
        )
        for county in counties
    )
    assert out_of_fold_regimes(state_profiles(flipped)) == original


def test_defaults_match_the_frozen_spec() -> None:
    config = FitConfig()
    assert SPEC_ID == "188-floor-presence-regime/v1"
    assert config.seeds == (SEED_PRIMARY, SEED_SECOND)
    assert config.bootstrap_replicates == 2000
    assert config.permutation_draws == 30
    assert config.gbt_max_iter == 100
    assert AUC_LIFT_MIN == 0.01
    assert PR_LIFT_MIN == 0.0
    assert BRIER_WORSE_MAX == 0.005
    assert SHUFFLE_LIFT_MAX == 0.05


def test_real_lift_requires_the_frozen_gates() -> None:
    wide = LiftInterval(0.02, 0.04, True, 0)
    pr_ok = LiftInterval(0.01, 0.03, True, 0)
    brier_ok = LiftInterval(-0.01, 0.001, True, 0)
    assert is_real_lift(wide, pr_ok, brier_ok, leakage_ok=True)
    assert not is_real_lift(LiftInterval(0.009, 0.04, True, 0), pr_ok, brier_ok, leakage_ok=True)
    assert not is_real_lift(wide, pr_ok, brier_ok, leakage_ok=False)
    assert not is_real_lift(wide, pr_ok, LiftInterval(-0.01, 0.02, True, 0), leakage_ok=True)


def test_disposition_rules() -> None:
    advance = decide(
        _fits(real=True),
        leakage_invariant=True,
        shuffled_auc_lift=0.01,
    )
    assert advance.method == "keep"
    assert advance.product == "advance"
    neither = decide(
        _fits(real=False),
        leakage_invariant=True,
        shuffled_auc_lift=0.01,
    )
    assert neither.method == "keep"
    assert neither.product == "stop"
    leaked = decide(
        _fits(real=True),
        leakage_invariant=False,
        shuffled_auc_lift=0.2,
    )
    assert leaked.method == "revise"
    assert leaked.product == "investigate"
    assert leaked.logistic_real_lift is False


def test_synthetic_fit_is_leakage_safe_and_has_no_county_file_rows() -> None:
    analysis = analyze(_counties(), config=FAST, expect_national=False)
    assert analysis.leakage_invariant
    assert len(analysis.predictions) == len(_counties()) * 2 * 2
    assert {row.model_family for row in analysis.predictions} == {FAMILY_LOGISTIC, FAMILY_GBT}
    logistic = [item for item in analysis.fits if item.family == FAMILY_LOGISTIC]
    assert abs(logistic[0].baseline.roc_auc - logistic[1].baseline.roc_auc) < 1e-6
    comment = render_comment(
        analysis,
        run_id="188-floor-presence-regime-test",
        commit="abc1234",
        counts={"REGISTRY.RUNS": 0},
        drive_note="Drive pending",
        grant="not-attempted",
    )
    assert "1. Question" in comment
    assert "7. Reproducibility" in comment
    assert "not a risk score" in comment
    assert "00001" not in comment
    for finding in lab_findings(analysis):
        prepare_finding(finding, finding_id="11111111-1111-1111-1111-111111111111")
    experiments = lab_experiments(analysis, "188-floor-presence-regime-test")
    assert len(experiments) == 4
    assert all(item.config["spec"] == SPEC_ID for item in experiments)


def test_prediction_writer_is_insert_only_and_grants_once() -> None:
    sql = prediction_table_sql()
    assert PREDICTION_TABLE in sql
    assert "DELETE" not in sql.upper()
    assert "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB" in sql
    session = _FakeSession()
    row = PredictionRow(
        fips="01001",
        state="AL",
        published=1,
        model_family=FAMILY_LOGISTIC,
        seed=SEED_PRIMARY,
        baseline_probability=0.2,
        challenger_probability=0.3,
        oof_regime=1,
    )
    result = write_prediction_tables(session, "188-floor-presence-regime-test", [row], ())
    assert result["granted"] is True
    assert result["predictions"] == 1
    executed = [statement for statement, _params in session.executed]
    assert any(statement.startswith("GRANT SELECT") for statement in executed)
    assert any("CREATE TABLE IF NOT EXISTS" in statement for statement in executed)
    inserted = [statement for statement in executed if statement.startswith("INSERT INTO")]
    assert inserted
    assert "01001" not in inserted[0]
    session.existing = True
    with pytest.raises(EdaWriteError):
        write_prediction_tables(session, "188-floor-presence-regime-test", [row], ())


def _fits(*, real: bool) -> tuple[FamilySeedResult, ...]:
    if real:
        auc = LiftInterval(0.02, 0.05, True, 0)
        pr_auc = LiftInterval(0.01, 0.04, True, 0)
        brier = LiftInterval(-0.02, 0.001, True, 0)
    else:
        auc = LiftInterval(-0.01, 0.005, True, 0)
        pr_auc = LiftInterval(-0.02, 0.01, True, 0)
        brier = LiftInterval(-0.001, 0.001, True, 0)
    score = Score(0.7, 0.4, 0.15)
    rows = []
    for seed in (SEED_PRIMARY, SEED_SECOND):
        for family in (FAMILY_LOGISTIC, FAMILY_GBT):
            rows.append(
                FamilySeedResult(
                    family=family,
                    seed=seed,
                    baseline=score,
                    challenger=score,
                    auc_lift=auc,
                    pr_lift=pr_auc,
                    brier_lift=brier,
                )
            )
    return tuple(rows)


def _counties() -> tuple[County, ...]:
    states = ("AA", "BB", "CC", "DD", "EE", "FF")
    rows: list[County] = []
    index = 0
    for state_index, state in enumerate(states):
        rural = state_index < 3
        for offset in range(24):
            index += 1
            rows.append(
                County(
                    fips=f"{index:05d}",
                    state=state,
                    population=1000.0 + offset * 25,
                    svi=(offset % 10) / 10,
                    uninsured=((offset + 3) % 10) / 10,
                    rucc=6 if rural else 1,
                    published=1 if (state_index + offset) % 3 == 0 else 0,
                    tick_established=rural,
                    pathogen_present=rural and offset % 2 == 0,
                )
            )
    assert len(rows) != EXPECTED_COUNTIES
    return tuple(rows)


def _row(index: int, *, human: str) -> dict[str, object]:
    return {
        "STATE": "AL",
        "FIPS": f"{index:05d}",
        "RELEASE_ID": PINNED_RELEASE_ID,
        "POPULATION": 1000,
        "SVI_PERCENTILE": 0.2,
        "UNINSURED_PERCENTILE": 0.3,
        "RUCC_2023": 1,
        "HUMAN_STATUS": human,
        "TICK_STATUS": "No records",
        "BURGDORFERI_STATUS": "No records",
    }


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
