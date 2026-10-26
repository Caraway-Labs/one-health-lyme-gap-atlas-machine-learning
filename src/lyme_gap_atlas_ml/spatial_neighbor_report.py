"""Write-up text for issue 113. County examples stay in this narrative."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from lyme_gap_atlas_ml.spatial_neighbors import SPEC_ID, Analysis, Flagged

_SHOW = 8
_ISSUE = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues"
_DRIVE = "https://drive.google.com/drive/folders/1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM"


def render_eda_record(
    result: Analysis,
    *,
    run_id: str,
    commit: str,
    counts: Mapping[str, int],
    drive_lines: Sequence[str],
) -> str:
    """Template record plus the issue-comment sections."""
    header = "\n".join(
        (
            "# 113: Where do neighboring counties diverge beyond expected "
            "measurement and coverage variability?",
            "",
            f"- Issue: [ML #113]({_ISSUE}/113), part of [ML #22]({_ISSUE}/22).",
            "- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`,",
            "  `CURRENT_SOURCE_METADATA_V`, and `CURRENT_MEASURE_METADATA_V`.",
            "  Pinned release `governed-2026-10-15-january-climate-prod`.",
            f"- Cohort: {result.county_n} counties. Published floors: {result.published_n}.",
            f"  No county-linked human record: {result.unpublished_n}.",
            "",
            "## Method and assumptions",
            "",
            f"Spec [{SPEC_ID}](113-analysis-spec.md), frozen before the contrast. "
            "Neighbor weights are not on the allow-list, so Moran's I and LISA "
            "were not estimated. The within-state robust z reuses the #106 size "
            "bands for the published incidence floor only.",
            "",
            "## Material findings and limits",
            "",
            _findings_prose(result),
            "",
            "## Decision",
            "",
            _decision(result),
            "",
            "## Reproduction and retained evidence",
            "",
            f"- Code revision at the contrast: `{commit}`.",
            "- Entry points: `sql/validation/113_spatial_neighbors.sql`,",
            "  `scripts/eda_113_spatial_neighbors.py`,",
            "  `src/lyme_gap_atlas_ml/spatial_neighbors.py`.",
            "- Commands: `uv run python scripts/check_ml_agent_context.py`, then",
            "  `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python "
            "scripts/eda_113_spatial_neighbors.py`, then `uv run python scripts/verify.py`.",
            "- Transient artifacts intentionally not committed: PNG files under",
            "  `artifacts/charts/113/` and in-memory county rows.",
            "  No county extract was committed.",
            "",
        )
    )
    return (
        header
        + "\n"
        + render_comment(
            result,
            run_id=run_id,
            commit=commit,
            counts=counts,
            drive_lines=drive_lines,
        )
    )


def render_comment(
    result: Analysis,
    *,
    run_id: str,
    commit: str,
    counts: Mapping[str, int],
    drive_lines: Sequence[str],
) -> str:
    """Issue comment and pull-request body."""
    rows = "\n".join(f"- `{name}` {count}" for name, count in counts.items())
    if drive_lines:
        drives = "\n".join(f"- {line}" for line in drive_lines)
    else:
        drives = "- No estimable chart was uploaded."
    if result.chart_bins:
        chart_note = (
            f"{result.chart_states} states have at least 11 published floors, "
            "so the state-median chart was drawn."
        )
    else:
        chart_note = (
            "Fewer than 11 states have at least 11 published floors, so no chart was drawn."
        )
    method = (
        f"Spec [{SPEC_ID}](docs/eda/113-analysis-spec.md), frozen before the contrast. "
        "The allow-listed catalog has no adjacency, centroid, latitude, longitude, "
        "or neighbor column. `EDA.COUNTY_ADJACENCY_107` has 0 rows. "
        "Geometry text was not read. Neighbor residuals, Moran's I, and LISA are "
        "implemented for a supplied FIPS-pair list and tested on fake edges. "
        "They were not run on live counties. The live contrast is the within-state "
        "robust z of the published incidence floor, using the #106 size bands and "
        "`shrunk_mad`. A case floor of 5 with a low z is a CDC floor heap, not a "
        "divergence flag. Missing floors stay missing. Eta-squared uses 2,000 "
        "permutations of published incidence values, seed 1132026, with Holm and BH "
        "on that one-test family. #106's 113 state-relative flags are the "
        "context-feature screen and were not refit. #107's national incidence "
        "screen is the comparison for the scaled-MAD counts."
    )
    caveats = (
        "Human floors are calendar 2023 surveillance lower bounds (CDC floor 5). "
        "They are not incidence, risk, or causation. A missing floor is not zero. "
        "No records and Unknown are not negatives. The within-state z compares a "
        "county with other published counties in the same state, including counties "
        "that do not share a border. It is not a neighbor outlier. The permutation "
        "exchanges published floors among counties that publish. It does not cover "
        "dependence that crosses a state line. Population is not a second "
        "denominator: the incidence floor is already per 100,000. #106 owns the "
        "population screen. Alaska, Hawaii, and the District of Columbia stay in "
        "the state contrast. Without an edge list they are not classified as "
        "graph islands."
    )
    return "\n".join(
        (
            "## 1. Question",
            "",
            "Where do neighboring counties diverge beyond expected measurement "
            "and coverage variability?",
            "",
            "## 2. Method",
            "",
            method,
            "",
            "## 3. Key findings",
            "",
            _findings_prose(result),
            "",
            chart_note,
            "",
            _table("High within-state divergence", result.high_flags),
            "",
            _table("Low within-state divergence", result.low_flags),
            "",
            _overlap(result),
            "",
            "## 4. Caveats",
            "",
            caveats,
            "",
            "## 5. Disposition",
            "",
            _decision(result),
            "",
            "## 6. Artifacts",
            "",
            f"- Run id: `{run_id}`",
            "- Snowflake, ML Lab only:",
            rows,
            "- No new lab table was created, so no new SELECT grant was issued.",
            f"- Drive folder: {_DRIVE}",
            drives,
            "- Doc: `docs/eda/113-spatial-neighbor-outliers.md`",
            "",
            "## 7. Reproducibility",
            "",
            f"- Commit at the contrast: `{commit}`",
            "- Release: `governed-2026-10-15-january-climate-prod`",
            "- Seed: `1132026`",
            f"- State permutation draws: {result.draws}",
            "- Commands:",
            "",
            "```text",
            "uv sync --locked --extra dev --extra snowflake",
            "uv run python scripts/check_ml_agent_context.py",
            "MPLBACKEND=Agg uv run --with matplotlib --with seaborn \\",
            "python scripts/eda_113_spatial_neighbors.py",
            "uv run python scripts/verify.py",
            "```",
            "",
        )
    )


def _decision(result: Analysis) -> str:
    kept = (
        "Keep, where it applies, is permission to show state-peer review "
        "candidates beside the #106 context flags. It is not a public score "
        "and not a change to the Tier 1 model."
    )
    return (
        "**Method: stop** for neighbor contrasts, Moran's I, and LISA on this release. "
        f"**Method: {result.within_state_disposition}** for the within-state "
        "published-incidence contrast. "
        f"**Product: {result.product_disposition}.** "
        "The neighbor screen needs a governed adjacency table of undirected FIPS "
        "pairs (`FIPS_A`, `FIPS_B`, `FIPS_A < FIPS_B`, `RELEASE_ID`) and no "
        "geometry text. This run does not create that table. " + kept
    )


def _findings_prose(result: Analysis) -> str:
    if result.national_matches_107:
        national = "The national scaled-MAD counts match #107 (high 37, low 0)."
    else:
        national = (
            "The national scaled-MAD counts are "
            f"high {result.national_high} and low {result.national_low}. "
            "#107 reported high 37 and low 0."
        )
    if result.silent_matches_107:
        silent = "States with no published county floor match #107 (19 states, 1437 counties)."
    else:
        silent = (
            "States with no published county floor: "
            f"{result.states_without_published} "
            f"({result.counties_in_silent_states} counties). "
            "#107 reported 19 states and 1437 counties."
        )
    eta = "not estimable" if result.eta_sq is None else f"{result.eta_sq:.4f}"
    tail = "not estimable" if result.eta_tail is None else f"{result.eta_tail:.4f}"
    bands = ", ".join(
        (
            f"{rule} {result.band_states.get(rule, 0)} states "
            f"and {result.band_counties.get(rule, 0)} published counties"
        )
        for rule in ("state_native", "shrunk", "below_band")
    )
    return "\n".join(
        (
            f"Atlas counties: {result.county_n}. Published floors: {result.published_n}. "
            f"No county-linked record: {result.unpublished_n}.",
            (
                f"Published incidence floor: n={result.published_n}, "
                f"median {result.national_median:.4g}, MAD {result.national_mad:.4g}. "
                f"{national}"
            ),
            silent,
            f"Peer bands: {bands}.",
            (
                f"Within-state high divergence: {len(result.high_flags)}. "
                f"Low divergence, case floor above 5: {len(result.low_flags)}. "
                f"Low z on a case floor of 5 (floor heaps, not divergence flags): "
                f"{result.floor_heaps}. "
                f"Case floors below 5: {result.case_floor_below_cdc}. "
                f"States whose scale is not estimable: {result.mad_not_estimable_states}."
            ),
            (
                f"Between-state share of squares: {eta}. "
                f"One-sided permutation tail: {tail}. "
                f"Holm {_tail(result.eta_holm)}. BH {_tail(result.eta_bh)}. "
                f"Draws {result.draws}, seed {result.seed}."
            ),
            "Adjacency sources on the allow-list: 0. Lab adjacency edges: 0. "
            "Neighbor residuals, Moran's I, and LISA: not estimable.",
            "#106 reported 113 state-relative context flags "
            "(Jaccard with its national screen 0.025). "
            "Those flags are log population, SVI, uninsured percentile, and "
            "rural-urban code. They are not incidence-floor neighbor outliers "
            "and were not refit. #122 is the established-tick class screen "
            "and is not a weights source.",
        )
    )


def _overlap(result: Analysis) -> str:
    if not result.prior_overlap:
        return (
            "None of the within-state high flags are among the eight national "
            "right-tail counties named by #107."
        )
    names = ", ".join(f"{item.county.name}, {item.county.state}" for item in result.prior_overlap)
    return f"Within-state high flags that are also in the #107 national right-tail list: {names}."


def _table(title: str, flags: Sequence[Flagged]) -> str:
    shown = flags[:_SHOW]
    if not shown:
        return f"{title}: none."
    header = (
        "| County | State | FIPS | Peer | Peer n | Incidence floor "
        "| State median | Robust z | Case floor |"
    )
    lines = [
        f"{title}. {len(shown)} of {len(flags)} shown.",
        "",
        header,
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in shown:
        case_floor = item.county.case_floor
        incidence = "" if item.county.incidence is None else f"{item.county.incidence:.4g}"
        lines.append(
            "| "
            + " | ".join(
                (
                    item.county.name,
                    item.county.state,
                    item.county.fips,
                    item.peer_rule,
                    str(item.peer_n),
                    incidence,
                    f"{item.median:.4g}",
                    f"{item.z:.2f}",
                    "" if case_floor is None else str(case_floor),
                )
            )
            + " |"
        )
    return "\n".join(lines)


def _tail(value: float | None) -> str:
    if value is None:
        return "not estimable"
    return f"{value:.4f}"
