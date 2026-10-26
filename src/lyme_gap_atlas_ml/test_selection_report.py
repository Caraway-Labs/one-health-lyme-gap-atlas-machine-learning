"""Narrative for issue 116. County names belong in this text, not in charts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from lyme_gap_atlas_ml.coverage_audit import (
    REFERENCE_NO_COUNTY_LINKED_RECORD,
    REFERENCE_PUBLISHED_HUMAN_FLOOR,
)
from lyme_gap_atlas_ml.test_selection import (
    METHOD_DECISIONS,
    NAIVE_SEED,
    REFERENCE_INTERVAL,
    REFERENCE_V_HUMAN_PATHOGEN,
    REFERENCE_V_HUMAN_TICK,
    REFERENCE_V_TICK_PATHOGEN,
    REPRODUCTION_SEED,
    SEED,
    SPEC_ID,
    Contrast,
    Reproduced,
    SelectionResult,
    Sensitivity,
    ShareCell,
)

ISSUE = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues"
_CALL = {
    "keep": (
        "Keep the two documentation contrasts and the reproduced associations as "
        "descriptive results with their state-cluster intervals. Quote the interval, "
        "not a significance label. Do not treat a county as an independent draw, and "
        "do not turn a published floor into incidence or risk."
    ),
    "revise": (
        "Revise before quoting a contrast as a stable difference. The frozen rule "
        "failed on at least one of the display match, an interval that includes zero, "
        "a county-resample interval that excludes zero while the state-cluster interval "
        "includes it, a material sensitivity, or an incomplete family. The climate "
        "comparison remains a no-go."
    ),
    "stop": (
        "Stop. Both share contrasts are not estimable, or a gate failed before the "
        "estimates were written. Do not fill the gap with a county-IID test."
    ),
}


def render_eda_record(
    result: SelectionResult,
    *,
    run_id: str,
    git_commit: str,
    row_counts: Mapping[str, int],
    drive_lines: Sequence[str],
) -> str:
    """Durable EDA record from the template, filled with this run."""
    q1 = result.contrast("q1_share_diff")
    q2 = result.contrast("q2_share_diff")
    counts = ", ".join(f"`{name}` {count}" for name, count in row_counts.items())
    links = [f"- {line}" for line in drive_lines] or ["- Drive links pending upload."]
    scaled = "yes" if result.svi_rescaled else "no"
    lines = [
        "# 116: Which county comparisons support a statistical difference?",
        "",
        f"- Issue: [ML #116]({ISSUE}/116), part of [ML #22]({ISSUE}/22).",
        f"  Spec: [{SPEC_ID}](116-analysis-spec.md).",
        "- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`.",
        f"  Pinned release `{result.release_id}`.",
        (
            f"- Cohort: rows read {result.counties}. Published floor {result.published_n}. "
            f"No county-linked record {result.no_record_n}. "
            f"Other human status {result.other_human_n}."
        ),
        "",
        "## Method and assumptions",
        "",
        f"Spec [{SPEC_ID}](116-analysis-spec.md), frozen before the read.",
        "The descriptive unit is the county. The resampling unit is the state.",
        "Welch t, paired t, Mann-Whitney, Wilcoxon signed-rank, ANOVA,",
        "Kruskal-Wallis, chi-square, Fisher exact, Pearson, and regression are rejected.",
        "Spearman is the chosen rank coefficient. Share differences use a state-cluster interval.",
        "Holm adjusts the four state-resample tail shares. Benjamini-Hochberg is not used.",
        "Q3, climate versus tick or pathogen documentation, is the predeclared no-go.",
        f"No model was fit. Seeds {SEED}, {NAIVE_SEED}, and {REPRODUCTION_SEED}.",
        "",
        "| Method | Decision | Why |",
        "| --- | --- | --- |",
        _method_rows(),
        "",
        "## Material findings and limits",
        "",
        (
            f"Epic #22 section 4.1 recorded {REFERENCE_PUBLISHED_HUMAN_FLOOR} published floors "
            f"and {REFERENCE_NO_COUNTY_LINKED_RECORD} counties with no county-linked record, "
            "out of 3144."
        ),
        f"This release has {result.published_n} and {result.no_record_n}.",
        f"Vulnerability rescaled by 100: {scaled}. Maximum: {_fmt(result.svi_max)}.",
        "",
        (
            f"Q1 eligible counties {q1.n} (metro {q1.n_left}, nonmetro {q1.n_right}). "
            f"Null rural-urban codes among known human statuses: {result.q1_excluded_rucc}."
        ),
        _contrast_sentence(q1),
        "",
        (
            f"Q2 eligible counties {q2.n} (lower vulnerability {q2.n_left}, "
            f"higher {q2.n_right}). "
            f"Null vulnerability among known human statuses: {result.q2_excluded_svi}."
        ),
        _contrast_sentence(q2),
        "",
        _family_block(result),
        "",
        (
            f"October 13 targets: tick x pathogen V {REFERENCE_V_TICK_PATHOGEN}, "
            f"human x tick V {REFERENCE_V_HUMAN_TICK}, "
            f"human x pathogen V {REFERENCE_V_HUMAN_PATHOGEN}, "
            f"interval {REFERENCE_INTERVAL[0]} to {REFERENCE_INTERVAL[1]}."
        ),
        (
            f"Helper eligible n: {result.tick_helper_n}. Helper V: {_fmt(result.tick_helper_v)}. "
            f"Established-plus-Reported collapse V: {_fmt(result.collapse_v)}. "
            "The issue 65 reference collapse was 0.4258."
        ),
        "",
        "| Association | This release | State-cluster interval | Width ratio | Epic display |",
        "| --- | --- | --- | --- | --- |",
        _reproduction_rows(result),
        "",
        "The exhaustive write-up's V near 0.81 keeps Unknown as its own level.",
        "Epic item 4's 0.5607 drops Unknown and out-of-scope counties.",
        "Those are different tables, not a failed replay of one table.",
        "",
        "Rural-urban published-floor shares, beside the 13 October counts.",
        "A 1-10 cell may be named here. It is omitted from lab aggregates and charts.",
        "",
        "| Code | Counties | Published | October counties | October published |",
        "| --- | ---: | ---: | ---: | ---: |",
        _share_rows(result.rucc_cells),
        "",
        (
            "Vulnerability bins, excluding a value of exactly 1 "
            f"({result.svi_exact_one_n} counties, {result.svi_exact_one_published} published):"
        ),
        "",
        "| Bin | Counties | Published | October counties | October published |",
        "| --- | ---: | ---: | ---: | ---: |",
        _share_rows(result.svi_cells),
        "",
        "A sensitivity move of at least 0.02, or a sign change, is material.",
        f"Material rows: {_material_names(result.sensitivities)}.",
        "",
        "| Sensitivity | Estimate | Absolute move | Sign change |",
        "| --- | ---: | ---: | --- |",
        _sensitivity_rows(result.sensitivities),
        "",
        "Q3 remains not estimable. No climate query was issued.",
        "",
        "Peer-review spot checks use the smallest FIPS under each frozen rule.",
        "`No records` is a documentation state. A null vulnerability value is missing, not zero.",
        "",
        "| Rule | County | State | FIPS | Human status | Tick | Pathogen | RUCC | SVI |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | ---: |",
        _spot_rows(result),
        "",
        "## Decision",
        "",
        f"**{result.disposition.upper()}**, mapped from the frozen rule.",
        _recommendation(result),
        "",
        _permission(result),
        "",
        "## Reproduction and retained evidence",
        "",
        f"- Code revision: `{git_commit}`. Run `{run_id}`. Release `{result.release_id}`.",
        "- Entry points: `sql/validation/116_test_selection.sql`,",
        "  `scripts/eda_116_test_selection.py`, `src/lyme_gap_atlas_ml/test_selection.py`.",
        "- Commands: `uv run python scripts/check_ml_agent_context.py`,",
        "  then `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python`",
        "  `scripts/eda_116_test_selection.py`, then `uv run python scripts/verify.py`.",
        f"- Lab row counts: {counts}.",
        "- Drive:",
        *links,
        "- Transient artifacts not committed: in-memory county rows,",
        "  PNG files under `artifacts/charts/116/`, and the local comment draft.",
        "",
        "The shared lab writers do not grant SELECT. This story creates no new table.",
        "Role administration is outside the Snowflake integration guide,",
        "so `OH_LYME_PROD_READ` still cannot count a new lab table until an owner grants it.",
        "",
    ]
    return "\n".join(lines)


def render_comment(
    result: SelectionResult,
    *,
    run_id: str,
    git_commit: str,
    row_counts: Mapping[str, int],
    drive_lines: Sequence[str],
) -> str:
    """Issue comment and pull-request body. Same seven sections."""
    q1 = result.contrast("q1_share_diff")
    q2 = result.contrast("q2_share_diff")
    h3 = result.contrast("h3_spearman_svi")
    h4 = result.contrast("h4_spearman_rucc")
    counts = ", ".join(f"{name} {count}" for name, count in row_counts.items())
    links = "; ".join(drive_lines) if drive_lines else "pending"
    lines = [
        "Part of #116",
        "",
        "Part of #22",
        "",
        "## 1. Question",
        "",
        "Which Atlas county comparisons can support an interpretable statistical",
        "difference or association, and which cannot? How robust are the 13 October",
        "associations in epic #22 section 4.1 (Cramer's V and the tick x pathogen",
        "state-block interval)?",
        "",
        "## 2. Method",
        "",
        f"Specification [{SPEC_ID}](docs/eda/116-analysis-spec.md), frozen before the read.",
        "Chosen summaries are the metro minus nonmetro published-floor share,",
        "the lower-minus-higher vulnerability share, and two Spearman coefficients,",
        "each with a 2,000-draw state-cluster percentile interval.",
        "Holm adjusts the four state-resample tail shares.",
        "Those tail shares are not sampling p-values.",
        "Chi-square, Fisher, Welch, rank tests, ANOVA, Pearson, and regression are rejected",
        "because the floor indicator is binary, the release has one row per county,",
        "or counties in a state share reporting rules.",
        "The tick x pathogen replay calls `evidence_association_65.analyze_aggregate_counties`",
        f"(seed {REPRODUCTION_SEED}).",
        "Climate strata versus tick or pathogen documentation are a predeclared no-go:",
        "this release's climate object is a January daily view,",
        "and the county atlas has no climate stratum. No `EXPERIMENTS` rows.",
        "",
        "## 3. Key findings",
        "",
        (
            f"Published floor {result.published_n} of {result.counties}; "
            f"no county-linked record {result.no_record_n}."
        ),
        (
            "The 13 October headline is "
            f"{REFERENCE_PUBLISHED_HUMAN_FLOOR} and {REFERENCE_NO_COUNTY_LINKED_RECORD}."
        ),
        "",
        (
            f"Q1 metro minus nonmetro share difference {_fmt(q1.estimate)} "
            f"(n {q1.n}; state-cluster {_interval(q1)}; "
            f"width ratio {_fmt(q1.width_ratio)}; Holm tail share {_fmt(q1.holm)})."
        ),
        (
            f"Q2 lower minus higher vulnerability {_fmt(q2.estimate)} "
            f"(n {q2.n}; state-cluster {_interval(q2)}; "
            f"width ratio {_fmt(q2.width_ratio)}; Holm {_fmt(q2.holm)})."
        ),
        f"Spearman vulnerability and published floor {_fmt(h3.estimate)} ({_interval(h3)}).",
        f"Spearman rural-urban code and published floor {_fmt(h4.estimate)} ({_interval(h4)}).",
        "",
        _reproduction_prose(result),
        "",
        "The exhaustive write-up's V near 0.81 keeps Unknown as a level on all 3144 counties.",
        "Epic item 4's 0.5607 drops Unknown.",
        (
            f"Collapse of Established and Reported: V {_fmt(result.collapse_v)} "
            "(issue 65 reference 0.4258)."
        ),
        "",
        f"Material sensitivities: {_material_names(result.sensitivities)}.",
        "Q3: not estimable.",
        f"Spot checks: {_spot_sentences(result)}",
        "",
        "## 4. Caveats",
        "",
        "A published floor is a surveillance lower bound, not incidence, risk, or causation.",
        "`No records` and `Unknown` are not negatives.",
        (
            f"Missing rural-urban codes ({result.q1_excluded_rucc}) and missing "
            f"vulnerability percentiles ({result.q2_excluded_svi}) stay out of the denominators "
            "and are not filled with zero."
        ),
        "The state-cluster interval is the reported uncertainty.",
        "The width ratio says how that interval compares with a county resample.",
        "State resampling does not cover dependence across a state line.",
        "Vintages differ: human cases are 2023, tick and pathogen status are cumulative",
        "through 2025, vulnerability is 2022, and the rural-urban code is 2023.",
        "No binary significance call is made.",
        "",
        "## 5. Disposition",
        "",
        f"**{result.disposition}.** {_recommendation(result)}",
        "",
        _permission(result),
        "",
        "## 6. Artifacts",
        "",
        f"Run `{run_id}`. Lab row counts: {counts}.",
        f"Drive: {links}.",
        "Record: `docs/eda/116-test-selection.md`. Spec: `docs/eda/116-analysis-spec.md`.",
        "No new lab table. The writers do not grant SELECT,",
        "and this adapter does not administer roles,",
        "so the ML Lead read role still cannot count a new lab table until an owner grants it.",
        "",
        "## 7. Reproducibility",
        "",
        f"Commit `{git_commit}`. Release `{result.release_id}`.",
        f"Seeds {SEED}, {NAIVE_SEED}, and {REPRODUCTION_SEED}. Commands:",
        "",
        "```text",
        "uv sync --locked --extra dev --extra snowflake",
        "uv run python scripts/check_ml_agent_context.py",
        (
            "MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
            "python scripts/eda_116_test_selection.py"
        ),
        "uv run python scripts/verify.py",
        "```",
        "",
        "County rows, chart PNGs, and Snowflake extracts were not committed.",
        "",
    ]
    return "\n".join(lines)


def _recommendation(result: SelectionResult) -> str:
    if result.disposition == "keep":
        return _CALL["keep"]
    if result.disposition == "stop":
        return _CALL["stop"]
    parts: list[str] = []
    if result.v_display_match and result.interval_display_match:
        parts.append("The October 13 four-decimal displays match.")
    else:
        parts.append("An October 13 four-decimal display does not match.")
    q1 = result.contrast("q1_share_diff")
    q2 = result.contrast("q2_share_diff")
    if q1.excludes_zero and q2.excludes_zero:
        parts.append("Both share-difference state-cluster intervals exclude zero.")
    else:
        parts.append("A share-difference state-cluster interval includes zero or is missing.")
    if result.material_sensitivity:
        signed = any(item.sign_change for item in result.sensitivities)
        sign_note = "A sensitivity changes sign." if signed else "No sensitivity changes sign."
        parts.append(
            "Leaving out a Census region moves a share difference by at least 0.02, "
            f"so the national magnitude is not stable across regions. {sign_note}"
        )
    if not result.family_complete:
        parts.append("The Holm family is incomplete.")
    parts.append("The climate comparison remains a no-go.")
    return " ".join(parts)


def _permission(result: SelectionResult) -> str:
    if result.disposition == "keep":
        return (
            "This is permission to quote the documented contrasts with their intervals. "
            "It is not permission to train a model, publish a score, or claim causation."
        )
    if result.disposition == "stop":
        return "Do not quote a share difference from this run."
    return (
        "Describe the direction with the state-cluster interval. "
        "Do not treat the national magnitude as a figure that holds inside every region. "
        "It is not permission to train a model, publish a score, or claim causation."
    )


def _method_rows() -> str:
    return "\n".join(
        f"| {item.method} | {item.decision} | {item.use} |" for item in METHOD_DECISIONS
    )


def _contrast_sentence(contrast: Contrast) -> str:
    return (
        f"{contrast.label}: estimate {_fmt(contrast.estimate)}, "
        f"state-cluster {_interval(contrast)}, "
        f"county-resample width ratio {_fmt(contrast.width_ratio)}, "
        f"tail share {_fmt(contrast.cluster.tail_share)}, "
        f"Holm-adjusted tail share {_fmt(contrast.holm)}."
    )


def _family_block(result: SelectionResult) -> str:
    lines = [_contrast_sentence(item) for item in result.contrasts]
    flag = "complete" if result.family_complete else "incomplete"
    return f"The Holm family is {flag}. " + " ".join(lines)


def _reproduction_rows(result: SelectionResult) -> str:
    return "\n".join(_one_reproduction(item) for item in result.reproduced)


def _one_reproduction(item: Reproduced) -> str:
    low = _fmt(item.cluster.low)
    high = _fmt(item.cluster.high)
    if item.association is None:
        value = "not estimable"
        n = 0
    else:
        value = _fmt(item.association.v)
        n = item.association.n
    ratio = _fmt(item.width_ratio)
    return f"| {item.name} | {value} (n {n}) | {low} to {high} | {ratio} | {item.target} |"


def _reproduction_prose(result: SelectionResult) -> str:
    parts: list[str] = []
    for item in result.reproduced:
        value = "not estimable" if item.association is None else _fmt(item.association.v)
        parts.append(
            f"{item.name} V {value} (epic {item.target}; "
            f"interval {_fmt(item.cluster.low)} to {_fmt(item.cluster.high)}; "
            f"width ratio {_fmt(item.width_ratio)})"
        )
    match = "match" if result.v_display_match and result.interval_display_match else "do not match"
    return f"Four-decimal epic displays {match}. " + " ".join(parts)


def _share_rows(cells: Sequence[ShareCell]) -> str:
    lines: list[str] = []
    for cell in cells:
        lines.append(
            f"| {cell.label} | {cell.n} | {cell.published} | "
            f"{_opt(cell.reference_n)} | {_opt(cell.reference_published)} |"
        )
    return "\n".join(lines)


def _sensitivity_rows(rows: Sequence[Sensitivity]) -> str:
    rendered: list[str] = []
    for item in rows:
        changed = "yes" if item.sign_change else "no"
        rendered.append(f"| {item.name} | {_fmt(item.estimate)} | {_fmt(item.move)} | {changed} |")
    return "\n".join(rendered)


def _material_names(rows: Sequence[Sensitivity]) -> str:
    names = [item.name for item in rows if item.material]
    return ", ".join(names) if names else "none"


def _spot_rows(result: SelectionResult) -> str:
    lines: list[str] = []
    for spot in result.spots:
        county = spot.county
        if county is None:
            lines.append(f"| {spot.rule} | none |  |  |  |  |  |  |  |")
            continue
        svi = "missing" if county.svi is None else f"{county.svi:.3f}"
        rucc = "" if county.rucc is None else str(county.rucc)
        lines.append(
            f"| {spot.rule} | {county.county} | {county.state} | {county.fips} | "
            f"{county.human} | {county.tick} | {county.pathogen} | {rucc} | {svi} |"
        )
    return "\n".join(lines)


def _spot_sentences(result: SelectionResult) -> str:
    parts: list[str] = []
    for spot in result.spots:
        county = spot.county
        if county is None:
            parts.append(f"{spot.rule}: none")
            continue
        parts.append(f"{county.county}, {county.state} ({county.fips}) for {spot.rule}")
    return "; ".join(parts)


def _interval(contrast: Contrast) -> str:
    return f"{_fmt(contrast.cluster.low)} to {_fmt(contrast.cluster.high)}"


def _fmt(value: float | None) -> str:
    if value is None:
        return "not estimable"
    return f"{value:.4f}"


def _opt(value: int | None) -> str:
    if value is None:
        return ""
    return str(value)
