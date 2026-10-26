"""Issue 196 gate on top of the issue 192 lookup.

The embedding, neighbor search, and raw bootstrap stay in ``peer_lookup``.
This module adds the conditional retained-neighbor gate, the cosine
denominator, and the stable-list ceiling. It does not rewrite issue 192 rows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from math import comb
from uuid import NAMESPACE_URL, uuid5

import numpy as np

from lyme_gap_atlas_ml.peer_lookup import (
    BOOTSTRAP_REPLICATES,
    COSINE_JACCARD_MIN,
    CROSS_STATE_MIN,
    DROP_ALL_MIN,
    GAP_RUN_ID,
    IN_SAMPLE_GAP_MIN,
    K_PRIMARY,
    K_SENSITIVITY,
    LSO_AGREEMENT_MIN,
    LSO_BASELINE_GAP_MIN,
    LSO_JACCARD_ADVANCE,
    LSO_JACCARD_MIN,
    PRIMARY_SEED,
    RECOVERY_MIN,
    SECOND_SEED,
    SEED_MEDIAN_GAP_MAX,
    SINGLE_BLOCK_MAX,
    SPEC_ID,
    TIE_EPS,
    Analysis,
    ExperimentMetric,
    ExperimentRow,
    lab_metrics,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import FindingRecord
from lyme_gap_atlas_ml.snowflake.eda_writer import EdaMetric

SPEC_ID_196 = "196-peer-county-rerun/v1"
ISSUE_NUMBER = 196
RUN_PREFIX = "196-peer-county-rerun-"
PRIOR_RUN_ID = "192-peer-county-lookup-20261026T1859Z"
PRIOR_METHOD = "revise"
CONDITIONAL_MEDIAN_MIN = 0.90
CONDITIONAL_LOW_MIN = 0.80
CEILING_N = 3144
CEILING_K = 5
CEILING_SEED = 1962026
CEILING_REPLICATES = 2000
CEILING_EXPECTATION = 0.499415
CEILING_SIMULATION_MEDIAN = 0.499248
CEILING_K15_EXPECTATION = 0.474395
PRODUCT_COLUMN = {"advance": "keep", "investigate": "follow-up", "stop": "stop"}
NEIGHBOR_READ_SQL = (
    "SELECT FIPS, EUCLIDEAN_NEIGHBORS, COSINE_NEIGHBORS "
    "FROM ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.PEER_COUNTY_NEIGHBORS_192 "
    f"WHERE RUN_ID = '{PRIOR_RUN_ID}' "
    "ORDER BY FIPS"
)


@dataclass(frozen=True)
class RerunDecision:
    method: str
    product: str
    failures: tuple[str, ...]
    method_column: str
    product_column: str


@dataclass(frozen=True)
class CeilingSimulation:
    median: float
    mean: float
    conditional_median: float
    failed: int


def exact_stable_jaccard(n: int = CEILING_N, k: int = CEILING_K) -> float:
    """Expected raw Jaccard of a fixed neighbor order under the bootstrap pool."""
    if n <= k or k < 1:
        raise ValueError("ceiling n must exceed k")
    total = 0.0
    for retained in range(k + 1):
        probability = comb(k, retained) * _present_and_absent(n, retained, k - retained)
        total += probability * retained / (2 * k - retained)
    return total


def simulate_stable_ceiling(
    *,
    n: int = CEILING_N,
    k: int = CEILING_K,
    replicates: int = CEILING_REPLICATES,
    seed: int = CEILING_SEED,
    min_contributing: int = 500,
) -> CeilingSimulation:
    """Median raw Jaccard of a fixed order under the issue 192 pool rule."""
    if n <= k or replicates < 2:
        raise ValueError("ceiling simulation needs n above k and at least two replicates")
    rng = np.random.Generator(np.random.PCG64(seed))
    raw_means: list[float] = []
    conditional_means: list[float] = []
    failed = 0
    indexes = np.arange(n)
    for _ in range(replicates):
        in_pool = np.zeros(n, dtype=bool)
        in_pool[np.unique(rng.choice(n, size=n, replace=True))] = True
        doubled = np.concatenate((in_pool, in_pool))
        cumulative = np.cumsum(doubled)
        start = indexes + 1
        stop = start + k
        retained = cumulative[stop - 1] - np.where(start == 0, 0, cumulative[start - 1])
        others = int(in_pool.sum()) - in_pool.astype(int)
        eligible = others >= k
        denominator = (2 * k) - retained
        raw = np.divide(
            retained,
            denominator,
            out=np.full(n, np.nan),
            where=eligible & (denominator != 0),
        )
        conditional = np.where(eligible & (retained > 0), 1.0, np.nan)
        raw_finite = raw[np.isfinite(raw)]
        conditional_finite = conditional[np.isfinite(conditional)]
        if raw_finite.size >= min_contributing:
            raw_means.append(float(raw_finite.mean()))
        else:
            failed += 1
        if conditional_finite.size >= min_contributing:
            conditional_means.append(float(conditional_finite.mean()))
    if not raw_means or not conditional_means:
        raise ValueError("ceiling simulation produced no replicate")
    return CeilingSimulation(
        median=float(np.median(np.array(raw_means))),
        mean=float(np.mean(np.array(raw_means))),
        conditional_median=float(np.median(np.array(conditional_means))),
        failed=failed,
    )


def decide_rerun(analysis: Analysis) -> RerunDecision:
    """Apply the frozen issue 196 gate. The raw Jaccard median is not a gate."""
    failures = _failures(analysis)
    method = "keep" if not failures else "revise"
    if (
        method == "keep"
        and analysis.cross_state_share >= CROSS_STATE_MIN
        and analysis.lso_jaccard >= LSO_JACCARD_ADVANCE
        and analysis.in_sample_gap is not None
        and analysis.in_sample_gap >= IN_SAMPLE_GAP_MIN
    ):
        product = "advance"
    else:
        product = "investigate"
    return RerunDecision(
        method=method,
        product=product,
        failures=failures,
        method_column=method,
        product_column=PRODUCT_COLUMN[product],
    )


def lab_metrics_196(analysis: Analysis) -> list[EdaMetric]:
    """Issue 192 aggregate rows, with the cosine denominator and the new gate."""
    rows = [
        _with_cosine_n(metric, analysis.type_agreement_cosine_n)
        if metric.metric_name == "type_agreement_cosine"
        else metric
        for metric in lab_metrics(analysis)
    ]
    _rate(rows, "conditional_median_jaccard", analysis.conditional_median, analysis.county_n)
    _rate(rows, "conditional_low_jaccard", analysis.conditional_low, analysis.county_n)
    _rate(rows, "conditional_high_jaccard", analysis.conditional_high, analysis.county_n)
    _rate(rows, "conditional_median_seed_b", analysis.conditional_median_b, analysis.county_n)
    _rate(rows, "conditional_k15_median", analysis.conditional_k15_median, analysis.county_n)
    rows.append(_metric("stable_ceiling_expectation", CEILING_N, CEILING_EXPECTATION))
    rows.append(
        _metric("stable_ceiling_simulation_median", CEILING_REPLICATES, CEILING_SIMULATION_MEDIAN)
    )
    return rows


def lab_findings_196(analysis: Analysis, decision: RerunDecision) -> tuple[FindingRecord, ...]:
    """Statements use the same disposition word the column stores."""
    failed = ", ".join(decision.failures) if decision.failures else "none"
    method = FindingRecord(
        topic="peer county lookup rerun",
        statement=(
            f"Method disposition is {decision.method_column}. "
            f"Gate failures: {failed}. "
            "A neighbor is similar on the listed context features only. "
            "No ground truth exists, so this is a lookup aid."
        ),
        disposition=decision.method_column,
        n_underlying=analysis.county_n,
        effect_size=analysis.conditional_median,
        ci_low=analysis.conditional_low,
        ci_high=analysis.conditional_high,
        uncertainty_note=(
            "Conditional bootstrap band for neighbor lists. Not a disease-rate interval."
        ),
        evidence={
            "conditional_median": analysis.conditional_median,
            "raw_bootstrap_median": analysis.bootstrap_median,
            "stable_ceiling": CEILING_EXPECTATION,
            "cosine_n": analysis.type_agreement_cosine_n,
        },
    )
    product = FindingRecord(
        topic="steward peer list rerun",
        statement=(
            f"Product disposition is {decision.product_column}. "
            "There is no ground truth. "
            "Situation agreement is partly circular because tick and pathogen "
            "statuses are also distance features. Human status is not."
        ),
        disposition=decision.product_column,
        n_underlying=analysis.county_n,
        effect_size=analysis.type_agreement_lso,
        uncertainty_note="Leave-state-out type agreement against stored community types.",
        evidence={
            "cross_state_share": analysis.cross_state_share,
            "type_agreement_lso": analysis.type_agreement_lso,
        },
    )
    return (method, product)


def experiment_rows_196(analysis: Analysis, run_id: str) -> tuple[ExperimentRow, ...]:
    """Same four comparisons as issue 192, with the conditional bootstrap metric."""
    split = {"unit": "county", "k": K_PRIMARY, "sensitivity_k": K_SENSITIVITY}
    shared = {
        "spec": SPEC_ID_196,
        "parent_spec": SPEC_ID,
        "prior_run_id": PRIOR_RUN_ID,
        "conditional_median_min": CONDITIONAL_MEDIAN_MIN,
        "conditional_low_min": CONDITIONAL_LOW_MIN,
        "sklearn": analysis.sklearn_version,
    }
    families = (
        (
            "euclidean_knn",
            "Exact Euclidean neighbors on the issue 120 embedding.",
            {
                "k": K_PRIMARY,
                "seeds": [PRIMARY_SEED, SECOND_SEED],
                "replicates": BOOTSTRAP_REPLICATES,
            },
            (
                _experiment_metric(
                    "conditional_bootstrap_jaccard",
                    analysis.conditional_median,
                    analysis.county_n,
                    analysis.conditional_low,
                    analysis.conditional_high,
                ),
                _experiment_metric(
                    "raw_bootstrap_jaccard",
                    analysis.bootstrap_median,
                    analysis.county_n,
                    analysis.bootstrap_low,
                    analysis.bootstrap_high,
                ),
                _experiment_metric("lso_jaccard", analysis.lso_jaccard, analysis.county_n),
                _experiment_metric(
                    "lso_type_agreement",
                    analysis.type_agreement_lso,
                    analysis.type_agreement_lso_n,
                ),
            ),
        ),
        (
            "cosine_knn",
            "Cosine neighbors on the same embedding.",
            {"k": K_PRIMARY},
            (
                _experiment_metric(
                    "cosine_euclidean_jaccard",
                    analysis.cosine_jaccard,
                    analysis.county_n,
                ),
                _experiment_metric(
                    "type_agreement",
                    analysis.type_agreement_cosine,
                    analysis.type_agreement_cosine_n,
                ),
            ),
        ),
        (
            "same_state_rucc",
            "Baseline peers share a state and a rural-urban code.",
            {"leave_state": "same_rucc_other_states"},
            (
                _experiment_metric(
                    "type_agreement",
                    analysis.type_agreement_baseline,
                    analysis.type_agreement_baseline_n,
                ),
                _experiment_metric(
                    "lso_type_agreement",
                    analysis.type_agreement_lso_baseline,
                    analysis.type_agreement_lso_baseline_n,
                ),
            ),
        ),
        (
            "nearest_prototype",
            "Nearest stored issue 120 prototype at gamma 0.5.",
            {"source_run": GAP_RUN_ID},
            (
                _experiment_metric("recovery", analysis.recovery, analysis.assignment_n),
                _experiment_metric("silhouette", analysis.silhouette, analysis.county_n),
            ),
        ),
    )
    rows: list[ExperimentRow] = []
    for family, hypothesis, config, metrics in families:
        rows.append(
            ExperimentRow(
                experiment_id=_experiment_id(run_id, family),
                hypothesis=hypothesis,
                model_family=family,
                config={**shared, **config},
                split_definition=split,
                status="succeeded",
                metrics=metrics,
            )
        )
    return tuple(rows)


def lists_match(
    stored: dict[str, tuple[str, str]],
    rows: tuple[object, ...],
) -> bool:
    """True when every recomputed k=5 list equals the stored issue 192 list."""
    if len(stored) != len(rows):
        return False
    for row in rows:
        fips = getattr(row, "fips", None)
        euclidean = getattr(row, "euclidean_neighbors", None)
        cosine = getattr(row, "cosine_neighbors", None)
        if (
            not isinstance(fips, str)
            or not isinstance(euclidean, str)
            or not isinstance(cosine, str)
        ):
            return False
        if stored.get(fips) != (euclidean, cosine):
            return False
    return True


def _failures(analysis: Analysis) -> tuple[str, ...]:
    failed: list[str] = []
    if not math.isclose(analysis.determinism_jaccard, 1.0, abs_tol=TIE_EPS):
        failed.append("determinism")
    if (
        not analysis.conditional_estimable
        or analysis.conditional_median is None
        or analysis.conditional_low is None
        or analysis.conditional_median < CONDITIONAL_MEDIAN_MIN
        or analysis.conditional_low < CONDITIONAL_LOW_MIN
    ):
        failed.append("bootstrap")
    if (
        analysis.conditional_median is None
        or analysis.conditional_median_b is None
        or abs(analysis.conditional_median - analysis.conditional_median_b) > SEED_MEDIAN_GAP_MAX
    ):
        failed.append("bootstrap_seeds")
    if analysis.cosine_jaccard < COSINE_JACCARD_MIN:
        failed.append("cosine_jaccard")
    if analysis.type_agreement_lso is None or analysis.type_agreement_lso < LSO_AGREEMENT_MIN:
        failed.append("lso_type_agreement")
    if analysis.lso_baseline_gap is None or analysis.lso_baseline_gap < LSO_BASELINE_GAP_MIN:
        failed.append("lso_baseline_gap")
    if analysis.lso_jaccard < LSO_JACCARD_MIN:
        failed.append("lso_jaccard")
    alone = max((row.alone_jaccard for row in analysis.ablations), default=0.0)
    dropped = min((row.dropped_jaccard for row in analysis.ablations), default=1.0)
    if analysis.ablations and alone >= SINGLE_BLOCK_MAX:
        failed.append("single_block")
    if analysis.ablations and dropped >= DROP_ALL_MIN:
        failed.append("drop_block")
    if analysis.silhouette is None or analysis.silhouette < 0:
        failed.append("silhouette")
    if analysis.recovery < RECOVERY_MIN:
        failed.append("prototype_recovery")
    return tuple(failed)


def _present_and_absent(n: int, present: int, absent: int) -> float:
    total = 0.0
    for omitted in range(present + 1):
        sign = -1.0 if omitted % 2 else 1.0
        total += sign * comb(present, omitted) * (1 - (absent + omitted) / n) ** n
    return total


def _with_cosine_n(metric: EdaMetric, count: int) -> EdaMetric:
    return EdaMetric(
        metric_name=metric.metric_name,
        n_underlying=count,
        metric_value=metric.metric_value,
        unit=metric.unit,
    )


def _metric(name: str, count: int, value: float) -> EdaMetric:
    return EdaMetric(metric_name=name, n_underlying=count, metric_value=value, unit="ratio")


def _rate(rows: list[EdaMetric], name: str, value: float | None, count: int) -> None:
    if value is None:
        return
    rows.append(_metric(name, count, value))


def _experiment_metric(
    name: str,
    value: float | None,
    count: int,
    low: float | None = None,
    high: float | None = None,
) -> ExperimentMetric:
    return ExperimentMetric(
        split_name="national",
        metric_name=name,
        metric_value=value,
        n=count,
        ci_low=low,
        ci_high=high,
    )


def _experiment_id(run_id: str, family: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"{run_id}:{family}"))
