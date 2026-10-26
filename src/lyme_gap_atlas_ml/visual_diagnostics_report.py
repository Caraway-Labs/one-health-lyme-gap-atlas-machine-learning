"""Narrative for issue 117. County names appear only in the spot-check section."""

from __future__ import annotations

from collections.abc import Mapping

from lyme_gap_atlas_ml.visual_diagnostics import SPEC_ID, Analysis, Spot

_ISSUE = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/117"
_PARENT = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22"

_CITES = (
    "County-mean January average temperature on the #107 decimal parse: "
    "n=3109, mean -1.412, median -2.159. "
    "County-mean January precipitation: n=3109, mean 1.459, median 1.171. "
    "#114 Spearman of SVI and log population is 0.1334 (interval 0.0155 to 0.2555). "
    "#114 Spearman of log population and RUCC is -0.7596. "
    "#114 three-feature two-component share is 0.8847 against the 13 October target 0.8850. "
    "#109 headlines on this pin remain 3144 counties, 651 published floors, "
    "and 2493 counties with no county-linked record. "
    "#116 state-cluster intervals are cited there and are not refit. "
    "No 13 October hexbin or county-by-time figure is in the repository."
)


def render_comment(
    result: Analysis,
    *,
    run_id: str,
    git_commit: str,
    row_counts: Mapping[str, int],
    drive_lines: str,
) -> str:
    """Seven-section note shared by the issue comment and the pull request."""
    counts = ", ".join(f"{name}={count}" for name, count in row_counts.items())
    return "\n".join(
        (
            "1. Question",
            "",
            "Which visual summaries reveal defensible Atlas county, space, or time patterns "
            "that standard tables and choropleths miss?",
            "",
            "2. Method (and why; link the spec)",
            "",
            f"Spec [{SPEC_ID}](docs/eda/117-analysis-spec.md), frozen before the fit, "
            "with amendment v1.2 before any diagnostic query. "
            "The hexbin uses the #107 climate parse and a 20-day county mean. "
            "Spearman reuses `cross_domain.spearman_arrays`. "
            "The heatmap clusters the #114 feature list with average linkage on "
            "1 minus absolute Spearman and does not refit those intervals. "
            "The time view is a state-by-day January temperature mean because a labeled "
            "county-by-day image would be a county series on a chart. "
            "Feature contribution is not estimated: no approved held-out model exists. "
            "No 3D surface and no interpolated map.",
            "",
            "3. Key findings with numbers",
            "",
            _findings(result),
            "",
            _CITES,
            "",
            "4. Caveats",
            "",
            "Counts are surveillance signals. A published human floor is a lower bound "
            "(CDC floor 5), not incidence or risk. No records and Unknown are not negatives. "
            "Missing is not zero. Human surveillance is calendar 2023. Tick and pathogen "
            "statuses are cumulative through 2025-12-31. Context fields are 2022 or 2023. "
            "Climate is January 2025 only. Those vintages are not one time base. "
            "Historical CDC objects were not read. Issue 112 was not run. "
            "State means are not a neighbor model, so they are not an issue 113 result. "
            "No p-value is reported. County names are not drawn on charts.",
            "",
            "5. Disposition: keep / revise / stop, plus go/no-go and a plain recommendation",
            "",
            f"Disposition: {result.disposition}.",
            "",
            _recommendation(result),
            "",
            "6. Artifacts",
            "",
            f"run_id: {run_id}",
            f"Snowflake row counts: {counts}",
            "No new table was created, so SELECT was not granted to OH_LYME_PROD_READ.",
            "REGISTRY.ARTIFACTS for run 114-cross-domain-20261026T0822Z has 3 chart rows "
            "registered from the ML Lead's Drive ids. Those Drive files were not changed.",
            f"Drive: {drive_lines}",
            "Doc: docs/eda/117-visual-diagnostics.md",
            "Spec: docs/eda/117-analysis-spec.md",
            "",
            "7. Reproducibility",
            "",
            f"Commit: {git_commit}",
            "Release: governed-2026-10-15-january-climate-prod",
            "Seed: 1172026, recorded and unused. Linkage and hex rounding are deterministic.",
            "Commands:",
            "uv sync --locked --extra dev --extra snowflake",
            "uv run python scripts/check_ml_agent_context.py",
            "MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
            "python scripts/eda_117_visual_diagnostics.py",
            "uv run python scripts/verify.py",
            "",
            "County-level climate means stayed in memory. They were not written to git or Drive.",
            "",
        )
    )


def render_eda_record(
    result: Analysis,
    *,
    run_id: str,
    git_commit: str,
    row_counts: Mapping[str, int],
    drive_lines: str,
) -> str:
    """Durable EDA record. Spot checks may name counties."""
    counts = ", ".join(f"`{name}` {count}" for name, count in row_counts.items())
    spots = "\n".join(f"- {_spot_line(spot)}" for spot in result.spots)
    return "\n".join(
        (
            "# 117: Which visuals show patterns that tables and choropleths miss?",
            "",
            f"- Issue: [ML #117]({_ISSUE}).",
            f"- Parent: [ML #22]({_PARENT}).",
            f"- Spec: [{SPEC_ID}](117-analysis-spec.md), amendment v1.2 before execution.",
            "- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`, and county means "
            "plus state-day means from `CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V`. "
            "Pinned release `governed-2026-10-15-january-climate-prod`.",
            f"- Cohort: {result.cohort_n} counties. Published floor {result.published_n}. "
            f"No county-linked record {result.unpublished_n}.",
            "",
            "## Method and assumptions",
            "",
            "The hexbin, the clustered Spearman heatmap, and the state-by-day temperature "
            "heatmap are the three displays. Feature contribution is the predeclared "
            "not-estimable chart. Baselines and thresholds are in the spec. "
            "No value was imputed as zero. Seed 1172026 is unused.",
            "",
            "## Material findings and limits",
            "",
            render_comment(
                result,
                run_id=run_id,
                git_commit=git_commit,
                row_counts=row_counts,
                drive_lines=drive_lines,
            ),
            "",
            "Spot checks chosen by smallest FIPS, not by the chart:",
            "",
            spots,
            "",
            "## Decision",
            "",
            f"**{result.disposition.upper()}** for quoting the panel as a display that beats "
            "a table or a one-month map. This is not permission to train a model or build a UI.",
            "",
            "## Reproduction and retained evidence",
            "",
            f"- Code revision/run: `{git_commit}`. Run `{run_id}`. Spec `{SPEC_ID}`.",
            "- Entry points: `sql/validation/117_visual_diagnostics.sql`, "
            "`scripts/eda_117_visual_diagnostics.py`, "
            "`src/lyme_gap_atlas_ml/visual_diagnostics.py`.",
            "- Commands: `uv run python scripts/check_ml_agent_context.py`, then "
            "`MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
            "python scripts/eda_117_visual_diagnostics.py`, then "
            "`uv run python scripts/verify.py`.",
            f"- Lab row counts: {counts}.",
            "- Transient artifacts not committed: county rows, chart PNGs under "
            "`artifacts/charts/117/`, and `outputs/117-run-id.txt`.",
            "",
        )
    )


def _findings(result: Analysis) -> str:
    hexbin = result.hexbin
    time = result.time
    heat = result.heatmap
    block = ", ".join(heat.block) if heat.block else "none"
    coldest = ", ".join(time.coldest_states) if time.coldest_states else "none"
    return "\n".join(
        (
            f"Hexbin: estimable={hexbin.estimable}, useful={hexbin.useful}, "
            f"n={hexbin.n}, overflow_n={hexbin.overflow_n}, "
            f"Spearman={_fmt(hexbin.spearman)}, Pearson={_fmt(hexbin.pearson)}, "
            f"joint_mode_differs={hexbin.joint_mode_differs}, "
            f"coefficient_gap={hexbin.coefficient_gap}, panel_shift={hexbin.panel_shift}. "
            f"Reason: {hexbin.reason}.",
            f"Temperature days with at least 20 eligible values: {result.tavg_ready_n}. "
            f"Precipitation days with at least 20 eligible values: {result.prcp_ready_n}.",
            f"Heatmap: estimable={heat.estimable}, useful={heat.useful}, block={block}. "
            f"Leaf order: {', '.join(heat.order)}.",
            f"State-by-day temperature: estimable={time.estimable}, useful={time.useful}, "
            f"distinct days={time.day_count}, wide days={time.wide_days}, "
            f"national range={_fmt(time.national_range)}, coldest states={coldest}. "
            f"Reason: {time.reason}.",
            "Feature contribution: not estimable. " + result.importance_reason,
            _follow_up(result),
        )
    )


def _recommendation(result: Analysis) -> str:
    if result.disposition == "keep":
        opening = (
            "Go, for analyst citation of the displays whose usefulness flag is true. "
            "Do not promote a model and do not treat a chart as disease risk."
        )
    elif result.disposition == "revise":
        opening = (
            "No-go for quoting this panel as evidence that the charts beat tables "
            "and choropleths. The estimable charts stay in the lab as negative or "
            "limited displays."
        )
    else:
        opening = (
            "No-go. The three visual diagnostics were not estimable, so there is no panel to cite."
        )
    return opening + " " + _follow_up(result)


def _follow_up(result: Analysis) -> str:
    parts = [
        _hex_follow(result.hexbin.estimable and result.hexbin.useful),
        _heat_follow(result.heatmap.useful),
        _time_follow(result.time.estimable and result.time.useful),
        "Feature contribution stops until a later story has an approved held-out evaluation. "
        "PCA loadings are not importance. No UI work is in this story.",
    ]
    return " ".join(parts)


def _hex_follow(useful: bool) -> str:
    if useful:
        return (
            "Issue 114 may note the joint January climate shape later. "
            "Do not add it to the #114 PCA from this run. "
            "It is not an issue 113 neighbor contrast. "
            "Issue 112 is not authorized and would not get a surveillance panel "
            "from one climate month. "
            "The hexbin is not a UI candidate."
        )
    return (
        "No climate-shape follow-up for issues 112, 113, or 114. The hexbin is not a UI candidate."
    )


def _heat_follow(useful: bool) -> str:
    if useful:
        return (
            "The named correlation block is a feature-reduction note for a later issue 114 design. "
            "This run does not refit PCA. It is not an issue 112 or 113 input. "
            "An aggregate correlation view is a UI candidate."
        )
    return (
        "The issue 114 table and redundancy heatmap are enough. "
        "No new block goes to issue 112 or 113, and the heatmap is not a UI candidate."
    )


def _time_follow(useful: bool) -> str:
    if useful:
        return (
            "Issue 112, which is not authorized, is the only place a within-January temperature "
            "path would be followed up, as a climate series rather than a human case panel. "
            "State means are not an issue 113 neighbor model. "
            "A state-by-day aggregate with no county names is a UI candidate."
        )
    return "No temporal follow-up. The state-day view is not an issue 113 input or a UI candidate."


def _spot_line(spot: Spot) -> str:
    tavg = "none" if spot.tavg_days is None else str(spot.tavg_days)
    prcp = "none" if spot.prcp_days is None else str(spot.prcp_days)
    return (
        f"{spot.label}: {spot.name}, {spot.state}, FIPS {spot.fips}, "
        f"human {spot.human}, tick {spot.tick}, pathogen {spot.pathogen}, "
        f"eligible January average-temperature days {tavg}, "
        f"precipitation days {prcp}."
    )


def _fmt(value: float | None) -> str:
    if value is None:
        return "not estimable"
    return f"{value:.4f}"
