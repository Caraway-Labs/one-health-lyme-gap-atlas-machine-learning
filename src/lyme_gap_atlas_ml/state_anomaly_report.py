"""Results narrative for issue 106.

The comment and the EDA record may name counties. Chart text is not built here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from lyme_gap_atlas_ml.class_anomaly import sklearn_version
from lyme_gap_atlas_ml.coverage_audit import PINNED_RELEASE_ID
from lyme_gap_atlas_ml.state_anomaly import SPEC_ID, FitResult, ScoredCounty

ISSUE = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues"


def render_comment(
    result: FitResult,
    *,
    run_id: str,
    git_commit: str,
    row_counts: Mapping[str, int],
    drive_links: Sequence[tuple[str, str]],
    missing_charts: Sequence[str],
    skipped_charts: Sequence[str],
) -> str:
    """Seven-section comment shared by the issue and the pull request."""
    sections = (
        ("Question", _question()),
        ("Method", _method(result)),
        ("Key findings", _findings(result)),
        ("Caveats", _caveats(result)),
        ("Disposition", _disposition(result)),
        ("Artifacts", _artifacts(run_id, row_counts, drive_links, missing_charts, skipped_charts)),
        ("Reproducibility", _reproducibility(git_commit)),
    )
    blocks = [
        f"{index}. {title}\n\n{body}" for index, (title, body) in enumerate(sections, start=1)
    ]
    return "\n\n".join(blocks) + "\n"


def render_eda_record(
    result: FitResult,
    *,
    run_id: str,
    git_commit: str,
    row_counts: Mapping[str, int],
    drive_links: Sequence[tuple[str, str]],
    missing_charts: Sequence[str],
    skipped_charts: Sequence[str],
) -> str:
    """Template-shaped EDA record."""
    return "\n".join(
        [
            "# 106: Which counties are unusual compared with peers in the same state?",
            "",
            (
                f"- Issue: [ML #106]({ISSUE}/106), part of [ML #22]({ISSUE}/22). "
                f"Spec: [{SPEC_ID}](106-analysis-spec.md)."
            ),
            (
                "- Data: `ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V`, "
                "`CURRENT_RELEASE_V`, and `CURRENT_SOURCE_METADATA_V`. "
                f"Pinned release `{PINNED_RELEASE_ID}`."
            ),
            (
                f"- Cohort: one county row on that release. Rows read {result.n_rows}. "
                f"Complete feature rows {result.n_fit}. Exclusions {result.exclusions}."
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
            _reproducibility(git_commit),
            "",
            _artifacts(run_id, row_counts, drive_links, missing_charts, skipped_charts),
            "",
            (
                "County scores, including names, stay in `EDA.COUNTY_STATE_ANOMALY_106`. "
                "Charts and Drive files are aggregate figures and do not name counties. "
                "A full county extract was not committed."
            ),
            "",
        ]
    )


def _question() -> str:
    return (
        "Which counties are unusual compared with peers inside the same state, and does a "
        "state-relative baseline make statistical sense given small and uneven state sample "
        "sizes? The answer is a surveillance-review flag kept separate from the HIGH, MEDIUM, "
        "and LOW tiers. It is not incidence, risk, causation, or a hot spot."
    )


def _method(result: FitResult) -> str:
    scaled = ", ".join(result.scaled_columns) if result.scaled_columns else "none"
    return (
        f"Spec [{SPEC_ID}](106-analysis-spec.md), frozen before the fit. "
        "Continuous features are log population, SVI percentile, uninsured percentile, and "
        f"rural-urban code. Percentile columns divided by 100: {scaled}. "
        "A state with at least 40 counties uses its own median and MAD. A state with 15 to 39 "
        "counties keeps the state median and shrinks the scale toward the leave-state-out "
        "Census region. A state with fewer than 15 counties uses a Census-region by tick-status "
        "class when that cell has at least 40 counties, and otherwise the Census region. "
        "The robust-z flag is a largest absolute z above 3.5. "
        "Percentile tails and robust-covariance distance are fit only for peer groups of at "
        "least 40 counties. Surveillance status uses a minority rule, not MAD, because a 0/1 "
        "status has no robust scale unless the split is exactly even. "
        "Isolation forest and local outlier factor run only in states with at least 80 counties. "
        f"Seeds 1062026 and 1062027. scikit-learn {sklearn_version()}. "
        "Temporal detection was not fit: the pinned release is one row per county."
    )


def _findings(result: FitResult) -> str:
    shift = (
        "not estimable"
        if result.median_abs_rank_shift is None
        else f"{result.median_abs_rank_shift:.1f}"
    )
    spearman = "not estimable" if result.spearman is None else f"{result.spearman:.3f}"
    interval = "not estimable"
    if result.flag_rate_interval is not None and result.flag_z_state >= 11:
        low, high = result.flag_rate_interval
        interval = f"{low:.3f} to {high:.3f}"
    lines = [
        (
            "Epic #22 section 4.1 recorded 3,144 counties, 651 with a published 2023 human floor, "
            "and 2,493 with no county-linked human record. This release matches those three "
            "counts and the 228-county established-tick / pathogen-present / no-human-floor gap. "
            "Section 4.1 did not record a state-relative anomaly count. The October 13 release id "
            "was `governed-2026-10-06-nlcd-demo-cohort`. This fit uses "
            f"`{PINNED_RELEASE_ID}`. #109 already showed the headline counts did not move."
        ),
        (
            f"State-relative robust z flags {result.flag_z_state} counties. "
            f"National robust z flags {result.flag_z_national}. "
            f"Jaccard {result.jaccard_national:.3f}. "
            f"Median absolute rank shift on the union {shift}. "
            f"Spearman of the two max absolute z values {spearman}. "
            f"State-cluster interval for the state-relative flag rate: {interval}."
        ),
        _safeguard_line(result),
        _detector_line(result),
        _band_line(result),
        _user_line(result),
        _table("State-relative robust-z review list", result.review),
        _table(
            "Flagged by the state-relative rule and not by the national rule", result.state_only
        ),
        _table(
            "Flagged by the national rule and not by the state-relative rule", result.national_only
        ),
        _surveillance_table(result),
    ]
    return "\n\n".join(lines)


def _safeguard_line(result: FitResult) -> str:
    if (
        result.flag_z_state >= 11
        and not (0 < result.small_flag_n < 11)
        and result.small_share is not None
    ):
        small = (
            f"{result.small_flag_n} state-relative flags "
            f"({result.small_share:.3f}) come from states with fewer than 40 counties. "
            f"Flags from states with fewer than 15 counties: {result.fallback_flag_n}."
        )
    elif result.small_flag_n == 0 and result.flag_z_state >= 11:
        small = "No state-relative flag comes from a state with fewer than 40 counties."
    else:
        small = (
            "The small-state share of the flag list is withheld here when the count is under 11, "
            "and is named in this write-up only when it is 0 or at least 11."
        )
        if result.flag_z_state >= 11 and result.small_flag_n == 0:
            small = "No state-relative flag comes from a state with fewer than 40 counties."
        elif result.small_flag_n:
            small = (
                f"State-relative flags from states under 40 counties: {result.small_flag_n}. "
                f"Flags from states under 15 counties: {result.fallback_flag_n}."
            )
    if result.urban_comparable and result.urban_gap is not None:
        urban = (
            f"Metro counties (rural-urban code 1 to 3) are {result.flag_metro_n} of the "
            f"state-relative flags and {result.cohort_metro_n} of the fit cohort. "
            f"The share gap is {result.urban_gap:.3f}."
        )
    else:
        urban = "The metro split of the flag list is not publishable as an aggregate."
    return f"{small} {urban}"


def _detector_line(result: FitResult) -> str:
    forest = "defensible" if result.forest_defensible else "not defensible"
    lof = "defensible" if result.lof_defensible else "not defensible"
    return (
        f"States eligible for a detector (at least 80 counties): {result.forest_eligible_states}. "
        f"States whose isolation-forest seeds both flag someone and agree at Jaccard 0.90 or "
        f"better: {result.forest_stable_states}. The forest is {forest} under the frozen bar. "
        f"Local outlier factor is {lof}. "
        "A miss does not by itself change the baseline disposition. "
        f"Robust distance failed in {result.mcd_failure_n} of {result.mcd_native_n} "
        "state-native states."
    )


def _band_line(result: FitResult) -> str:
    parts = []
    for band in ("fallback", "shrunk", "state_native"):
        states = result.band_state_counts.get(band, 0)
        counties = result.band_county_counts.get(band, 0)
        parts.append(f"{band} {states} states and {counties} counties")
    return "Peer bands: " + "; ".join(parts) + "."


def _user_line(result: FitResult) -> str:
    if not result.review:
        return (
            "What a user would see: no state-relative robust-z flag, so there is no county "
            "sentence to show. The exploratory signal stays separate from the tiers."
        )
    county = result.review[0]
    return (
        "What a user would see, for the first listed flag, as an exploratory sentence and not "
        "as a shipped screen: "
        f"Exploratory state-relative signal, separate from the HIGH, MEDIUM, and LOW tiers. "
        f"{county.county_name}, {county.state}, is unusual compared with {county.peer_label} "
        f"(n={county.peer_n}) because {county.reason} "
        "This is a surveillance-review flag. It is not a tier, an incidence, a risk, or a hot spot."
    )


def _table(title: str, rows: Sequence[ScoredCounty]) -> str:
    if not rows:
        return f"{title}: none."
    header = (
        f"{title}. {len(rows)} rows shown.\n\n"
        "| County | State | FIPS | Peer | Peer n | Population | SVI | Uninsured | RUCC | "
        "Dominant | State z | National z | State flag | National flag | Reason |\n"
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | "
        "--- | --- | --- |"
    )
    body = "\n".join(_row(row) for row in rows)
    return f"{header}\n{body}"


def _row(row: ScoredCounty) -> str:
    state_z = "na" if not _finite(row.max_abs_z_state) else f"{row.max_abs_z_state:.2f}"
    national_z = "na" if not _finite(row.max_abs_z_national) else f"{row.max_abs_z_national:.2f}"
    return (
        f"| {row.county_name} | {row.state} | {row.fips} | {row.peer_rule} | {row.peer_n} | "
        f"{row.population:,.0f} | {row.svi_percentile:.3f} | {row.uninsured_percentile:.3f} | "
        f"{row.rucc} | {row.dominant_feature} | {state_z} | {national_z} | "
        f"{_yes(row.flag_z_state)} | {_yes(row.flag_z_national)} | {row.reason} |"
    )


def _surveillance_table(result: FitResult) -> str:
    flagged = sum(1 for row in result.counties if row.flag_surveillance)
    national = sum(1 for row in result.counties if row.flag_surveillance_national)
    intro = (
        f"Surveillance-status minority rule flags {flagged} counties inside their peer group "
        f"and {national} counties under the same rule fit nationally. "
        "That rule is not part of the robust-z disposition."
    )
    return intro + "\n\n" + _table("Surveillance-status review list", result.surveillance_review)


def _caveats(result: FitResult) -> str:
    return (
        "Scores are surveillance-review flags. They are not incidence, risk, causation, or "
        "hot spots. "
        "`No records` and `Unknown` are not negatives. A missing human floor is not zero. "
        "A published human count is a lower bound. Counties in one state share reporting rules, "
        "so the interval resamples states. Population, vulnerability, insurance, rural-urban code, "
        "the 2023 human year, and cumulative tick and pathogen status are not one time base. "
        "Temporal detection is not feasible on this single snapshot and was not fit. "
        "Historical CDC objects were not read. "
        f"Exclusions before the fit: {result.exclusions}. "
        "No tier, Tier 1 model, PROD batch, or API field changes."
    )


def _disposition(result: FitResult) -> str:
    call = result.disposition
    paragraph = {
        "proceed": (
            "Proceed with a follow-on design for the interpretable state-relative baseline only. "
            "Do not change the tiers. Isolation forest and local outlier factor stay out of that "
            "follow-on unless the frozen detector bar was met."
        ),
        "revise": (
            "Revise the peer rule or the screen before anyone uses a list. The frozen safeguards "
            "fired, or a data-quality exclusion appeared. Do not build a model on this fit."
        ),
        "defer": (
            "Defer a state-relative product signal. The baseline does not add a distinct, "
            "stable review list under the frozen rule, or the national and state-relative lists "
            "are too similar to justify a second screen."
        ),
        "stop": "Stop. A predeclared gate failed.",
    }[call]
    met = [
        name
        for name, ok in (
            ("isolation forest", result.forest_defensible),
            ("local outlier factor", result.lof_defensible),
        )
        if ok
    ]
    if met:
        detector = (
            "The detector bar was met for "
            + " and ".join(met)
            + ", so a later story could test that method again."
        )
    else:
        detector = (
            "The detector bar was missed, so the follow-on does not include isolation forest "
            "or local outlier factor."
        )
    outlines = ""
    if call == "proceed":
        outlines = "\n\n" + _outlines(result)
    return (
        f"{call}. {paragraph} {detector} "
        "A code-only slice, if a later review column is authorized, is log population and the "
        "rural-urban code. A protected slice is the social-vulnerability percentile and the "
        "uninsured percentile. Surveillance status is a third slice. It can explain a pattern. "
        "It is not an outreach rank." + outlines
    )


def _outlines(result: FitResult) -> str:
    lines = [
        "Proposed follow-on outlines under #22. These are not opened as issues.",
        "",
        (
            "1. Code-only. Question: which counties are unusual for their state on size and "
            "rural-urban code, as a review flag beside the tiers? Model family: within-peer "
            "median and MAD robust z, with the frozen shrinkage and region or class fallback. "
            "Baseline: the national robust z on the same two features. Evaluation: Jaccard, "
            "median absolute rank shift, small-state share, and a state-cluster bootstrap. "
            "Persistence: ML Lab score table only. Not PROD and not the tier batch."
        ),
        (
            "2. Protected. Question: does adding SVI and uninsured percentiles change the "
            "explanation of a code-only flag, without using them as an outreach rank? "
            "Model family: the same robust z, explanation only. Baseline: the code-only flag "
            "set. Evaluation: share of flags whose dominant feature is one of those two "
            "percentiles. Persistence: separate lab columns. Not an API field."
        ),
    ]
    if result.lof_defensible:
        lines.append(
            "3. Local outlier factor, because the frozen bar was met. Question: which counties "
            "in states of at least 80 are density outliers relative to state peers, as a review "
            "flag beside the robust-z list? Model family: local outlier factor, 20 neighbors, "
            "contamination 0.05. Baseline: the state-relative robust z, compared by matched-count "
            "Jaccard. Evaluation: nested contamination stability at 0.90 and a state-cluster "
            "bootstrap of the flag rate. Persistence: ML Lab score columns only. Not PROD and not "
            "the tier batch. Isolation forest stays out: its seed bar was not met."
        )
    if result.forest_defensible:
        lines.append(
            "Isolation forest, because the frozen seed bar was met. Question: which counties in "
            "states of at least 80 are isolated from state peers on the continuous features? "
            "Model family: isolation forest, 200 trees, contamination 0.05, two seeds. Baseline: "
            "state-relative robust z. Evaluation: seed Jaccard at 0.90 and matched-count Jaccard. "
            "Persistence: ML Lab score columns only. Not PROD and not the tier batch."
        )
    return "\n".join(lines)


def _artifacts(
    run_id: str,
    row_counts: Mapping[str, int],
    drive_links: Sequence[tuple[str, str]],
    missing_charts: Sequence[str],
    skipped_charts: Sequence[str],
) -> str:
    counts = ", ".join(f"`{name}` {count}" for name, count in row_counts.items()) or "none"
    links = ", ".join(f"[{name}]({url})" for name, url in drive_links) or "none"
    missing = ", ".join(missing_charts) or "none"
    skipped = ", ".join(skipped_charts) or "none"
    return (
        f"Run id `{run_id}`. Lab row counts: {counts}. Drive charts: {links}. "
        f"Upload failures: {missing}. Charts skipped for small-cell protection: {skipped}. "
        "EDA record: `docs/eda/106-state-relative-anomaly.md`. "
        "Spec: `docs/eda/106-analysis-spec.md`. "
        "The shared lab writers do not grant SELECT. `OH_LYME_PROD_READ` cannot count "
        "`EDA.COUNTY_STATE_ANOMALY_106` until an owner grants it."
    )


def _reproducibility(git_commit: str) -> str:
    return (
        f"Commit `{git_commit}`. Release `{PINNED_RELEASE_ID}`. Seeds 1062026 and 1062027.\n\n"
        "```text\n"
        "uv sync --locked --extra dev --extra snowflake\n"
        "uv run python scripts/check_ml_agent_context.py\n"
        "MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
        "python scripts/eda_106_state_anomaly.py\n"
        "uv run python scripts/verify.py\n"
        "```"
    )


def _yes(flag: bool) -> str:
    if flag:
        return "yes"
    return "no"


def _finite(value: float) -> bool:
    return value == value and value not in {float("inf"), float("-inf")}
