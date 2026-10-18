"""Serializable story 119 fit record. Class ids stay unnamed here."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from lyme_gap_atlas_ml.latent_class_fit import ClassSelection
from lyme_gap_atlas_ml.latent_class_inputs import (
    BUNDLE_SHA256,
    DATASET_ID,
    DATASET_VERSION,
    FEATURE_SET_ID,
    FEATURE_SET_VERSION,
    RELEASE_ID,
    LatentClassInputError,
    SurveillanceCounty,
)

ESTIMAND_ORDER = ("four-state", "tick-pathogen")
_PROBABILITY_TOLERANCE = 1e-6


def build_result_document(
    counties: Sequence[SurveillanceCounty],
    selections: Mapping[str, ClassSelection],
    *,
    code_revision: str,
    numpy_version: str,
    sklearn_version: str,
) -> dict[str, object]:
    """Build the repository record of both fits and every county assignment."""
    if tuple(selections) != ESTIMAND_ORDER:
        raise LatentClassInputError("both estimands are required, in the declared order")
    estimands = {name: _estimand_payload(counties, selections[name]) for name in ESTIMAND_ORDER}
    return {
        "schema": "atlas-ml-latent-class-result/119-v1",
        "experiment": {"id": "surveillance-latent-class-experiment", "version": "v1"},
        "dataset": {"id": DATASET_ID, "version": DATASET_VERSION},
        "feature_set": {"id": FEATURE_SET_ID, "version": FEATURE_SET_VERSION},
        "release_id": RELEASE_ID,
        "bundle_sha256": BUNDLE_SHA256,
        "county_count": len(counties),
        "code_revision": code_revision,
        "dependencies": {"numpy": numpy_version, "scikit-learn": sklearn_version},
        "estimator": "in-repository categorical latent class EM",
        "storage": "repository",
        "snowflake_objects_written": [],
        "estimands": estimands,
    }


def render_selection_note(document: Mapping[str, object], *, code_revision: str) -> str:
    """Describe class-count evidence without naming classes or a follow-up list."""
    estimands = document["estimands"]
    if not isinstance(estimands, Mapping):
        raise LatentClassInputError("result estimands are missing")
    sections = [
        "# ML #119 class-count selection",
        "",
        (
            "Owning task: [ML #133]"
            "(https://github.com/Caraway-Labs/"
            "one-health-lyme-gap-atlas-machine-learning/issues/133). "
            "The class count for each estimand was chosen by the rule in "
            "[119-validation-design.md](119-validation-design.md). "
            "The follow-up county list was not an input."
        ),
        "",
        f"Code revision at the fit: `{code_revision}`. "
        "The estimator is the categorical latent class EM in "
        "`lyme_gap_atlas_ml.latent_class_fit`. "
        "scikit-learn supplied the adjusted Rand index only. "
        "Training ran on the local machine. "
        "No Snowflake object was written. "
        "The read context was user MATTHEWCARAWAY, role OH_LYME_PROD_READ, "
        "database ONE_HEALTH_LYME_GAP_ATLAS_PROD, schema PRESENTATION, "
        "warehouse COMPUTE_WH, and empty secondary roles. "
        "Objects read: PRESENTATION.CURRENT_RELEASE_V and PRESENTATION.CURRENT_COUNTY_ATLAS_V. "
        "The model parameters and county assignments are in "
        "[119-latent-class-v1-result.json](../../config/experiments/119-latent-class-v1-result.json).",
        "",
        "Class identifiers are arbitrary labels from the primary seed. "
        "This note does not give them plain-language names.",
        "",
        "Reproduce the fit from the ignored county extract after the release check:",
        "",
        "```powershell",
        "uv run python scripts/fit_119_latent_class.py "
        "--counties outputs/119-latent-class/counties.json "
        "--release-id governed-2026-10-15-january-climate-prod "
        "--bundle-sha256 53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d "
        "--output config/experiments/119-latent-class-v1-result.json "
        "--note docs/methodology/119-class-count-selection.md",
        "```",
        "",
    ]
    for name in ESTIMAND_ORDER:
        payload = estimands[name]
        if not isinstance(payload, Mapping):
            raise LatentClassInputError("estimand payload is missing")
        sections.extend(_estimand_section(str(name), payload))
    sections.append(
        "A difference in library version or floating-point summation is recorded "
        "with the result dependencies. It is not a reason to change the class count."
    )
    sections.append("")
    return "\n".join(sections)


def _estimand_payload(
    counties: Sequence[SurveillanceCounty], selection: ClassSelection
) -> dict[str, object]:
    candidates = [
        {
            "n_classes": candidate.n_classes,
            "bic": candidate.bic,
            "log_likelihood": candidate.log_likelihood,
            "median_adjusted_rand_index": candidate.median_adjusted_rand_index,
            "adjusted_rand_indexes": list(candidate.adjusted_rand_indexes),
            "minimum_class_counties": candidate.minimum_class_counties,
            "stable": candidate.stable,
            "eligible": candidate.eligible,
        }
        for candidate in selection.candidates
    ]
    model = selection.model
    if model is None:
        return {
            "selected_classes": None,
            "blocked_reason": selection.blocked_reason,
            "candidates": candidates,
            "model": None,
            "assignments": [],
        }
    if len(model.hard_assignments) != len(counties) or len(model.probabilities) != len(counties):
        raise LatentClassInputError("assignment length does not match the county cohort")
    assignments: list[dict[str, object]] = []
    for county, class_id, probability in zip(
        counties, model.hard_assignments, model.probabilities, strict=True
    ):
        if abs(sum(probability) - 1.0) > _PROBABILITY_TOLERANCE:
            raise LatentClassInputError("class probabilities do not sum to 1")
        if class_id != max(range(len(probability)), key=probability.__getitem__):
            raise LatentClassInputError("hard assignment does not match the class probabilities")
        assignments.append(
            {
                "fips": county.fips,
                "state": county.state,
                "population": county.population,
                "class_id": class_id,
                "probability": [float(value) for value in probability],
            }
        )
    features = [
        {
            "name": feature_name,
            "levels": list(levels),
            "probability_given_class": [list(row) for row in class_rows],
        }
        for feature_name, levels, class_rows in zip(
            model.feature_names, model.levels, model.emissions, strict=True
        )
    ]
    return {
        "selected_classes": selection.selected_classes,
        "blocked_reason": None,
        "candidates": candidates,
        "model": {
            "seed": model.seed,
            "log_likelihood": model.log_likelihood,
            "bic": model.bic,
            "n_parameters": model.n_parameters,
            "converged": model.converged,
            "class_priors": list(model.class_priors),
            "features": features,
        },
        "assignments": assignments,
    }


def _as_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise LatentClassInputError("expected a number in the class-count table")
    return float(value)


def _estimand_section(name: str, payload: Mapping[str, object]) -> list[str]:
    selected = payload["selected_classes"]
    reason = payload["blocked_reason"]
    lines = [
        f"## {name}",
        "",
        f"Selected class count: `{selected}`.",
    ]
    if reason:
        lines.append(f"Blocked reason: {reason}.")
    lines.extend(
        [
            "",
            "| Classes | BIC | Median adjusted Rand index | Smallest class | Eligible |",
            "| ---: | ---: | ---: | ---: | --- |",
        ]
    )
    candidates = payload["candidates"]
    if not isinstance(candidates, list):
        raise LatentClassInputError("class-count candidates are missing")
    for candidate in candidates:
        if not isinstance(candidate, Mapping):
            raise LatentClassInputError("class-count candidate is malformed")
        bic = _as_float(candidate["bic"])
        rand_index = _as_float(candidate["median_adjusted_rand_index"])
        lines.append(
            f"| {candidate['n_classes']} | {bic:.3f} | {rand_index:.4f} | "
            f"{candidate['minimum_class_counties']} | {candidate['eligible']} |"
        )
    lines.append("")
    return lines
