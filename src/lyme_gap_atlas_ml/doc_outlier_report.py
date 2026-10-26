"""Render the issue 190 write-up. County examples are allowed in this text."""

from __future__ import annotations

from collections.abc import Mapping

from lyme_gap_atlas_ml.doc_outliers import (
    BOOTSTRAP_DRAWS,
    CLUSTER_DRAWS,
    CLUSTER_SEED,
    CONTAMINATION,
    FOREST_TREES,
    PERMUTATION_DRAWS,
    PERMUTATION_SEED,
    PRIMARY_SEED,
    SECOND_SEED,
    SPEC_ID,
    Analysis,
    FlagRow,
)

DOC_PATH = "docs/eda/190-within-state-doc-outliers.md"
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
    matched = (
        "matched the expected 651 and 2493"
        if analysis.cohort_matches_expected
        else "differed from the expected 651 and 2493"
    )
    header = "\n".join(
        (
            "# 190: Which counties are documented differently from their state peers?",
            "",
            f"- Issue: [#190]({_ISSUE}/190); program epic [#22]({_ISSUE}/22).",
            "- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`.",
            "- Release: `governed-2026-10-15-january-climate-prod`.",
            (
                f"- Cohort: {analysis.county_n} counties, {analysis.state_n} states, one snapshot. "
                f"Published floor {analysis.published_n}. "
                f"No county-linked record {analysis.absent_n}. Counts {matched}."
            ),
            "",
            "## Method and assumptions",
            "",
            f"Spec [{SPEC_ID}](190-analysis-spec.md), frozen before the fit.",
            "The baseline is the #113 robust z, applied inside each state.",
            "A documentation indicator is not flagged by that baseline.",
            "The isolation forest and local outlier factor use the frozen fallback scale.",
            "#120 types and #121 situation groups are comparisons, not features.",
            "",
            "## Material findings and limits",
            "",
            comment.rstrip("\n"),
            "",
            "## Decision",
            "",
            (
                f"Method {analysis.method_if}. Product {analysis.product}. "
                "This is not a release and not a change to the Tier 1 model."
            ),
            "",
            "## Reproduction and retained evidence",
            "",
            f"- Code revision/run: commit `{commit}`, run `{run_id}`, spec `{SPEC_ID}`.",
            "- Entry points: `sql/validation/190_doc_outliers.sql`, "
            "`src/lyme_gap_atlas_ml/doc_outliers.py`, `scripts/eda_190_doc_outliers.py`.",
            "- Command: `MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
            "python scripts/eda_190_doc_outliers.py`.",
            "- Gate: `uv run python scripts/verify.py`.",
            "- Transient artifacts not committed: `artifacts/charts/190/` and `outputs/`.",
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
    parts = [
        "1. Question",
        "",
        "Which counties' documentation differs most from their own state's counties, "
        "and does an isolation forest add a stable review list beyond the within-state "
        "robust z from #113?",
        "",
        "2. Method (and why; link the spec)",
        "",
        f"Spec [{SPEC_ID}](docs/eda/190-analysis-spec.md), frozen before the fit. "
        "States with fewer than 11 counties are counted and not scored. "
        "Within-state standardization uses the state median and the #113 scale "
        f"`MAD_SCALE` 1.482602218505602. The baseline omits a column whose MAD is 0. "
        "The forest and local outlier factor keep a varying column whose MAD is 0 "
        "by using the mean absolute deviation from the median, because a rare "
        "documentation status would otherwise be invisible. "
        f"Baseline flag: absolute z above 3.5, then at most max(1, floor(0.05 * n)) "
        "counties per state. "
        f"Isolation forest: {FOREST_TREES} trees, contamination {CONTAMINATION}, "
        f"bootstrap samples, seeds {PRIMARY_SEED} and {SECOND_SEED}. "
        f"Local outlier factor: contamination {CONTAMINATION}, brute neighbors, no seed. "
        f"Bootstrap: {BOOTSTRAP_DRAWS} within-state subsamples of 80 percent, seed {CLUSTER_SEED}. "
        f"State-cluster interval: {CLUSTER_DRAWS} draws, seed {CLUSTER_SEED}. "
        f"Permutation: {PERMUTATION_DRAWS} within-state shuffles of the documentation columns, "
        f"seed {PERMUTATION_SEED}, refitting the primary forest. "
        "No ROC-AUC or other label score is computed. There are no ground-truth labels.",
        "",
        "3. Key findings with numbers",
        "",
        _findings(analysis),
        "",
        "4. Caveats",
        "",
        "A flag means documented differently from state peers. "
        "It is not a data error and it is not a statement about disease burden. "
        "Published floors are surveillance signals and lower bounds where the CDC floor is 5. "
        "`No records` and `Unknown` are not negatives. A missing floor is not zero. "
        "No ground truth exists, so this is a data-review signal, not a validated detector. "
        "#188 showed that state-level composition can masquerade as a county signal. "
        "The permutation check is the guard, and a pass would still not be validation. "
        "The #113 baseline cannot flag a documentation indicator: an uneven 0/1 column has MAD 0, "
        "and an even split has absolute z 1/MAD_SCALE, about 0.67, below 3.5. "
        f"SVI rescaled by 100: {analysis.svi_rescaled}. "
        f"Uninsured percentile rescaled by 100: {analysis.uninsured_rescaled}.",
        "",
        "5. Disposition",
        "",
        f"Method, isolation forest: {analysis.method_if}. "
        f"Method, robust z: {analysis.method_z}. "
        f"Method, local outlier factor: {analysis.method_lof}. "
        f"Product: {analysis.product}.",
        "",
        "6. Artifacts",
        "",
        f"Run id `{run_id}`. Grant SELECT for OH_LYME_PROD_READ: {grant}.",
        _counts(counts),
        drive_note,
        f"Write-up: `{DOC_PATH}`.",
        "",
        "7. Reproducibility",
        "",
        f"Commit `{commit}`. Release `governed-2026-10-15-january-climate-prod`. "
        f"Seeds {PRIMARY_SEED}, {SECOND_SEED}, cluster and bootstrap {CLUSTER_SEED}, "
        f"permutation {PERMUTATION_SEED}.",
        "Command: `MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
        "python scripts/eda_190_doc_outliers.py`.",
        "Gate: `uv run python scripts/verify.py`.",
        "",
    ]
    return "\n".join(parts)


def _findings(analysis: Analysis) -> str:
    interval = "not estimable"
    if analysis.flag_rate_low is not None and analysis.flag_rate_high is not None:
        interval = f"{_num(analysis.flag_rate_low)} to {_num(analysis.flag_rate_high)}"
    lines = [
        (
            f"Scored counties {analysis.scored_n} in {analysis.scored_states} states. "
            f"Complete rows {analysis.complete_n}. "
            f"States below 11 counties: {analysis.below_11_states} states, "
            f"{analysis.below_11_counties} counties, not scored. "
            f"States where a documentation column entered the baseline: "
            f"{analysis.baseline_doc_states}."
        ),
        (
            f"Primary forest flag rate {_num(analysis.flag_rate_if)} "
            f"(state-cluster interval {interval}). "
            f"Seed Jaccard {_num(analysis.seed_jaccard)}. "
            f"Seed score Spearman {_num(analysis.seed_spearman)}. "
            f"Bootstrap median Jaccard: robust z {_num(analysis.bootstrap_z)}, "
            f"forest {_num(analysis.bootstrap_if)}, "
            f"local outlier factor {_num(analysis.bootstrap_lof)}."
        ),
        (
            f"Permutation median Jaccard, forest {_num(analysis.permutation_jaccard_if)}, "
            f"robust z {_num(analysis.permutation_jaccard_z)}. "
            f"Size Spearman: robust z {_num(analysis.size_spearman_z)}, "
            f"forest {_num(analysis.size_spearman_if)}, "
            f"local outlier factor {_num(analysis.size_spearman_lof)}. "
            f"Stable useful flags {analysis.stable_useful_n}. "
            f"Jaccard of those flags with the baseline {_num(analysis.useful_baseline_jaccard)}. "
            f"Situation concentration: {analysis.concentrated}."
        ),
        "",
        _table(
            ("Band", "Method", "Scored counties", "Flags"),
            tuple(
                (item.band, item.method, str(item.counties), str(item.flags))
                for item in analysis.bands
            ),
        ),
        "",
        _table(
            ("Left", "Right", "Spearman", "Jaccard", "Matched Jaccard"),
            tuple(
                (
                    item.left,
                    item.right,
                    _num(item.spearman),
                    _num(item.jaccard),
                    _num(item.matched_jaccard),
                )
                for item in analysis.agreements
            ),
        ),
        "",
        _table(
            ("Situation", "Scored counties", "Primary forest flags"),
            tuple(
                (item.name, str(item.scored_n), str(item.flag_n)) for item in analysis.situations
            ),
        ),
        "",
        _table(
            ("#120 cluster", "Cohort counties in the scored set", "Primary forest flags"),
            tuple(
                (str(item.cluster_id), str(item.cohort_n), str(item.flag_n))
                for item in analysis.clusters
            )
            or (("none", "0", "0"),),
        ),
        "",
        "Example primary-forest flags, highest score first. "
        "A stable useful flag also meets the seed, bootstrap, and permutation rules.",
        "",
        _table(
            (
                "County",
                "State",
                "Score",
                "Baseline flag",
                "Other seed",
                "Stable useful",
                "Dominant",
            ),
            tuple(_example(row) for row in analysis.examples)
            or (("none", "", "", "", "", "", ""),),
        ),
        "",
        _state_table(analysis),
    ]
    return "\n".join(lines)


def _example(row: FlagRow) -> tuple[str, ...]:
    return (
        row.county_name,
        row.state,
        _num(row.score_if_primary),
        _yes(row.flag_robust_z),
        _yes(row.flag_if_seed_b),
        _yes(row.stable_useful),
        row.dominant_feature or "",
    )


def _state_table(analysis: Analysis) -> str:
    grouped: dict[str, list[FlagRow]] = {}
    for row in analysis.rows:
        grouped.setdefault(row.state, []).append(row)
    body = []
    for state in sorted(grouped):
        members = grouped[state]
        scored = [row for row in members if row.scored]
        if not scored:
            body.append((state, str(len(members)), "not scored", "0", "0", "0"))
            continue
        body.append(
            (
                state,
                str(len(members)),
                str(len(scored)),
                str(sum(row.flag_robust_z for row in scored)),
                str(sum(row.flag_if_primary for row in scored)),
                str(sum(row.flag_lof for row in scored)),
            )
        )
    return _table(("State", "Counties", "Scored", "Robust z", "Forest", "LOF"), tuple(body))


def _counts(counts: Mapping[str, int]) -> str:
    if not counts:
        return "Lab row counts were not recorded."
    parts = [f"`{name}` {count}" for name, count in counts.items()]
    return "Lab row counts: " + ", ".join(parts) + "."


def _table(header: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> str:
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _num(value: float | None) -> str:
    if value is None:
        return "not estimable"
    return f"{value:.4f}"


def _yes(value: bool) -> str:
    return "yes" if value else "no"
