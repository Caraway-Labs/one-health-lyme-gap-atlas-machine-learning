"""Markdown write-up for issue 123. The lab table suppresses small-state shares."""

from __future__ import annotations

import statistics
from collections.abc import Mapping, Sequence

from lyme_gap_atlas_ml.coverage_audit import PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.state_regimes import (
    EXPECTED_STATES,
    EXPECTED_ZERO_COUNTIES,
    EXPECTED_ZERO_STATES,
    SEED_DESCRIPTIVE,
    SEED_PUBLICATION_FREE,
    SMALL_CELL,
    SPEC_ID,
    Analysis,
    ProfileFit,
    StateProfile,
    feature_sentence,
)

DOC_PATH = "docs/eda/123-state-reporting-regimes.md"
SPEC_PATH = "docs/eda/123-analysis-spec.md"


def render_eda_record(
    analysis: Analysis,
    *,
    run_id: str,
    commit: str,
    counts: Mapping[str, int],
    drive_lines: str,
    grant: str,
) -> str:
    """Template header plus the issue comment sections."""
    header = "\n".join(
        (
            "# 123: Which state reporting regimes resemble each other?",
            "",
            "- Issue: [#123](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/123); parent epic [#118](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/118); program epic [#22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22).",  # noqa: E501
            f"- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`. Release `{PINNED_RELEASE_ID}`.",  # noqa: E501
            "- Cohort: 3,144 counties rolled to 51 state rows, including the District of Columbia. One snapshot.",  # noqa: E501
            "",
            "## Method and assumptions",
            "",
            f"Spec [{SPEC_ID}]({SPEC_PATH}), frozen before the fit. {feature_sentence(analysis.decision)}",  # noqa: E501
            "",
            "## Material findings and limits",
            "",
            render_comment(
                analysis,
                run_id=run_id,
                commit=commit,
                counts=counts,
                drive_lines=drive_lines,
                grant=grant,
            ),
            "",
            "## Decision",
            "",
            (
                f"{analysis.decision.method.upper()} for the clustering method. "
                f"{analysis.decision.product.upper()} for product value. "
                "This is not a release, a tier change, or a production score."
            ),
            "",
            "## Reproduction and retained evidence",
            "",
            f"- Fit commit `{commit}`, run `{run_id}`, release `{PINNED_RELEASE_ID}`.",
            "- Entry points: `sql/validation/123_state_regimes.sql`, `scripts/eda_123_state_regimes.py`, `src/lyme_gap_atlas_ml/state_regimes.py`.",  # noqa: E501
            "- Commands: see the reproducibility section above.",
            "- Transient artifacts not committed: chart PNGs under ignored `artifacts/charts/123/`. No county extract.",  # noqa: E501
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
    drive_lines: str,
    grant: str,
) -> str:
    """The seven sections shared by the issue comment and the pull request."""
    sections = (
        _question(analysis),
        _method(),
        _findings(analysis),
        _caveats(analysis),
        _disposition(analysis),
        _artifacts(run_id, counts, drive_lines, grant),
        _reproduction(commit),
    )
    return "\n\n".join(sections)


def _question(analysis: Analysis) -> str:
    questions = analysis.questions
    high_group = _group_text(questions.northeast_high_group)
    zero_group = _group_text(questions.zero_published_group)
    high_names = ", ".join(questions.northeast_high_states) or "none"
    zero_lines = _zero_lines(analysis)
    return "\n".join(
        (
            "1. Question",
            "",
            "Which states resemble each other in publication, tick documentation, and pathogen documentation? Which descriptive group contains the high-publication Northeast states, and which contains states with no published county floor? After publication rate is removed, which states still look alike on tick coverage, pathogen coverage, and rural mix? Which profile may a later county model use?",  # noqa: E501
            "",
            f"High-publication Census Northeast states, defined before the fit as a published-floor share of at least 0.5, are {high_names}. The descriptive group with the most of them is {high_group}.",  # noqa: E501
            "",
            f"The descriptive group with the most states that have no published county floor is {zero_group}. Every such state stays in the partition, and its stored median is missing:",  # noqa: E501
            "",
            zero_lines,
            "",
            feature_sentence(analysis.decision),
        )
    )


def _method() -> str:
    return "\n".join(
        (
            "2. Method (and why; link the spec)",
            "",
            f"Spec [{SPEC_ID}]({SPEC_PATH}), frozen before the fit. The 51 state rows are clustered with Ward linkage and Euclidean distance after `StandardScaler`, the same linkage class, scaler, silhouette, and adjusted Rand index #110 uses. The #116 `resample_interval` supplies the 2,000-draw bootstrap. The cut is the admissible k in 2 through 6 with the highest silhouette, with leave-one-state-out and the bootstrap as the stability evidence. Average linkage, complete linkage, and a descriptive fit that drops the median columns are recorded and do not choose the cut.",  # noqa: E501
            "",
            "A state with no published floor keeps a missing median. The descriptive distance uses an observation indicator plus a median coordinate that is 0 only because that indicator is 0. The stored median is never filled with zero. The publication-free profile is the established-tick share, the pathogen-present share, and the nonmetropolitan share (`RUCC_2023` 4 through 9, the #116 split). It does not include the publication share or the published floor.",  # noqa: E501
            "",
            "#109 supplies the status definitions: a published floor is `published_count_floor`, an established tick is `Established`, and a pathogen record is `Present`. `No records` and `Unknown` stay in the denominator. #107 supplies the comparison of 19 states and 1,437 counties with no published county floor.",  # noqa: E501
        )
    )


def _findings(analysis: Analysis) -> str:
    lines = [
        "3. Key findings with numbers",
        "",
        _profile_line(analysis.descriptive),
        "",
        _profile_line(analysis.publication_free),
        "",
        (
            f"Cross-profile adjusted Rand index: {analysis.cross_ari:.4f}. "
            f"Zero-published states: {analysis.zero_states} "
            f"(#107 comparison {EXPECTED_ZERO_STATES}). "
            f"Counties in those states: {analysis.zero_counties} "
            f"(#107 comparison {EXPECTED_ZERO_COUNTIES}). "
            f"Comparison matched: {analysis.matches_107}."
        ),
        "",
        "k grid. Admissible means leave-one-state-out median at least 0.70 and bootstrap lower endpoint at least 0.40.",  # noqa: E501
        "",
        _k_table(analysis),
        "",
        "Contingency of state counts, descriptive rows by publication-free columns. This write-up shows every count.",  # noqa: E501
        "",
        _contingency_table(analysis),
        "",
        "Descriptive groups",
        "",
        _group_block(analysis, analysis.descriptive),
        "",
        "Publication-free groups",
        "",
        _group_block(analysis, analysis.publication_free),
        "",
        "State table. Shares are county shares. The median is the published floor rate per 100,000. Missing means the state published no county floor.",  # noqa: E501
        "",
        _state_table(analysis),
    ]
    return "\n".join(lines)


def _caveats(analysis: Analysis) -> str:
    small = [state.state for state in analysis.states if state.county_n < SMALL_CELL]
    small_text = ", ".join(small) if small else "none"
    return "\n".join(
        (
            "4. Caveats",
            "",
            "Counts are surveillance signals and lower bounds. The published floor starts at the CDC floor of 5. It is not incidence, risk, or causation. `No records` and `Unknown` are not negatives. A missing floor is not zero. A group is a partition of reporting regimes, not a risk tier. No production score is published.",  # noqa: E501
            "",
            "Human surveillance is calendar 2023. Tick and pathogen status are cumulative through 2025-12-31. The rural-urban code is 2023. Those windows are not one time base. The bootstrap resamples states and does not cover dependence that crosses a state line.",  # noqa: E501
            "",
            f"States with fewer than 11 counties ({small_text}) stay in both groups. The dendrogram labels them with postal codes and does not print share values. The lab assignment table, other git files, and Drive charts suppress their shares, median, rural share, county count, and zero-published flag. This write-up shows the full state rows.",  # noqa: E501
            "",
            f"Descriptive median contrast: {analysis.descriptive.median_contrast}. A false contrast means the observed medians did not vary, so the median coordinate adds no distance and the indicator still marks states with no median.",  # noqa: E501
        )
    )


def _disposition(analysis: Analysis) -> str:
    reasons = ", ".join(analysis.decision.reasons) if analysis.decision.reasons else "none"
    return "\n".join(
        (
            "5. Disposition",
            "",
            f"Method: {analysis.decision.method}. Product: {analysis.decision.product}.",
            "",
            feature_sentence(analysis.decision),
            "",
            f"Rule failures: {reasons}.",
        )
    )


def _artifacts(run_id: str, counts: Mapping[str, int], drive_lines: str, grant: str) -> str:
    count_text = ", ".join(f"{name}={count}" for name, count in counts.items())
    return "\n".join(
        (
            "6. Artifacts",
            "",
            f"run_id: {run_id}",
            "",
            f"Snowflake row counts: {count_text}.",
            "",
            f"SELECT grant on EDA.STATE_REGIME_GROUPS_123 to OH_LYME_PROD_READ: {grant}.",
            "",
            f"Drive: {drive_lines}",
            "",
            f"Doc: {DOC_PATH}",
            "",
            f"Spec: {SPEC_PATH}",
        )
    )


def _reproduction(commit: str) -> str:
    return "\n".join(
        (
            "7. Reproducibility",
            "",
            f"Commit: {commit}",
            f"Release: {PINNED_RELEASE_ID}",
            f"Bundle SHA-256: {PINNED_BUNDLE_SHA256}",
            f"Seeds: descriptive bootstrap {SEED_DESCRIPTIVE}, publication-free bootstrap {SEED_PUBLICATION_FREE}. Ward has no seed.",  # noqa: E501
            f"State count in the fit: {EXPECTED_STATES}. scikit-learn version is recorded on the run.",  # noqa: E501
            "",
            "```text",
            "uv sync --locked --extra dev --extra snowflake",
            "uv run python scripts/check_ml_agent_context.py",
            "MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_123_state_regimes.py",  # noqa: E501
            "uv run python scripts/verify.py",
            "```",
        )
    )


def _profile_line(profile: ProfileFit) -> str:
    chosen = profile.chosen
    share = "not applicable" if profile.share_only_ari is None else f"{profile.share_only_ari:.4f}"
    low = _num(chosen.bootstrap_low)
    high = _num(chosen.bootstrap_high)
    return (
        f"{profile.name}: k={chosen.k}, cut_stable={profile.cut_stable}, "
        f"silhouette={_num(chosen.silhouette)}, "
        f"leave-one-state-out median={_num(chosen.loso_median)} "
        f"(minimum {_num(chosen.loso_min)}, failures {chosen.loso_failed}), "
        f"bootstrap {low} to {high} "
        f"(estimable {chosen.bootstrap_estimable}, failures {chosen.bootstrap_failed}), "
        f"average-linkage adjusted Rand {profile.average_ari:.4f}, "
        f"complete-linkage adjusted Rand {profile.complete_ari:.4f}, "
        f"share-only adjusted Rand {share}, "
        f"tree adjusted Rand {profile.tree_ari:.4f}."
    )


def _k_table(analysis: Analysis) -> str:
    lines = [
        "| Profile | k | Silhouette | LOSO median | Bootstrap low | Bootstrap high | Admissible | Chosen |",  # noqa: E501
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for profile in (analysis.descriptive, analysis.publication_free):
        for fit in profile.fits:
            lines.append(
                "| "
                + " | ".join(
                    (
                        profile.name,
                        str(fit.k),
                        _num(fit.silhouette),
                        _num(fit.loso_median),
                        _num(fit.bootstrap_low),
                        _num(fit.bootstrap_high),
                        str(fit.admissible),
                        str(fit.k == profile.chosen.k),
                    )
                )
                + " |"
            )
    return "\n".join(lines)


def _contingency_table(analysis: Analysis) -> str:
    header = "| Descriptive group | " + " | ".join(
        f"Publication-free {group}" for group in analysis.publication_free_ids
    )
    divider = "| --- | " + " | ".join("---:" for _ in analysis.publication_free_ids)
    lines = [header + " |", divider + " |"]
    for index, group in enumerate(analysis.descriptive_ids):
        cells = " | ".join(str(value) for value in analysis.contingency[index])
        lines.append(f"| {group} | {cells} |")
    return "\n".join(lines)


def _group_block(analysis: Analysis, profile: ProfileFit) -> str:
    blocks = [
        _one_group(analysis.states, profile.labels, group)
        for group in range(1, profile.chosen.k + 1)
    ]  # noqa: E501
    return "\n\n".join(blocks)


def _one_group(states: Sequence[StateProfile], labels: Sequence[int], group: int) -> str:
    members = [state for state, label in zip(states, labels, strict=True) if label == group]
    names = ", ".join(state.state for state in members)
    publishable = [state for state in members if state.county_n >= SMALL_CELL]
    if len(publishable) < SMALL_CELL:
        numeric = "Numeric summary suppressed because fewer than 11 member states have at least 11 counties."  # noqa: E501
    else:
        floors = [
            state.median_published_floor
            for state in publishable
            if state.median_published_floor is not None
        ]
        floor_text = (
            f"{statistics.median(floors):.2f}" if len(floors) >= SMALL_CELL else "suppressed"
        )
        numeric = (
            "Medians among member states with at least 11 counties: "
            f"published share {statistics.median(state.published_share for state in publishable):.4f}, "  # noqa: E501
            f"established-tick share {statistics.median(state.tick_established_share for state in publishable):.4f}, "  # noqa: E501
            f"pathogen-present share {statistics.median(state.pathogen_present_share for state in publishable):.4f}, "  # noqa: E501
            f"rural nonmetro share {statistics.median(state.rural_nonmetro_share for state in publishable):.4f}, "  # noqa: E501
            f"published floor rate per 100,000 {floor_text}."
        )
    return f"Group {group}: {names}. {numeric}"


def _state_table(analysis: Analysis) -> str:
    lines = [
        "| State | Counties | Published share | Established tick share | Pathogen present share | Median published floor | Rural nonmetro share | Descriptive group | Publication-free group |",  # noqa: E501
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, state in enumerate(analysis.states):
        median = (
            "missing"
            if state.median_published_floor is None
            else f"{state.median_published_floor:.2f}"
        )
        lines.append(
            "| "
            + " | ".join(
                (
                    state.state,
                    str(state.county_n),
                    f"{state.published_share:.4f}",
                    f"{state.tick_established_share:.4f}",
                    f"{state.pathogen_present_share:.4f}",
                    median,
                    f"{state.rural_nonmetro_share:.4f}",
                    str(analysis.descriptive.labels[index]),
                    str(analysis.publication_free.labels[index]),
                )
            )
            + " |"
        )
    return "\n".join(lines)


def _zero_lines(analysis: Analysis) -> str:
    by_state = {state.state: state for state in analysis.states}
    labels = dict(
        zip((state.state for state in analysis.states), analysis.descriptive.labels, strict=True)
    )  # noqa: E501
    lines = [
        "| State | Counties | Descriptive group | Stored median |",
        "| --- | ---: | ---: | --- |",
    ]  # noqa: E501
    for code in analysis.questions.zero_published_states:
        state = by_state[code]
        if state.median_published_floor is not None:
            stored = f"{state.median_published_floor:.2f}"
        else:
            stored = "missing"
        lines.append(f"| {code} | {state.county_n} | {labels[code]} | {stored} |")
    if len(lines) == 2:
        return "No state has a zero published-floor share."
    return "\n".join(lines)


def _group_text(group: int | None) -> str:
    if group is None:
        return "not defined"
    return f"group {group}"


def _num(value: float | None) -> str:
    if value is None:
        return "not estimable"
    return f"{value:.4f}"
