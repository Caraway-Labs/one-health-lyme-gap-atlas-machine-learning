"""Markdown for issue 107. County names appear only in the narrative surfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from lyme_gap_atlas_ml.county_distributions import (
    REFERENCE_HIGH,
    REFERENCE_INSUFFICIENT,
    REFERENCE_LOW,
    REFERENCE_MEDIUM,
    REFERENCE_SUFFICIENT,
    SEED,
    SPEC_ID,
    Analysis,
    SignalGroup,
)

_ISSUE_107 = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/107"
_ISSUE_22 = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22"
_SPEC = "docs/eda/107-analysis-spec.md"
_RUN_COMMAND = (
    "MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_107_distributions.py"
)


def render_comment(
    result: Analysis,
    *,
    run_id: str,
    git_commit: str,
    row_counts: Mapping[str, int],
    drive_lines: Sequence[str],
    adjacency_note: str,
) -> str:
    """Issue comment and pull-request body."""
    rows = "\n".join(f"- `{name}` {count}" for name, count in row_counts.items())
    drives = "\n".join(f"- {line}" for line in drive_lines) or "- Drive upload pending"
    return "\n".join(
        (
            "## 1. Question",
            "",
            "What is typical and what is unusual in each county signal, how variable is it, "
            "and are the HIGH / MEDIUM / LOW tier boundaries interpretable?",
            "",
            "## 2. Method",
            "",
            f"Spec [{SPEC_ID}]({_SPEC}), frozen before the distribution queries. "
            "Exact statistics use the raw values. Histogram bins use the fixed edges in the spec. "
            "Climate day summaries are aggregated in Snowflake. "
            "County-mean climate is summarized from those county averages. "
            "Unweighted summaries give each county one weight. Population-weighted summaries give "
            "each person one weight. The county set is the governed release, not a sample, so "
            "there is no standard error and no hypothesis test. "
            f"Seed {SEED} is recorded and unused. "
            "IQR fences and scaled-MAD flags are review candidates. "
            "INSUFFICIENT evidence is counted on its own and is not called LOW.",
            "",
            "## 3. Key findings",
            "",
            _findings(result),
            "",
            "## 4. Caveats",
            "",
            "Human floors are calendar 2023 surveillance lower bounds (CDC floor 5). "
            "They are not incidence, risk, or causation. "
            "Population, SVI, and uninsured context are 2022. RUCC is 2023. "
            "Tick and pathogen statuses are cumulative through 2025-12-31. "
            "Climate, when read, is the stored county-day window, not a multi-year series. "
            "The tier view is release `governed-2026-09-18-unknown-coverage`, "
            "model `tier1-statistical-reference-v1`, policy `tier1-review-percentile-v1`. "
            "It is not a score computed on the October 15 atlas. "
            "Neighboring counties are dependent. Adjacency does not adjust these summaries. "
            "NLCD covers two counties and is not a national distribution. "
            "A missing human floor is not zero. No records and Unknown are not negatives.",
            "",
            "## 5. Disposition",
            "",
            _disposition(result),
            "",
            "## 6. Artifacts",
            "",
            f"- Run id: `{run_id}`",
            "- Snowflake, ML Lab only:",
            rows,
            f"- Adjacency: {adjacency_note}",
            drives,
            "- Doc: `docs/eda/107-county-distributions.md`",
            "",
            "## 7. Reproducibility",
            "",
            f"- Commit: `{git_commit}`",
            "- Release: `governed-2026-10-15-january-climate-prod`",
            "- Tier batch release: `governed-2026-09-18-unknown-coverage`",
            f"- Seed: `{SEED}`",
            "- Commands:",
            "",
            "```text",
            "uv sync --locked --extra dev --extra snowflake",
            "uv run python scripts/check_ml_agent_context.py",
            _RUN_COMMAND,
            "uv run python scripts/verify.py",
            "```",
            "",
        )
    )


def render_eda_record(
    result: Analysis,
    *,
    run_id: str,
    git_commit: str,
    row_counts: Mapping[str, int],
    drive_lines: Sequence[str],
    adjacency_note: str,
) -> str:
    """Durable EDA record. The comment below it carries the same numbers."""
    counts = ", ".join(f"`{name}` {count}" for name, count in row_counts.items())
    drives = "; ".join(drive_lines) or "Drive upload pending"
    return "\n".join(
        (
            "# 107: What is typical, how variable, and are the tier boundaries interpretable?",
            "",
            f"- Issue: [ML #107]({_ISSUE_107}), part of [ML #22]({_ISSUE_22}).",
            "- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_TIER1_COUNTY_REVIEW_V`, "
            "`CURRENT_RELEASE_V`, `CURRENT_SOURCE_METADATA_V`, climate county-day values, "
            "and an NLCD county count. Pinned atlas release "
            "`governed-2026-10-15-january-climate-prod`. Tier batch release "
            "`governed-2026-09-18-unknown-coverage`.",
            f"- Cohort: {result.counties} counties, {result.distinct_fips} distinct FIPS. "
            f"Published human floors: {result.published}. "
            f"No county-linked human record: {result.unpublished}.",
            "",
            "## Method and assumptions",
            "",
            f"Spec [{SPEC_ID}](107-analysis-spec.md), frozen before execution. "
            "The finite county set is the denominator. People are the weight in the "
            "population-weighted summaries. Seed "
            f"`{SEED}` is unused. Outlier flags are not deletions.",
            "",
            "## Material findings and limits",
            "",
            _findings(result),
            "",
            "## Decision",
            "",
            _disposition(result),
            "",
            "## Reproduction and retained evidence",
            "",
            f"- Code revision/run: `{git_commit}`, run `{run_id}`, spec `{SPEC_ID}`.",
            "- Entry points: `sql/validation/107_county_distributions.sql`, "
            "`scripts/eda_107_distributions.py`, `src/lyme_gap_atlas_ml/county_distributions.py`.",
            "- Commands: `uv run python scripts/check_ml_agent_context.py`, then "
            f"`{_RUN_COMMAND}`, "
            "then `uv run python scripts/verify.py`.",
            f"- Lab row counts: {counts}.",
            f"- Adjacency: {adjacency_note}.",
            f"- Drive: {drives}.",
            "- Transient artifacts intentionally not committed: PNG files under "
            "`artifacts/charts/107/`, `outputs/107-run-id.txt`, and in-memory county rows. "
            "No county extract was committed.",
            "",
        )
    )


def _findings(result: Analysis) -> str:
    incidence = _group(result.signals, "incidence_floor_2023", "national", "US")
    case = _group(result.signals, "case_count_floor_2023", "national", "US")
    population = _group(result.signals, "population", "national", "US")
    svi = _group(result.signals, "svi_percentile", "national", "US")
    lines = [
        f"Atlas counties: {result.counties}. Published floors: {result.published} "
        f"(October 13 reference {REFERENCE_SUFFICIENT}). "
        f"No county-linked record: {result.unpublished} "
        f"(reference {REFERENCE_INSUFFICIENT}).",
        "",
        _summary_line("Published case floor", case),
        _summary_line("Published incidence floor per 100,000", incidence),
        _summary_line("Population", population),
        _summary_line("SVI percentile", svi),
        "",
        f"Published case floors equal to 5: {result.case_floor_at_5}. "
        f"Incidence histogram peaks: {result.incidence_peaks}. "
        f"SVI rescaled from a 0–100 column: {'yes' if result.svi_rescaled else 'no'}. "
        f"Uninsured rescaled: {'yes' if result.uninsured_rescaled else 'no'}.",
        "",
        f"States with no published county floor: {result.nonpublishing_states} "
        f"({result.counties_in_nonpublishing_states} counties, "
        f"{result.null_floors_in_nonpublishing_states} null floors). "
        f"Null floors in states that publish at least one floor: "
        f"{result.null_floors_in_publishing_states}.",
        "",
        _examples(result),
        "",
        _tier_lines(result),
        "",
        _climate_lines(result),
        "",
        f"NLCD counties on this release: {result.nlcd_counties}. "
        "That is not a national land-cover distribution.",
    ]
    return "\n".join(lines)


def _summary_line(label: str, group: SignalGroup | None) -> str:
    if group is None or group.summary.n == 0:
        return f"{label}: not estimable."
    summary = group.summary
    return (
        f"{label}: n={summary.n}, mean {_num(summary.mean)}, "
        f"population-weighted mean {_num(summary.weighted_mean)}, "
        f"median {_num(summary.median)}, mode {_num(summary.mode)}, "
        f"modal bin {summary.modal_bin}, IQR {_num(summary.iqr)}, "
        f"variance {_num(summary.variance)}, SD {_num(summary.sd)}, "
        f"skewness {_num(summary.skewness)}. "
        f"IQR flags low/high {summary.iqr_low}/{summary.iqr_high}. "
        f"MAD flags low/high {summary.mad_low}/{summary.mad_high} "
        f"(estimable: {'yes' if summary.mad_estimable else 'no'})."
    )


def _examples(result: Analysis) -> str:
    if not result.incidence_examples:
        return "No published incidence floor exceeded the scaled-MAD review threshold."
    lines = [
        "Right-tail review candidates on the published incidence floor "
        "(scaled MAD above 3.5). These are surveillance review candidates, not disease findings."
    ]
    for example in result.incidence_examples:
        lines.append(
            f"- {example.county}, {example.state}: incidence floor {example.value:.4g}, "
            f"robust z {example.robust_z:.2f}."
        )
    return "\n".join(lines)


def _tier_lines(result: Analysis) -> str:
    tier = result.tier
    bounds = []
    for label in ("HIGH", "MEDIUM", "LOW"):
        found = tier.score_bounds.get(label)
        if found is None:
            bounds.append(f"{label} score range not estimable")
        else:
            bounds.append(
                f"{label} raw score min/median/max {found[0]:.4g}/{found[1]:.4g}/{found[2]:.4g}"
            )
    cross = ", ".join(
        f"{sufficiency}/{label} {count}"
        for (sufficiency, label), count in sorted(tier.sufficiency_by_tier.items())
    )
    return "\n".join(
        (
            f"Stored tiers: HIGH {tier.high} (reference {REFERENCE_HIGH}), "
            f"MEDIUM {tier.medium} (reference {REFERENCE_MEDIUM}), "
            f"LOW {tier.low} (reference {REFERENCE_LOW}). "
            f"SUFFICIENT {tier.sufficient} (reference {REFERENCE_SUFFICIENT}). "
            f"INSUFFICIENT {tier.insufficient} (reference {REFERENCE_INSUFFICIENT}). "
            "INSUFFICIENT is not reported as LOW.",
            f"Percentile column rescaled from a 0–1 fraction: "
            f"{'yes' if tier.percentile_rescaled else 'no'}. "
            f"Stored tier versus the 70/90 rule: {tier.stored_versus_rule} disagreements.",
            "Absolute scores implied by this batch: " + "; ".join(bounds) + ".",
            f"Sufficiency by stored tier: {cross}.",
            "Human-evidence labels on the tier view: "
            + ", ".join(tier.human_evidence_levels)
            + ". "
            f"Rows whose sufficiency or human-evidence label does not match the current atlas "
            f"human status: {tier.sufficiency_versus_human}.",
            "HIGH share by Census region is in `EDA.METRICS_LONG` (`high_share`). "
            "A 1–10 cell is suppressed there.",
        )
    )


def _climate_lines(result: Analysis) -> str:
    if not result.climate_days:
        return (
            f"Climate days read: {result.climate_days_read}. "
            "No eligible climate values, so that distribution is not estimable."
        )
    lines = [
        f"Eligible climate county-day values: {result.climate_days_read}. "
        "Day-level summaries were aggregated in Snowflake. "
        "The exact day-level mode is not estimable from that aggregate."
    ]
    for group in result.climate_days:
        if group.geography_type != "national":
            continue
        lines.append(_summary_line(group.signal, group))
    for group in result.climate_county_means:
        if group.geography_type == "national":
            lines.append(_summary_line(f"{group.signal} (county mean)", group))
    return "\n".join(lines)


def _disposition(result: Analysis) -> str:
    if result.disposition == "keep":
        decision = "KEEP"
        reason = (
            "The October 15 atlas still has 3,144 counties, 651 published floors, and "
            "2,493 counties with no county-linked record. The September tier batch still "
            "stores HIGH 315, MEDIUM 628, LOW 2,201, SUFFICIENT 651, and INSUFFICIENT 2,493."
        )
    elif result.disposition == "revise":
        decision = "REVISE"
        reason = (
            "At least one October 13 reference count differs on this read. "
            "Use the counts in this note until that difference is explained."
        )
    else:
        decision = "STOP"
        reason = "The release pin or the 3,144-FIPS gate failed. The distribution is not usable."
    recommendation = (
        "Show the stored HIGH, MEDIUM, and LOW labels as a relative review order on this "
        "September score batch, and always show SUFFICIENT or INSUFFICIENT beside the tier. "
        "Do not read LOW as a low disease burden, and do not read a high published floor as a "
        "confirmed outbreak. The published numbers are 2023 surveillance floors, they start at 5, "
        "and a county with no county-linked record is unpublished, not a zero. "
        "The tier view is an older batch than the October 15 atlas, so the product should not "
        "describe it as a score on the current atlas."
    )
    return f"**{decision}.** {reason}\n\n{recommendation}"


def _num(value: float | None) -> str:
    if value is None:
        return "not estimable"
    return f"{value:.4g}"


def _group(
    groups: Sequence[SignalGroup],
    signal: str,
    geography_type: str,
    geography_id: str,
) -> SignalGroup | None:
    for group in groups:
        if (
            group.signal == signal
            and group.geography_type == geography_type
            and group.geography_id == geography_id
        ):
            return group
    return None
