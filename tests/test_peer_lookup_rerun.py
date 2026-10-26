"""Issue 196 gate rules. Fixtures use made-up ids. No live Snowflake connection."""

from __future__ import annotations

from dataclasses import replace

import pytest

from lyme_gap_atlas_ml.peer_lookup import (
    County,
    ExperimentMetric,
    ExperimentRow,
    NeighborRow,
    lab_metrics,
    score_counties,
)
from lyme_gap_atlas_ml.peer_lookup_rerun import (
    CEILING_EXPECTATION,
    CEILING_K15_EXPECTATION,
    CEILING_SIMULATION_MEDIAN,
    CONDITIONAL_LOW_MIN,
    CONDITIONAL_MEDIAN_MIN,
    NEIGHBOR_READ_SQL,
    PRIOR_RUN_ID,
    decide_rerun,
    exact_stable_jaccard,
    lab_findings_196,
    lab_metrics_196,
    lists_match,
    simulate_stable_ceiling,
)
from lyme_gap_atlas_ml.snowflake.eda_writer import ML_LAB_DATABASE
from lyme_gap_atlas_ml.snowflake.ml_agent_access import IDENTITY_SQL, ML_AGENT_ROLE
from lyme_gap_atlas_ml.snowflake.peer_lookup_rerun import (
    NEIGHBOR_TABLE,
    write_differing_neighbors,
    write_rerun_experiments,
)
from lyme_gap_atlas_ml.snowflake.peer_neighbors import READER_ROLES, RunAlreadyWritten
from lyme_gap_atlas_ml.state_regimes import HUMAN_NONE, HUMAN_PUBLISHED


def test_exact_ceiling_matches_the_frozen_spec() -> None:
    assert round(exact_stable_jaccard(), 6) == CEILING_EXPECTATION
    assert round(exact_stable_jaccard(k=15), 6) == CEILING_K15_EXPECTATION
    assert CONDITIONAL_MEDIAN_MIN == 0.90
    assert CONDITIONAL_LOW_MIN == 0.80


def test_simulation_confirms_the_raw_ceiling_and_the_conditional_ceiling() -> None:
    simulated = simulate_stable_ceiling()
    assert round(simulated.median, 6) == CEILING_SIMULATION_MEDIAN
    assert simulated.conditional_median == pytest.approx(1.0)
    assert simulated.failed == 0


def test_conditional_score_is_one_on_a_fixed_embedding() -> None:
    analysis = score_counties(_panel(), _clusters(), replicates=4, min_contributing=20)
    assert analysis.conditional_median == pytest.approx(1.0)
    assert analysis.conditional_low == pytest.approx(1.0)
    assert analysis.conditional_median_b == pytest.approx(1.0)
    decision = decide_rerun(analysis)
    assert "bootstrap" not in decision.failures
    missed = decide_rerun(replace(analysis, conditional_median=0.89, conditional_low=0.79))
    assert "bootstrap" in missed.failures
    assert missed.method == "revise"


def test_cosine_metric_uses_its_own_denominator() -> None:
    analysis = score_counties(_panel(), _clusters(), replicates=2, min_contributing=20)
    shifted = replace(
        analysis,
        type_agreement_euclidean_n=770,
        type_agreement_cosine_n=776,
        type_agreement_cosine=0.94,
    )
    original = {metric.metric_name: metric for metric in lab_metrics(shifted)}
    updated = {metric.metric_name: metric for metric in lab_metrics_196(shifted)}
    assert original["type_agreement_cosine"].n_underlying == 770
    assert updated["type_agreement_cosine"].n_underlying == 776
    assert updated["conditional_median_jaccard"].metric_value == pytest.approx(1.0)


def test_finding_disposition_matches_the_statement() -> None:
    analysis = score_counties(_panel(), _clusters(), replicates=2, min_contributing=20)
    decision = replace(
        decide_rerun(analysis),
        method="keep",
        product="investigate",
        failures=(),
        method_column="keep",
        product_column="follow-up",
    )
    method, product = lab_findings_196(analysis, decision)
    assert method.disposition == "keep"
    assert method.disposition in method.statement
    assert product.disposition == "follow-up"
    assert product.disposition in product.statement
    assert "investigate" not in product.statement


def test_neighbor_read_does_not_select_free_text_or_names() -> None:
    assert PRIOR_RUN_ID in NEIGHBOR_READ_SQL
    for banned in ("GEOMETRY", "PART_TEXT", "COUNTY_NAME", "CONTEXT_LIMITATIONS", "PAYLOAD"):
        assert banned not in NEIGHBOR_READ_SQL
    stored = {"99001": ("99002,99003,99004,99005,99006", "99002,99003,99004,99005,99007")}
    row = NeighborRow(
        fips="99001",
        county_name="Made Up",
        state="ZZ",
        cluster_id=None,
        situation="other",
        prototype_cluster_id=1,
        euclidean_neighbors="99002,99003,99004,99005,99006",
        cosine_neighbors="99002,99003,99004,99005,99007",
        euclidean_distance_k=0.2,
        baseline_peer_n=12,
        leave_state_type_agreement=None,
    )
    assert lists_match(stored, (row,))
    assert not lists_match(stored, ())


class _Session:
    def __init__(self, existing: int = 0) -> None:
        self.existing = existing
        self.calls: list[str] = []
        self.params: list[tuple[object, ...]] = []

    def query(self, sql: str, params: object = None) -> list[tuple[object, ...]]:
        self.calls.append(sql)
        if sql == IDENTITY_SQL:
            return [(ML_AGENT_ROLE, "OH_LYME_ML_LAB_XS_WH", ML_LAB_DATABASE)]
        if sql.startswith("SELECT COUNT"):
            return [(self.existing,)]
        if sql.startswith("SHOW GRANTS"):
            return [(role, "SELECT", NEIGHBOR_TABLE) for role in READER_ROLES]
        raise AssertionError(sql if params is None else f"{sql} {params}")

    def execute(self, sql: str, params: object) -> None:
        self.calls.append(sql)
        self.params.append(tuple(params) if isinstance(params, tuple) else tuple(params))


def test_experiment_insert_skips_a_small_cell_and_refuses_a_repeat() -> None:
    session = _Session()
    experiment = ExperimentRow(
        experiment_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        hypothesis="Conditional neighbors.",
        model_family="euclidean_knn",
        config={"k": 5},
        split_definition={"unit": "county"},
        status="succeeded",
        metrics=(
            ExperimentMetric("national", "conditional_bootstrap_jaccard", 1.0, 40, 1.0, 1.0),
            ExperimentMetric("national", "tiny", 1.0, 4, None, None),
        ),
    )
    write_rerun_experiments(session, "196-peer-county-rerun-20261026T2200Z", [experiment])
    bound = " ".join(str(item) for params in session.params for item in params)
    assert "conditional_bootstrap_jaccard" in bound
    assert "tiny" not in bound
    assert "DELETE" not in "\n".join(session.calls).upper()
    with pytest.raises(RunAlreadyWritten):
        write_rerun_experiments(_Session(existing=1), "196-peer-county-rerun-20261026T2200Z", [])


def test_differing_neighbor_table_grants_both_reader_roles() -> None:
    session = _Session()
    row = NeighborRow(
        fips="99001",
        county_name="Made Up",
        state="ZZ",
        cluster_id=1,
        situation="other",
        prototype_cluster_id=1,
        euclidean_neighbors="99002,99003,99004,99005,99006",
        cosine_neighbors="99002,99003,99004,99005,99007",
        euclidean_distance_k=0.2,
        baseline_peer_n=12,
        leave_state_type_agreement=0.5,
    )
    grant = write_differing_neighbors(session, "196-peer-county-rerun-20261026T2200Z", [row])
    assert grant == "OH_LYME_PROD_READ=pass,OH_LYME_ML_LAB_READ=pass"
    joined = "\n".join(session.calls)
    assert "PEER_COUNTY_NEIGHBORS_196" in joined
    assert "99001" in " ".join(str(item) for params in session.params for item in params)


def _clusters() -> dict[str, int]:
    return {f"{index:05d}": 1 if index <= 20 else 2 for index in range(1, 41)}


def _panel() -> tuple[County, ...]:
    rows = []
    for index in range(1, 41):
        if index == 1:
            human, tick, pathogen = HUMAN_NONE, "Established", "Present"
        elif index == 2:
            human, tick, pathogen = HUMAN_NONE, "Established", "No records"
        elif index == 3:
            human, tick, pathogen = HUMAN_PUBLISHED, "Established", "Present"
        elif index == 4:
            human, tick, pathogen = HUMAN_NONE, "No records", "No records"
        else:
            human, tick, pathogen = HUMAN_NONE, "Reported", "Unknown"
        rows.append(
            County(
                fips=f"{index:05d}",
                name=f"County {index}",
                state="AA" if index <= 20 else "BB",
                population=1000.0 + index,
                svi=index / 100,
                uninsured=min(0.95, 0.05 + index / 80),
                rucc=(index % 9) + 1,
                human_status=human,
                scapularis="Established" if index % 2 == 0 else "No records",
                pacificus="No records",
                burgdorferi=pathogen,
                tick_status=tick,
            )
        )
    return tuple(rows)
