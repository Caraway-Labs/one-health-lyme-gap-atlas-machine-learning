"""Render the issue 194 write-up. County rows stay out of the text."""

from __future__ import annotations

from collections.abc import Mapping

from lyme_gap_atlas_ml.regime_tick_geography import (
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    EXPECTED_ABSENT,
    EXPECTED_COUNTIES,
    EXPECTED_PUBLISHED,
    FAMILY_GBT,
    FAMILY_LOGISTIC,
    REFERENCE_188_LOGISTIC,
    REFERENCE_188_TREE,
    SEED_PRIMARY,
    SEED_SECOND,
    SHUFFLE_SEED,
    SMALL_CELL,
    SPEC_ID,
    Analysis,
    FamilySeedResult,
)

DOC_PATH = "docs/eda/194-regime-vs-tick-geography.md"
_ISSUE = "https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues"


def render_eda_record(
    analysis: Analysis,
    *,
    run_id: str,
    commit: str,
    counts: Mapping[str, int],
    drive_note: str,
    grant: str,
) -> str:
    """Return the durable EDA record, including the seven comment sections."""
    comment = render_comment(
        analysis,
        run_id=run_id,
        commit=commit,
        counts=counts,
        drive_note=drive_note,
        grant=grant,
    )
    if analysis.cohort_matches_expected:
        matched = f"matched the expected {EXPECTED_PUBLISHED} and {EXPECTED_ABSENT}"
    else:
        matched = f"differed from the expected {EXPECTED_PUBLISHED} and {EXPECTED_ABSENT}"
    cohort = (
        f"- Cohort: {analysis.counties} counties, {analysis.states} states, one snapshot. "
        f"Published floor {analysis.published_n}. "
        f"No county-linked record {analysis.absent_n}. Counts {matched}."
    )
    header = "\n".join(
        (
            "# 194: Does the state regime add signal beyond tick geography?",
            "",
            f"- Issue: [#194]({_ISSUE}/194); program epic [#22]({_ISSUE}/22).",
            "- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`.",
            "- Release: `governed-2026-10-15-january-climate-prod`.",
            cohort,
            "",
            "## Method and assumptions",
            "",
            f"Spec [{SPEC_ID}](194-analysis-spec.md), frozen before the fit.",
            "Model A is state tick-established share, county tick status, county pathogen",
            "status, and the #188 context features. Model B adds the #188 out-of-fold",
            "publication-free regime. A held-out state's tick share uses that state's tick",
            "statuses and does not use its floors. The descriptive #123 groups are not fit.",
            "",
            "## Material findings and limits",
            "",
            comment.rstrip("\n"),
            "",
            "## Decision",
            "",
            (
                f"{analysis.decision.method.upper()} for the method. "
                f"{analysis.decision.product.upper()} for product value. "
                "This is not a release, a tier change, or a production score."
            ),
            "",
            "## Reproduction and retained evidence",
            "",
            (
                f"- Fit commit `{commit}`, run `{run_id}`, "
                "release `governed-2026-10-15-january-climate-prod`."
            ),
            "- Entry points: `sql/validation/194_regime_tick_geography.sql`,",
            "  `scripts/eda_194_regime_tick_geography.py`,",
            "  `src/lyme_gap_atlas_ml/regime_tick_geography.py`.",
            "- Commands: see the reproducibility section above.",
            "- Transient artifacts not committed: chart PNGs under ignored",
            "  `artifacts/charts/194/`. No county extract.",
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
    drive_note: str,
    grant: str,
) -> str:
    """Return the seven sections for the pull-request body."""
    logistic = _primary(analysis, FAMILY_LOGISTIC)
    tree = _primary(analysis, FAMILY_GBT)
    point = logistic.challenger.roc_auc - logistic.baseline.roc_auc
    count_text = ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
    sections = (
        "1. Question",
        "",
        "Does the publication-free state regime still separate a published county floor",
        "from its absence after tick geography is already in the model?",
        "",
        "2. Method (and why; link the spec)",
        "",
        f"Spec [{SPEC_ID}](docs/eda/194-analysis-spec.md), frozen before the fit.",
        "Leave-one-state-out on 51 states, the same folds and out-of-fold regime",
        "assignment as #188. Model A: state tick-established share, county tick status,",
        "county pathogen status, SVI percentile, uninsured percentile, rural-urban code,",
        "and log population. Model B adds the regime id. Logistic regression is L2 with",
        f"C=1.0. Trees are a depth-3 gradient booster. Seeds {SEED_PRIMARY} and",
        f"{SEED_SECOND}. The lift interval resamples states {BOOTSTRAP_REPLICATES} times",
        f"with seed {BOOTSTRAP_SEED}. The shuffled-regime control uses seed {SHUFFLE_SEED}.",
        "A pass needs a ROC-AUC interval whose lower end is above 0.01, a PR-AUC interval",
        "above 0, and a Brier interval whose upper end is below 0.005, after the leakage",
        "tests pass.",
        "",
        "3. Key findings with numbers",
        "",
        _finding_prose(analysis, point),
        "",
        _score_table(analysis),
        "",
        _lift_lines(logistic, tree),
        "",
        (
            f"Label invariance: {analysis.leakage_invariant}. "
            f"Shuffled-regime logistic ROC-AUC lift, seed {SHUFFLE_SEED}: "
            f"{analysis.shuffled_auc_lift:.4f}. "
            f"Shuffled model A ROC-AUC gap: {analysis.shuffle_baseline_gap:.6f}. "
            f"SVI rescaled by 100: {analysis.svi_rescaled}. "
            f"Uninsured percentile rescaled by 100: {analysis.uninsured_rescaled}. "
            f"Cohort matches {EXPECTED_PUBLISHED} and {EXPECTED_ABSENT}: "
            f"{analysis.cohort_matches_expected}."
        ),
        "",
        _summary_lines(analysis),
        "",
        (
            "#188 logistic ROC-AUC moved from "
            f"{REFERENCE_188_LOGISTIC[0]:.4f} to {REFERENCE_188_LOGISTIC[1]:.4f} "
            f"(lift {REFERENCE_188_LOGISTIC[2]:.4f}, interval "
            f"{REFERENCE_188_LOGISTIC[3]:.4f} to {REFERENCE_188_LOGISTIC[4]:.4f}) "
            "when the regime was added to demographics only. "
            "The tree comparison was "
            f"{REFERENCE_188_TREE[0]:.4f} to {REFERENCE_188_TREE[1]:.4f} "
            f"(lift {REFERENCE_188_TREE[2]:.4f}, interval "
            f"{REFERENCE_188_TREE[3]:.4f} to {REFERENCE_188_TREE[4]:.4f}). "
            "This story's model A already contains the state tick share that #188 folded "
            "into the regime."
        ),
        "",
        _state_table(analysis),
        "",
        "4. Caveats",
        "",
        "Counts are surveillance signals and lower bounds. The published floor starts at",
        "the CDC floor of 5. It is not a disease rate and not causation. No records and",
        "Unknown are not negatives. A missing floor is not zero. Predictions are not a",
        "risk score, not a production score, and not for a public page.",
        "The regime still uses the state's tick-documentation share, pathogen-documentation",
        "share, and rural mix. Model A already has the state tick share and the county",
        "pathogen status, so a remaining lift can be state pathogen mix, state rural mix,",
        "or the cluster label. It is not a separate reporting culture. Human surveillance",
        "is calendar 2023. SVI, uninsured share, and population are 2022. Tick and pathogen",
        "status are cumulative through 2025-12-31. The state bootstrap does not cover",
        "dependence that crosses a state line.",
        "",
        "5. Disposition",
        "",
        (
            f"Method: {analysis.decision.method}. Product: {analysis.decision.product}. "
            f"Leakage checks passed: {analysis.decision.leakage_ok}. "
            f"Logistic pass rule: {analysis.decision.logistic_real_lift}. "
            f"Tree ROC-AUC interval stays positive: {analysis.decision.tree_auc_positive}. "
            "Rule failures: "
            + (", ".join(analysis.decision.reasons) if analysis.decision.reasons else "none")
            + "."
        ),
        "",
        "6. Artifacts",
        "",
        f"run_id: {run_id}",
        "",
        f"Snowflake row counts: {count_text}.",
        "",
        f"SELECT grants on EDA.REGIME_VS_TICK_GEOGRAPHY_194: {grant}.",
        "",
        drive_note,
        "",
        "Doc: docs/eda/194-regime-vs-tick-geography.md",
        "",
        "Spec: docs/eda/194-analysis-spec.md",
        "",
        "7. Reproducibility",
        "",
        f"Commit: {commit}",
        "Release: governed-2026-10-15-january-climate-prod",
        (
            f"Seeds: logistic and trees {SEED_PRIMARY} and {SEED_SECOND}; "
            f"bootstrap {BOOTSTRAP_SEED}; shuffled regime {SHUFFLE_SEED}."
        ),
        (
            f"Counties in the fit: {analysis.counties}. "
            f"Expected counties {EXPECTED_COUNTIES}. "
            f"scikit-learn {analysis.sklearn_version}."
        ),
        "",
        "```text",
        "uv sync --locked --extra dev --extra snowflake",
        "uv run python scripts/check_ml_agent_context.py",
        (
            "MPLBACKEND=Agg uv run --with matplotlib --with seaborn "
            "python scripts/eda_194_regime_tick_geography.py"
        ),
        "uv run python scripts/verify.py",
        "```",
        "",
    )
    return "\n".join(sections)


def _finding_prose(analysis: Analysis, point: float) -> str:
    logistic = _primary(analysis, FAMILY_LOGISTIC)
    tree = _primary(analysis, FAMILY_GBT)
    tree_point = tree.challenger.roc_auc - tree.baseline.roc_auc
    return (
        f"On the primary seed, logistic ROC-AUC is {logistic.baseline.roc_auc:.4f} "
        f"for tick geography and {logistic.challenger.roc_auc:.4f} with the regime "
        f"(lift {point:.4f}, interval {_span(logistic)}). "
        f"The tree model moves from {tree.baseline.roc_auc:.4f} to {tree.challenger.roc_auc:.4f} "
        f"(lift {tree_point:.4f}, interval {_span(tree)}). " + _claim(analysis)
    )


def _claim(analysis: Analysis) -> str:
    if analysis.decision.logistic_real_lift:
        return (
            "The regime still clears the frozen bar after tick geography is controlled. "
            "That is a reason to keep the feature in a later design discussion. "
            "It is not a score to publish."
        )
    logistic = _primary(analysis, FAMILY_LOGISTIC)
    point = logistic.challenger.roc_auc - logistic.baseline.roc_auc
    high = logistic.auc_lift.high
    if point < 0 or (high is not None and high <= 0) or abs(point) < 0.01:
        return (
            "The regime lift disappears once tick geography is in the model. "
            "The #188 gain over demographics is consistent with the regime restating "
            "tick geography. That is a reason to stop treating the regime as extra signal."
        )
    return (
        "The point lift stays positive and does not clear the frozen bar. "
        "The #188 gain over demographics is mostly the tick geography already in model A."
    )


def _span(fit: FamilySeedResult) -> str:
    if fit.auc_lift.low is None or fit.auc_lift.high is None:
        return "not estimable"
    return f"{fit.auc_lift.low:.4f} to {fit.auc_lift.high:.4f}"


def _score_table(analysis: Analysis) -> str:
    lines = [
        (
            "| Family | Seed | Tick AUC | Regime AUC | Tick PR | Regime PR "
            "| Tick Brier | Regime Brier |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for fit in analysis.fits:
        lines.append(
            "| "
            + " | ".join(
                (
                    fit.family,
                    str(fit.seed),
                    f"{fit.baseline.roc_auc:.4f}",
                    f"{fit.challenger.roc_auc:.4f}",
                    f"{fit.baseline.pr_auc:.4f}",
                    f"{fit.challenger.pr_auc:.4f}",
                    f"{fit.baseline.brier:.4f}",
                    f"{fit.challenger.brier:.4f}",
                )
            )
            + " |"
        )
    return "\n".join(lines)


def _lift_lines(logistic: FamilySeedResult, tree: FamilySeedResult) -> str:
    return "\n".join(
        (
            (
                "Logistic primary lifts, regime minus tick geography: "
                f"ROC-AUC {_span(logistic)}, "
                f"PR-AUC {_pair(logistic.pr_lift.low, logistic.pr_lift.high)}, "
                f"Brier {_pair(logistic.brier_lift.low, logistic.brier_lift.high)}."
            ),
            (
                "Tree primary lifts: "
                f"ROC-AUC {_span(tree)}, "
                f"PR-AUC {_pair(tree.pr_lift.low, tree.pr_lift.high)}, "
                f"Brier {_pair(tree.brier_lift.low, tree.brier_lift.high)}."
            ),
        )
    )


def _pair(low: float | None, high: float | None) -> str:
    if low is None or high is None:
        return "not estimable"
    return f"{low:.4f} to {high:.4f}"


def _summary_lines(analysis: Analysis) -> str:
    lines = [
        (
            "Per-state ROC-AUC lift, primary seed, states with at least "
            "11 counties and both outcome classes."
        )
    ]
    for summary in analysis.state_summaries:
        if summary.median_lift is None:
            lines.append(f"{summary.family}: no estimable state lift at n >= {SMALL_CELL}.")
            continue
        lines.append(
            f"{summary.family}: {summary.estimable_n} states, "
            f"median lift {summary.median_lift:.4f}, "
            f"positive lifts {summary.positive_n}."
        )
    return " ".join(lines)


def _state_table(analysis: Analysis) -> str:
    lines = [
        (
            "Per-state ROC-AUC on the primary seed. A blank AUC means the state "
            "has one outcome class. States with fewer than 11 counties are listed "
            "and marked small n. This write-up may show those counts. Lab aggregate "
            "tables suppress them."
        ),
        "",
        (
            "| State | Counties | Published | Note | Logit tick AUC "
            "| Logit regime AUC | Logit lift | Tree lift |"
        ),
        "| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    states = sorted({item.state for item in analysis.state_lifts})
    for state in states:
        rows = [item for item in analysis.state_lifts if item.state == state]
        logistic = next(item for item in rows if item.family == FAMILY_LOGISTIC)
        tree = next(item for item in rows if item.family == FAMILY_GBT)
        note = "small n" if logistic.county_n < SMALL_CELL else ""
        lines.append(
            "| "
            + " | ".join(
                (
                    state,
                    str(logistic.county_n),
                    str(logistic.published_n),
                    note,
                    _fmt(logistic.baseline_auc),
                    _fmt(logistic.challenger_auc),
                    _fmt(logistic.lift),
                    _fmt(tree.lift),
                )
            )
            + " |"
        )
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.4f}"


def _primary(analysis: Analysis, family: str) -> FamilySeedResult:
    for fit in analysis.fits:
        if fit.family == family and fit.seed == SEED_PRIMARY:
            return fit
    raise ValueError("primary fit is missing")
