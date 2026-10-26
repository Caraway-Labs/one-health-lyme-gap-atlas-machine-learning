"""Offline checks for the issue 114 association register. No warehouse session."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from lyme_gap_atlas_ml.coverage_audit import CENSUS_REGIONS, PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.cross_domain import (
    SPEC_ID,
    Analysis,
    County,
    CrossDomainError,
    ExperimentMetric,
    ExperimentSpec,
    Loading,
    PairResult,
    PairSpec,
    PcaFit,
    ReproductionResult,
    Spot,
    _average_rank,
    _context_mask,
    _cross_mask,
    _frame,
    _vifs,
    bh,
    bias_corrected_cramers_v,
    lab_findings,
    load_cross_domain_queries,
    pca_share,
    prepare_counties,
    release_matches,
    spearman_arrays,
)
from lyme_gap_atlas_ml.cross_domain_report import render_comment
from lyme_gap_atlas_ml.snowflake.cross_domain_experiments import (
    RunAlreadyWritten,
    experiment_metric_names,
    write_pca_experiments,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import prepare_finding
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE
from lyme_gap_atlas_ml.test_selection import (
    HUMAN_NONE,
    HUMAN_PUBLISHED,
    IntervalEstimate,
    cramers_v,
    spearman_rho,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "validation" / "114_cross_domain.sql"
STATES = tuple(CENSUS_REGIONS)


def test_spearman_arrays_match_the_helper_including_ties() -> None:
    left = np.array([1.0, 2.0, 2.0, 4.0, 5.0])
    right = np.array([1.0, 3.0, 3.0, 2.0, 5.0])
    paired = list(zip(left.tolist(), right.tolist(), strict=True))
    found = spearman_arrays(left, right)
    assert found is not None
    assert found == pytest.approx(spearman_rho(paired))
    assert _average_rank(left).tolist() == pytest.approx([1.0, 2.5, 2.5, 4.0, 5.0])


def test_bias_corrected_v_is_below_the_uncorrected_value() -> None:
    table = [[40, 10], [12, 38]]
    association = cramers_v(table)
    assert association is not None
    corrected = bias_corrected_cramers_v(table)
    assert corrected is not None
    assert corrected < association.v
    phi2 = association.chi2 / association.n
    phi2_tilde = max(0.0, phi2 - 1 / (association.n - 1))
    row_tilde = 2 - 1 / (association.n - 1)
    expected = math.sqrt(phi2_tilde / (row_tilde - 1))
    assert corrected == pytest.approx(expected)


def test_bh_is_monotone_in_the_ordered_tail_shares() -> None:
    adjusted = bh((("a", 0.01), ("b", 0.04), ("c", 0.20)))
    assert adjusted["a"] == pytest.approx(0.03)
    assert adjusted["b"] == pytest.approx(0.06)
    assert adjusted["c"] == pytest.approx(0.20)
    assert adjusted["a"] <= adjusted["b"] <= adjusted["c"]


def test_pca_share_and_duplicate_column_vif() -> None:
    generator = np.random.default_rng(114)
    left = generator.normal(size=40)
    right = generator.normal(size=40)
    matrix = np.column_stack((left, right, left + right))
    share = pca_share(matrix)
    assert share is not None
    assert share == pytest.approx(1.0, abs=1e-8)
    vifs = _vifs(np.column_stack((left, left)), ("left", "copy"))
    assert vifs["left"] == math.inf
    assert vifs["copy"] == math.inf


def test_missing_svi_stays_missing_and_unknown_is_not_zero() -> None:
    counties = (
        _county("01001", "Autauga", None, 0.2, HUMAN_NONE, "Unknown", "Unknown"),
        _county("01003", "Baldwin", 0.4, 0.3, HUMAN_PUBLISHED, "Established", "Present"),
    )
    frame = _frame(counties)
    assert math.isnan(frame.columns["svi_percentile"][0])
    assert frame.tick_code[0] == -1
    assert frame.columns["tick_established"][0] != 0
    assert math.isnan(frame.columns["tick_established"][0])
    assert not bool(_cross_mask(frame)[0])
    assert not bool(_context_mask(frame)[0])
    assert bool(_cross_mask(frame)[1])


def test_unit_rule_divides_a_percentile_above_one() -> None:
    counties = (
        _county("01001", "Autauga", 50.0, 20.0, HUMAN_NONE, "No records", "No records"),
        _county("01003", "Baldwin", 10.0, 5.0, HUMAN_PUBLISHED, "Reported", "Present"),
    )
    frame = _frame(counties)
    assert frame.svi_rescaled is True
    assert frame.uninsured_rescaled is True
    assert frame.columns["svi_percentile"][0] == pytest.approx(0.5)


def test_prepare_counties_rejects_a_short_cohort_and_accepts_the_pin() -> None:
    with pytest.raises(CrossDomainError, match="3144"):
        prepare_counties((_row(0),), release_id=PINNED_RELEASE_ID)
    rows = tuple(_row(index) for index in range(3144))
    counties = prepare_counties(rows, release_id=PINNED_RELEASE_ID)
    assert len(counties) == 3144
    assert counties[0].fips == "00000"
    release_matches(_release_row())
    with pytest.raises(CrossDomainError, match="release"):
        release_matches({**_release_row(), "RELEASE_ID": "other"})


def test_queries_stay_on_the_atlas_columns() -> None:
    queries = load_cross_domain_queries(SQL_PATH.read_text(encoding="utf-8"))
    assert set(queries) == {"release_identity", "cohort_rows"}
    combined = "\n".join(queries.values()).upper()
    assert "CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V" not in combined
    assert "GEOMETRY" not in combined
    assert "PAYLOAD" not in combined
    assert "PART_TEXT" not in combined
    assert "LIMITATIONS" not in combined


def test_experiment_writer_is_insert_only() -> None:
    experiment = ExperimentSpec(
        experiment_id="114-cross-domain-test-pca-context",
        model_family="pca",
        hypothesis="Three-feature correlation PCA.",
        config={"spec_id": SPEC_ID, "seed": 1142026},
        split_definition={"cohort": "context", "imputation": "none"},
        status="succeeded",
        metrics=(ExperimentMetric("pc1_pc2", "explained_variance_share", 0.885, None, None, 3144),),
    )
    session = _FakeSession()
    written = write_pca_experiments(session, "114-cross-domain-test", (experiment,))
    assert written == 1
    sql = "\n".join(call[0] for call in session.calls)
    assert ML_LAB_DATABASE in sql
    assert "DELETE" not in sql.upper()
    assert "GRANT" not in sql.upper()
    assert experiment_metric_names() == (
        "explained_variance_share",
        "loading",
        "condition_number",
        "vif",
    )
    with pytest.raises(RunAlreadyWritten):
        write_pca_experiments(_FakeSession(existing=1), "114-cross-domain-test", (experiment,))


def test_findings_and_comment_use_the_allowed_disposition_words() -> None:
    analysis = _analysis()
    findings = lab_findings(analysis)
    assert [record.disposition for record in findings] == ["keep", "follow-up", "follow-up", "keep"]
    for index, record in enumerate(findings, start=1):
        prepared = prepare_finding(record, finding_id=f"11411411-0000-4000-8000-{index:012d}")
        assert "LIMITATIONS" not in prepared.statement.upper()
    comment = render_comment(
        analysis,
        run_id="114-cross-domain-20261026T1200Z",
        git_commit="abc123",
        row_counts={"REGISTRY.RUNS": 1},
        drive_links={"redundancy-heatmap.png": "https://drive.google.com/file/d/example/view"},
    )
    for heading in (
        "## 1. Question",
        "## 2. Method",
        "## 3. Key findings",
        "## 4. Caveats",
        "## 5. Disposition",
        "## 6. Artifacts",
        "## 7. Reproducibility",
    ):
        assert heading in comment
    assert "110-peer-county-clusters-20261026T0644Z" in comment
    assert "no GRANT" in comment
    assert "keeps the October 13 description" in comment


def _county(
    fips: str,
    name: str,
    svi: float | None,
    uninsured: float,
    human: str,
    tick: str,
    pathogen: str,
) -> County:
    return County(fips, name, "AL", 1000.0, svi, uninsured, 2, human, tick, pathogen, True)


def _row(index: int) -> dict[str, object]:
    state = STATES[index % len(STATES)]
    return {
        "FIPS": f"{index:05d}",
        "COUNTY": "County",
        "STATE": state,
        "RELEASE_ID": PINNED_RELEASE_ID,
        "POPULATION": 1000 + index,
        "SVI_PERCENTILE": 0.4,
        "UNINSURED_PERCENTILE": 0.2,
        "RUCC_2023": 2,
        "HUMAN_STATUS": HUMAN_NONE,
        "TICK_STATUS": "No records",
        "BURGDORFERI_STATUS": "No records",
        "IN_CONTIGUOUS_TICK_SCOPE": True,
    }


def _release_row() -> dict[str, object]:
    return {
        "RELEASE_ID": PINNED_RELEASE_ID,
        "SCHEMA_VERSION": "2.0.0",
        "BUNDLE_SHA256": PINNED_BUNDLE_SHA256,
        "METHODOLOGY_VERSION": "semantic-2.0.0",
        "SCOPE": "US_COUNTIES",
    }


def _analysis() -> Analysis:
    interval = IntervalEstimate(0.2, 0.5, 0, 2000, 49, 2000, True, 0.0)
    spec = PairSpec(
        "D1",
        "SVI x uninsured percentile",
        "svi_percentile",
        "uninsured_percentile",
        "spearman",
        True,
    )
    pair = PairResult(
        spec=spec,
        estimate=0.4,
        n=3144,
        cluster=interval,
        naive=interval,
        width_ratio=1.0,
        partial=0.3,
        partial_low=0.1,
        partial_high=0.5,
        partial_n=3144,
        region_material=False,
        bh=0.01,
        holm_adjusted=0.01,
        qualified=True,
        confounder=False,
        redundancy=False,
        rank_tier=0,
    )
    context = PcaFit(
        name="context",
        n=3144,
        features=("log_population", "svi_percentile", "uninsured_percentile"),
        shares=(0.70, 0.185, 0.115),
        two_component=0.885,
        condition_number=2.0,
        vifs={"log_population": 1.2, "svi_percentile": 1.1, "uninsured_percentile": 1.1},
        loadings=(Loading("log_population", 1, 0.5, 0.4, 0.6),),
        region_shares={"Northeast": 0.885},
        region_material=False,
        estimable=True,
    )
    cross = PcaFit(
        name="cross_domain",
        n=3109,
        features=context.features,
        shares=(0.4, 0.2),
        two_component=0.6,
        condition_number=4.0,
        vifs={"log_population": 1.4},
        loadings=(Loading("human_published", 1, 0.1, None, None),),
        region_shares={},
        region_material=False,
        estimable=True,
    )
    return Analysis(
        release_id=PINNED_RELEASE_ID,
        counties=3144,
        published_n=651,
        no_record_n=2493,
        svi_rescaled=False,
        uninsured_rescaled=False,
        context_n=3144,
        cross_n=3109,
        pairs=(pair,),
        reproduction=(
            ReproductionResult(
                "tick_pathogen", 0.5607, 0.55, 3109, "0.5607", True, 0.4650, 0.6524, 0.4
            ),
        ),
        context_pca=context,
        cross_pca=cross,
        small_state_share=0.885,
        scope_share=0.884,
        small_state_material=False,
        scope_material=False,
        representation="keep",
        follow_up="advance",
        recommendations=(
            "Keep in the joint context block: log_population, svi_percentile.",
            "Drop January climate. No native-double field reached 20 usable days.",
        ),
        spots=(
            Spot(
                "published floor",
                "01001",
                "Autauga",
                "AL",
                HUMAN_PUBLISHED,
                "Established",
                "Present",
            ),
        ),
        heatmap_labels=("svi_percentile",),
        heatmap=((1.0,),),
        family_complete=True,
    )


class _FakeSession:
    def __init__(self, existing: int = 0) -> None:
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []
        self.existing = existing

    def query(self, sql: str, params: tuple[object, ...] | None = None) -> list[tuple[object, ...]]:
        self.calls.append((sql, params))
        if "CURRENT_ROLE" in sql:
            return [("OH_LYME_ML_AGENT", "OH_LYME_ML_LAB_XS_WH", ML_LAB_DATABASE)]
        return [(self.existing,)]

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> None:
        self.calls.append((sql, params))
