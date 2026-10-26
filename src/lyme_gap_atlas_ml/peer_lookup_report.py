"""Render the issue 192 write-up. County examples are allowed in this text."""

from __future__ import annotations

from collections.abc import Mapping

from lyme_gap_atlas_ml.peer_lookup import (
    BOOTSTRAP_REPLICATES,
    GAP_RUN_ID,
    K_PRIMARY,
    K_SENSITIVITY,
    PRIMARY_SEED,
    SECOND_SEED,
    SPEC_ID,
    Analysis,
    Example,
)

DOC_PATH = "docs/eda/192-peer-county-lookup.md"
_ISSUE = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues"


def render_eda_record(
    analysis: Analysis,
    *,
    run_id: str,
    commit: str,
    counts: Mapping[str, int],
    drive_note: str,
    grant: str,
) -> str:
    """Return the durable EDA record, including the seven comment sections."""
    comment = render_comment(
        analysis,
        run_id=run_id,
        commit=commit,
        counts=counts,
        drive_note=drive_note,
        grant=grant,
    )
    counts_note = (
        "matched 810 and 228"
        if analysis.wider_n == 810 and analysis.double_n == 228
        else "differed from 810 and 228"
    )
    decision = "PROCEED" if analysis.product == "advance" else "INCONCLUSIVE"
    header = "\n".join(
        (
            "# 192: Which counties look alike on the #120 context features?",
            "",
            f"- Issue: [#192]({_ISSUE}/192); program epic [#22]({_ISSUE}/22).",
            "- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`,",
            f"  and lab `EDA.GAP_COMMUNITY_ASSIGNMENTS_120` run `{GAP_RUN_ID}`.",
            "- Release: `governed-2026-10-15-january-climate-prod`.",
            (
                f"- Cohort: {analysis.county_n} counties, {analysis.state_n} states. "
                f"Published floor {analysis.published_n}. "
                f"No county-linked record {analysis.absent_n}. "
                f"Wider established-tick gap {analysis.wider_n}. "
                f"Double gap {analysis.double_n}. Reference gap counts {counts_note}."
            ),
            "",
            "## Method and assumptions",
            "",
            f"Spec [{SPEC_ID}](192-analysis-spec.md), frozen before the fit.",
            "Euclidean and cosine neighbors use one embedding of the #120 feature set.",
            "The baseline is the same state and the same rural-urban code.",
            "No ground truth exists. Similar means similar on those context features only.",
            "",
            "## Material findings and limits",
            "",
            comment.rstrip("\n"),
            "",
            "## Decision",
            "",
            (
                f"{decision}. Method {analysis.method}. Product {analysis.product}. "
                "This is not a release and not a change to the Tier 1 model."
            ),
            "",
            "## Reproduction and retained evidence",
            "",
            f"- Code revision/run: commit `{commit}`, run `{run_id}`, spec `{SPEC_ID}`.",
            "- Entry points: `sql/validation/192_peer_lookup.sql`, "
            "`src/lyme_gap_atlas_ml/peer_lookup.py`, `scripts/eda_192_peer_lookup.py`.",
            "- Command: `MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
            "python scripts/eda_192_peer_lookup.py`.",
            "- Gate: `uv run python scripts/verify.py`.",
            "- Transient artifacts not committed: `artifacts/charts/192/` and `outputs/`.",
            "",
        )
    )
    return header


def render_comment(
    analysis: Analysis,
    *,
    run_id: str,
    commit: str,
    counts: Mapping[str, int],
    drive_note: str,
    grant: str,
) -> str:
    """Return the seven sections shared by the issue comment and the pull request."""
    failed = ", ".join(analysis.failures) if analysis.failures else "none"
    count_line = ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
    ablation = "\n".join(
        f"| {row.block} | {row.dropped_jaccard:.4f} | {row.alone_jaccard:.4f} |"
        for row in analysis.ablations
    )
    examples = "\n".join(
        _example_line(row, rank)
        for rank, row in enumerate([*analysis.examples_near, *analysis.examples_far], start=1)
    )
    parts = [
        "1. Question",
        "",
        "For a county, which other counties are nearest on the #120 context features, "
        "does that short list survive a redraw of the county pool and a held-out state, "
        "and does it beat a same-state same-RUCC match on #120 type agreement?",
        "",
        "2. Method (and why; link the spec)",
        "",
        f"Spec [{SPEC_ID}](docs/eda/192-analysis-spec.md), frozen before the fit. "
        "The embedding is the #120 feature set: z-scored social-vulnerability percentile, "
        "uninsured percentile, and log population, plus one-hot rural-urban code and the "
        f"three surveillance statuses scaled so squared Euclidean distance matches gamma "
        f"0.5. Cosine uses that same embedding. k = {K_PRIMARY} is the short list. "
        f"k = {K_SENSITIVITY} is reported and cannot rescue a miss. "
        "The baseline peer set is every other county in the same state with the same "
        "rural-urban code. When the state is held out, that set is empty, so the "
        "leave-state-out type comparison uses other-state counties with the same code. "
        f"Bootstrap: {BOOTSTRAP_REPLICATES} draws, seeds {PRIMARY_SEED} and {SECOND_SEED}. "
        "Nearest prototype uses the stored #120 labels and is not a new clustering. "
        "No ground truth exists.",
        "",
        "3. Key findings with numbers",
        "",
        (
            f"Counties {analysis.county_n}. States {analysis.state_n}. "
            f"Stored #120 types {analysis.assignment_n}. "
            f"Determinism Jaccard {_num(analysis.determinism_jaccard)}. "
            f"Cosine versus Euclidean Jaccard {_num(analysis.cosine_jaccard)}. "
            f"In-sample type agreement, Euclidean {_num(analysis.type_agreement_euclidean)} "
            f"(n={analysis.type_agreement_euclidean_n}), "
            f"cosine {_num(analysis.type_agreement_cosine)}, "
            f"same-state same-RUCC {_num(analysis.type_agreement_baseline)} "
            f"(n={analysis.type_agreement_baseline_n}). "
            f"In-sample gap {_num(analysis.in_sample_gap)}. "
            f"Leave-state-out type agreement, Euclidean {_num(analysis.type_agreement_lso)} "
            f"(n={analysis.type_agreement_lso_n}), "
            f"cosine {_num(analysis.type_agreement_lso_cosine)}, "
            f"same-RUCC outside the state {_num(analysis.type_agreement_lso_baseline)} "
            f"(n={analysis.type_agreement_lso_baseline_n}). "
            f"Leave-state-out gap {_num(analysis.lso_baseline_gap)}. "
            f"Leave-state-out neighbor Jaccard {_num(analysis.lso_jaccard)}. "
            f"Cross-state share {_num(analysis.cross_state_share)}. "
            f"Bootstrap median Jaccard {_num(analysis.bootstrap_median)} "
            f"(interval {_num(analysis.bootstrap_low)} to {_num(analysis.bootstrap_high)}, "
            f"estimable {analysis.bootstrap_estimable}, failed replicates "
            f"{analysis.bootstrap_failed}). "
            f"Second-seed bootstrap median {_num(analysis.bootstrap_median_b)}. "
            f"k=15 bootstrap median {_num(analysis.k15_bootstrap_median)}. "
            f"k=15 leave-state-out type agreement {_num(analysis.k15_lso_agreement)}. "
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
        "distances. They are not a disease ranking.",
        "",
        examples,
        "",
        "4. Caveats",
        "",
        "No ground truth exists. A neighbor list is a lookup aid, not a validated "
        "similarity. Similar means similar on the listed context features only. "
        "It is not similar disease burden, not risk, and not causation. "
        "A published human floor is a lower bound (CDC floor 5). "
        "No records and Unknown are not negatives. A missing floor is not zero. "
        "Human surveillance is calendar 2023. Population, social vulnerability, and "
        "uninsured share are 2022. The rural-urban code is 2023. Tick and pathogen "
        "statuses are cumulative through 2025-12-31. "
        "The leave-state-out does not cover dependence that crosses a state line. "
        "The bootstrap band is a stability band for the lists, not a confidence "
        "interval for a disease rate. "
        f"#120 types exist for {analysis.assignment_n} counties, from run `{GAP_RUN_ID}`. "
        "Counties outside that cohort have no stored type, so type agreement ignores them.",
        "",
        "5. Disposition",
        "",
        f"Method: {analysis.method}. Product: {analysis.product}. "
        f"Rule failures: {failed}. "
        "This is not a release and not a change to the Tier 1 model.",
        "",
        "6. Artifacts",
        "",
        f"run_id: {run_id}",
        f"Snowflake row counts: {count_line}.",
        f"SELECT grants: {grant}.",
        drive_note,
        "Doc: docs/eda/192-peer-county-lookup.md",
        "Spec: docs/eda/192-analysis-spec.md",
        "",
        "7. Reproducibility",
        "",
        f"Commit: {commit}",
        "Release: governed-2026-10-15-january-climate-prod",
        f"Seeds: {PRIMARY_SEED} and {SECOND_SEED}. Bootstrap replicates: {BOOTSTRAP_REPLICATES}.",
        "Commands:",
        "uv sync --locked --extra dev --extra snowflake",
        "uv run python scripts/check_ml_agent_context.py",
        "MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
        "python scripts/eda_192_peer_lookup.py",
        "uv run python scripts/verify.py",
        "County neighbor rows were not written to git or Drive. "
        "They stay in EDA.PEER_COUNTY_NEIGHBORS_192.",
        "",
        "Part of #192",
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
