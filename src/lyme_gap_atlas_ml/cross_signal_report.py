"""Markdown for issue 111. County names appear only in the narrative surfaces."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from lyme_gap_atlas_ml.cross_signal_disagreement import (
    CLASS_HUMAN_ONLY,
    CLASS_UNKNOWN,
    CLASSES,
    NAIVE_SEED,
    REGIONS,
    SEED,
    SPEC_ID,
    Analysis,
    Candidate,
)

_ISSUE_111 = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/111"
_ISSUE_22 = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22"
_RUN_COMMAND = (
    "MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_111_cross_signal.py"
)
_EXAMPLE_LABELS = (
    ("reporting_artifact", "Double gap in a state that publishes no county floor"),
    ("source_coverage", "Human floor with neither tick nor pathogen record"),
    ("follow_up", "Double gap in a state that publishes a county floor"),
)
_DRIVE_FOLDER = (
    "Drive folder https://drive.google.com/drive/folders/191hhct-v-vch7tHVmcTO1iPO1WTDXs4_"
)
_STATE_REVIEW_CHART = (
    "state-review-counts.png "
    "https://drive.google.com/file/d/1HmzHz-NpIFQzbJlzzqfInWRExG_92ah1/view "
    "(13093 bytes; Drive metadata size matches the local PNG)"
)
_DISAGREEMENT_MATRIX_CHART = (
    "disagreement-type-matrix.png "
    "https://drive.google.com/file/d/1Jpw5rGYfsVSKiVZ14QNx0CJab2mlbgbU/view "
    "(28831 bytes; in the issue-111 Drive folder and registered in REGISTRY.ARTIFACTS)"
)


def _drive_lines() -> tuple[str, ...]:
    """Drive links for the two registered issue-111 charts."""
    return (_DRIVE_FOLDER, _STATE_REVIEW_CHART, _DISAGREEMENT_MATRIX_CHART)


def render_comment(
    result: Analysis,
    *,
    run_id: str,
    git_commit: str,
    row_counts: Mapping[str, int],
    drive_lines: Sequence[str],
) -> str:
    """Issue comment and pull-request body. The two stay the same text."""
    rows = "\n".join(f"- `{name}` {count}" for name, count in row_counts.items())
    drives = "\n".join(f"- {line}" for line in drive_lines) or "- Drive upload pending"
    return "\n".join(
        (
            "## 1. Question",
            "",
            "Where do the published human, tick, and pathogen documentation states disagree, "
            "and which part is a state-reporting or source-coverage artifact rather than a "
            "follow-up candidate?",
            "",
            "## 2. Method",
            "",
            f"Spec [{SPEC_ID}](docs/eda/111-analysis-spec.md), frozen before the counts. "
            "The numeric residual in the cross-signal disagreement contract is not computed: "
            "the three signals are not on one approved comparison scale. "
            "Classes come from `HUMAN_STATUS`, `TICK_STATUS`, and `BURGDORFERI_STATUS`. "
            "`No records` and `Unknown` stay unobserved. A missing human floor is not zero. "
            "Associations use the #116 state-cluster bootstrap and Holm step-down on states "
            "that publish at least one county floor. "
            f"Seeds {SEED} and {NAIVE_SEED}.",
            "",
            "## 3. Key findings",
            "",
            _findings(result),
            "",
            "## 4. Caveats",
            "",
            "Human surveillance is calendar 2023. Tick and pathogen statuses are cumulative "
            "through 2025-12-31. Social vulnerability is 2022. Those windows are not one time "
            "base. A blank human floor in a state that publishes no county floor is that state's "
            "publication rule. `No records` is not evidence of absence. Counts are surveillance "
            "signals and lower bounds where a floor is published (CDC floor 5). They are not "
            "incidence, risk, or causation. State-cluster intervals do not cover dependence that "
            "crosses a state line. Northeast has fewer than 10 states, so its interval is not "
            "estimable. Review yield is not estimable: the examples illustrate the flags and "
            "are not an adjudicated sample.",
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
            drives,
            "- Doc: `docs/eda/111-cross-signal-disagreement.md`",
            "- `OH_LYME_PROD_READ` cannot count `EDA.CROSS_SIGNAL_CANDIDATES_111` until an owner "
            "grants SELECT. This run does not grant it.",
            "",
            "## 7. Reproducibility",
            "",
            f"- Commit: `{git_commit}`",
            f"- Release: `{result.release_id}`",
            f"- Seeds: cluster `{SEED}`, county resample `{NAIVE_SEED}`",
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
) -> str:
    """Durable EDA record from the template, with the same numbers as the comment."""
    counts = ", ".join(f"`{name}` {count}" for name, count in row_counts.items())
    drives = "; ".join(drive_lines) or "Drive upload pending"
    return "\n".join(
        (
            "# 111: Where do human, tick, and pathogen documentation states disagree?",
            "",
            f"- Issue: [ML #111]({_ISSUE_111}), part of [ML #22]({_ISSUE_22}). "
            "Question: which documentation gaps are reporting or source-coverage artifacts, "
            "and which remain a follow-up list?",
            f"- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`, and "
            f"`CURRENT_SOURCE_METADATA_V`. Pinned release `{result.release_id}`.",
            "- Cohort: one row per county on that release, including the District of Columbia, "
            "Connecticut planning-region FIPS, Alaska, and Hawaii. "
            f"Rows read: {result.counties}. Vulnerability rescaled by 100: "
            f"{'yes' if result.svi_rescaled else 'no'}.",
            "",
            "## Method and assumptions",
            "",
            f"Spec [{SPEC_ID}](111-analysis-spec.md), frozen before any disagreement count. "
            "The contract residual, score, and flag are absent. "
            "The class rules, the publishing-state cohort, seeds "
            f"`{SEED}` and `{NAIVE_SEED}`. The disposition rule is in the spec. "
            "State counts are points. National and Census-region counts use the #116 state-cluster "
            "percentile interval. Holm adjusts the four publishing-state tail shares when every "
            "interval is estimable. Benjamini-Hochberg is not used.",
            "",
            "## Material findings and limits",
            "",
            _findings(result),
            "",
            "### Region counts",
            "",
            _region_table(result),
            "",
            "A 1–10 cell is exact in this write-up and suppressed in the lab metrics and charts. "
            "State counts are in `EDA.METRICS_LONG` for this run, with that suppression.",
            "",
            "## Decision",
            "",
            _disposition(result),
            "",
            "## Reproduction and retained evidence",
            "",
            f"- Code revision/run: `{git_commit}`, run `{run_id}`, spec `{SPEC_ID}`.",
            "- Entry points: `sql/validation/111_cross_signal_disagreement.sql`, "
            "`scripts/eda_111_cross_signal.py`, "
            "`src/lyme_gap_atlas_ml/cross_signal_disagreement.py`.",
            "- Commands: `uv run python scripts/check_ml_agent_context.py`, then "
            f"`{_RUN_COMMAND}`, "
            "then `uv run python scripts/verify.py`.",
            f"- Lab row counts: {counts}.",
            f"- Drive: {drives}.",
            "- Transient artifacts intentionally not committed: PNG files under "
            "`artifacts/charts/111/` and any in-memory county rows. "
            "Candidate rows stay in `EDA.CROSS_SIGNAL_CANDIDATES_111`. "
            "No county extract was committed.",
            "",
        )
    )


def _findings(result: Analysis) -> str:
    lines = [
        "October 13 comparison, exact integers:",
        "",
        "| Check | Observed | Reference |",
        "| --- | ---: | ---: |",
    ]
    for item in result.references:
        lines.append(f"| {item.name} | {item.observed} | {item.expected} |")
    lines.extend(
        (
            "",
            f"Zero-floor state set matches the nineteen-state list: "
            f"{'yes' if result.zero_floor_matches else 'no'} "
            f"({len(result.zero_floor_states)} states).",
            "",
            "Documentation classes:",
            "",
            "| Class | Counties |",
            "| --- | ---: |",
        )
    )
    for name in CLASSES:
        lines.append(f"| {name} | {result.counts[name]} |")
    lines.extend(
        (
            "",
            f"Double-gap counties explained by a zero-floor state: {result.artifact_double_gap_n}. "
            f"Double-gap follow-up counties, in states that publish a floor: {result.follow_up_n}. "
            "Human floor with neither tick nor pathogen record: "
            f"{result.counts[CLASS_HUMAN_ONLY]}. "
            f"Unknown or out of scope, unranked: {result.counts[CLASS_UNKNOWN]}.",
            "",
            _contrast_table(result),
            "",
            _examples(result),
        )
    )
    return "\n".join(lines)


def _contrast_table(result: Analysis) -> str:
    lines = [
        "Publishing-state associations. The interval is the state-cluster percentile interval.",
        "",
        "| Contrast | Estimate | Low | High | Holm | Material sensitivity |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in result.contrasts:
        lines.append(
            "| "
            + " | ".join(
                (
                    item.name,
                    _num(item.estimate),
                    _num(item.cluster.low),
                    _num(item.cluster.high),
                    _num(item.holm),
                    "yes" if item.material else "no",
                )
            )
            + " |"
        )
    cramers = "not estimable" if result.cramers_v_metro is None else f"{result.cramers_v_metro:.4f}"
    lines.append("")
    lines.append(
        f"Companion Cramér's V for the metro table, not a test: {cramers}. "
        f"Holm family {'was' if result.holm_applied else 'was not'} applied."
    )
    return "\n".join(lines)


def _examples(result: Analysis) -> str:
    lines = [
        "False-positive review, smallest FIPS in each prespecified group. "
        "These rows illustrate the flag. They are not a rank."
    ]
    for key, title in _EXAMPLE_LABELS:
        lines.extend(("", f"### {title}", ""))
        group = result.examples.get(key, ())
        if not group:
            lines.append("None in this cohort.")
            continue
        for candidate in group:
            lines.append(_example_line(candidate))
    return "\n".join(lines)


def _example_line(candidate: Candidate) -> str:
    if candidate.population is None:
        population = "population not used"
    else:
        population = f"population {candidate.population:.0f}"
    return (
        f"- {candidate.county}, {candidate.state} ({candidate.fips}): "
        f"{candidate.documentation_class}, reading {candidate.review_reading}. "
        f"Tick {candidate.tick}; pathogen {candidate.pathogen}; human {candidate.human}. "
        f"{population}. Supporting `{candidate.supporting or 'none'}`. "
        f"Gap tokens `{candidate.contradicting or 'none'}`."
    )


def _region_table(result: Analysis) -> str:
    header = "| Class | " + " | ".join(REGIONS) + " |"
    rule = "| --- | " + " | ".join("---:" for _ in REGIONS) + " |"
    lines = [header, rule]
    for name in CLASSES:
        cells = [str(result.by_region.get((region, name), 0)) for region in REGIONS]
        lines.append("| " + name + " | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _disposition(result: Analysis) -> str:
    if result.disposition == "investigate":
        decision = "INVESTIGATE"
        reason = (
            f"The October 13 counts match, and {result.follow_up_n} double-gap counties "
            "sit in states that publish a county floor. That residual list is the follow-up "
            "candidate set in `EDA.CROSS_SIGNAL_CANDIDATES_111` where `REVIEW_READING` is "
            "`follow_up`. It is a review list, not a score."
        )
    elif result.disposition == "revise":
        decision = "REVISE"
        reason = (
            "At least one October 13 count or the nineteen-state set differs on this release. "
            "Do not treat the candidate table as a reproduction of that list until the named "
            "difference is explained."
        )
    else:
        decision = "STOP"
        reason = (
            "The follow-up double gap is below 11 counties, or a gate failed before a usable "
            "list. There is no publishable residual list that state non-publication leaves behind."
        )
    return (
        f"**{decision}.** {reason} Advance is not available from this run: epic #22 says to "
        "inspect and not to rank by risk, and a public map or workflow needs a separate review. "
        "Keep the lab table for analyst inspection of the follow-up rows. Do not train a model "
        "on the class or the reading."
    )


def _num(value: float | None) -> str:
    if value is None:
        return "not estimable"
    return f"{value:.4f}"
