"""Render the issue 196 write-up. County examples are allowed in this text."""

from __future__ import annotations

from collections.abc import Mapping

from lyme_gap_atlas_ml.peer_lookup import (
    BOOTSTRAP_REPLICATES,
    GAP_RUN_ID,
    K_PRIMARY,
    K_SENSITIVITY,
    PRIMARY_SEED,
    SECOND_SEED,
    Analysis,
    Example,
)
from lyme_gap_atlas_ml.peer_lookup_rerun import (
    CEILING_EXPECTATION,
    CEILING_K15_EXPECTATION,
    CEILING_REPLICATES,
    CEILING_SEED,
    CEILING_SIMULATION_MEDIAN,
    CONDITIONAL_LOW_MIN,
    CONDITIONAL_MEDIAN_MIN,
    PRIOR_METHOD,
    PRIOR_RUN_ID,
    SPEC_ID_196,
    RerunDecision,
)

DOC_PATH = "docs/eda/196-peer-county-rerun.md"
SPEC_LINK = "196-analysis-spec.md"
_ISSUE = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues"


def render_eda_record(
    analysis: Analysis,
    decision: RerunDecision,
    *,
    run_id: str,
    commit: str,
    counts: Mapping[str, int],
    drive_note: str,
    grant: str,
    lists_unchanged: bool,
) -> str:
    """Return the durable EDA record, including the seven comment sections."""
    comment = render_comment(
        analysis,
        decision,
        run_id=run_id,
        commit=commit,
        counts=counts,
        drive_note=drive_note,
        grant=grant,
        lists_unchanged=lists_unchanged,
    )
    decision_word = "PROCEED" if decision.product == "advance" else "INCONCLUSIVE"
    header = "\n".join(
        (
            "# 196: Is the peer-county list stable once the bootstrap gate can measure stability?",
            "",
            f"- Issue: [#196]({_ISSUE}/196); program epic [#22]({_ISSUE}/22).",
            "- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`,",
            f"  lab `EDA.GAP_COMMUNITY_ASSIGNMENTS_120` run `{GAP_RUN_ID}`,",
            f"  and lab `EDA.PEER_COUNTY_NEIGHBORS_192` run `{PRIOR_RUN_ID}`.",
            "- Release: `governed-2026-10-15-january-climate-prod`.",
            (
                f"- Cohort: {analysis.county_n} counties, {analysis.state_n} states. "
                f"Published floor {analysis.published_n}. "
                f"No county-linked record {analysis.absent_n}. "
                f"Wider established-tick gap {analysis.wider_n}. "
                f"Double gap {analysis.double_n}."
            ),
            "",
            "## Method and assumptions",
            "",
            f"Spec [{SPEC_ID_196}]({SPEC_LINK}), frozen before the fit.",
            "The lookup is the issue 192 embedding and exact neighbor search.",
            "The bootstrap gate is conditional retained-neighbor Jaccard.",
            "No ground truth exists. Similar means similar on those context features only.",
            "",
            "## Material findings and limits",
            "",
            comment.rstrip("\n"),
            "",
            "## Decision",
            "",
            (
                f"{decision_word}. Method {decision.method}. Product {decision.product}. "
                f"The issue 192 method call was {PRIOR_METHOD}. "
                "This is not a release and not a change to the Tier 1 model."
            ),
            "",
            "## Reproduction and retained evidence",
            "",
            f"- Code revision/run: commit `{commit}`, run `{run_id}`, spec `{SPEC_ID_196}`.",
            "- Entry points: `sql/validation/192_peer_lookup.sql`, "
            "`src/lyme_gap_atlas_ml/peer_lookup.py`, "
            "`src/lyme_gap_atlas_ml/peer_lookup_rerun.py`, "
            "`scripts/eda_196_peer_lookup.py`.",
            "- Command: `MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
            "python scripts/eda_196_peer_lookup.py`.",
            "- Gate: `uv run python scripts/verify.py`.",
            "- Transient artifacts not committed: `artifacts/charts/196/` and `outputs/`.",
            "",
        )
    )
    return header


def render_comment(
    analysis: Analysis,
    decision: RerunDecision,
    *,
    run_id: str,
    commit: str,
    counts: Mapping[str, int],
    drive_note: str,
    grant: str,
    lists_unchanged: bool,
) -> str:
    """Return the seven sections shared by the pull request and the write-up."""
    failed = ", ".join(decision.failures) if decision.failures else "none"
    count_line = ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
    changed = "changes" if decision.method != PRIOR_METHOD else "does not change"
    neighbor_note = (
        f"Recomputed k=5 lists match `{PRIOR_RUN_ID}` in `EDA.PEER_COUNTY_NEIGHBORS_192`. "
        "No new neighbor table was created."
        if lists_unchanged
        else "Recomputed lists differ. Rows were inserted in `EDA.PEER_COUNTY_NEIGHBORS_196`."
    )
    examples = "\n".join(
        _example_line(row, rank)
        for rank, row in enumerate([*analysis.examples_near, *analysis.examples_far], start=1)
    )
    ablation = "\n".join(
        f"| {row.block} | {row.dropped_jaccard:.4f} | {row.alone_jaccard:.4f} |"
        for row in analysis.ablations
    )
    parts = [
        "1. Question",
        "",
        "Is the peer-county list stable when the county pool is redrawn, once the result "
        "is compared with what a perfectly stable list scores under the same resampling? "
        "Should the issue 192 method call change?",
        "",
        "2. Method (and why; link the spec)",
        "",
        f"Spec [{SPEC_ID_196}]({SPEC_LINK}), frozen before the fit. "
        "The issue 192 raw Jaccard keep line of 0.50 sits on the mechanical ceiling: "
        f"a fixed neighbor order has expected raw Jaccard {CEILING_EXPECTATION:.6f}, "
        f"and a {CEILING_REPLICATES}-replicate simulation (seed {CEILING_SEED}) "
        f"has median {CEILING_SIMULATION_MEDIAN:.6f}. "
        "The new statistic is the share of in-sample Euclidean neighbors that remain "
        "neighbors when they are still in the bootstrap pool. A fixed order scores 1. "
        f"Keep requires an estimable interval, a median of at least {CONDITIONAL_MEDIAN_MIN:.2f}, "
        f"and a lower endpoint of at least {CONDITIONAL_LOW_MIN:.2f}. "
        "The two-seed gap stays at most 0.05. Every other issue 192 keep gate is unchanged. "
        f"k = {K_PRIMARY} is the gate. k = {K_SENSITIVITY} is reported and cannot rescue a miss. "
        f"Bootstrap: {BOOTSTRAP_REPLICATES} draws, seeds {PRIMARY_SEED} and {SECOND_SEED}. "
        "The cosine type-agreement row uses the cosine estimable count. "
        "The issue 192 raw median 0.4999 was already known when this gate was written. "
        "The keep line is not a function of that median. No ground truth exists.",
        "",
        "3. Key findings with numbers",
        "",
        (
            f"Counties {analysis.county_n}. States {analysis.state_n}. "
            f"Stored #120 types {analysis.assignment_n}. "
            f"Conditional bootstrap median {_num(analysis.conditional_median)} "
            f"(interval {_num(analysis.conditional_low)} to {_num(analysis.conditional_high)}, "
            f"estimable {analysis.conditional_estimable}, failed replicates "
            f"{analysis.conditional_failed}). "
            f"Second-seed conditional median {_num(analysis.conditional_median_b)}. "
            f"k=15 conditional median {_num(analysis.conditional_k15_median)}. "
            f"Simulated stable-list raw ceiling {CEILING_EXPECTATION:.6f}, "
            f"simulation median {CEILING_SIMULATION_MEDIAN:.6f}. "
            f"k=15 raw ceiling {CEILING_K15_EXPECTATION:.6f}. "
            f"Raw bootstrap median {_num(analysis.bootstrap_median)} "
            f"(interval {_num(analysis.bootstrap_low)} to {_num(analysis.bootstrap_high)}). "
            f"Second-seed raw median {_num(analysis.bootstrap_median_b)}. "
            f"k=15 raw median {_num(analysis.k15_bootstrap_median)}. "
            f"The issue 192 method call was {PRIOR_METHOD} and it {changed} to {decision.method}. "
            f"Cosine type-agreement n={analysis.type_agreement_cosine_n}. "
            f"Euclidean type-agreement n={analysis.type_agreement_euclidean_n}. "
            f"Determinism Jaccard {_num(analysis.determinism_jaccard)}. "
            f"Cosine versus Euclidean Jaccard {_num(analysis.cosine_jaccard)}. "
            f"In-sample type agreement, Euclidean {_num(analysis.type_agreement_euclidean)} "
            f"(n={analysis.type_agreement_euclidean_n}), "
            f"cosine {_num(analysis.type_agreement_cosine)} "
            f"(n={analysis.type_agreement_cosine_n}), "
            f"same-state same-RUCC {_num(analysis.type_agreement_baseline)} "
            f"(n={analysis.type_agreement_baseline_n}). "
            f"Leave-state-out type agreement, Euclidean {_num(analysis.type_agreement_lso)} "
            f"(n={analysis.type_agreement_lso_n}), "
            f"cosine {_num(analysis.type_agreement_lso_cosine)}, "
            f"same-RUCC outside the state {_num(analysis.type_agreement_lso_baseline)} "
            f"(n={analysis.type_agreement_lso_baseline_n}). "
            f"Leave-state-out gap {_num(analysis.lso_baseline_gap)}. "
            f"Leave-state-out neighbor Jaccard {_num(analysis.lso_jaccard)}. "
            f"Cross-state share {_num(analysis.cross_state_share)}. "
            f"Prototype recovery {_num(analysis.recovery)}. "
            f"Silhouette {_num(analysis.silhouette)}. "
            f"Situation agreement {_num(analysis.situation_agreement)}. "
            "Situation agreement is partly circular: tick and pathogen statuses are "
            "distance features. Human status is not. "
            f"Gate failures: {failed}."
        ),
        "",
        "| Block | Jaccard after drop | Jaccard of the block alone |",
        "| --- | ---: | ---: |",
        ablation,
        "",
        "Examples are the three smallest and three largest 5th-neighbor Euclidean "
        "distances. They are not a surveillance ranking.",
        "",
        examples,
        "",
        "4. Caveats",
        "",
        "No ground truth exists. A neighbor list is a lookup on the listed context "
        "features. It is a surveillance-signal comparison. "
        "A published human floor is a lower bound (CDC floor 5). "
        "No records and Unknown are not negatives. A missing floor is not zero. "
        "Human surveillance is calendar 2023. Population, social vulnerability, and "
        "uninsured share are 2022. The rural-urban code is 2023. Tick and pathogen "
        "statuses are cumulative through 2025-12-31. "
        "The leave-state-out does not cover dependence that crosses a state line. "
        "The bootstrap band is a stability band for the lists, not a disease-rate interval. "
        f"The issue 192 raw median 0.4999 was known before the gate was redefined. "
        f"#120 types exist for {analysis.assignment_n} counties, from run `{GAP_RUN_ID}`. "
        "Counties outside that cohort have no stored type, so type agreement ignores them. "
        "FINDINGS records product advance as keep, investigate as follow-up, and stop as stop. "
        "The statement uses that same word.",
        "",
        "5. Disposition",
        "",
        f"Method: {decision.method}. Product: {decision.product}. "
        f"The issue 192 method call {changed}. "
        f"Rule failures: {failed}. "
        "This is not a release and not a change to the Tier 1 model.",
        "",
        "6. Artifacts",
        "",
        f"run_id: {run_id}",
        f"Snowflake row counts: {count_line}.",
        neighbor_note,
        f"SELECT grants: {grant}.",
        drive_note,
        "Doc: docs/eda/196-peer-county-rerun.md",
        f"Spec: docs/eda/{SPEC_LINK}",
        "",
        "7. Reproducibility",
        "",
        f"Commit: {commit}",
        "Release: governed-2026-10-15-january-climate-prod",
        f"Fit seeds: {PRIMARY_SEED} and {SECOND_SEED}. "
        f"Bootstrap replicates: {BOOTSTRAP_REPLICATES}. "
        f"Ceiling simulation seed: {CEILING_SEED}. "
        f"Ceiling replicates: {CEILING_REPLICATES}.",
        "Commands:",
        "uv sync --locked --extra dev --extra snowflake",
        "uv run python scripts/check_ml_agent_context.py",
        "MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
        "python scripts/eda_196_peer_lookup.py",
        "uv run python scripts/verify.py",
        "County neighbor rows were not written to git or Drive.",
        "",
        "Part of #196",
        "Part of #22",
    ]
    return "\n".join(parts) + "\n"


def _example_line(row: Example, rank: int) -> str:
    peers = "; ".join(f"{name}, {state} ({fips})" for fips, name, state in row.neighbors)
    return (
        f"{rank}. {row.county_name}, {row.state} ({row.fips}), "
        f"5th-neighbor distance {row.distance:.4f}. Neighbors: {peers}."
    )


def _num(value: float | None) -> str:
    if value is None:
        return "not estimable"
    return f"{value:.4f}"
