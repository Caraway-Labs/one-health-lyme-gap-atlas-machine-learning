"""Issue 123 state reporting regimes. No live warehouse connection."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from lyme_gap_atlas_ml.coverage_audit import PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.peer_clusters import sklearn_version
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import prepare_finding
from lyme_gap_atlas_ml.snowflake.eda_writer import prepare_eda_metric
from lyme_gap_atlas_ml.snowflake.ml_agent_access import StatementError
from lyme_gap_atlas_ml.snowflake.state_regime_groups import (
    _GRANT,
    GROUP_TABLE,
    group_table_sql,
    write_group_tables,
)
from lyme_gap_atlas_ml.state_regimes import (
    DESCRIPTIVE_FEATURES,
    EXPECTED_STATES,
    PUBLICATION_FREE_FEATURES,
    SCHEMA_VERSION,
    SCOPE,
    SPEC_ID,
    Analysis,
    Decision,
    KFit,
    ProfileFit,
    QuestionLabels,
    StateProfile,
    StateRegimeError,
    aggregate_states,
    analyze,
    assignment_rows,
    decide,
    descriptive_raw,
    feature_sentence,
    lab_experiments,
    lab_findings,
    lab_metrics,
    load_state_queries,
    publication_free_raw,
    release_matches,
    require_cohort,
)

SQL_PATH = Path("sql/validation/123_state_regimes.sql")
POSTAL = (
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "DC",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
)


def test_queries_read_the_floor_and_not_free_text() -> None:
    queries = load_state_queries(SQL_PATH.read_text(encoding="utf-8"))
    joined = "\n".join(queries.values()).upper()
    assert "INCIDENCE_FLOOR_2023" in joined
    assert "RUCC_2023" in joined
    for token in ("LIMITATIONS", "PART_TEXT", "PAYLOAD", "GEOMETRY", "CASE_COUNT_FLOOR"):
        assert token not in joined
    assert "\n    COUNTY," not in joined
    assert "\n    COUNTY\n" not in joined
    assert SPEC_ID == "123-state-reporting-regimes/v1"


def test_release_pin_matches_the_frozen_spec() -> None:
    ok, reasons = release_matches(
        {
            "RELEASE_ID": PINNED_RELEASE_ID,
            "SCHEMA_VERSION": SCHEMA_VERSION,
            "METHODOLOGY_VERSION": "semantic-2.0.0",
            "SCOPE": SCOPE,
            "BUNDLE_SHA256": PINNED_BUNDLE_SHA256,
        }
    )
    assert ok
    assert reasons == ()
    shifted, mismatch = release_matches(
        {
            "RELEASE_ID": "other",
            "SCHEMA_VERSION": SCHEMA_VERSION,
            "METHODOLOGY_VERSION": "semantic-2.0.0",
            "SCOPE": SCOPE,
            "BUNDLE_SHA256": PINNED_BUNDLE_SHA256,
        }
    )
    assert not shifted
    assert mismatch == ("release_id",)


def test_missing_median_stays_missing_and_out_of_the_publication_free_profile() -> None:
    quiet = _county("AA", "01001", "no_county_linked_record", None)
    quiet_2 = _county("AA", "01003", "no_county_linked_record", None)
    loud = _county("BB", "02001", "published_count_floor", 10)
    loud_2 = _county("BB", "02003", "published_count_floor", 20)
    other = _county("CC", "04001", "published_count_floor", 30)
    other_2 = _county("CC", "04003", "published_count_floor", 40)
    states = aggregate_states(
        (quiet, quiet_2, loud, loud_2, other, other_2),
        release_id=PINNED_RELEASE_ID,
    )
    hidden = states[0]
    assert hidden.state == "AA"
    assert hidden.zero_published
    assert hidden.median_published_floor is None
    assert hidden.published_share == 0
    assert states[1].median_published_floor == 15
    assert states[2].median_published_floor == 35
    raw, contrast = descriptive_raw(states)
    assert contrast
    assert raw[0, 3] == 0
    assert raw[0, 4] == 0
    changed = (replace(states[0], published_share=0.4), states[1], states[2])
    assert publication_free_raw(states).tolist() == publication_free_raw(changed).tolist()
    assert descriptive_raw(changed)[0][0, 0] != raw[0, 0]


def test_a_floor_on_an_unpublished_county_stops() -> None:
    row = _county("AA", "01001", "no_county_linked_record", 5)
    try:
        aggregate_states((row,), release_id=PINNED_RELEASE_ID)
    except StateRegimeError as error:
        assert "unpublished" in str(error)
    else:
        raise AssertionError("expected a stop")


def test_cohort_gate_requires_the_atlas_counts() -> None:
    try:
        require_cohort(())
    except StateRegimeError as error:
        assert "51" in str(error)
    else:
        raise AssertionError("expected a stop")


def test_small_state_keeps_its_group_and_loses_its_shares() -> None:
    analysis = _hand_analysis(cross_ari=0.2)
    rows = {row.state: row for row in assignment_rows(analysis)}
    small = rows["DC"]
    assert small.descriptive_group >= 1
    assert small.publication_free_group >= 1
    assert small.published_share is None
    assert small.median_published_floor is None
    assert small.county_n is None
    assert small.zero_published is None
    large = rows["WY"]
    assert large.county_n is not None and large.county_n >= 11
    assert large.zero_published is False
    assert large.median_published_floor == 40
    zero = rows["AL"]
    assert zero.zero_published is True
    assert zero.median_published_floor is None
    assert zero.published_share == 0


def test_advance_requires_a_low_cross_profile_rand_index() -> None:
    advance = decide(_hand_analysis(cross_ari=0.2))
    assert advance.method == "keep"
    assert advance.product == "advance"
    assert advance.feature_profile == "publication_free"
    assert "publication-free profile may be used" in feature_sentence(advance)
    investigate = decide(_hand_analysis(cross_ari=0.9))
    assert investigate.method == "keep"
    assert investigate.product == "investigate"
    assert investigate.feature_profile is None
    assert feature_sentence(investigate).startswith("No profile may be used")


def test_lab_records_suppress_small_cells_and_accept_the_writers() -> None:
    analysis = _hand_analysis(cross_ari=0.2)
    prepared = [prepare_eda_metric(metric) for metric in lab_metrics(analysis)]
    assert prepared
    assert all(metric.metric_name[:1].isalpha() for metric in prepared)
    findings = lab_findings(analysis)
    assert prepare_finding(findings[0], finding_id="12345678-1234-1234-1234-123456789abc")
    session = _FakeSession()
    result = write_group_tables(
        session,
        "123-state-reporting-regimes-20261026T1200Z",
        assignment_rows(analysis),
        lab_experiments(analysis, "123-state-reporting-regimes-20261026T1200Z"),
    )
    assert result["groups"] == EXPECTED_STATES
    assert result["granted"] is True
    inserted = [
        params
        for sql, params in session.calls
        if sql.startswith("INSERT INTO") and "STATE_REGIME_GROUPS_123" in sql and params
    ]
    small = next(params for params in inserted if params[1] == "DC")
    assert small[2] is None
    assert small[3] is None
    assert small[8] >= 1
    assert "DELETE" not in group_table_sql().upper()
    assert GROUP_TABLE.endswith("EDA.STATE_REGIME_GROUPS_123")
    assert "OH_LYME_PROD_READ" in _GRANT


def test_separated_states_keep_the_method_and_withhold_the_feature() -> None:
    analysis = analyze(_separated_states())
    assert analysis.matches_107
    assert analysis.decision.method == "keep"
    assert analysis.decision.product == "investigate"
    assert analysis.decision.feature_profile is None
    assert analysis.descriptive.tree_ari == 1
    assert analysis.publication_free.tree_ari == 1
    assert analysis.publication_free.features == PUBLICATION_FREE_FEATURES
    assert "published_share" not in analysis.publication_free.features
    assert set(analysis.descriptive.labels) == {1, 2}
    assert len(analysis.descriptive.labels) == EXPECTED_STATES
    hidden = [state for state in analysis.states if state.zero_published]
    assert len(hidden) == 19
    assert all(state.median_published_floor is None for state in hidden)
    assert sum(state.county_n for state in hidden) == 1437
    labeled = {
        state.state: label
        for state, label in zip(analysis.states, analysis.descriptive.labels, strict=True)
    }
    hidden_codes = {state.state for state in hidden}
    assert all(label >= 1 for code, label in labeled.items() if code in hidden_codes)


def _separated_states() -> tuple[StateProfile, ...]:
    counts = [75] * 19
    counts[0] = 157
    counts[8] = 5
    rows: list[StateProfile] = []
    for index, code in enumerate(POSTAL):
        if index < 19:
            rows.append(
                _profile(
                    code,
                    counts[index],
                    published_share=0.0,
                    tick=0.1,
                    pathogen=0.1,
                    rural=0.8,
                    median=None,
                )
            )
        else:
            rows.append(
                _profile(
                    code,
                    40,
                    published_share=0.8,
                    tick=0.9,
                    pathogen=0.9,
                    rural=0.2,
                    median=40.0,
                )
            )
    return tuple(rows)


def _hand_analysis(cross_ari: float) -> Analysis:
    states = _separated_states()
    zero_labels = tuple(1 if state.zero_published else 2 for state in states)
    profile_d = _fit("descriptive", DESCRIPTIVE_FEATURES, zero_labels, share_only=0.4)
    profile_f = _fit("publication_free", PUBLICATION_FREE_FEATURES, zero_labels, share_only=None)
    return Analysis(
        states=states,
        descriptive=profile_d,
        publication_free=profile_f,
        cross_ari=cross_ari,
        contingency=((19, 0), (0, 32)),
        descriptive_ids=(1, 2),
        publication_free_ids=(1, 2),
        zero_states=19,
        zero_counties=1437,
        matches_107=True,
        questions=QuestionLabels(
            2,
            ("MA",),
            1,
            tuple(state.state for state in states if state.zero_published),
        ),
        decision=Decision("revise", "investigate", None, ()),
        sklearn_version=sklearn_version(),
    )


def _fit(
    name: str,
    features: tuple[str, ...],
    labels: tuple[int, ...],
    *,
    share_only: float | None,
) -> ProfileFit:
    chosen = KFit(
        k=2,
        labels=labels,
        silhouette=0.8,
        loso_median=0.95,
        loso_min=0.9,
        loso_failed=0,
        bootstrap_low=0.9,
        bootstrap_high=1.0,
        bootstrap_estimable=True,
        bootstrap_failed=0,
        admissible=True,
    )
    return ProfileFit(
        name=name,
        features=features,
        seed=1232026,
        chosen=chosen,
        fits=(chosen,),
        labels=labels,
        cut_stable=True,
        average_ari=0.5,
        complete_ari=0.5,
        share_only_ari=share_only,
        tree_ari=1.0,
        cut_height=1.0,
        leaf_order=tuple(range(EXPECTED_STATES)),
        children=tuple((index, index + 1) for index in range(EXPECTED_STATES - 1)),
        distances=tuple(float(index) for index in range(EXPECTED_STATES - 1)),
        median_contrast=True,
    )


def _profile(
    code: str,
    county_n: int,
    *,
    published_share: float,
    tick: float,
    pathogen: float,
    rural: float,
    median: float | None,
) -> StateProfile:
    return StateProfile(
        state=code,
        county_n=county_n,
        published_n=0 if published_share == 0 else 1,
        tick_established_n=1,
        pathogen_present_n=1,
        rural_nonmetro_n=1,
        published_share=published_share,
        tick_established_share=tick,
        pathogen_present_share=pathogen,
        rural_nonmetro_share=rural,
        median_published_floor=median,
        zero_published=published_share == 0,
    )


def _county(state: str, fips: str, human: str, floor: float | None) -> dict[str, object]:
    return {
        "STATE": state,
        "FIPS": fips,
        "RUCC_2023": 6,
        "HUMAN_STATUS": human,
        "TICK_STATUS": "Established",
        "BURGDORFERI_STATUS": "Present",
        "INCIDENCE_FLOOR_2023": floor,
        "RELEASE_ID": PINNED_RELEASE_ID,
    }


class _FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []

    def query(self, sql: str, params: tuple[object, ...] | None = None) -> list[tuple[object, ...]]:
        self.calls.append((sql, params))
        if "CURRENT_ROLE" in sql:
            return [
                (
                    "OH_LYME_ML_AGENT",
                    "OH_LYME_ML_LAB_XS_WH",
                    "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB",
                )
            ]
        if "COUNT" in sql.upper():
            return [(0,)]
        raise StatementError(permission_denied=False)

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.calls.append((sql, params))
