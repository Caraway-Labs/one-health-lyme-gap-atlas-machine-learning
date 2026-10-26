"""Issue 194 regime versus tick geography. No live warehouse connection."""

from __future__ import annotations

from pathlib import Path

import pytest

from lyme_gap_atlas_ml.coverage_audit import PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.floor_presence import FloorPresenceError, release_matches
from lyme_gap_atlas_ml.regime_tick_geography import (
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
    FamilySeedResult,
    FitConfig,
    GeographyCounty,
    LiftInterval,
    PredictionRow,
    RegimeTickError,
    Score,
    analyze,
    decide,
    feature_width,
    histogram_bins,
    is_real_lift,
    lab_experiments,
    lab_findings,
    load_regime_queries,
    parse_geography,
    shuffled_regime_maps,
    state_tick_shares,
)
from lyme_gap_atlas_ml.regime_tick_report import render_comment
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import prepare_finding
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE, EdaWriteError
from lyme_gap_atlas_ml.snowflake.ml_agent_access import IDENTITY_SQL, ML_AGENT_ROLE
from lyme_gap_atlas_ml.snowflake.regime_tick_predictions import (
    PREDICTION_TABLE,
    READER_ROLES,
    RunAlreadyWritten,
    mark_run_finished,
    prediction_table_sql,
    write_prediction_tables,
)

SQL_PATH = Path("sql/validation/194_regime_tick_geography.sql")
FAST = FitConfig(
    seeds=(SEED_PRIMARY, SEED_SECOND),
    gbt_max_iter=8,
    gbt_min_samples_leaf=4,
    bootstrap_replicates=40,
)


def test_sql_stays_on_the_allow_list() -> None:
    text = SQL_PATH.read_text(encoding="utf-8")
    queries = load_regime_queries(text)
    assert tuple(queries) == ("release_identity", "cohort_rows")
    joined = "\n".join(queries.values()).upper()
    for column in EXCLUDED_COLUMNS:
        assert column not in joined
    assert "CURRENT_COUNTY_ATLAS_V" in joined
    assert "CURRENT_RELEASE_V" in joined


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
        parse_geography([_row(1, human="other")], release_id=PINNED_RELEASE_ID)


def test_tick_share_ignores_floors_and_width_is_frozen() -> None:
    counties = _pair()
    shares = state_tick_shares(counties)
    assert shares["ZA"] == 0.5
    flipped = tuple(
        GeographyCounty(
            fips=county.fips,
            state=county.state,
            population=county.population,
            svi=county.svi,
            uninsured=county.uninsured,
            rucc=county.rucc,
            published=1 - county.published,
            tick_status=county.tick_status,
            pathogen_status=county.pathogen_status,
        )
        for county in counties
    )
    assert state_tick_shares(flipped) == shares
    assert feature_width(challenger=False) == 20
    assert feature_width(challenger=True) == 22
    assert SPEC_ID == "194-regime-vs-tick-geography/v1"
    assert AUC_LIFT_MIN == 0.01
    assert PR_LIFT_MIN == 0.0
    assert BRIER_WORSE_MAX == 0.005
    assert SHUFFLE_LIFT_MAX == 0.05


def test_shuffled_regime_keeps_the_id_constant_inside_a_state() -> None:
    states = ("ZA", "ZB", "ZC", "ZD")
    held = {"ZA": 1, "ZB": 2, "ZC": 1, "ZD": 2}
    maps = {state: dict(held) for state in states}
    shuffled = shuffled_regime_maps(maps, 1949001)
    assigned = {state: shuffled[state][state] for state in states}
    assert sorted(assigned.values()) == sorted(held.values())
    for fold in shuffled.values():
        assert fold == assigned


def test_histogram_omits_bins_between_1_and_10() -> None:
    shown = histogram_bins([0.01] * 12 + [-0.3])
    counts = dict(shown)
    assert counts["-0.10 to 0.00"] == 0 or "-0.10 to 0.00" not in counts
    assert all(count == 0 or count >= 11 for count in counts.values())
    assert 1 not in counts.values()


def test_real_lift_and_disposition() -> None:
    wide = LiftInterval(0.02, 0.04, True, 0)
    pr_ok = LiftInterval(0.01, 0.03, True, 0)
    brier_ok = LiftInterval(-0.01, 0.001, True, 0)
    assert is_real_lift(wide, pr_ok, brier_ok, leakage_ok=True)
    assert not is_real_lift(LiftInterval(0.009, 0.04, True, 0), pr_ok, brier_ok, leakage_ok=True)
    advance = decide(
        _fits(real=True),
        leakage_invariant=True,
        shuffled_auc_lift=0.01,
        shuffle_baseline_gap=0.0,
    )
    assert advance.method == "keep"
    assert advance.product == "advance"
    neither = decide(
        _fits(real=False),
        leakage_invariant=True,
        shuffled_auc_lift=0.01,
        shuffle_baseline_gap=0.0,
    )
    assert neither.method == "keep"
    assert neither.product == "stop"
    leaked = decide(
        _fits(real=True),
        leakage_invariant=False,
        shuffled_auc_lift=0.2,
        shuffle_baseline_gap=0.0,
    )
    assert leaked.method == "revise"
    assert leaked.product == "investigate"
    assert leaked.logistic_real_lift is False


def test_synthetic_fit_is_leakage_safe() -> None:
    analysis = analyze(_counties(), config=FAST, expect_national=False)
    assert analysis.leakage_invariant
    assert analysis.shuffle_baseline_gap <= 1e-6
    assert abs(analysis.shuffled_auc_lift) < 1
    assert len(analysis.predictions) == len(_counties()) * 2 * 2
    logistic = [item for item in analysis.fits if item.family == FAMILY_LOGISTIC]
    assert abs(logistic[0].baseline.roc_auc - logistic[1].baseline.roc_auc) < 1e-6
    comment = render_comment(
        analysis,
        run_id="194-regime-vs-tick-geography-test",
        commit="abc1234",
        counts={"REGISTRY.RUNS": 0},
        drive_note="Drive pending",
        grant="not-attempted",
    )
    assert "1. Question" in comment
    assert "7. Reproducibility" in comment
    assert "99001" not in comment
    assert "risk score" in comment
    for finding in lab_findings(analysis):
        prepare_finding(finding, finding_id="11111111-1111-1111-1111-111111111111")
    experiments = lab_experiments(analysis, "194-regime-vs-tick-geography-test")
    assert len(experiments) == 4
    assert all(item.config["spec"] == SPEC_ID for item in experiments)
    with pytest.raises(RegimeTickError):
        analyze(_counties()[:2], config=FAST, expect_national=False)


def test_prediction_writer_grants_both_roles() -> None:
    sql = prediction_table_sql()
    assert PREDICTION_TABLE.endswith("EDA.REGIME_VS_TICK_GEOGRAPHY_194")
    assert ML_LAB_DATABASE in sql
    assert "DELETE" not in sql.upper()
    session = _FakeSession()
    row = PredictionRow(
        fips="99901",
        state="ZZ",
        published=0,
        model_family=FAMILY_LOGISTIC,
        seed=SEED_PRIMARY,
        baseline_probability=0.2,
        challenger_probability=0.3,
        oof_regime=1,
        state_tick_share=0.25,
    )
    result = write_prediction_tables(session, "194-regime-vs-tick-geography-test", [row], ())
    assert result["predictions"] == 1
    assert result["grants"] == "OH_LYME_PROD_READ=pass,OH_LYME_ML_LAB_READ=pass"
    joined = "\n".join(statement for statement, _params in session.executed)
    for role in READER_ROLES:
        assert f"GRANT SELECT ON TABLE {PREDICTION_TABLE} TO ROLE {role}" in joined
    assert "99901" not in joined
    assert mark_run_finished(session, "194-regime-vs-tick-geography-test") == "pass"
    session.existing = True
    with pytest.raises((RunAlreadyWritten, EdaWriteError)):
        write_prediction_tables(session, "194-regime-vs-tick-geography-test", [row], ())


def _fits(*, real: bool) -> tuple[FamilySeedResult, ...]:
    if real:
        auc = LiftInterval(0.02, 0.05, True, 0)
        pr_auc = LiftInterval(0.01, 0.04, True, 0)
        brier = LiftInterval(-0.02, 0.001, True, 0)
        tree_auc = auc
    else:
        auc = LiftInterval(-0.01, 0.005, True, 0)
        pr_auc = LiftInterval(-0.02, 0.01, True, 0)
        brier = LiftInterval(-0.001, 0.02, True, 0)
        tree_auc = auc
    score = Score(0.9, 0.5, 0.1)
    rows = []
    for seed in (SEED_PRIMARY, SEED_SECOND):
        for family in (FAMILY_LOGISTIC, FAMILY_GBT):
            rows.append(
                FamilySeedResult(
                    family=family,
                    seed=seed,
                    baseline=score,
                    challenger=score,
                    auc_lift=tree_auc if family == FAMILY_GBT else auc,
                    pr_lift=pr_auc,
                    brier_lift=brier,
                )
            )
    return tuple(rows)


def _pair() -> tuple[GeographyCounty, ...]:
    return (
        _county(1, "ZA", published=1, tick="Established"),
        _county(2, "ZA", published=0, tick="No records"),
    )


def _counties() -> tuple[GeographyCounty, ...]:
    states = ("ZA", "ZB", "ZC", "ZD")
    rows: list[GeographyCounty] = []
    index = 99000
    for state_index, state in enumerate(states):
        for offset in range(12):
            index += 1
            published = 1 if state_index < 2 and offset % 2 == 0 else 0
            if state_index == 2 and offset == 0:
                published = 1
            tick = "Established" if state_index < 2 else "No records"
            pathogen = "Present" if state_index == 0 else "No records"
            rows.append(
                _county(
                    index,
                    state,
                    published=published,
                    tick=tick,
                    pathogen=pathogen,
                    rucc=2 if state_index < 2 else 7,
                )
            )
    assert len(rows) != EXPECTED_COUNTIES
    assert all(not row.fips.startswith("01") for row in rows)
    return tuple(rows)


def _county(
    index: int,
    state: str,
    *,
    published: int,
    tick: str,
    pathogen: str = "No records",
    rucc: int = 4,
) -> GeographyCounty:
    return GeographyCounty(
        fips=f"{index:05d}",
        state=state,
        population=1000.0 + index,
        svi=(index % 10) / 10,
        uninsured=((index + 3) % 10) / 10,
        rucc=rucc,
        published=published,
        tick_status=tick,
        pathogen_status=pathogen,
    )


def _row(index: int, *, human: str) -> dict[str, object]:
    return {
        "STATE": "ZZ",
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
        if sql == IDENTITY_SQL:
            return [(ML_AGENT_ROLE, "OH_LYME_ML_LAB_XS_WH", ML_LAB_DATABASE)]
        if "COUNT" in sql:
            return [(1 if self.existing else 0,)]
        if sql.startswith("SHOW GRANTS"):
            return [(role, "SELECT", PREDICTION_TABLE) for role in READER_ROLES]
        return []

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.executed.append((sql, params))
