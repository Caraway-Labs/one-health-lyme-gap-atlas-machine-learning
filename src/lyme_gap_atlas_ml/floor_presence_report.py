"""Render the issue 188 write-up. County rows stay out of the text."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from lyme_gap_atlas_ml.floor_presence import (
    BOOTSTRAP_REPLICATES,
    BOOTSTRAP_SEED,
    EXPECTED_ABSENT,
    EXPECTED_COUNTIES,
    EXPECTED_PUBLISHED,
    FAMILY_GBT,
    FAMILY_LOGISTIC,
    FEATURE_BASELINE,
    FEATURE_CHALLENGER,
    PERMUTATION_DRAWS,
    PERMUTATION_SEED,
    SEED_PRIMARY,
    SEED_SECOND,
    SHUFFLE_SEED,
    SMALL_CELL,
    SPEC_ID,
    Analysis,
    FamilySeedResult,
    StateError,
    StateModelError,
)

DOC_PATH = "docs/eda/188-floor-presence-regime.md"
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
            "# 188: Does a state reporting regime explain a missing published floor?",
            "",
            f"- Issue: [#188]({_ISSUE}/188); program epic [#22]({_ISSUE}/22).",
            "- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` and `CURRENT_RELEASE_V`.",
            "- Release: `governed-2026-10-15-january-climate-prod`.",
            cohort,
            "",
            "## Method and assumptions",
            "",
            f"Spec [{SPEC_ID}](188-analysis-spec.md), frozen before the fit.",
            "The regime feature is the #123 publication-free profile, rebuilt inside each",
            "leave-state-out fold so the held-out state's own county floors are not an input.",
            "The #123 descriptive groups are not fit. #121 axes and the #120 community type",
            "are not features.",
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
            "- Entry points: `sql/validation/188_floor_presence.sql`,",
            "  `scripts/eda_188_floor_presence.py`, `src/lyme_gap_atlas_ml/floor_presence.py`.",
            "- Commands: see the reproducibility section above.",
            (
                "- Transient artifacts not committed: chart PNGs under ignored "
                "`artifacts/charts/188/`."
            ),
            "  No county extract.",
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
    """Return the seven-section comment shared by the issue and the pull request."""
    logistic = _fit(analysis, FAMILY_LOGISTIC, SEED_PRIMARY)
    gbt = _fit(analysis, FAMILY_GBT, SEED_PRIMARY)
    logistic_second = _fit(analysis, FAMILY_LOGISTIC, SEED_SECOND)
    gbt_second = _fit(analysis, FAMILY_GBT, SEED_SECOND)
    count_text = ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
    failures = ", ".join(analysis.decision.reasons) if analysis.decision.reasons else "none"
    method = (
        f"Spec [{SPEC_ID}](docs/eda/188-analysis-spec.md), frozen before the fit. "
        "Leave-one-state-out on 51 states. Baseline: SVI percentile, uninsured percentile, "
        "rural-urban category, and log population. Challenger: baseline plus the #123 "
        "publication-free regime, Ward k=2, refit on the other states and assigned to the "
        "held-out state by the nearest training centroid. Logistic regression uses L2 with "
        "C=1.0. Trees use a depth-3 gradient booster with L2 regularization 1.0. "
        f"Seeds {SEED_PRIMARY} and {SEED_SECOND}. The lift interval resamples states "
        f"{BOOTSTRAP_REPLICATES} times with seed {BOOTSTRAP_SEED}. A real lift needs a "
        "ROC-AUC interval whose lower end is above 0.01, a PR-AUC interval above 0, and a "
        "Brier interval whose upper end is below 0.005, after the leakage tests pass."
    )
    context = (
        "#123 publication-free groups were the profile allowed for a later county model. "
        "This is that model, with the regime rebuilt out of fold. The #123 descriptive "
        "groups stay out because they use the publication share. #121 county contrasts are "
        "not features. #120 community types are not features. #107 counted 19 states and "
        "1,437 counties with no published county floor. A regime built from the state's own "
        "floors would look stronger than this leakage-safe feature."
    )
    sections = [
        "1. Question",
        "",
        (
            "How well do county demographics alone separate a published human floor from its "
            "absence, and how much does the state reporting regime add once the held-out "
            "state's own floors are kept out of that feature?"
        ),
        "",
        "2. Method (and why; link the spec)",
        "",
        method,
        "",
        "3. Key findings with numbers",
        "",
        _reading(analysis),
        "",
        _score_table(logistic, gbt, logistic_second, gbt_second),
        "",
        _lift_lines(logistic, gbt),
        "",
        (
            f"Label invariance: {analysis.leakage_invariant}. "
            f"Shuffled-label logistic ROC-AUC lift, seed {SHUFFLE_SEED}: "
            f"{analysis.shuffled_auc_lift:.4f}."
        ),
        (
            f"SVI rescaled by 100: {analysis.svi_rescaled}. "
            f"Uninsured percentile rescaled by 100: {analysis.uninsured_rescaled}. "
            f"Cohort matches 651 and 2493: {analysis.cohort_matches_expected}."
        ),
        "",
        (
            "Permutation importance is the drop in pooled ROC-AUC after shuffling one column, "
            f"primary seed, {PERMUTATION_DRAWS} draws, seed {PERMUTATION_SEED}."
        ),
        "",
        _importance_table(analysis),
        "",
        (
            "Calibration uses ten equal-count bins of predicted probability, primary seed. "
            "The share is the share with a published floor."
        ),
        "",
        _calibration_table(analysis),
        "",
        (
            "Per-state errors use probability 0.5 on the primary seed. States with fewer than "
            "11 counties are listed and marked small n. This write-up may show those counts. "
            "Lab aggregate tables suppress them."
        ),
        "",
        _state_table(analysis),
        "",
        context,
        "",
        "4. Caveats",
        "",
        (
            "Counts are surveillance signals and lower bounds. The published floor starts at "
            "the CDC floor of 5. It is not a disease rate and not causation. No records and "
            "Unknown are not negatives. A missing floor is not zero. Predictions are not a "
            "risk score, not a production score, and not for a public page."
        ),
        (
            "The regime still uses the state's tick-documentation share, pathogen-documentation "
            "share, and rural mix. County rural-urban code is already in the baseline, so some "
            "of the regime is a state rural summary. Human surveillance is calendar 2023. SVI, "
            "uninsured share, and population are 2022. Tick and pathogen status are cumulative "
            "through 2025-12-31. The state bootstrap does not cover dependence that crosses a "
            "state line."
        ),
        (
            "Demographics move together, so permutation importance splits credit among "
            "correlated columns. The 0.5 error count is not a tuned operating point."
        ),
        "",
        "5. Disposition",
        "",
        f"Method: {analysis.decision.method}. Product: {analysis.decision.product}.",
        (
            f"Leakage checks passed: {analysis.decision.leakage_ok}. "
            f"Logistic real lift: {analysis.decision.logistic_real_lift}. "
            f"Tree real lift: {analysis.decision.gbt_real_lift}."
        ),
        f"Rule failures: {failures}.",
        "",
        "6. Artifacts",
        "",
        f"run_id: {run_id}",
        "",
        f"Snowflake row counts: {count_text}.",
        "",
        (
            "SELECT grant on EXPERIMENTS.FLOOR_PRESENCE_PREDICTIONS_188 "
            f"to OH_LYME_PROD_READ: {grant}."
        ),
        "",
        drive_note,
        "",
        f"Doc: {DOC_PATH}",
        "",
        "Spec: docs/eda/188-analysis-spec.md",
        "",
        "7. Reproducibility",
        "",
        f"Commit: {commit}",
        "Release: governed-2026-10-15-january-climate-prod",
        (
            f"Seeds: logistic and trees {SEED_PRIMARY} and {SEED_SECOND}; "
            f"bootstrap {BOOTSTRAP_SEED}; permutation {PERMUTATION_SEED}; "
            f"shuffled labels {SHUFFLE_SEED}."
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
            "python scripts/eda_188_floor_presence.py"
        ),
        "uv run python scripts/verify.py",
        "```",
    ]
    return "\n".join(sections) + "\n"


def _reading(analysis: Analysis) -> str:
    logistic = _fit(analysis, FAMILY_LOGISTIC, SEED_PRIMARY)
    gbt = _fit(analysis, FAMILY_GBT, SEED_PRIMARY)
    base = logistic.baseline.roc_auc
    chal = logistic.challenger.roc_auc
    tree_lift = gbt.challenger.roc_auc - gbt.baseline.roc_auc
    logistic_band = _fmt_interval(logistic.auc_lift.low, logistic.auc_lift.high)
    tree_band = _fmt_interval(gbt.auc_lift.low, gbt.auc_lift.high)
    lead = (
        f"On the primary seed, logistic ROC-AUC is {base:.4f} for demographics alone "
        f"and {chal:.4f} with the leakage-safe regime "
        f"(lift {chal - base:.4f}, interval {logistic_band}). "
        f"The tree model moves from {gbt.baseline.roc_auc:.4f} "
        f"to {gbt.challenger.roc_auc:.4f} "
        f"(lift {tree_lift:.4f}, interval {tree_band})."
    )
    if analysis.decision.product == "advance":
        tail = (
            " Both families clear the frozen lift bar. The regime adds separation beyond "
            "the county profile. That is a reason to keep the feature in a later design "
            "discussion. It is not a score to publish."
        )
    elif analysis.decision.method == "keep" and analysis.decision.product == "stop":
        tail = (
            " The leakage-safe regime does not clear the frozen lift bar for either family. "
            "Do not carry the regime forward as a product input. The method did answer the "
            "question."
        )
    elif analysis.decision.method == "revise":
        tail = (
            " A leakage or stability check failed, so the lift is not evidence for the "
            "regime feature."
        )
    else:
        tail = (
            " The families do not agree on a lift that clears the bar. The regime feature "
            "is not ready to carry forward."
        )
    return lead + tail


def _score_table(
    logistic: FamilySeedResult,
    gbt: FamilySeedResult,
    logistic_second: FamilySeedResult,
    gbt_second: FamilySeedResult,
) -> str:
    header = (
        "| Family | Seed | Base AUC | Chal AUC | Base PR | Chal PR | Base Brier | Chal Brier |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    )
    rows = [_score_line(item) for item in (logistic, logistic_second, gbt, gbt_second)]
    return "\n".join((*header, *rows))


def _score_line(fit: FamilySeedResult) -> str:
    return (
        f"| {fit.family} | {fit.seed} | {fit.baseline.roc_auc:.4f} | "
        f"{fit.challenger.roc_auc:.4f} | {fit.baseline.pr_auc:.4f} | "
        f"{fit.challenger.pr_auc:.4f} | {fit.baseline.brier:.4f} | "
        f"{fit.challenger.brier:.4f} |"
    )


def _lift_lines(logistic: FamilySeedResult, gbt: FamilySeedResult) -> str:
    logistic_line = (
        "Logistic primary lifts, challenger minus baseline: "
        f"ROC-AUC {_fmt_interval(logistic.auc_lift.low, logistic.auc_lift.high)}, "
        f"PR-AUC {_fmt_interval(logistic.pr_lift.low, logistic.pr_lift.high)}, "
        f"Brier {_fmt_interval(logistic.brier_lift.low, logistic.brier_lift.high)}."
    )
    tree_line = (
        "Tree primary lifts: "
        f"ROC-AUC {_fmt_interval(gbt.auc_lift.low, gbt.auc_lift.high)}, "
        f"PR-AUC {_fmt_interval(gbt.pr_lift.low, gbt.pr_lift.high)}, "
        f"Brier {_fmt_interval(gbt.brier_lift.low, gbt.brier_lift.high)}."
    )
    return "\n".join((logistic_line, tree_line))


def _importance_table(analysis: Analysis) -> str:
    lines = [
        "| Family | Feature set | Feature | Mean AUC drop |",
        "| --- | --- | --- | ---: |",
    ]
    for item in analysis.importance:
        lines.append(
            f"| {item.family} | {item.feature_set} | {item.feature} | {item.auc_drop:.4f} |"
        )
    return "\n".join(lines)


def _calibration_table(analysis: Analysis) -> str:
    lines = [
        "| Family | Feature set | Bin | n | Mean predicted | Observed share |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in analysis.calibration:
        if row.family != FAMILY_LOGISTIC or row.n < SMALL_CELL:
            continue
        lines.append(
            f"| {row.family} | {row.feature_set} | {row.bin_index} | {row.n} | "
            f"{row.mean_predicted:.4f} | {row.observed_rate:.4f} |"
        )
    lines.append("")
    lines.append("Tree calibration bins are stored in `EDA.METRICS_LONG` for this run.")
    return "\n".join(lines)


def _state_table(analysis: Analysis) -> str:
    lines = [
        (
            "| State | Counties | Published | Note | Logit base err | Logit chal err | "
            "Tree base err | Tree chal err | Logit base Brier | Logit chal Brier |"
        ),
        "| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for state in analysis.state_errors:
        note = "small n" if state.county_n < SMALL_CELL else ""
        cells = [
            state.state,
            str(state.county_n),
            str(state.published_n),
            note,
            str(_errors(state, FAMILY_LOGISTIC, FEATURE_BASELINE)),
            str(_errors(state, FAMILY_LOGISTIC, FEATURE_CHALLENGER)),
            str(_errors(state, FAMILY_GBT, FEATURE_BASELINE)),
            str(_errors(state, FAMILY_GBT, FEATURE_CHALLENGER)),
            f"{_brier(state, FAMILY_LOGISTIC, FEATURE_BASELINE):.4f}",
            f"{_brier(state, FAMILY_LOGISTIC, FEATURE_CHALLENGER):.4f}",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _errors(state: StateError, family: str, feature: str) -> int:
    return _model(state, family, feature).errors_at_half


def _brier(state: StateError, family: str, feature: str) -> float:
    return _model(state, family, feature).brier


def _model(state: StateError, family: str, feature: str) -> StateModelError:
    for model in state.models:
        if model.family == family and model.feature_set == feature:
            return model
    raise KeyError(family)


def _fit(analysis: Analysis, family: str, seed: int) -> FamilySeedResult:
    for fit in analysis.fits:
        if fit.family == family and fit.seed == seed:
            return fit
    raise KeyError(family)


def _fmt_interval(low: float | None, high: float | None) -> str:
    if low is None or high is None:
        return "not estimable"
    return f"{low:.4f} to {high:.4f}"


def chart_frames(analysis: Analysis) -> dict[str, Sequence[tuple[str, float]]]:
    """Aggregate series for the charts. No county names and no small-cell rows."""
    logistic = _fit(analysis, FAMILY_LOGISTIC, SEED_PRIMARY)
    gbt = _fit(analysis, FAMILY_GBT, SEED_PRIMARY)
    return {
        "auc": (
            ("Logistic baseline", logistic.baseline.roc_auc),
            ("Logistic regime", logistic.challenger.roc_auc),
            ("Tree baseline", gbt.baseline.roc_auc),
            ("Tree regime", gbt.challenger.roc_auc),
        ),
        "lift": (
            ("Logistic", logistic.challenger.roc_auc - logistic.baseline.roc_auc),
            ("Tree", gbt.challenger.roc_auc - gbt.baseline.roc_auc),
        ),
    }
