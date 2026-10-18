"""Categorical latent class fit for story 119.

The model treats the indicators as independent within a class. Class count is
chosen from the frozen stability rule. Nothing in this module reads a
follow-up list.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median
from typing import cast

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import adjusted_rand_score  # type: ignore[import-untyped]

from lyme_gap_atlas_ml.latent_class_inputs import (
    ESTIMAND_A_COLUMNS,
    ESTIMAND_B_COLUMNS,
    LatentClassInputError,
    SurveillanceCounty,
)

ESTIMAND_A_LEVELS = (
    ("no_county_linked_record", "published_count_floor"),
    ("Established", "Reported", "No records", "Unknown"),
    ("Established", "Reported", "No records", "Unknown"),
    ("Present", "No records", "Unknown"),
)
ESTIMAND_B_LEVELS = ESTIMAND_A_LEVELS[1:]
_LOG_FLOOR = 1e-300


@dataclass(frozen=True)
class FitConfig:
    """Frozen class-count settings from the story 119 experiment."""

    class_counts: tuple[int, ...] = (2, 3, 4, 5, 6)
    primary_seed: int = 1192026
    alternate_seeds: tuple[int, ...] = (1192027, 1192028, 1192029, 1192030)
    random_starts: int = 20
    minimum_median_ari: float = 0.90
    minimum_class_counties: int = 30
    bic_margin: float = 6.0
    max_iterations: int = 200
    tolerance: float = 1e-8


@dataclass(frozen=True)
class ClassModel:
    """One fitted latent class model and its county assignments."""

    n_classes: int
    seed: int
    log_likelihood: float
    bic: float
    n_parameters: int
    converged: bool
    feature_names: tuple[str, ...]
    levels: tuple[tuple[str, ...], ...]
    class_priors: tuple[float, ...]
    emissions: tuple[tuple[tuple[float, ...], ...], ...]
    hard_assignments: tuple[int, ...]
    probabilities: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class ClassCountCandidate:
    """Stability evidence for one class count. It does not name a situation."""

    n_classes: int
    bic: float
    log_likelihood: float
    median_adjusted_rand_index: float
    adjusted_rand_indexes: tuple[float, ...]
    minimum_class_counties: int
    stable: bool
    eligible: bool


@dataclass(frozen=True)
class ClassSelection:
    """The class count chosen by the frozen rule, or a blocked selection."""

    selected_classes: int | None
    blocked_reason: str | None
    candidates: tuple[ClassCountCandidate, ...]
    model: ClassModel | None


def observations(
    counties: Sequence[SurveillanceCounty], estimand: str
) -> tuple[tuple[str, ...], ...]:
    """Return the indicator rows for one estimand, with blanks retained."""
    if estimand == "four-state":
        return tuple(county.estimand_a() for county in counties)
    if estimand == "tick-pathogen":
        return tuple(county.estimand_b() for county in counties)
    raise LatentClassInputError(f"unknown estimand: {estimand}")


def feature_names(estimand: str) -> tuple[str, ...]:
    """Return the admitted indicator names for one estimand."""
    if estimand == "four-state":
        return ESTIMAND_A_COLUMNS
    if estimand == "tick-pathogen":
        return ESTIMAND_B_COLUMNS
    raise LatentClassInputError(f"unknown estimand: {estimand}")


def feature_levels(estimand: str) -> tuple[tuple[str, ...], ...]:
    """Return the declared level order for one estimand."""
    if estimand == "four-state":
        return ESTIMAND_A_LEVELS
    if estimand == "tick-pathogen":
        return ESTIMAND_B_LEVELS
    raise LatentClassInputError(f"unknown estimand: {estimand}")


def select_class_count(
    rows: Sequence[Sequence[str]],
    levels: Sequence[Sequence[str]],
    names: Sequence[str],
    config: FitConfig | None = None,
) -> ClassSelection:
    """Choose K from stability and BIC. The follow-up list is not an argument."""
    settings = config or FitConfig()
    if not settings.alternate_seeds or settings.random_starts < 1:
        raise LatentClassInputError("stability fit requires alternate seeds and random starts")
    coded = _encode(rows, levels)
    level_counts = tuple(len(feature_levels_) for feature_levels_ in levels)
    primary = {
        n_classes: _fit_best(coded, level_counts, n_classes, settings.primary_seed, settings)
        for n_classes in settings.class_counts
    }
    candidates: list[ClassCountCandidate] = []
    for n_classes in settings.class_counts:
        model = primary[n_classes]
        if model is None:
            candidates.append(_failed_candidate(n_classes))
            continue
        alternate_models: list[ClassModel] = []
        failed = False
        for seed in settings.alternate_seeds:
            fitted = _fit_best(coded, level_counts, n_classes, seed, settings)
            if fitted is None:
                failed = True
                break
            alternate_models.append(fitted)
        if failed:
            candidates.append(_failed_candidate(n_classes))
            continue
        scores = tuple(
            float(adjusted_rand_score(model.hard_assignments, fitted.hard_assignments))
            for fitted in alternate_models
        )
        smallest = min(_class_sizes(model.hard_assignments, n_classes))
        stable = median(scores) >= settings.minimum_median_ari
        candidates.append(
            ClassCountCandidate(
                n_classes=n_classes,
                bic=model.bic,
                log_likelihood=model.log_likelihood,
                median_adjusted_rand_index=float(median(scores)),
                adjusted_rand_indexes=scores,
                minimum_class_counties=smallest,
                stable=stable,
                eligible=stable and smallest >= settings.minimum_class_counties,
            )
        )
    selected, reason = choose_class_count(candidates, bic_margin=settings.bic_margin)
    if selected is None:
        return ClassSelection(None, reason, tuple(candidates), None)
    chosen_model = primary[selected]
    if chosen_model is None:
        return ClassSelection(None, "selected class count has no fit", tuple(candidates), None)
    return ClassSelection(
        selected, None, tuple(candidates), _attach_labels(chosen_model, names, levels)
    )


def choose_class_count(
    candidates: Sequence[ClassCountCandidate], *, bic_margin: float
) -> tuple[int | None, str | None]:
    """Apply the frozen BIC margin to class counts that already passed stability."""
    eligible = [candidate for candidate in candidates if candidate.eligible]
    if not eligible:
        return None, "no class count met the stability rule"
    best_bic = min(candidate.bic for candidate in eligible)
    selected = min(
        candidate.n_classes for candidate in eligible if candidate.bic <= best_bic + bic_margin
    )
    return selected, None


def parameter_count(n_classes: int, level_counts: Sequence[int]) -> int:
    """Count free parameters for independent categorical indicators."""
    return (n_classes - 1) + n_classes * sum(count - 1 for count in level_counts)


def _encode(rows: Sequence[Sequence[str]], levels: Sequence[Sequence[str]]) -> NDArray[np.int64]:
    if not rows:
        raise LatentClassInputError("latent class fit requires at least one county")
    lookups = [
        {level: index for index, level in enumerate(feature_levels_)} for feature_levels_ in levels
    ]
    coded = np.empty((len(rows), len(levels)), dtype=np.int64)
    for row_index, row in enumerate(rows):
        if len(row) != len(levels):
            raise LatentClassInputError("observation width does not match the estimand")
        for feature_index, value in enumerate(row):
            try:
                coded[row_index, feature_index] = lookups[feature_index][value]
            except KeyError as error:
                raise LatentClassInputError(f"unrecognized level: {value}") from error
    return coded


def _fit_best(
    coded: NDArray[np.int64],
    level_counts: Sequence[int],
    n_classes: int,
    seed: int,
    config: FitConfig,
) -> ClassModel | None:
    sequence = np.random.SeedSequence(seed)
    best: ClassModel | None = None
    for child in sequence.spawn(config.random_starts):
        fitted = _fit_once(
            coded,
            level_counts,
            n_classes,
            np.random.default_rng(child),
            config.max_iterations,
            config.tolerance,
        )
        if fitted is None:
            continue
        if best is None or fitted.log_likelihood > best.log_likelihood:
            best = fitted
    if best is None:
        return None
    return ClassModel(
        n_classes=best.n_classes,
        seed=seed,
        log_likelihood=best.log_likelihood,
        bic=best.bic,
        n_parameters=best.n_parameters,
        converged=best.converged,
        feature_names=(),
        levels=(),
        class_priors=best.class_priors,
        emissions=best.emissions,
        hard_assignments=best.hard_assignments,
        probabilities=best.probabilities,
    )


def _attach_labels(
    model: ClassModel, names: Sequence[str], levels: Sequence[Sequence[str]]
) -> ClassModel:
    return ClassModel(
        n_classes=model.n_classes,
        seed=model.seed,
        log_likelihood=model.log_likelihood,
        bic=model.bic,
        n_parameters=model.n_parameters,
        converged=model.converged,
        feature_names=tuple(names),
        levels=tuple(tuple(feature_levels_) for feature_levels_ in levels),
        class_priors=model.class_priors,
        emissions=model.emissions,
        hard_assignments=model.hard_assignments,
        probabilities=model.probabilities,
    )


def _failed_candidate(n_classes: int) -> ClassCountCandidate:
    return ClassCountCandidate(
        n_classes=n_classes,
        bic=float("inf"),
        log_likelihood=float("-inf"),
        median_adjusted_rand_index=0.0,
        adjusted_rand_indexes=(),
        minimum_class_counties=0,
        stable=False,
        eligible=False,
    )


def _fit_once(
    coded: NDArray[np.int64],
    level_counts: Sequence[int],
    n_classes: int,
    rng: np.random.Generator,
    max_iterations: int,
    tolerance: float,
) -> ClassModel | None:
    n_rows = coded.shape[0]
    priors = rng.dirichlet(np.ones(n_classes))
    emissions = [rng.dirichlet(np.ones(n_levels), size=n_classes) for n_levels in level_counts]
    previous: float | None = None
    converged = False
    responsibilities = cast(NDArray[np.float64], np.empty((n_rows, n_classes)))
    log_likelihood = -np.inf
    for _ in range(max_iterations):
        responsibilities, log_likelihood = _expectation(coded, priors, emissions)
        if previous is not None and abs(log_likelihood - previous) <= tolerance * (
            1.0 + abs(log_likelihood)
        ):
            converged = True
            break
        previous = log_likelihood
        updated = _maximization(coded, responsibilities, level_counts)
        if updated is None:
            return None
        priors, emissions = updated
    else:
        responsibilities, log_likelihood = _expectation(coded, priors, emissions)
    n_parameters = parameter_count(n_classes, level_counts)
    bic = -2.0 * log_likelihood + n_parameters * float(np.log(n_rows))
    hard = tuple(int(index) for index in np.argmax(responsibilities, axis=1))
    return ClassModel(
        n_classes=n_classes,
        seed=0,
        log_likelihood=log_likelihood,
        bic=bic,
        n_parameters=n_parameters,
        converged=converged,
        feature_names=(),
        levels=(),
        class_priors=tuple(float(value) for value in priors),
        emissions=tuple(
            tuple(tuple(float(value) for value in row) for row in theta) for theta in emissions
        ),
        hard_assignments=hard,
        probabilities=tuple(tuple(float(value) for value in row) for row in responsibilities),
    )


def _expectation(
    coded: NDArray[np.int64],
    priors: NDArray[np.float64],
    emissions: Sequence[NDArray[np.float64]],
) -> tuple[NDArray[np.float64], float]:
    n_rows = coded.shape[0]
    log_joint = np.tile(np.log(np.maximum(priors, _LOG_FLOOR)), (n_rows, 1))
    for feature_index, theta in enumerate(emissions):
        observed = coded[:, feature_index]
        log_joint += np.log(np.maximum(theta[:, observed], _LOG_FLOOR)).T
    peak = np.max(log_joint, axis=1, keepdims=True)
    shifted = np.exp(log_joint - peak)
    totals = np.sum(shifted, axis=1, keepdims=True)
    responsibilities = shifted / totals
    log_likelihood = float(np.sum(peak + np.log(totals)))
    return responsibilities, log_likelihood


def _maximization(
    coded: NDArray[np.int64],
    responsibilities: NDArray[np.float64],
    level_counts: Sequence[int],
) -> tuple[NDArray[np.float64], list[NDArray[np.float64]]] | None:
    class_mass = np.sum(responsibilities, axis=0)
    if bool(np.any(class_mass <= 1e-8)):
        return None
    priors = class_mass / responsibilities.shape[0]
    emissions: list[NDArray[np.float64]] = []
    for feature_index, n_levels in enumerate(level_counts):
        indicators = np.eye(n_levels, dtype=np.float64)[coded[:, feature_index]]
        emissions.append((responsibilities.T @ indicators) / class_mass[:, np.newaxis])
    return priors, emissions


def _class_sizes(assignments: Sequence[int], n_classes: int) -> tuple[int, ...]:
    counts = [0] * n_classes
    for assignment in assignments:
        counts[assignment] += 1
    return tuple(counts)
