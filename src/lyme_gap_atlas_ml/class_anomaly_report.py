"""Results narrative for issue 122.

The comment and the EDA record may name counties. Chart text is not built here.
"""

from __future__ import annotations

from collections.abc import Mapping

from lyme_gap_atlas_ml.class_anomaly import (
    EXPECTED_CLASS_N,
    EXPECTED_DOUBLE_GAP_N,
    EXPECTED_GAP_810_N,
    SPEC_ID,
    FitResult,
    ScoredCounty,
)
from lyme_gap_atlas_ml.coverage_audit import (
    PINNED_RELEASE_ID,
    REFERENCE_COUNTIES,
    REFERENCE_NO_COUNTY_LINKED_RECORD,
    REFERENCE_PUBLISHED_HUMAN_FLOOR,
)

_FORBIDDEN = ("hot spot", "hotspot", "incidence", "higher risk", "causation", "causal")


def render_comment(
    result: FitResult,
    *,
    run_id: str,
    git_commit: str,
    row_counts: Mapping[str, int],
    drive_links: tuple[tuple[str, str], ...],
    missing_charts: tuple[str, ...],
    prior_artifact_note: str,
) -> str:
    """Seven-section comment shared by the issue and the pull request."""
    sections = (
        ("Question", _question()),
        ("Method", _method(result)),
        ("Key findings", _findings(result)),
        ("Caveats", _caveats(result)),
        ("Disposition", _disposition(result)),
        (
            "Artifacts",
            _artifacts(run_id, row_counts, drive_links, missing_charts, prior_artifact_note),
        ),
        ("Reproducibility", _reproducibility(run_id, git_commit)),
    )
    blocks = [
        f"{index}. {title}\n\n{body}" for index, (title, body) in enumerate(sections, start=1)
    ]
    text = "\n\n".join(blocks)
    _reject_forbidden(text)
    return text + "\n"


def render_eda_record(
    result: FitResult,
    *,
    run_id: str,
    git_commit: str,
    row_counts: Mapping[str, int],
    drive_links: tuple[tuple[str, str], ...],
    missing_charts: tuple[str, ...],
) -> str:
    """Template-shaped EDA record. The county table matches the comment."""
    issue = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues"
    text = "\n".join(
        [
            "# 122: Which established-tick counties are unusual for their class?",
            "",
            (
                f"- Issue: [ML #122]({issue}/122), part of [ML #22]({issue}/22). "
                f"Spec: [{SPEC_ID}](122-analysis-spec.md)."
            ),
            (
                "- Data: `ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V` "
                f"and `CURRENT_RELEASE_V`. Pinned release `{PINNED_RELEASE_ID}`."
            ),
            (
                "- Cohort: counties with aggregate tick status Established. "
                f"Expected class size {EXPECTED_CLASS_N}. Observed class size {result.n_class}. "
                f"Fit rows {result.n_fit}."
            ),
            "",
            "## Method and assumptions",
            "",
            _method(result),
            "",
            "## Material findings and limits",
            "",
            _findings(result),
            "",
            _caveats(result),
            "",
            "## Decision",
            "",
            _disposition(result),
            "",
            "## Reproduction and retained evidence",
            "",
            _reproducibility(run_id, git_commit),
            "",
            _artifacts(run_id, row_counts, drive_links, missing_charts, ""),
            "",
            "County scores, including names, stay in `EDA.COUNTY_ANOMALY_SCORES_122`.",
            "Charts and Drive files are aggregate figures and do not name counties.",
            "A full county extract was not committed.",
            "",
        ]
    )
    _reject_forbidden(text)
    return text


def _question() -> str:
    return (
        "Inside the established-tick class, which counties are unusual on log population, "
        "social-vulnerability percentile, uninsured percentile, or rural-urban code, and is "
        "each unusual county unusual because of size, vulnerability, insurance, or rurality? "
        "An anomaly score is a data-quality review flag. It is not a disease burden, a "
        "priority for a visit, or a training label."
    )


def _method(result: FitResult) -> str:
    dropped = ", ".join(result.features_dropped) if result.features_dropped else "none"
    scaled = ", ".join(result.scaled_columns) if result.scaled_columns else "none"
    return (
        f"Spec [{SPEC_ID}](122-analysis-spec.md), frozen before the fit. Class rule: "
        f"`TICK_STATUS = Established`. Features kept: {', '.join(result.features_kept)}. "
        f"Dropped constant features: {dropped}. Percentile columns divided by 100: {scaled}. "
        "Population enters as a natural log. The robust z-score flags a county whose largest "
        "absolute z exceeds 3.5. The robust-covariance distance uses MinCovDet with support "
        "fraction 0.8 and the chi-square 0.975 cutoff. The isolation forest uses 200 trees, "
        "seeds 1222026 and 1222027, and contamination 0.02, 0.05, and 0.10. The primary "
        "screen is seed 1222026 at contamination 0.05. The forest adds a distinct set only "
        "when the seed Jaccard is at least 0.90 and both matched-count Jaccards are below 0.80. "
        "The dominant feature is the largest absolute robust z, labeled joint below 2.5 and "
        "tie when the top two match. Intervals are state-cluster bootstrap percentiles, "
        "400 draws, seed 1222026."
    )


def _findings(result: FitResult) -> str:
    primary = result.flag_counts["if_primary"]
    rate = primary / result.n_fit if result.n_fit else 0.0
    interval = _interval(result.flag_rate_interval)
    overlap_rate = primary and result.overlap_primary_228 / primary
    gap_sentence = (
        f"The double-gap predicate on published columns is {result.double_gap_n}, "
        f"matching the epic reference {EXPECTED_DOUBLE_GAP_N}."
        if result.double_gap_reproduced
        else (
            f"The double-gap predicate on published columns is {result.double_gap_n}, "
            f"not the epic reference {EXPECTED_DOUBLE_GAP_N}. The wider gap predicate is "
            f"{result.gap_810_n} (epic reference {EXPECTED_GAP_810_N})."
        )
    )
    forest = (
        "The forest flags a different matched-count set than both baselines, and the seeds agree."
        if result.forest_adds
        else "The forest does not add a distinct review set beyond the robust baselines."
    )
    lines = [
        (
            f"Epic #22 section 4.1 recorded  {REFERENCE_COUNTIES} counties, "
            f"{REFERENCE_PUBLISHED_HUMAN_FLOOR} with a published 2023 human floor, and "
            f"{REFERENCE_NO_COUNTY_LINKED_RECORD} with no county-linked human record. "
            "It did not record an isolation-forest flag count, so there is no October 13 "
            "flag rate to match. The same section names the 228-county established-tick / "
            "pathogen-documented / no-human-floor gap. Section 5.1 names that gap and the "
            f"810-county established-tick / no-human-floor list. This class has {result.n_class} "
            f"counties and {result.n_fit} complete feature rows. {gap_sentence}"
        ),
        (
            f"Robust z flags {result.flag_counts['robust_z']} counties. "
            f"Robust distance flags {result.flag_counts['mahalanobis']} "
            f"({'distance fit failed' if not result.mcd_ok else 'distance fit succeeded'}). "
            f"Primary forest flags {primary} ({rate:.3f}{interval}). "
            f"The other seed at the same contamination flags {result.flag_counts['if_seed_b']}. "
            f"Contamination 0.02 and 0.10 on the primary seed flag "
            f"{result.flag_counts['if_c02']} and {result.flag_counts['if_c10']}. "
            f"The second seed flags {result.flag_counts['if_b_c02']} and "
            f"{result.flag_counts['if_b_c10']} at those settings. "
            f"Seed Jaccard is {result.seed_jaccard:.3f}. "
            f"Matched-count Jaccard versus robust z is {result.matched_jaccard_robust_z:.3f} "
            f"and versus robust distance is {result.matched_jaccard_mcd:.3f}. {forest}"
        ),
        (
            f"Primary flags inside the double-gap predicate: {result.overlap_primary_228} "
            f"({overlap_rate:.3f} of primary flags){_interval(result.overlap_interval)}. "
            f"Primary flags inside the wider gap: {result.overlap_primary_810}. "
            f"Robust-z flags inside the double-gap predicate: {result.robust_z_in_228}. "
            f"Robust-distance flags inside it: {result.mcd_in_228}."
        ),
        _drivers(result),
        (
            f"Within-class median population is {result.population_median:,.0f}. "
            "Modeled feature medians: "
            + ", ".join(
                f"{name} {value:.3f}" for name, value in sorted(result.feature_medians.items())
            )
            + ". These are class location summaries, not a comparison that changes the flag rule."
        ),
        _county_section(
            "Primary forest review list",
            result.review,
            result.flag_counts["if_primary"],
        ),
        _county_section(
            "Robust z flags the forest does not",
            result.baseline_only_z,
            None,
        ),
        _county_section(
            "Robust distance flags the forest does not",
            result.baseline_only_mcd,
            None,
        ),
        _exclusions(result),
    ]
    return "\n\n".join(lines)


def _drivers(result: FitResult) -> str:
    parts = []
    for method, counts in result.driver_counts.items():
        total = sum(counts.values())
        if total == 0:
            parts.append(f"{method}: no flags")
            continue
        detail = ", ".join(
            f"{feature} {count} ({count / total:.3f})" for feature, count in sorted(counts.items())
        )
        parts.append(f"{method}: {detail}")
    return (
        "Share of flagged counties whose largest absolute robust z is each feature "
        "(joint means no feature reaches 2.5; tie means the top two match): "
        + "; ".join(parts)
        + "."
    )


def _county_section(title: str, rows: tuple[ScoredCounty, ...], full_count: int | None) -> str:
    if not rows:
        return f"{title}: none."
    note = ""
    if full_count is not None and full_count != len(rows):
        note = f" Showing {len(rows)} of {full_count}, highest primary score first."
    header = (
        "| County | State | FIPS | Population | SVI percentile | Uninsured percentile | "
        "RUCC | Human status | Pathogen status | Dominant feature | Max abs z | "
        "Distance squared | Forest score | Robust z flag | Distance flag | Double gap | Wider gap |"
    )
    divider = (
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- "
        "| ---: | ---: | ---: | --- | --- | --- | --- |"
    )
    body = "\n".join(_county_line(row) for row in rows)
    return f"{title}.{note}\n\n{header}\n{divider}\n{body}"


def _county_line(row: ScoredCounty) -> str:
    distance = "" if row.mahalanobis_squared is None else f"{row.mahalanobis_squared:.2f}"
    return (
        f"| {_cell(row.county_name)} | {row.state} | {row.fips} | {row.population:,.0f} | "
        f"{row.svi_percentile:.3f} | {row.uninsured_percentile:.3f} | {row.rucc} | "
        f"{_status_label(row.human_status)} | {_status_label(row.burgdorferi_status)} | "
        f"{row.dominant_feature} | {row.robust_z_max_abs:.2f} | {distance} | "
        f"{row.if_score_primary:.3f} | {_yes(row.flag_robust_z)} | {_yes(row.flag_mahalanobis)} | "
        f"{_yes(row.in_double_gap)} | {_yes(row.in_gap_810)} |"
    )


def _exclusions(result: FitResult) -> str:
    if not result.exclusions:
        return (
            "Data-quality exclusions before the fit: 0. No class row was dropped for a null "
            "feature, a nonpositive population, or a rural-urban code outside 1 through 9."
        )
    shown = result.exclusions[:40]
    lines = "\n".join(
        f"- {_cell(row.county_name)}, {row.state}, {row.fips}: {row.reason}" for row in shown
    )
    extra = ""
    if len(result.exclusions) > len(shown):
        extra = (
            f"\n\n{len(result.exclusions) - len(shown)} further exclusions are counted "
            "and are not stored as anomaly scores."
        )
    return (
        f"Data-quality exclusions before the fit: {len(result.exclusions)}. "
        "These rows are not anomaly flags.\n\n" + lines + extra
    )


def _caveats(result: FitResult) -> str:
    return (
        "Counties in a state share reporting rules, so the bootstrap resamples states. "
        "The interval is a resampling range. Population, vulnerability, insurance, "
        "and the rural-urban code are not the same vintage as tick status. "
        "A missing human floor is not zero. "
        "`No records` and `Unknown` are not negatives. A published human count is a lower bound. "
        f"MinCovDet status: {'succeeded' if result.mcd_ok else 'failed'}. "
        "The score is not a map label and not an input to the Tier 1 model."
    )


def _disposition(result: FitResult) -> str:
    advice = {
        "keep": (
            "Keep the screen as a data-quality review flag. Do not build a disease model next. "
            "The forest does not add a separate list, so a later ranking, if one is authorized, "
            "can carry the robust distance as one review column."
        ),
        "follow-up": (
            "Follow up with a reviewer on the named list. Do not build a disease model next. "
            "Either the forest disagrees with both baselines or one feature drives most flags, "
            "so the list needs a person to decide whether the oddity is a data problem."
        ),
        "revise": (
            "Revise before anyone uses the list. A data-quality exclusion, a double-gap count "
            "that does not match 228, a failed distance fit, or an unstable forest seed is "
            "enough to hold the screen. Do not build a model on this fit."
        ),
        "stop": "Stop. The predeclared class or release gate did not hold. Do not build a model.",
    }[result.disposition]
    return (
        f"{result.disposition}. {advice} A code-only slice, if a later review column is "
        "authorized, is log population and the rural-urban code. A protected slice is the "
        "social-vulnerability percentile and the uninsured percentile. That pair can explain "
        "why a county was flagged. It is not an outreach rank."
    )


def _artifacts(
    run_id: str,
    row_counts: Mapping[str, int],
    drive_links: tuple[tuple[str, str], ...],
    missing_charts: tuple[str, ...],
    prior_artifact_note: str,
) -> str:
    counts = ", ".join(f"`{name}` {count}" for name, count in row_counts.items()) or "none yet"
    links = (
        ", ".join(f"[{name}]({url})" for name, url in drive_links)
        if drive_links
        else "no Drive chart link"
    )
    missing = ", ".join(missing_charts) if missing_charts else "none"
    prior = f" {prior_artifact_note}" if prior_artifact_note else ""
    return (
        f"Run id `{run_id}`. Lab row counts: {counts}. Drive charts: {links}. "
        f"Missing charts: {missing}. EDA record: `docs/eda/122-established-class-anomaly.md`. "
        f"Spec: `docs/eda/122-analysis-spec.md`.{prior}"
    )


def _reproducibility(run_id: str, git_commit: str) -> str:
    return (
        f"Commit `{git_commit}`. Release `{PINNED_RELEASE_ID}`. Seeds 1222026 and 1222027. "
        f"Run id `{run_id}`.\n\n"
        "```text\n"
        "uv sync --locked --extra dev --extra snowflake\n"
        "uv run python scripts/check_ml_agent_context.py\n"
        "MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
        "python scripts/eda_122_class_anomaly.py\n"
        "uv run python scripts/verify.py\n"
        "```"
    )


def _interval(interval: tuple[float, float] | None) -> str:
    if interval is None:
        return ""
    return f", state-cluster interval {interval[0]:.3f} to {interval[1]:.3f}"


def _status_label(value: str) -> str:
    labels = {
        "published_count_floor": "published count floor",
        "no_county_linked_record": "no county-linked human record",
        "Present": "pathogen present",
        "No records": "no pathogen record",
        "Unknown": "unknown",
        "Established": "established",
    }
    return labels.get(value, value)


def _yes(value: bool) -> str:
    return "yes" if value else "no"


def _cell(value: str) -> str:
    return value.replace("|", "/")


def _reject_forbidden(text: str) -> None:
    lowered = text.lower()
    for phrase in _FORBIDDEN:
        if phrase in lowered:
            raise ValueError(f"narrative contains a forbidden phrase: {phrase}")
