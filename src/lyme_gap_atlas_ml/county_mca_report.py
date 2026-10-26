"""Narrative for issue 121. The text names contrasts and group summaries, not counties."""

from __future__ import annotations

from lyme_gap_atlas_ml.county_mca import (
    SPEC_ID,
    Analysis,
    CategoryCount,
    GroupLocation,
)

_SITUATION_LABELS = {
    "aligned": "Aligned reference",
    "double_gap": "Double gap",
    "wider_gap": "Wider established-tick gap",
    "human_ahead": "Published floor, no pathogen record",
    "undocumented": "No human, tick, or pathogen documentation",
}


def render_comment(analysis: Analysis, *, run_id: str, commit: str, charts: list[str]) -> str:
    """The seven-section briefing shared by the issue comment and the pull request."""
    shares = analysis.greenacre_shares[:3]
    share_text = ", ".join(
        f"{_axis_name(index)} {share:.4f}" for index, share in enumerate(shares, start=1)
    )
    contrasts = (
        " ".join(row.sentence for row in analysis.contrasts)
        or "No axis had a positive Greenacre share."
    )
    group_lines = "\n".join(_format_group(group) for group in analysis.groups)
    stability = _stability_text(analysis)
    rare = ", ".join(analysis.rare_leaders) if analysis.rare_leaders else "none"
    ratio = (
        "not estimable" if analysis.separation_ratio is None else f"{analysis.separation_ratio:.4f}"
    )
    reproduced = all(group.reproduced for group in analysis.groups)
    if reproduced:
        reproduction = "The five epic situation counts match the October references."
    else:
        reproduction = (
            "At least one epic situation count does not match the October reference. "
            "The live counts are below."
        )
    chart_lines = (
        "\n".join(f"- {line}" for line in charts) if charts else "- Charts are not uploaded yet."
    )
    method = analysis.method_disposition
    product = analysis.product_disposition
    lines = [
        "1. Question",
        "",
        "Which two or three contrasts explain most of the categorical difference among counties,",
        "and where do the aligned counties and the double-gap counties sit on that map?",
        "Is the picture stable if one population bin edge moves?",
        "",
        "2. Method (and why; link the spec)",
        "",
        "Multiple correspondence analysis on seven categorical variables:",
        "social-vulnerability quartile, population band, rural-urban code, human status,",
        "blacklegged-tick status, western-blacklegged-tick status, and pathogen status.",
        "Status definitions are the #109 levels. The attributes are surveillance documentation,",
        "the #114 reading, not incidence. #123 state reporting groups are not inputs.",
        f"Spec [{SPEC_ID}](docs/eda/121-analysis-spec.md), frozen before any axis was named.",
        "Headline inertia is the Greenacre adjustment. Rare categories stay in the fit.",
        "The sensitivity moves only the population edge at 50 thousand to 100 thousand.",
        "Axes are an exploratory exhibit, not features for another model,",
        "and the map is not a risk surface.",
        "",
        "3. Key findings with numbers",
        "",
        f"Greenacre-adjusted shares: {share_text}.",
        "",
        contrasts,
        "",
        reproduction,
        "",
        group_lines,
        "",
        f"Counties outside those five situations: {analysis.other_n}.",
        "The double-gap counties are inside the wider gap,",
        "so those two centroids are not two disjoint clouds.",
        f"Aligned versus double-gap separation ratio: {ratio}.",
        "",
        f"Sensitivity: {stability}. Rare leaders on axis 1 or axis 2: {rare}.",
        "",
        "4. Caveats",
        "",
        "Counts are surveillance signals and lower bounds where a human floor is published.",
        "`No records` and `Unknown` are not negatives. A missing floor is not zero.",
        "Counties in one state share reporting rules, so there is no county-independent interval.",
        "The human year, the 2022 context layer, and the tick and pathogen window through 2025",
        "are not one time base. A rare category can still pull an axis;",
        "that case is a revise rule, not a hidden drop.",
        "The hex map suppresses cells below 11 and does not draw county points.",
        "",
        "5. Disposition",
        "",
        f"Method: {method}. Product: {product}.",
        f"{method} is the method call for the MCA exhibit.",
        f"{product} is the product call.",
        "Neither publishes a score or sends these axes into another model.",
        "",
        "6. Artifacts",
        "",
        f"- run_id `{run_id}`",
        "- Snowflake: `REGISTRY.RUNS`, `EDA.METRICS_LONG`, `EDA.FINDINGS`,",
        "  `EDA.COUNTY_MCA_COORDINATES_121`, `EXPERIMENTS.EXPERIMENTS`,",
        "  `EXPERIMENTS.MODEL_METRICS`, `REGISTRY.QUERIES`, `REGISTRY.ARTIFACTS`",
        "- Coordinates, when written, stay in the ML Lab table above.",
        "  They are not in git or Drive.",
        "- Drive:",
        chart_lines,
        "- Doc: `docs/eda/121-county-contrasts.md`",
        "- #123 chart registration for run `123-state-reporting-regimes-20261026T1159Z`:",
        "  three `REGISTRY.ARTIFACTS` rows (`descriptive-dendrogram.png`,",
        "  `publication-free-dendrogram.png`, `group-contingency.png`).",
        "  This story did not upload or edit those Drive files.",
        "",
        "7. Reproducibility",
        "",
        f"- Commit: `{commit}`",
        f"- Release: `{analysis.gate.release_id}`",
        f"- Bundle: `{analysis.gate.bundle_sha256}`",
        "- Seed: `1212026`, recorded and not consumed by the singular-value decomposition",
        f"- SVI scaled by 100: {analysis.gate.svi_scaled}",
        "",
        "```text",
        "uv sync --locked --extra dev --extra snowflake",
        "uv run python scripts/check_ml_agent_context.py",
        "MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
        "python scripts/eda_121_county_mca.py",
        "uv run python scripts/verify.py",
        "```",
        "",
    ]
    return "\n".join(lines)


def render_eda_record(
    analysis: Analysis,
    *,
    run_id: str,
    commit: str,
    charts: list[str],
    row_counts: dict[str, int],
) -> str:
    """Template record plus the same seven sections as the issue comment."""
    counts = ", ".join(f"`{name}` {value}" for name, value in row_counts.items())
    before = _frequency_table(
        [row for row in analysis.frequencies if row.stage == "before_binning" and row.count > 0]
    )
    comment = render_comment(analysis, run_id=run_id, commit=commit, charts=charts)
    issue = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues"
    lines = [
        "# 121: Which contrasts separate counties?",
        "",
        f"- Issue: [#121]({issue}/121); parent epic [#118]({issue}/118);",
        f"  program epic [#22]({issue}/22).",
        "- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`.",
        f"  Release `{analysis.gate.release_id}`.",
        f"- Cohort: {analysis.gate.county_n} counties, one snapshot.",
        f"  Published human floor {analysis.gate.published_n}.",
        f"  No county-linked human record {analysis.gate.unlinked_n}.",
        "",
        "## Method and assumptions",
        "",
        f"Spec [{SPEC_ID}](121-analysis-spec.md), frozen before the axes were interpreted.",
        "The fit is multiple correspondence analysis with the Greenacre inertia adjustment.",
        "Bin edges, the rare-category rule, the seed, and the one-edge stability rule",
        "are in the spec. #109 defines the statuses.",
        "#114 defines the documentation reading and the SVI unit rule.",
        "#123 state groups are not features here.",
        "",
        "## Material findings and limits",
        "",
        "Category frequencies before the MCA bins, levels with a positive count:",
        "",
        before,
        "",
        comment,
        "",
        "## Decision",
        "",
        f"Method **{analysis.method_disposition}**. Product **{analysis.product_disposition}**.",
        "The axes stay an exploratory exhibit.",
        "They are not a production score and not a risk surface.",
        "",
        "## Reproduction and retained evidence",
        "",
        f"- Run `{run_id}`. Commit `{commit}`. Seed `1212026`.",
        f"- Lab row counts: {counts}.",
        "- Entry points: `sql/validation/121_county_mca.sql`,",
        "  `scripts/eda_121_county_mca.py`, `src/lyme_gap_atlas_ml/county_mca.py`.",
        "- Commands:",
        "",
        "```text",
        "uv sync --locked --extra dev --extra snowflake",
        "uv run python scripts/check_ml_agent_context.py",
        "MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
        "python scripts/eda_121_county_mca.py",
        "uv run python scripts/verify.py",
        "```",
        "",
        "- Transient artifacts not committed: county coordinate rows, hex-cell arrays,",
        "  and PNGs under `artifacts/charts/121/`.",
        "  Coordinates that were persisted stay in `EDA.COUNTY_MCA_COORDINATES_121` only.",
        "",
    ]
    return "\n".join(lines)


def _format_group(group: GroupLocation) -> str:
    label = _SITUATION_LABELS[group.name]
    match = "matches" if group.reproduced else "does not match"
    return (
        f"- {label}: {group.count} counties, {match} the reference {group.reference}. "
        f"Centroid on axes 1 and 2: ({group.centroid_1:.4f}, {group.centroid_2:.4f})."
    )


def _frequency_table(rows: list[CategoryCount]) -> str:
    lines = ["| Variable | Level | Counties |", "| --- | --- | ---: |"]
    for row in rows:
        lines.append(f"| {row.variable} | {row.level} | {row.count} |")
    return "\n".join(lines)


def _stability_text(analysis: Analysis) -> str:
    stability = analysis.stability
    if stability is None:
        return "not estimable"
    gate = "passes" if stability.stable else "fails"
    return (
        f"Spearman axis 1 {stability.spearman_1:.4f}, axis 2 {stability.spearman_2:.4f}, "
        f"axis 3 {stability.spearman_3:.4f}; Procrustes similarity {stability.procrustes:.4f} "
        f"on {stability.shared_categories} shared categories; the stability gate {gate}"
    )


def _axis_name(index: int) -> str:
    return f"axis {index}"
