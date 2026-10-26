"""Narrative for issue 120. Example counties may be named here. Charts may not."""

from __future__ import annotations

from lyme_gap_atlas_ml.gap_communities import (
    RUCC_TEXT,
    SPEC_ID,
    Analysis,
    ClusterProfile,
    ExampleCounty,
)

_CHART_NOTE = "Charts are not uploaded yet."


def render_comment(
    analysis: Analysis,
    *,
    run_id: str,
    commit: str,
    charts: list[str],
    row_counts: dict[str, int] | None = None,
    grant: bool | None = None,
) -> str:
    """The seven-section briefing shared by the issue comment and the pull request."""
    chart_lines = "\n".join(f"- {line}" for line in charts) if charts else f"- {_CHART_NOTE}"
    counts = row_counts or {}
    count_text = ", ".join(f"{key}={value}" for key, value in counts.items()) or "not written yet"
    grant_text = "not attempted" if grant is None else str(grant).lower()
    lines = [
        "1. Question",
        "",
        "Inside the established-tick gap, which counties resemble each other,",
        "what does each community type look like in plain language,",
        "which type contains the most people, which type is the most rural,",
        "and do the double-gap counties concentrate in one type?",
        "",
        "2. Method (and why; link the spec)",
        "",
        "K-prototypes on mixed numeric and categorical fields, inside the #121",
        "established-tick gap (expected 810) with the double-gap subset (expected 228)",
        "reported inside it. #109 supplies the status levels. #114 supplies the",
        "percentile unit rule. #110 supplies the second-seed adjusted Rand index,",
        "the silhouette ranking, and the county-resample stability pattern.",
        "#121 axis scores and latent-class labels are not features.",
        f"Spec [{SPEC_ID}](docs/eda/120-analysis-spec.md), frozen before the fit.",
        "The kmodes package is not pinned. The Huang mixed distance is implemented",
        "in this repository: scaled numerics, gamma 0.5 times the mean scaled",
        "standard deviation, and simple matching on categories. Blanks stay categories.",
        "Cluster membership is not disease risk and not a production score.",
        "",
        "3. Key findings with numbers",
        "",
        _summary(analysis),
        "",
        _grid(analysis),
        "",
        _profiles(analysis),
        "",
        "4. Caveats",
        "",
        "Counts are surveillance signals. A published human count is a lower bound",
        "(CDC floor 5), not incidence. No records and Unknown are not negatives.",
        "A missing human floor is not zero. The 2022 vulnerability and insurance",
        "layer, the 2023 rural-urban code, and the tick and pathogen statuses",
        "through 2025 are not one time base. Counties in one state share reporting",
        "rules. The bootstrap band is a stability check for the partition, not a",
        "confidence interval for a disease rate. No Tier 1 model, PROD batch,",
        "tier policy, or API contract was changed.",
        "",
        "5. Disposition",
        "",
        f"Method: {analysis.method_disposition}. Product: {analysis.product_disposition}.",
        _reasons(analysis),
        "Advance would mean the types are stable enough to brief as separate",
        "outreach descriptions. It would not authorize a model, a rank, or a public map.",
        "",
        "6. Artifacts",
        "",
        f"Run id: `{run_id}`.",
        f"Snowflake row counts: {count_text}.",
        f"SELECT grant to OH_LYME_PROD_READ: {grant_text}.",
        "Narrative: `docs/eda/120-gap-communities.md`.",
        "Spec: `docs/eda/120-analysis-spec.md`.",
        chart_lines,
        "Also registered the two #121 charts the ML Lead supplied for run",
        "`121-county-contrasts-20261026T1251Z`: `category-pulls.png`",
        "(Drive id 1JhZBDAEcUUrx-Gej_SLV_lSh-LaTS3ve, 17498 bytes) and",
        "`axis-map.png` (Drive id 1wyktxL9P9efH5tjhJy72CJfKcO2LqjI5, 14429 bytes).",
        "`REGISTRY.ARTIFACTS` has 3 rows for that run, including the existing",
        "`greenacre-scree.png`. Nothing in the issue-121 Drive folder was changed.",
        "",
        "7. Reproducibility",
        "",
        f"Commit `{commit}`. Release `{analysis.gate.release_id}`.",
        "Seeds 1202026, 1202027, and 1202028.",
        "County rows stayed in memory and were not written to git or Drive.",
        "",
        "```text",
        "uv sync --locked --extra dev --extra snowflake",
        "uv run python scripts/check_ml_agent_context.py",
        "MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_120_gap_communities.py",  # noqa: E501
        "uv run python scripts/verify.py",
        "```",
    ]
    return "\n".join(lines) + "\n"


def render_eda_record(
    analysis: Analysis,
    *,
    run_id: str,
    commit: str,
    charts: list[str],
    row_counts: dict[str, int],
    grant: bool,
) -> str:
    """The durable EDA record, from the repository template."""
    chart_text = ", ".join(charts) if charts else _CHART_NOTE
    return "\n".join(
        [
            "# 120: Which community types sit inside the established-tick gap?",
            "",
            "- Issue: [#120](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/120);",
            "  parent epic [#118](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/118);",
            "  program epic [#22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).",
            "  Question: which community types inside the established-tick gap are alike",
            "  enough to share one outreach description?",
            f"- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`. Release `{analysis.gate.release_id}`.",  # noqa: E501
            f"- Cohort: established aggregate tick status and no published human floor. Live cohort {analysis.cohort_n}.",  # noqa: E501
            f"  Double-gap subset {analysis.double_gap_n}. Reference counts are 810 and 228.",
            "",
            "## Method and assumptions",
            "",
            f"Spec [{SPEC_ID}](120-analysis-spec.md), frozen before the fit.",
            "K-prototypes with the Huang mixed distance. Numeric fields are z-scored.",
            "Categorical blanks stay categories. #109 defines statuses. #114 defines the",
            "percentile unit rule. #110 defines the stability checks this spec adapts.",
            "#121 defines the cohort predicates and is not a feature source.",
            "Seeds 1202026, 1202027, and 1202028. Cluster membership is not disease risk.",
            "",
            "## Material findings and limits",
            "",
            _summary(analysis),
            "",
            _grid(analysis),
            "",
            _distributions(analysis),
            "",
            _profiles(analysis),
            "",
            "A published human count elsewhere on the atlas is a lower bound, not incidence.",
            "No records and Unknown are not negatives. Missing is not zero.",
            "Vintages differ across 2022, 2023, and 2025. No production score is published.",
            "",
            "## Decision",
            "",
            f"Method {analysis.method_disposition}. Product {analysis.product_disposition}.",
            _reasons(analysis),
            "The product call does not authorize model promotion, a public map, or a PROD write.",
            "",
            "## Reproduction and retained evidence",
            "",
            (
                f"- Code revision/run/config/data references: commit `{commit}`, "
                f"run `{run_id}`, spec `{SPEC_ID}`."
            ),
            (
                "- Entry points: `sql/validation/120_gap_communities.sql`, "
                "`scripts/eda_120_gap_communities.py`,"
            ),
            "  `src/lyme_gap_atlas_ml/gap_communities.py`.",
            "- Commands: `uv sync --locked --extra dev --extra snowflake`;",
            "  `uv run python scripts/check_ml_agent_context.py`;",
            "  `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_120_gap_communities.py`;",  # noqa: E501
            "  `uv run python scripts/verify.py`.",
            "- Lab row counts: "
            + ", ".join(f"{key}={value}" for key, value in row_counts.items())
            + ".",
            f"  SELECT grant recorded: {str(grant).lower()}.",
            f"- Charts: {chart_text}.",
            "- Transient artifacts intentionally not committed: county assignment rows",
            "  (ML Lab table only), chart PNGs under ignored `artifacts/charts/120/`,",
            "  and any local query cache.",
            "",
        ]
    )


def _summary(analysis: Analysis) -> str:
    gamma = "not computed" if analysis.gamma is None else f"{analysis.gamma:.4f}"
    selected = "none" if analysis.selected is None else str(analysis.selected.k)
    reported = "none" if analysis.reported is None else str(analysis.reported.k)
    people = _cluster_phrase(analysis, analysis.most_people_cluster, "most people")
    rural = _cluster_phrase(analysis, analysis.most_rural_cluster, "most rural")
    return (
        f"National extract {analysis.gate.county_n} counties, published floor {analysis.gate.published_n}, "  # noqa: E501
        f"no county-linked human record {analysis.gate.unlinked_n}. "
        f"Established-tick gap {analysis.cohort_n} (reference 810). "
        f"Double gap inside it {analysis.double_gap_n} (reference 228). "
        f"Double-gap counties outside the cohort: {analysis.double_gap_outside}. "
        f"Cohort rows excluded for a missing numeric: {analysis.excluded_n}. "
        f"Gamma {gamma}. Selected k {selected}. Reported k {reported}. "
        f"{people} {rural}"
    )


def _grid(analysis: Analysis) -> str:
    if not analysis.candidates:
        return "No candidate k was fit."
    lines = [
        "| k | Converged | Seed ARI | Silhouette | Bootstrap low | Bootstrap high | Min size |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]  # noqa: E501
    for candidate in analysis.candidates:
        lines.append(
            "| {k} | {conv} | {ari} | {sil} | {low} | {high} | {size} |".format(
                k=candidate.k,
                conv="yes" if candidate.converged else "no",
                ari=_fmt(candidate.seed_ari),
                sil=_fmt(candidate.silhouette),
                low=_fmt(candidate.bootstrap_low),
                high=_fmt(candidate.bootstrap_high),
                size=candidate.min_size,
            )
        )
    return "\n".join(lines)


def _distributions(analysis: Analysis) -> str:
    lines = [
        (
            "Pre-clustering frequencies inside the clustering cohort. "
            "A bin can be small; the chart omits counts from 1 to 10."
        ),
        "",
    ]
    lines.append("| Feature | Bin | Counties |")
    lines.append("| --- | --- | ---: |")
    for frequency in (
        *analysis.population_bins,
        *analysis.svi_bins,
        *analysis.uninsured_bins,
        *analysis.rucc_bins,
    ):
        if frequency.n == 0:
            continue
        lines.append(f"| {frequency.feature} | {frequency.label} | {frequency.n} |")
    return "\n".join(lines)


def _profiles(analysis: Analysis) -> str:
    if not analysis.profiles:
        return "No cluster profile was produced."
    blocks = [_profile_block(profile, analysis.cohort_n) for profile in analysis.profiles]
    total_double = sum(profile.double_gap_n for profile in analysis.profiles)
    blocks.append(
        f"Double-gap counties assigned to a reported cluster: {total_double} of {analysis.double_gap_n}."  # noqa: E501
    )
    return "\n\n".join(blocks)


def _profile_block(profile: ClusterProfile, cohort_n: int) -> str:
    share = 0.0 if cohort_n == 0 else profile.n / cohort_n
    rural = RUCC_TEXT.get(profile.mode_rucc, profile.mode_rucc)
    median_rucc = "not defined" if profile.median_rucc is None else f"{profile.median_rucc:.1f}"
    distance = _fmt(profile.nearest_prototype_distance)
    examples = "; ".join(_example(example) for example in profile.examples) or "none"
    distinct = "yes" if profile.distinguishable else "no"
    return "\n".join(
        [
            f"Type {profile.cluster_id}: {profile.n} counties ({share:.1%} of the cohort) and {_people(profile.population_total)}.",  # noqa: E501
            f"Median county population {_people(profile.median_population).removesuffix(' people')}.",  # noqa: E501
            f"Median social-vulnerability percentile {profile.median_svi:.2f}.",
            f"Median uninsured percentile {profile.median_uninsured:.2f}.",
            f"Median rural-urban code {median_rucc}. The most common code is {rural}.",
            f"Most common blacklegged-tick status: {profile.mode_scapularis}.",
            f"Most common western-blacklegged-tick status: {profile.mode_pacificus}.",
            f"Most common pathogen status: {profile.mode_pathogen}.",
            f"Double-gap counties in this type: {profile.double_gap_n}.",
            f"Nearest other prototype is {distance} on the mixed distance. Distinguishable: {distinct}.",  # noqa: E501
            f"Counties closest to the prototype, not a ranking of disease: {examples}.",
        ]
    )


def _example(example: ExampleCounty) -> str:
    gap = "double gap" if example.in_double_gap else "wider gap only"
    return (
        f"{example.name}, {example.state} ({example.fips}; population {example.population:.0f}; "
        f"vulnerability {example.svi:.2f}; uninsured {example.uninsured:.2f}; "
        f"rural-urban code {example.rucc}; {gap})"
    )


def _cluster_phrase(analysis: Analysis, cluster_id: int | None, label: str) -> str:
    if cluster_id is None:
        return f"The {label} type is not defined."
    return f"The {label} type is {cluster_id}."


def _reasons(analysis: Analysis) -> str:
    if not analysis.reasons:
        return "No revise or stop reason fired."
    return "Reasons: " + "; ".join(analysis.reasons) + "."


def _fmt(value: float | None) -> str:
    if value is None:
        return "not estimable"
    return f"{value:.4f}"


def _people(population: float) -> str:
    if population >= 1_000_000:
        return f"{population / 1_000_000:.2f} million people"
    return f"{population / 1_000:.1f} thousand people"
