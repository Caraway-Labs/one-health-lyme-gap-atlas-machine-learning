"""Issue 111 documentation classes, with fakes and no live credentials."""

from __future__ import annotations

from pathlib import Path

from lyme_gap_atlas_ml.class_anomaly import load_marked_queries
from lyme_gap_atlas_ml.coverage_audit import PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.cross_signal_disagreement import (
    CLASS_DOCUMENTED,
    CLASS_DOUBLE,
    CLASS_HUMAN_ONLY,
    CLASS_NONE,
    CLASS_PATHOGEN_ONLY,
    CLASS_UNKNOWN,
    EXPECTED_VINTAGES,
    HUMAN_NONE,
    HUMAN_PUBLISHED,
    QUERY_NAMES,
    READING_ARTIFACT,
    READING_FOLLOW,
    READING_SOURCE,
    READING_WEAKER,
    County,
    CrossSignalError,
    analyze,
    display_count,
    lab_findings,
    lab_metrics,
    prepare_counties,
    product_disposition,
    require_live_cohort,
    state_review_bars,
)
from lyme_gap_atlas_ml.cross_signal_report import _drive_lines, render_comment
from lyme_gap_atlas_ml.snowflake.anomaly_scores import RunAlreadyWritten
from lyme_gap_atlas_ml.snowflake.cross_signal_candidates import (
    candidate_table_sql,
    write_candidates,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import prepare_finding
from lyme_gap_atlas_ml.snowflake.eda_writer import prepare_eda_metric
from lyme_gap_atlas_ml.test_selection import spearman_rho, state_cluster_interval

_SOUTH = ("AL", "KY", "MS", "TN", "AR", "LA", "OK", "TX", "FL", "GA", "MD", "NC")


def test_product_disposition_follows_the_frozen_rule() -> None:
    assert product_disposition(True, 11) == "investigate"
    assert product_disposition(False, 11) == "revise"
    assert product_disposition(True, 10) == "stop"
    assert product_disposition(False, 0) == "stop"


def test_classes_keep_unobserved_separate_from_negatives() -> None:
    result = analyze(_rule_counties())
    by_fips = {item.fips: item for item in result.candidates}
    assert result.counts[CLASS_UNKNOWN] == 2
    assert result.counts[CLASS_HUMAN_ONLY] == 1
    assert result.counts[CLASS_DOUBLE] == 2
    assert result.counts[CLASS_NONE] == 1
    assert result.counts[CLASS_DOCUMENTED] == 1
    assert result.counts[CLASS_PATHOGEN_ONLY] == 1
    assert "01003" not in by_fips
    assert "01009" not in by_fips
    assert by_fips["01002"].review_reading == READING_SOURCE
    assert by_fips["01004"].review_reading == READING_FOLLOW
    assert by_fips["48001"].review_reading == READING_ARTIFACT
    assert by_fips["01006"].review_reading == READING_SOURCE
    assert by_fips["01007"].review_reading == READING_WEAKER
    assert by_fips["01008"].review_reading == READING_SOURCE
    assert by_fips["01011"].review_reading == READING_SOURCE
    assert by_fips["01004"].contradicting == "human_no_county_linked_record"
    assert "residual" not in result.__dataclass_fields__
    assert result.disposition == "stop"
    assert result.examples["follow_up"][0].fips == "01004"


def test_svi_above_the_unit_cut_is_rescaled_before_bins() -> None:
    counties = [
        _county(
            "01001",
            state="AL",
            svi=20.0,
            human=HUMAN_PUBLISHED,
            tick="Established",
            pathogen="Present",
        ),
        _county("01002", state="AL", svi=80.0),
    ]
    result = analyze(counties)
    assert result.svi_rescaled is True
    assert result.svi_max == 0.8


def test_prepare_rejects_a_bad_fips_and_an_unknown_status() -> None:
    row = _row("01001")
    row["FIPS"] = "1001"
    try:
        prepare_counties([row], release_id="rel")
    except CrossSignalError as error:
        assert "five digits" in str(error)
    else:
        raise AssertionError("short FIPS was accepted")
    row = _row("01001")
    row["TICK_STATUS"] = "Maybe"
    try:
        prepare_counties([row], release_id="rel")
    except CrossSignalError as error:
        assert "status" in str(error)
    else:
        raise AssertionError("unknown status was accepted")


def test_live_gate_stops_on_a_vintage_mismatch() -> None:
    release = {
        "RELEASE_ID": PINNED_RELEASE_ID,
        "BUNDLE_SHA256": PINNED_BUNDLE_SHA256,
        "SCHEMA_VERSION": "2.0.0",
        "METHODOLOGY_VERSION": "semantic-2.0.0",
        "SCOPE": "US_COUNTIES",
    }
    vintages = dict(EXPECTED_VINTAGES)
    vintages["human"] = "2022"
    try:
        require_live_cohort((_county("01001"),), release, vintages)
    except CrossSignalError as error:
        assert "vintage" in str(error)
    else:
        raise AssertionError("vintage mismatch was accepted")


def test_state_cluster_interval_and_spearman_reuse_the_116_helpers() -> None:
    short = state_cluster_interval(tuple("ABCDEFGHI"), lambda _draw: 1.0, 1112026)
    assert short.estimable is False
    keys = tuple(f"{index:02d}" for index in range(12))
    interval = state_cluster_interval(keys, lambda draw: float(len(draw)), 1112026)
    assert interval.estimable is True
    assert interval.low is not None and interval.high is not None
    assert interval.low <= 12 <= interval.high
    assert spearman_rho(((1.0, 1.0), (2.0, 2.0), (3.0, 3.0))) == 1.0


def test_publishing_state_double_gap_is_the_follow_up_reading() -> None:
    result = analyze(_publishing_counties())
    assert result.follow_up_n == 24
    assert result.artifact_double_gap_n == 0
    assert result.disposition == "revise"
    assert result.references_match is False
    assert len(result.candidates) == 24
    assert {item.review_reading for item in result.candidates} == {READING_FOLLOW}
    assert all(item.vintage_mismatch for item in result.candidates)
    national = result.count_intervals[("national", "US", CLASS_DOUBLE)]
    assert national.estimable is True
    northeast = result.count_intervals[("census_region", "Northeast", CLASS_DOUBLE)]
    assert northeast.estimable is False
    metrics = [prepare_eda_metric(metric) for metric in lab_metrics(result)]
    state_gap = next(
        metric
        for metric in metrics
        if metric.metric_name == "class_count"
        and metric.geography_id == "AL"
        and metric.dimensions_json is not None
        and "double_gap" in metric.dimensions_json
        and "zero_count" not in metric.dimensions_json
    )
    assert state_gap.is_suppressed is True
    assert state_gap.metric_value is None
    zero = next(
        metric
        for metric in metrics
        if metric.metric_name == "class_count"
        and metric.geography_type == "national"
        and metric.dimensions_json is not None
        and CLASS_PATHOGEN_ONLY in metric.dimensions_json
    )
    assert zero.is_suppressed is False
    assert zero.metric_value == 0.0
    findings = lab_findings(result)
    prepared = prepare_finding(findings[0], finding_id="11111111-1111-1111-1111-111111111111")
    assert prepared.disposition == "revise"
    assert prepared.statement
    comment = render_comment(
        result,
        run_id="111-cross-signal-disagreement-test",
        git_commit="abc1234",
        row_counts={"EDA.FINDINGS": 3},
        drive_lines=("Drive upload pending",),
    )
    assert "## 1. Question" in comment
    drive = _drive_lines()
    assert any("1Jpw5rGYfsVSKiVZ14QNx0CJab2mlbgbU" in line for line in drive)
    assert all("was not kept" not in line for line in drive)
    assert "not incidence, risk, or causation" in comment
    assert display_count(2) == "<11"
    assert all(height is None for _state, _label, height in state_review_bars(result))


def test_candidate_writer_stays_in_the_lab_and_does_not_grant() -> None:
    sql = candidate_table_sql()
    assert "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.CROSS_SIGNAL_CANDIDATES_111" in sql
    assert "GRANT" not in sql.upper()
    session = _Session()
    result = analyze(_rule_counties())
    written = write_candidates(session, "111-cross-signal-disagreement-test", result.candidates)
    assert written == len(result.candidates)
    assert all("GRANT" not in statement.upper() for statement in session.statements)
    session.count = 1
    try:
        write_candidates(session, "111-cross-signal-disagreement-test", result.candidates)
    except RunAlreadyWritten:
        pass
    else:
        raise AssertionError("an existing run was inserted again")


def test_validation_sql_matches_the_registered_names() -> None:
    text = Path("sql/validation/111_cross_signal_disagreement.sql").read_text(encoding="utf-8")
    queries = load_marked_queries(text, QUERY_NAMES)
    assert "POPULATION" in queries["cohort_rows"]
    assert "GEOMETRY" not in queries["cohort_rows"].upper()
    assert "PAYLOAD" not in queries["cohort_rows"].upper()


class _Session:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.count = 0

    def query(self, sql: str, params: object = None) -> list[tuple[object, ...]]:
        self.statements.append(sql)
        if "CURRENT_ROLE" in sql:
            return [
                (
                    "OH_LYME_ML_AGENT",
                    "OH_LYME_ML_LAB_XS_WH",
                    "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB",
                )
            ]
        return [(self.count,)]

    def execute(self, sql: str, params: object) -> None:
        self.statements.append(sql)


def _publishing_counties() -> list[County]:
    counties: list[County] = []
    for index, state in enumerate(_SOUTH):
        prefix = 10 + index
        counties.append(
            _county(
                f"{prefix:02d}001",
                state=state,
                human=HUMAN_PUBLISHED,
                tick="Established",
                pathogen="Present",
                rucc=1,
                svi=0.2,
                population=200_000.0,
            )
        )
        for suffix in (2, 3):
            counties.append(
                _county(
                    f"{prefix:02d}00{suffix}",
                    state=state,
                    human=HUMAN_NONE,
                    tick="Established",
                    pathogen="Present",
                    rucc=6,
                    svi=0.8,
                    population=8_000.0,
                )
            )
    return counties


def _rule_counties() -> list[County]:
    return [
        _county("01001", human=HUMAN_PUBLISHED, tick="Established", pathogen="Present"),
        _county("01002", human=HUMAN_PUBLISHED, tick="No records", pathogen="No records"),
        _county("01003", human=HUMAN_NONE, tick="No records", pathogen="No records"),
        _county("01004", human=HUMAN_NONE, tick="Established", pathogen="Present"),
        _county(
            "48001",
            state="TX",
            county="Anderson",
            human=HUMAN_NONE,
            tick="Established",
            pathogen="Present",
        ),
        _county("01006", human=HUMAN_NONE, tick="Established", pathogen="No records"),
        _county("01007", human=HUMAN_NONE, tick="Reported", pathogen="Present"),
        _county("01008", human=HUMAN_NONE, tick="Reported", pathogen="No records"),
        _county("01009", human=HUMAN_NONE, tick="Unknown", pathogen="Unknown", in_scope=False),
        _county(
            "01010",
            human=HUMAN_NONE,
            tick="Established",
            pathogen="Present",
            in_scope=False,
        ),
        _county("01011", human=HUMAN_NONE, tick="No records", pathogen="Present"),
    ]


def _county(fips: str, **overrides: object) -> County:
    values: dict[str, object] = {
        "fips": fips,
        "county": "Example",
        "state": "AL",
        "release_id": "rel",
        "population": 20_000.0,
        "svi": 0.4,
        "rucc": 2,
        "human": HUMAN_NONE,
        "tick": "No records",
        "pathogen": "No records",
        "in_scope": True,
    }
    values.update(overrides)
    return County(**values)  # type: ignore[arg-type]


def _row(fips: str) -> dict[str, object]:
    return {
        "FIPS": fips,
        "COUNTY": "Example",
        "STATE": "AL",
        "RELEASE_ID": "rel",
        "POPULATION": 10,
        "SVI_PERCENTILE": 0.2,
        "RUCC_2023": 3,
        "HUMAN_STATUS": HUMAN_NONE,
        "TICK_STATUS": "No records",
        "BURGDORFERI_STATUS": "No records",
        "IN_CONTIGUOUS_TICK_SCOPE": True,
    }
