"""Narrative for issue 114. County names are allowed here and kept out of charts."""

from __future__ import annotations

from lyme_gap_atlas_ml.cross_domain import (
    OCT13_TWO_COMPONENT,
    SPEC_ID,
    Analysis,
    PairResult,
)

_TEMPLATE_NOTE = (
    "A published human floor is a surveillance lower bound, not incidence or risk. "
    "No records and Unknown are documentation states, not negatives. Missing is not zero."
)


def render_comment(
    analysis: Analysis,
    *,
    run_id: str,
    git_commit: str,
    row_counts: dict[str, int],
    drive_links: dict[str, str],
) -> str:
    """Issue comment and pull-request body."""
    counts = ", ".join(f"{name} {count}" for name, count in row_counts.items())
    links = (
        ", ".join(f"{name}: {url}" for name, url in drive_links.items())
        or "pending Drive registration"
    )
    return "\n".join(
        (
            "## 1. Question",
            "",
            "Which signals move together across climate, tick and pathogen documentation, "
            "the human published floor, and SVI, uninsured, population, and rurality, "
            "and does the October 13 two-component share of about 88.5% on SVI, "
            "uninsured percentile, and log population still describe that block?",
            "",
            "## 2. Method",
            "",
            f"Spec `{SPEC_ID}` in `docs/eda/114-analysis-spec.md`. "
            "Spearman, uncorrected Cramér's V, Holm, and the state-cluster interval "
            "are the #116 helpers. "
            "Kruskal epsilon-squared is the #63 omnibus. "
            "Bias-corrected V uses that chi-square. "
            "Partials remove log population, rurality, and state means. "
            "Benjamini-Hochberg adjusts the twelve signed tail shares. "
            "January VALUE_NATIVE_DOUBLE climate fields are not estimable "
            "under the #110 20-day rule and were not read again.",
            "",
            "## 3. Key findings",
            "",
            _numbers(analysis),
            "",
            "## 4. Caveats",
            "",
            _TEMPLATE_NOTE + " The 2022 context layer, the 2023 human floor and rural-urban code, "
            "and tick and pathogen status through 2025 are not one time base. "
            "State-cluster intervals do not cover dependence that crosses a state line. "
            "No causal claim follows.",
            "",
            "## 5. Disposition",
            "",
            _disposition(analysis),
            "",
            "## 6. Artifacts",
            "",
            f"run_id `{run_id}`. Snowflake row counts: {counts}. "
            f"Drive: {links}. Doc: `docs/eda/114-cross-domain-associations.md`. "
            "No new table was created, so no GRANT was issued. "
            "Issue 110 run `110-peer-county-clusters-20261026T0644Z` has 2 artifact rows "
            "(`cluster-profile.png`, `stability-heatmap.png`), "
            "registered insert-only with no Drive edit.",
            "",
            "## 7. Reproducibility",
            "",
            f"Commit `{git_commit}`. Release `{analysis.release_id}`. Seeds 1142026 and 1142027.",
            "",
            "```text",
            "uv sync --locked --extra dev --extra snowflake",
            "uv run python scripts/check_ml_agent_context.py",
            "MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
            "python scripts/eda_114_cross_domain.py",
            "uv run python scripts/verify.py",
            "```",
            "",
        )
    )


def render_eda_record(
    analysis: Analysis,
    *,
    run_id: str,
    git_commit: str,
    row_counts: dict[str, int],
    drive_links: dict[str, str],
) -> str:
    """Durable EDA record from the template."""
    counts = ", ".join(f"`{name}` {count}" for name, count in row_counts.items())
    links = ", ".join(f"{name} {url}" for name, url in drive_links.items()) or "not registered yet"
    spots = "\n".join(
        (
            f"- {spot.label}: {spot.name}, {spot.state}, FIPS {spot.fips}, "
            f"human {spot.human}, tick {spot.tick}, pathogen {spot.pathogen}."
        )
        for spot in analysis.spots
        if spot.fips
    )
    issue = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues"
    return "\n".join(
        (
            "# 114: Which cross-domain signals move together?",
            "",
            f"- Issue: [ML #114]({issue}/114), part of [ML #22]({issue}/22).",
            f"  Spec: [{SPEC_ID}](114-analysis-spec.md).",
            "- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`.",
            f"  Pinned release `{analysis.release_id}`.",
            (
                f"- Cohort: {analysis.counties} counties. "
                f"Published floor {analysis.published_n}. "
                f"No county-linked record {analysis.no_record_n}. "
                f"Context complete case {analysis.context_n}. "
                f"Cross-domain complete case {analysis.cross_n}."
            ),
            "",
            "## Method and assumptions",
            "",
            f"Spec [{SPEC_ID}](114-analysis-spec.md), frozen before the fit.",
            "The descriptive unit is the county. The resampling unit is the state.",
            "Spearman and the state-cluster interval come from `test_selection`.",
            "Kruskal epsilon-squared comes from `eda63.omnibus`.",
            "Bias-corrected Cramér's V uses the chi-square from `cramers_v`.",
            "Partials residualize average ranks within state on log population and rurality.",
            "BH is the primary adjustment for the twelve signed tail shares. "
            "Holm is the sensitivity.",
            "Climate is the #110 native-double result: no county reached 20 usable days.",
            "No missing value was imputed as zero. Seeds 1142026 and 1142027.",
            "",
            "## Material findings and limits",
            "",
            _numbers(analysis),
            "",
            _pair_table(analysis),
            "",
            "Reproduction points, compared with the #116 displays. A cited interval is used",
            "only when the point still matches at four decimals.",
            "",
            _reproduction_table(analysis),
            "",
            "Recommendations:",
            "",
            _recommendation_lines(analysis),
            "",
            "Spot checks chosen by smallest FIPS, not by the coefficients:",
            "",
            spots,
            "",
            _TEMPLATE_NOTE
            + " Vintages are 2022 for SVI, uninsured, and population, 2023 for the human floor "
            "and rural-urban code, and cumulative through 2025 for tick and pathogen status. "
            "State resampling does not cover cross-border dependence.",
            "",
            "## Decision",
            "",
            (
                f"Representation call: **{analysis.representation}**. "
                f"Follow-up call: **{analysis.follow_up}**."
            ),
            "",
            _plain_recommendation(analysis),
            "",
            "This is permission to quote the named coefficients with their intervals. "
            "It is not permission to train a model or publish a score.",
            "",
            "## Reproduction and retained evidence",
            "",
            f"- Code revision/run: `{git_commit}`. Run `{run_id}`. Spec `{SPEC_ID}`.",
            "- Entry points: `sql/validation/114_cross_domain.sql`, "
            "`scripts/eda_114_cross_domain.py`, `src/lyme_gap_atlas_ml/cross_domain.py`.",
            "- Commands: `uv run python scripts/check_ml_agent_context.py`, then "
            "`MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
            "python scripts/eda_114_cross_domain.py`, then `uv run python scripts/verify.py`.",
            f"- Lab row counts: {counts}.",
            f"- Drive: {links}.",
            "- Transient artifacts not committed: county rows, chart PNGs under "
            "`artifacts/charts/114/`, and `outputs/114-run-id.txt`.",
            "",
        )
    )


def _numbers(analysis: Analysis) -> str:
    context = analysis.context_pca
    cross = analysis.cross_pca
    share = _fmt(context.two_component)
    gap = None if context.two_component is None else context.two_component - OCT13_TWO_COMPONENT
    return "\n".join(
        (
            (
                f"Headline counts: published floor {analysis.published_n}, "
                f"no county-linked record {analysis.no_record_n}, of {analysis.counties}."
            ),
            (
                f"SVI rescaled by 100: {analysis.svi_rescaled}. "
                f"Uninsured percentile rescaled by 100: {analysis.uninsured_rescaled}."
            ),
            (
                f"Three-feature PCA n {context.n}, two-component share {share}, "
                f"October 13 target 0.8850, difference {_fmt(gap)}."
            ),
            (
                f"Cross-domain PCA n {cross.n}, two-component share {_fmt(cross.two_component)}. "
                "That share is a different block and is not the 88.5% figure."
            ),
            (
                f"Context condition number {_fmt(context.condition_number)}. "
                f"Cross-domain condition number {_fmt(cross.condition_number)}."
            ),
            f"Signed BH family complete: {analysis.family_complete}.",
            (
                "Climate fields not estimable: average temperature "
                "(usable native-double days 0 to 1), precipitation (0 to 6), "
                "maximum temperature, and minimum temperature."
            ),
            (
                f"Small-state three-feature share {_fmt(analysis.small_state_share)}, "
                f"material move {analysis.small_state_material}. "
                f"Contiguous-scope share {_fmt(analysis.scope_share)}, "
                f"material move {analysis.scope_material}."
            ),
        )
    )


def _pair_table(analysis: Analysis) -> str:
    lines = [
        "| Rank | Pair | Estimate | State-cluster interval | Partial | BH tail | Qualified |",
        "| --- | --- | ---: | --- | ---: | ---: | --- |",
    ]
    for index, item in enumerate(analysis.pairs, start=1):
        lines.append(
            "| "
            + " | ".join(
                (
                    str(index),
                    item.spec.pair_id + " " + item.spec.label,
                    _fmt(item.estimate),
                    _interval(item),
                    _fmt(item.partial),
                    _fmt(item.bh),
                    "yes" if item.qualified else "no",
                )
            )
            + " |"
        )
    return "\n".join(lines)


def _reproduction_table(analysis: Analysis) -> str:
    lines = [
        "| Association | Point | Bias-corrected V | n | Matches #116 display | Cited interval |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for item in analysis.reproduction:
        cited = "not cited"
        if item.matches_reference and item.cited_low is not None and item.cited_high is not None:
            cited = f"{item.cited_low:.4f} to {item.cited_high:.4f}"
        lines.append(
            f"| {item.name} | {_fmt(item.estimate)} | {_fmt(item.corrected)} | {item.n} "
            f"| {item.matches_reference} | {cited} |"
        )
    return "\n".join(lines)


def _recommendation_lines(analysis: Analysis) -> str:
    return "\n".join(f"- {note}" for note in analysis.recommendations)


def _disposition(analysis: Analysis) -> str:
    return (
        f"Representation: **{analysis.representation}**. Follow-up: **{analysis.follow_up}**.\n\n"
        + _plain_recommendation(analysis)
    )


def _plain_recommendation(analysis: Analysis) -> str:
    top = next((item for item in analysis.pairs if item.qualified), None)
    top_text = "No signed row met the frozen follow-up gate."
    if top is not None:
        top_text = (
            f"The highest gated row is {top.spec.pair_id} ({top.spec.label}), "
            f"estimate {_fmt(top.estimate)}, partial {_fmt(top.partial)}."
        )
    return (
        f"The three-feature block {analysis.representation}s the October 13 description "
        f"under the frozen 0.880 to 0.890 band. {top_text} "
        "January climate stays out of the feature matrix. "
        "Use the keep and drop lines as a representation note for a later design story, "
        "not as a training decision."
    )


def _interval(item: PairResult) -> str:
    if item.cluster is None or not item.cluster.estimable:
        return "not estimable"
    return f"{_fmt(item.cluster.low)} to {_fmt(item.cluster.high)}"


def _fmt(value: float | None) -> str:
    if value is None:
        return "not estimable"
    return f"{value:.4f}"
