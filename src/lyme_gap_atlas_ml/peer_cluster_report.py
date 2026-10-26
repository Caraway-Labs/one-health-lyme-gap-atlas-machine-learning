"""Issue 110 results write-up. County names stay in this text, not in chart frames."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from lyme_gap_atlas_ml.coverage_audit import PINNED_RELEASE_ID
from lyme_gap_atlas_ml.peer_clusters import (
    ALT_SEED,
    K_PRIMARY,
    OCT13_SILHOUETTE,
    OCT13_WEIGHT_ARI,
    PRIMARY_SEED,
    SPEC_ID,
    Analysis,
    SliceFit,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import FindingRecord

STABILITY_COLUMNS = (
    "seed_ari",
    "state_low",
    "county_low",
    "region_min",
    "state_median",
    "ward_ari",
    "weight_ari",
    "silhouette",
)


def build_findings(analysis: Analysis) -> tuple[FindingRecord, ...]:
    """Aggregate statements. County names and five-digit ids stay out of this text."""
    context = analysis.slice("context")
    decision = analysis.decision
    sizes = "match" if decision.sizes_reproduced else "do not match"
    silhouette = "matches" if decision.silhouette_reproduced else "does not match"
    weight = "matches" if decision.weight_reproduced else "does not match"
    n = context.n if context.estimable else 0
    reproduction = (
        f"Context-only K-means at k={K_PRIMARY} {sizes} the October 13 size multiset. "
        f"Silhouette {_fmt(context.silhouette)} {silhouette} {_fmt(OCT13_SILHOUETTE)}. "
        f"Doubled SVI-weight adjusted Rand {_fmt(context.weight_ari)} {weight} "
        f"{_fmt(OCT13_WEIGHT_ARI)}."
    )
    stability = (
        f"Context-only seed adjusted Rand is {_fmt(context.seed_ari)}. "
        f"State-cluster adjusted Rand lower endpoint is {_fmt(context.state_low)}. "
        f"Region-holdout minimum is {_fmt(context.region_min)}. "
        f"Ward adjusted Rand is {_fmt(context.ward_ari)}."
    )
    call = (
        f"Cluster decision is {decision.cluster}. Product call is {decision.product}. "
        f"Multi-domain estimable is {str(analysis.slice('multidomain').estimable).lower()}."
    )
    disposition = decision.cluster if decision.cluster in {"keep", "revise", "stop"} else "stop"
    return (
        FindingRecord(
            topic="peer-clusters",
            statement=reproduction,
            disposition=disposition,
            n_underlying=max(n, 0),
            effect_size=context.silhouette,
            evidence={"comparison": "october-13", "slice": "context"},
            uncertainty_note="October 13 comparison uses the frozen absolute tolerances.",
        ),
        FindingRecord(
            topic="peer-clusters",
            statement=stability,
            disposition=disposition,
            n_underlying=max(n, 0),
            effect_size=context.state_low,
            ci_low=context.state_low,
            ci_high=context.state_high,
            evidence={"interval": "state-cluster", "slice": "context"},
            uncertainty_note="State-cluster percentile interval. It resamples states.",
        ),
        FindingRecord(
            topic="peer-clusters",
            statement=call,
            disposition=disposition,
            n_underlying=max(n, 0),
            evidence={"product": decision.product},
            uncertainty_note="The product call does not authorize a model or a public score.",
        ),
    )


def profile_frame(analysis: Analysis) -> tuple[dict[str, object], ...]:
    """Standardized cluster means for the chart. Small clusters are omitted."""
    rows: list[dict[str, object]] = []
    for name in ("context", "multidomain"):
        fit = analysis.slice(name)
        if not fit.estimable or not _sizes_ok(fit):
            continue
        for cluster_id, center in enumerate(fit.centers, start=1):
            size = fit.sizes[cluster_id - 1]
            for feature, mean in zip(fit.features, center, strict=True):
                rows.append(
                    {
                        "slice": name,
                        "cluster": f"Group {cluster_id}",
                        "feature": feature,
                        "mean": mean,
                        "n": size,
                    }
                )
    return tuple(rows)


def stability_frame(
    analysis: Analysis,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[tuple[float | None, ...], ...]]:
    """Stability values by slice. A missing index stays missing."""
    rows: list[tuple[float | None, ...]] = []
    names: list[str] = []
    for fit in analysis.slices:
        if not fit.estimable:
            continue
        names.append(fit.name)
        values = {
            "seed_ari": fit.seed_ari,
            "state_low": fit.state_low,
            "county_low": fit.county_low,
            "region_min": fit.region_min,
            "state_median": fit.state_holdout_median,
            "ward_ari": fit.ward_ari,
            "weight_ari": fit.weight_ari,
            "silhouette": fit.silhouette,
        }
        rows.append(tuple(values[column] for column in STABILITY_COLUMNS))
    return tuple(names), STABILITY_COLUMNS, tuple(rows)


def render_comment(
    analysis: Analysis,
    *,
    run_id: str,
    git_commit: str,
    row_counts: Mapping[str, int],
    drive_links: Sequence[tuple[str, str]],
    missing_charts: Sequence[str],
    grant_note: str,
) -> str:
    """The issue comment and the pull-request body."""
    context = analysis.slice("context")
    multi = analysis.slice("multidomain")
    lines = [
        "1. Question",
        "",
        "Do the four context-only clusters in epic #22 section 4.1 reproduce on the pinned "
        "release, are they stable enough to keep, and can multi-domain environmental, vector, "
        "human, and population features reveal stable peer-county groups?",
        "",
        "2. Method (and why; link the spec)",
        "",
        f"Spec [{SPEC_ID}](docs/eda/110-analysis-spec.md), frozen before the fit. "
        "The October 13 fitting code is not in this repository. The recorded groups used "
        "social-vulnerability percentile and log population. This run repeats that pair as "
        "the context-only slice, with z-score standardization and Euclidean K-means at k=4, "
        "because that is the simplest distance baseline that can be compared with the recorded "
        "silhouette and the doubled-SVI-weight adjusted Rand index. Ward clustering is the "
        "second baseline on the same matrix. Coverage statuses stay in their own slice so a "
        "peer group is not defined by reporting behavior. Climate means enter only the climate "
        "and multi-domain slices, and a missing day is left out of the county mean. "
        f"Seeds {PRIMARY_SEED} and {ALT_SEED}. State-cluster and county-resample intervals use "
        "the #116 helpers on the context-only and multi-domain slices.",
        "",
        "3. Key findings with numbers",
        "",
        _findings_text(analysis, context, multi),
        "",
        _representatives_text(analysis),
        "",
        "4. Caveats",
        "",
        "Counts are surveillance signals. A published human floor is a lower bound (CDC floor 5), "
        "not incidence or risk. No records and Unknown are not negatives. Missing is not zero. "
        "The context fields, the rural-urban code, tick status, and the January 2025 climate "
        "window are not one time base. State-cluster intervals do not cover dependence that "
        "crosses a state line. No county-adjacency table was used. The October 13 seed, "
        "standardization, and scikit-learn version were not recorded, so a numeric difference "
        "can come from those choices or from the release pin. Land cover is not a national "
        f"feature on this run (NLCD county count {_fmt_int(analysis.nlcd_counties)}). "
        "Density methods ran only if the frozen gate opened.",
        "",
        "5. Disposition: advance / investigate / stop (or keep / revise / stop)",
        "",
        f"Cluster decision: {analysis.decision.cluster}. "
        f"Product call: {analysis.decision.product}.",
        "",
        _recommendation(analysis),
        "",
        "6. Artifacts",
        "",
        f"run_id: {run_id}",
        _counts(row_counts),
        _drives(drive_links, missing_charts),
        grant_note,
        "Doc: docs/eda/110-peer-county-clusters.md",
        "Spec: docs/eda/110-analysis-spec.md",
        "",
        "7. Reproducibility",
        "",
        f"Commit: {git_commit}",
        f"Release: {PINNED_RELEASE_ID}",
        f"Seeds: primary {PRIMARY_SEED}, alternate {ALT_SEED}. "
        "Bootstrap uses those seeds inside the #116 helpers. "
        "Primary fits use n_init=10. Each bootstrap replicate uses n_init=1.",
        "Commands:",
        "uv sync --locked --extra dev --extra snowflake",
        "uv run python scripts/check_ml_agent_context.py",
        "MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_110_peer_clusters.py",  # noqa: E501
        "uv run python scripts/verify.py",
        "",
        "County-level cluster rows were not written to git or Drive. "
        "Transient chart PNG files under artifacts/charts/110 were uploaded or listed as missing "
        "and were not committed.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def render_eda_record(
    analysis: Analysis,
    *,
    run_id: str,
    git_commit: str,
    row_counts: Mapping[str, int],
    drive_links: Sequence[tuple[str, str]],
    missing_charts: Sequence[str],
    grant_note: str,
) -> str:
    """Durable EDA record. The comment sections are the findings."""
    comment = render_comment(
        analysis,
        run_id=run_id,
        git_commit=git_commit,
        row_counts=row_counts,
        drive_links=drive_links,
        missing_charts=missing_charts,
        grant_note=grant_note,
    )
    context = analysis.slice("context")
    header = "\n".join(
        [
            "# 110: Do stable peer-county groups exist on the pinned release?",
            "",
            "- Issue: [#110](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/110); "  # noqa: E501
            "parent [#22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). "  # noqa: E501
            "Question: do the four context-only clusters reproduce, are they stable enough to keep, "  # noqa: E501
            "and can multi-domain features reveal stable peer groups?",
            f"- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`, "
            f"county means from `CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V`, and an NLCD county count "  # noqa: E501
            f"from `CURRENT_COUNTY_OBSERVATIONS_V`. Release `{PINNED_RELEASE_ID}`.",
            "- Cohort: the 3,144-county atlas. Context-only uses complete log population and SVI. "
            "Climate and multi-domain use counties with at least 20 observed-or-zero January days "
            "for average temperature and precipitation. Coverage statuses are a separate slice.",
            "",
            "## Method and assumptions",
            "",
            f"Spec [{SPEC_ID}](110-analysis-spec.md), frozen before the fit. "
            f"Context-only exclusions {context.excluded}. "
            f"Percentile columns divided by 100: {', '.join(context.percentile_divided) or 'none'}. "  # noqa: E501
            "No missing value was replaced with zero. "
            f"Cluster decision {analysis.decision.cluster}. Product call {analysis.decision.product}.",  # noqa: E501
            "",
            "## Material findings and limits",
            "",
            comment,
            "",
            "## Decision",
            "",
            _decision_label(analysis),
            "",
            "## Reproduction and retained evidence",
            "",
            f"- Code revision: `{git_commit}`. Run `{run_id}`. Spec `{SPEC_ID}`.",
            "- Entry points: `sql/validation/110_peer_clusters.sql`, "
            "`scripts/eda_110_peer_clusters.py`, `src/lyme_gap_atlas_ml/peer_clusters.py`.",
            "- Commands: `uv run python scripts/check_ml_agent_context.py` and "
            "`MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_110_peer_clusters.py`.",  # noqa: E501
            "- Lifecycle: descriptive EDA only. No Tier 1 change and no promotion review.",
            "- Transient artifacts intentionally not committed: county-level frames, "
            "`outputs/110-run-id.txt`, and `artifacts/charts/110/*.png`.",
            "",
        ]
    )
    return header


def _findings_text(analysis: Analysis, context: SliceFit, multi: SliceFit) -> str:
    parts = [
        _slice_paragraph("Context-only", context),
        (
            "October 13 reference: sizes 703, 828, 461, and 1152; silhouette 0.389; "
            f"SVI-weight adjusted Rand 0.365. This run: sizes {_size_text(context)}; "
            f"silhouette {_fmt(context.silhouette)}; SVI-weight adjusted Rand {_fmt(context.weight_ari)}. "  # noqa: E501
            f"Sizes reproduced: {analysis.decision.sizes_reproduced}. "
            f"Silhouette reproduced: {analysis.decision.silhouette_reproduced}. "
            f"Weight result reproduced: {analysis.decision.weight_reproduced}. "
            "The epic text says the groups were stable across seeds and that doubling the SVI "
            "weight changed membership. Seed adjusted Rand on this pin is "
            f"{_fmt(context.seed_ari)}. A difference from 0.389 or 0.365 is left as a difference: "
            "the original seed, scaler, and library version are not in the repository, and the "
            f"pinned release is {PINNED_RELEASE_ID}."
        ),
        _slice_paragraph("Extended context", analysis.slice("extended")),
        _slice_paragraph("Climate", analysis.slice("climate")),
        _slice_paragraph("Coverage", analysis.slice("coverage")),
        _slice_paragraph("Multi-domain", multi),
        (
            "Surveillance check, context-only: publishing-state Cramér's V "
            f"{_fmt(context.cramer_publishing)}; Census-region Cramér's V {_fmt(context.cramer_region)}; "  # noqa: E501
            f"human-status Cramér's V {_fmt(context.cramer_human)}; tick-status Cramér's V "
            f"{_fmt(context.cramer_tick)}; largest non-publishing share "
            f"{_fmt(context.max_nonpublish_share)} "
            f"(count {_fmt_int(context.max_nonpublish_count)}). "
            "Multi-domain Census-region Cramér's V "
            f"{_fmt(multi.cramer_region)}."
        ),
        _density_text(context),
        _concept(),
    ]
    return "\n\n".join(parts)


def _slice_paragraph(title: str, fit: SliceFit) -> str:
    if not fit.estimable:
        return f"{title}: not estimable ({fit.note}). Excluded {fit.excluded}."
    return (
        f"{title}: n={fit.n}, excluded {fit.excluded}, silhouette {_fmt(fit.silhouette)}, "
        f"sizes {_size_text(fit)}, seed adjusted Rand {_fmt(fit.seed_ari)}, "
        f"state-cluster interval {_fmt(fit.state_low)} to {_fmt(fit.state_high)} "
        f"(estimable {fit.state_estimable}), county-resample interval {_fmt(fit.county_low)} to "
        f"{_fmt(fit.county_high)} (estimable {fit.county_estimable}), "
        f"region-holdout minimum {_fmt(fit.region_min)}, "
        f"state-holdout median {_fmt(fit.state_holdout_median)} "
        f"(minimum {_fmt(fit.state_holdout_min)}), Ward adjusted Rand {_fmt(fit.ward_ari)}, "
        f"SVI-weight adjusted Rand {_fmt(fit.weight_ari)}, unscaled adjusted Rand "
        f"{_fmt(fit.unscaled_ari)}. "
        f"Standardized means: {_means_text(fit)}."
    )


def _means_text(fit: SliceFit) -> str:
    if not _sizes_ok(fit):
        return "cluster means are suppressed because a cluster count is below 11"
    chunks: list[str] = []
    for cluster_id, center in enumerate(fit.centers, start=1):
        pairs = ", ".join(
            f"{feature} {_fmt(value)}" for feature, value in zip(fit.features, center, strict=True)
        )
        chunks.append(f"group {cluster_id} (n={fit.sizes[cluster_id - 1]}: {pairs})")
    return "; ".join(chunks)


def _representatives_text(analysis: Analysis) -> str:
    lines = [
        "Representative counties are the three nearest the cluster mean in standardized space."
    ]  # noqa: E501
    shown = [
        item
        for item in analysis.slice("context").representatives
        + analysis.slice("multidomain").representatives
    ]
    if not shown:
        lines.append("No representative counties were available.")
        return "\n".join(lines)
    lines.append("")
    header = (
        "| Slice | Group | Rank | County | State | Distance | Population | SVI | RUCC | "
        "Human | Tick | Pathogen |"
    )
    lines.append(header)
    lines.append("| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |")
    for item in shown:
        lines.append(
            "| "
            + " | ".join(
                [
                    item.slice_name,
                    str(item.cluster_id),
                    str(item.rank),
                    item.name,
                    item.state,
                    _fmt(item.distance),
                    str(int(item.population)),
                    _fmt(item.svi),
                    "" if item.rucc is None else str(item.rucc),
                    item.human,
                    item.tick,
                    item.pathogen,
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _density_text(context: SliceFit) -> str:
    density = context.density
    if density is None or not density.opened:
        return (
            "The density gate stayed closed, so Gaussian mixture, DBSCAN, and HDBSCAN were not fit."
        )
    return (
        "The density gate opened. "
        f"Gaussian-mixture adjusted Rand {_fmt(density.gmm_ari)}, silhouette {_fmt(density.gmm_silhouette)}. "  # noqa: E501
        f"DBSCAN clusters {_fmt_int(density.dbscan_clusters)}, noise {_fmt_int(density.dbscan_noise)}. "  # noqa: E501
        f"HDBSCAN clusters {_fmt_int(density.hdbscan_clusters)}, noise {_fmt_int(density.hdbscan_noise)}. "  # noqa: E501
        "Those fits were not used to choose k."
    )


def _concept() -> str:
    return (
        "Find similar counties, as text only: a reviewer would pick a county and see the nearest "
        "counties in one frozen standardized space, with the distance and that cluster's aggregate "
        "profile (size, social-vulnerability percentile, uninsured percentile, rural-urban code, "
        "and January temperature and precipitation when the county is in the climate cohort). "
        "Surveillance status would be shown beside the peers as documentation. It would not be a "
        "distance feature, a risk score, or a priority rank. This run does not build that view."
    )


def _recommendation(analysis: Analysis) -> str:
    decision = analysis.decision
    if decision.product == "stop":
        return (
            "Stop here. The context-only fit did not produce a partition that can be quoted. "
            "Do not draft a peer-county tool from this run, and do not change the tiers."
        )
    if decision.product == "advance" and decision.cluster == "keep":
        return (
            "The multi-domain groups met the frozen stability bars and were not a restatement of "
            "Census region or of non-publishing states. A later story could design the text-only "
            "similarity view. This run still does not authorize a model, an API, or a public score."
        )
    if decision.cluster == "keep":
        return (
            "The four context-only groups can be quoted as a descriptive partition of size and "
            "social vulnerability. They are not stable enough, or not independent enough of region "
            "or reporting, to become a find-similar-counties product. Keep them as description. "
            "Do not build the view, and do not change the tiers."
        )
    reasons = ", ".join(decision.reasons) if decision.reasons else "the frozen bars"
    return (
        "Do not keep these groups as peer counties. "
        f"The context-only partition missed {reasons}. "
        "The October 13 note already treated the SVI-weight change as material, and this pin is "
        "held to that same kind of bar. Multi-domain features did not clear the product bar either. "  # noqa: E501
        "Investigate only if a later story freezes a different peer definition. "
        "Do not build a similarity score, and do not change the tiers."
    )


def _decision_label(analysis: Analysis) -> str:
    if analysis.decision.product == "advance":
        return (
            "FOLLOW_UP. The product call is advance, which only proposes a later design story. "
            "It is not permission to ship a score."
        )
    if analysis.decision.cluster == "stop":
        return "NOT_ESTIMABLE. The context-only fit did not clear the stop gates."
    return (
        "INCONCLUSIVE. The groups are descriptive at most. The product call is investigate or the "
        "cluster decision is revise, so no similarity view should be built from this fit."
    )


def _counts(row_counts: Mapping[str, int]) -> str:
    if not row_counts:
        return "Snowflake row counts: not written."
    body = ", ".join(f"{name}={count}" for name, count in row_counts.items())
    return f"Snowflake row counts: {body}."


def _drives(links: Sequence[tuple[str, str]], missing: Sequence[str]) -> str:
    parts = [f"{name}: {url}" for name, url in links]
    if missing:
        parts.append("Missing charts: " + ", ".join(missing))
    if not parts:
        return "Drive: no charts registered."
    return "Drive: " + "; ".join(parts)


def _size_text(fit: SliceFit) -> str:
    if not fit.sizes:
        return "none"
    if not _sizes_ok(fit):
        return "suppressed"
    return "/".join(str(size) for size in fit.sizes)


def _sizes_ok(fit: SliceFit) -> bool:
    small = [size for size in fit.sizes if 0 < size < 11]
    if not small:
        return True
    return not (len(small) == 1 or sum(small) < 11)


def _fmt(value: float | None) -> str:
    if value is None:
        return "not estimable"
    return f"{value:.4f}"


def _fmt_int(value: int | None) -> str:
    if value is None:
        return "not estimable"
    return str(value)
