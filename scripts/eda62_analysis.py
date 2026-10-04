"""Issue-local offline statistics, not source authority or scientific admission.

Call screen_taxa without outcomes, commit selection and matching input identity,
then call analyze_selected after governed published-projection EDA admission.
Private native lineage verification and ML feature admission are separate.
No warehouse I/O, paid calls, model fitting or automatic source substitution.
"""

import math
import random
import re
import statistics
from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Sequence
from typing import Any

TAXA = ("scapularis_status", "pacificus_status")
POSITIVE = {"Established": "ESTABLISHED", "Reported": "REPORTED"}
MIN_N = 30
SEED = 62
BOOTSTRAP_DRAWS = 2000


def county_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reject duplicate county units; leave source authority to governed receipts."""
    if len(rows) > 3144:
        raise ValueError("Exceeds this governed county release's 3,144-row analysis bound")
    seen = set()
    valid = []
    for row in rows:
        fips = row.get("fips")
        if not isinstance(fips, str) or re.fullmatch(r"[0-9]{5}", fips) is None:
            continue
        if fips in seen:
            raise ValueError("Duplicate or conflicting county identity; no independent cohort")
        seen.add(fips)
        valid.append(row)
    return valid


def screen_taxa(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Select using status semantics and county N only; never read SVI values."""
    valid = county_rows(rows)
    counts = {taxon: dict(Counter(row.get(taxon) for row in valid)) for taxon in TAXA}
    chosen = next(
        (
            taxon
            for taxon in TAXA
            if all(counts[taxon].get(state, 0) >= MIN_N for state in POSITIVE)
        ),
        None,
    )
    return {
        "selected_taxon": chosen,
        "consumer_county_rows": len(rows),
        "unique_valid_fips": len(valid),
        "invalid_fips_excluded": len(rows) - len(valid),
        "source_state_county_n": counts,
        "outcomes_inspected": False,
        "status": "CANDIDATE_SELECTED" if chosen else "NOT_ESTIMABLE_FOR_THIS_INPUT",
    }


def quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered or not 0 <= probability <= 1:
        raise ValueError("Nonempty values and probability in [0,1] required")
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def superiority(a: Sequence[float], b: Sequence[float]) -> float:
    """P(A>B) + half P(A=B); ties never broken randomly."""
    if not a or not b:
        raise ValueError("Both positive evidence groups must be nonempty")
    ordered_b = sorted(b)
    credit = sum(
        bisect_left(ordered_b, x) + (bisect_right(ordered_b, x) - bisect_left(ordered_b, x)) / 2
        for x in a
    )
    return credit / (len(a) * len(b))


def category(probability: float) -> str:
    magnitude = abs(probability - 0.5)
    if magnitude >= 0.10 - 1e-12:
        return "MATERIAL_DIFFERENCE"
    if magnitude >= 0.05 - 1e-12:
        return "SMALL_DIFFERENCE"
    return "NO_MEANINGFUL_DIRECTIONAL_RANK_DIFFERENCE"


def describe(values: Sequence[float]) -> dict[str, float | int]:
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "q1": quantile(values, 0.25),
        "q3": quantile(values, 0.75),
        "iqr": quantile(values, 0.75) - quantile(values, 0.25),
        "min": min(values),
        "max": max(values),
    }


def distribution_descriptors(a: Sequence[float], b: Sequence[float]) -> dict[str, float]:
    """CDF/range descriptors do not establish equivalent distributions."""
    ordered_a, ordered_b = sorted(a), sorted(b)
    cdf_distance = max(
        abs(bisect_right(ordered_a, x) / len(a) - bisect_right(ordered_b, x) / len(b))
        for x in set(a) | set(b)
    )
    span = max(max(a), max(b)) - min(min(a), min(b))
    overlap = max(0.0, min(max(a), max(b)) - max(min(a), min(b)))
    return {
        "empirical_cdf_max_distance": cdf_distance,
        "common_range_fraction": overlap / span if span else 1.0,
    }


def mann_whitney(a: Sequence[float], b: Sequence[float]) -> dict[str, float | str]:
    """Tie-adjusted normal approximation, two-sided and continuity-corrected."""
    n_a, n_b = len(a), len(b)
    u = superiority(a, b) * n_a * n_b
    n = n_a + n_b
    tie_term = sum(t**3 - t for t in Counter([*a, *b]).values())
    variance = n_a * n_b / 12 * (n + 1 - tie_term / (n * (n - 1)))
    distance = max(0.0, abs(u - n_a * n_b / 2) - 0.5)
    p = math.erfc(distance / math.sqrt(2 * variance)) if variance > 0 else 1.0
    return {
        "u_established": u,
        "p_two_sided_county_independence_only": p,
        "p_interpretation": "ancillary; not adjusted for spatial/state dependence",
        "approximation": "normal; tie-adjusted variance; continuity correction",
    }


def clustered_interval(groups: dict[str, tuple[list[float], list[float]]]) -> dict[str, Any]:
    states = sorted(groups)
    mixed = sum(bool(a) and bool(b) for a, b in groups.values())
    base = {
        "seed": SEED,
        "requested_draws": BOOTSTRAP_DRAWS,
        "state_n": len(states),
        "mixed_state_n": mixed,
    }
    if len(states) < 10 or mixed < 5:
        return {**base, "status": "NOT_ESTIMABLE", "valid_draws": 0, "interval": None}
    rng = random.Random(SEED)
    estimates = []
    for _ in range(BOOTSTRAP_DRAWS):
        a, b = [], []
        for state in rng.choices(states, k=len(states)):
            state_a, state_b = groups[state]
            a.extend(state_a)
            b.extend(state_b)
        if a and b:
            estimates.append(superiority(a, b))
    if len(estimates) < 0.9 * BOOTSTRAP_DRAWS:
        return {**base, "status": "NOT_ESTIMABLE", "valid_draws": len(estimates), "interval": None}
    return {
        **base,
        "status": "EXPLORATORY_CLUSTER_INTERVAL",
        "valid_draws": len(estimates),
        "interval": [quantile(estimates, 0.025), quantile(estimates, 0.975)],
        "limitation": "whole-state sampling does not remove cross-state spatial correlation",
    }


def interval_category_supported(interval: Sequence[float], point_category: str) -> bool:
    low, high = interval
    probabilities = [low, high]
    if low <= 0.5 <= high:
        probabilities.append(0.5)
    return all(category(x) == point_category for x in probabilities)


def analyze_selected(rows: Sequence[dict[str, Any]], selected_taxon: str) -> dict[str, Any]:
    """Execute an already registered selection; never switch after SVI exclusions."""
    screen = screen_taxa(rows)
    if selected_taxon not in TAXA or screen["selected_taxon"] != selected_taxon:
        raise ValueError("Taxon must match the outcome-blind preregistered selection")
    valid = county_rows(rows)
    a, b = [], []
    states: dict[str, tuple[list[float], list[float]]] = {}
    excluded: Counter[str] = Counter()
    for row in valid:
        status = row.get(selected_taxon)
        if status not in POSITIVE:
            excluded[f"status:{status}"] += 1
            continue
        value = row.get("svi_percentile")
        if value is None:
            excluded["svi_missing"] += 1
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (float, int))
            or not math.isfinite(value)
        ):
            excluded["svi_invalid"] += 1
            continue
        if not 0 <= value <= 1:
            excluded["svi_invalid"] += 1
            continue
        state = row["fips"][:2]
        state_a, state_b = states.setdefault(state, ([], []))
        (a if status == "Established" else b).append(float(value))
        (state_a if status == "Established" else state_b).append(float(value))
    base = {
        "selected_taxon": selected_taxon,
        "screen": screen,
        "complete_county_n": {"ESTABLISHED": len(a), "REPORTED": len(b)},
        "exclusions": dict(excluded),
        "invalid_fips_excluded": screen["invalid_fips_excluded"],
        "source_authority_verified_by_statistics": False,
    }
    if min(len(a), len(b)) < MIN_N:
        return {
            **base,
            "status": "NOT_ESTIMABLE",
            "reason": "insufficient complete-case N",
            "effect": None,
            "interval": None,
        }
    effect = superiority(a, b)
    point_category = category(effect)
    state_counts = {
        state: {
            "ESTABLISHED": len(x),
            "REPORTED": len(y),
            "established_share": len(x) / len(a),
            "reported_share": len(y) / len(b),
        }
        for state, (x, y) in sorted(states.items())
    }
    dominant = [
        state
        for state, counts in state_counts.items()
        if max(counts["established_share"], counts["reported_share"]) > 0.25
    ]
    leave_out = {}
    geographic_robust = True
    for state in dominant:
        other_a = [value for key, (x, _) in states.items() if key != state for value in x]
        other_b = [value for key, (_, y) in states.items() if key != state for value in y]
        enough = min(len(other_a), len(other_b)) >= MIN_N
        alternative = superiority(other_a, other_b) if enough else None
        robust = enough and category(alternative) == point_category
        geographic_robust = geographic_robust and robust
        leave_out[state] = {
            "n_a": len(other_a),
            "n_b": len(other_b),
            "superiority": alternative,
            "category_retained": robust,
        }
    within = {
        state: {"n_a": len(x), "n_b": len(y), "superiority": superiority(x, y)}
        for state, (x, y) in sorted(states.items())
        if min(len(x), len(y)) >= 10
    }
    uncertainty = clustered_interval(states)
    interval = uncertainty["interval"]
    supported = (
        interval is not None
        and geographic_robust
        and interval_category_supported(interval, point_category)
    )
    return {
        **base,
        "status": "EXPLORATORY_ESTIMATE" if interval else "DESCRIPTIVE_ONLY",
        "groups": {"ESTABLISHED": describe(a), "REPORTED": describe(b)},
        "superiority": effect,
        "rank_biserial": 2 * effect - 1,
        "median_difference": statistics.median(a) - statistics.median(b),
        "mean_difference": statistics.mean(a) - statistics.mean(b),
        "distribution_descriptors": distribution_descriptors(a, b),
        "mann_whitney": mann_whitney(a, b),
        "uncertainty": uncertainty,
        "point_directional_rank_category": point_category,
        "category_supported_by_interval_and_sensitivity": supported,
        "state_counts": state_counts,
        "dominant_states": dominant,
        "leave_dominant_state_out": leave_out,
        "within_state_descriptive": within,
        "interpretation": "directional rank association only; no equivalence or causal claim",
    }
