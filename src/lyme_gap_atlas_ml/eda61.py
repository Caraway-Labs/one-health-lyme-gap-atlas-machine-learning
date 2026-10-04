"""Issue #61's offline, descriptive county association; no warehouse transport."""

from __future__ import annotations

import math
import random
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import mean

FIPS = re.compile(r"[0-9]{5}\Z")


@dataclass(frozen=True)
class County:
    fips: str
    population: float
    svi_percentile: float
    floor: float

    @property
    def rate(self) -> float:
        return self.floor / self.population * 100_000


def number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(str(value))
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def cohort(
    svi: Sequence[Mapping[str, object]],
    human: Sequence[Mapping[str, object]],
    canonical_fips: Sequence[str],
) -> tuple[list[County], dict[str, object]]:
    """Consume pinned rows after authority/scope checks; never impute missing outcomes."""
    canonical = set(canonical_fips)
    if len(canonical) != len(canonical_fips) or any(not FIPS.fullmatch(f) for f in canonical):
        raise ValueError("invalid or duplicate canonical county frame")
    identity: dict[str, Mapping[str, object]] = {}
    svi_record_ids: set[str] = set()
    for row in svi:
        fips = str(row.get("county_fips", ""))
        if not FIPS.fullmatch(fips) or fips in identity:
            raise ValueError("invalid or duplicate SVI FIPS")
        if fips not in canonical:
            raise ValueError("SVI FIPS absent from canonical mapping")
        record_id = str(row.get("source_record_id") or "")
        if not record_id or record_id in svi_record_ids:
            raise ValueError("missing or duplicate immutable SVI source-record identity")
        svi_record_ids.add(record_id)
        identity[fips] = row
    totals: defaultdict[str, float] = defaultdict(float)
    rows = Counter[str]()
    record_ids: set[str] = set()
    unmatched: set[str] = set()
    for row in human:
        record_id = str(row.get("source_record_id") or "")
        if not record_id or record_id in record_ids:
            raise ValueError("missing or duplicate immutable Lyme source-record identity")
        record_ids.add(record_id)
        if number(row.get("report_year")) != 2022:
            rows["other_year"] += 1
            continue
        rows["2022_source_rows"] += 1
        if str(row.get("case_status", "")).casefold() not in {"confirmed", "probable"}:
            rows["other_case_scope"] += 1
            continue
        fips = str(row.get("county_fips", ""))
        if not FIPS.fullmatch(fips):
            rows["noncounty_geography"] += 1
            continue
        frequency = number(row.get("frequency"))
        if frequency is None or frequency < 0 or not frequency.is_integer():
            raise ValueError("eligible published frequency must be a nonnegative integer")
        rows["numeric_fips_scope_rows"] += 1
        if fips not in canonical:
            unmatched.add(fips)
            rows["unmatched_source_rows"] += 1
            continue
        totals[fips] += frequency
    if unmatched:
        raise ValueError("numeric Lyme FIPS absent from canonical mapping")
    exclusions = Counter[str]()
    complete: list[County] = []
    for fips in sorted(canonical):
        svi_source = identity.get(fips)
        population = number(svi_source.get("population")) if svi_source is not None else None
        percentile = number(svi_source.get("svi_percentile")) if svi_source is not None else None
        reasons = []
        if fips not in totals:
            reasons.append("no_county_linked_record")
        if svi_source is None:
            reasons.append("missing_svi_source_row")
        else:
            if population is None or population <= 0:
                reasons.append("invalid_population")
            if percentile is None or not 0 <= percentile <= 1:
                reasons.append("missing_or_invalid_svi")
        exclusions.update(reasons)
        if reasons:
            exclusions["unique_excluded_counties"] += 1
        else:
            assert population is not None and percentile is not None
            county = County(fips, population, percentile, totals[fips])
            if not math.isfinite(county.rate):
                raise ValueError("nonfinite derived floor per 100k")
            complete.append(county)
    return complete, {
        "source_observation_rows": len(human),
        "svi_source_rows": len(svi),
        "svi_unique_source_counties": len(identity),
        "canonical_unique_counties": len(canonical),
        "county_linked_outcome_counties": len(totals),
        "primary_unique_counties": len(complete),
        "outcome_states_canonical_counties": {
            "no_county_linked_record": len(canonical) - len(totals),
            "observed_zero_floor": sum(value == 0 for value in totals.values()),
            "observed_positive_floor": sum(value > 0 for value in totals.values()),
        },
        "row_states": dict(rows),
        "county_exclusions_nonexclusive": dict(exclusions),
    }


def ranks(values: Sequence[float]) -> list[float]:
    result = [0.0] * len(values)
    order = sorted(range(len(values)), key=lambda index: values[index])
    start = 0
    while start < len(order):
        stop = start + 1
        while stop < len(order) and values[order[stop]] == values[order[start]]:
            stop += 1
        for index in order[start:stop]:
            result[index] = (start + 1 + stop) / 2
        start = stop
    return result


def correlation(x: Sequence[float], y: Sequence[float]) -> float | None:
    if len(x) != len(y):
        raise ValueError("paired vectors must have equal length")
    if len(x) < 3:
        return None
    rx, ry = ranks(x), ranks(y)
    mx, my = mean(rx), mean(ry)
    xx, yy = sum((v - mx) ** 2 for v in rx), sum((v - my) ** 2 for v in ry)
    if xx == 0 or yy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True)) / math.sqrt(xx * yy)


def quantile(values: Sequence[float], probability: float) -> float:
    if not values or not 0 <= probability <= 1:
        raise ValueError("quantile requires data and probability in [0,1]")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def distribution(values: Sequence[float]) -> dict[str, object]:
    return {
        "quantiles": {str(p): quantile(values, p) for p in (0, 0.01, 0.25, 0.5, 0.75, 0.99, 1)},
        "zero_count": values.count(0),
        "unique_values": len(set(values)),
        "tied_observations": sum(n for n in Counter(values).values() if n > 1),
    }


def state_rank_variance(counties: Sequence[County], values: Sequence[float]) -> float | None:
    ranked = ranks(values)
    overall = mean(ranked)
    groups: defaultdict[str, list[float]] = defaultdict(list)
    for county, rank in zip(counties, ranked, strict=True):
        groups[county.fips[:2]].append(rank)
    total = sum((rank - overall) ** 2 for rank in ranked)
    return (
        sum(len(group) * (mean(group) - overall) ** 2 for group in groups.values()) / total
        if total
        else None
    )


def analyze(counties: Sequence[County]) -> dict[str, object]:
    if len({c.fips for c in counties}) != len(counties):
        raise ValueError("primary cohort must contain unique counties")
    if not counties:
        return {"status": "NOT_ESTIMABLE", "reason": "empty validated complete cohort", "n": 0}
    populations = [c.population for c in counties]
    x, y = [c.svi_percentile for c in counties], [c.rate for c in counties]
    rho = correlation(x, y)
    lower, upper = quantile(populations, 0.01), quantile(populations, 0.99)
    sensitivity = [c for c in counties if lower <= c.population <= upper]
    sensitivity_rho = correlation(
        [c.svi_percentile for c in sensitivity], [c.rate for c in sensitivity]
    )
    groups: defaultdict[str, list[County]] = defaultdict(list)
    for county in counties:
        groups[county.fips[:2]].append(county)
    states = sorted(groups)
    samples: list[float] = []
    rng = random.Random(61)
    # A descriptive interval needs broad state coverage; fewer groups remains descriptive only.
    if rho is not None and len(states) >= 20:
        for _ in range(2000):
            draw = [c for state in rng.choices(states, k=len(states)) for c in groups[state]]
            value = correlation([c.svi_percentile for c in draw], [c.rate for c in draw])
            if value is not None:
                samples.append(value)
    disposition = "NOT_ESTIMABLE" if rho is None else "NO_SIGNAL"
    if rho is not None and abs(rho) >= 0.1:
        disposition = "WEAK_SIGNAL"
    if (
        rho is not None
        and abs(rho) >= 0.3
        and sensitivity_rho is not None
        and abs(sensitivity_rho) >= 0.3
        and rho * sensitivity_rho > 0
    ):
        disposition = "SIGNAL"
    return {
        "status": disposition,
        "n": len(counties),
        "spearman": rho,
        "population": distribution(populations),
        "svi_percentile": distribution(x),
        "published_county_linked_case_floor_per_100k": distribution(y),
        "sensitivity": {
            "population_bounds": [lower, upper],
            "n": len(sensitivity),
            "spearman": sensitivity_rho,
        },
        "state_groups": len(states),
        "state_counties": {state: len(groups[state]) for state in states},
        "state_summaries": {
            state: {
                "n": len(groups[state]),
                "median_svi_percentile": quantile([c.svi_percentile for c in groups[state]], 0.5),
                "median_floor_per_100k": quantile([c.rate for c in groups[state]], 0.5),
            }
            for state in states
        },
        "between_state_rank_variance_share": {
            "svi": state_rank_variance(counties, x),
            "floor_per_100k": state_rank_variance(counties, y),
        },
        "state_cluster_bootstrap": {
            "seed": 61,
            "draws": 2000 if rho is not None and len(states) >= 20 else 0,
            "valid_draws": len(samples),
            "descriptive_95_percent_interval": (
                [quantile(samples, 0.025), quantile(samples, 0.975)]
                if len(samples) >= 1900
                else None
            ),
            "limitation": (
                "State grouping does not resolve cross-border spatial dependence; no p-value."
            ),
        },
    }
