"""Issue-local finite-cohort SVI/RUCC analysis; no transport or IID inference."""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean, median
from typing import Any, cast

RELEASE = "governed-2026-09-17-unknown-coverage"
BUNDLE_SHA256 = "55192e53b0b046cfe5148c13ffe5c570f615ec233e2b5c1103247f00b1a51233"
SEED = 6302026
STATE_FIPS = frozenset(
    [
        "01",
        "02",
        "04",
        "05",
        "06",
        "08",
        "09",
        "10",
        "11",
        "12",
        "13",
        "15",
        "16",
        "17",
        "18",
        "19",
        "20",
        "21",
        "22",
        "23",
        "24",
        "25",
        "26",
        "27",
        "28",
        "29",
        "30",
        "31",
        "32",
        "33",
        "34",
        "35",
        "36",
        "37",
        "38",
        "39",
        "40",
        "41",
        "42",
        "44",
        "45",
        "46",
        "47",
        "48",
        "49",
        "50",
        "51",
        "53",
        "54",
        "55",
        "56",
    ]
)


@dataclass(frozen=True)
class County:
    fips: str
    svi: float
    rucc: int


def quantile(values: list[float], probability: float) -> float:
    """Linear interpolation at (n-1)*p, including singleton samples."""
    if not values or not 0 <= probability <= 1:
        raise ValueError("nonempty sample and probability in [0,1] required")
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    low = math.floor(index)
    high = math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def omnibus(groups: dict[int, list[float]]) -> dict[str, float | int]:
    """Tie-corrected Kruskal-Wallis H and rank epsilon squared, no p-value."""
    if len(groups) < 2 or any(not values for values in groups.values()):
        raise ValueError("at least two nonempty groups required")
    ordered = sorted((value, group) for group, values in groups.items() for value in values)
    n = len(ordered)
    k = len(groups)
    if n <= k or any(not math.isfinite(value) for value, _ in ordered):
        raise ValueError("finite values and N > k required")
    ranks: dict[int, float] = defaultdict(float)
    tie_sum = 0
    start = 0
    while start < n:
        end = start + 1
        while end < n and ordered[end][0] == ordered[start][0]:
            end += 1
        rank = (start + 1 + end) / 2
        for _, group in ordered[start:end]:
            ranks[group] += rank
        size = end - start
        tie_sum += size**3 - size
        start = end
    correction = 1 - tie_sum / (n**3 - n)
    if correction <= 0:
        raise ValueError("all outcomes tied: omnibus not estimable")
    h = (
        12 / (n * (n + 1)) * sum(ranks[g] ** 2 / len(groups[g]) for g in groups) - 3 * (n + 1)
    ) / correction
    h = max(0.0, h)  # floating point cancellation at the null
    return {"n": n, "k": k, "h": h, "epsilon_squared": max(0.0, (h - k + 1) / (n - k))}


def cohort(rows: list[dict[str, Any]], canonical: set[str]) -> tuple[list[County], dict[str, Any]]:
    """Fail closed on identity; count missing outcomes without imputing them."""
    if len(canonical) != 3144 or len(rows) > 3144:
        raise ValueError("canonical cohort must have 3144 IDs; reject overflow/truncation")
    ids = [row.get("FIPS") for row in rows]
    if any(not isinstance(fips, str) or len(fips) != 5 or not fips.isdigit() for fips in ids):
        raise ValueError("five-digit string FIPS required")
    if len(set(ids)) != len(ids) or set(ids) != canonical:
        raise ValueError("duplicate or incomplete canonical county identity")
    if any(row.get("RELEASE_ID") != RELEASE for row in rows):
        raise ValueError("release mismatch")
    eligible = []
    exclusions: Counter[str] = Counter()
    missing_by_rucc: Counter[str] = Counter()
    for row in rows:
        fips = row["FIPS"]
        if fips[:2] not in STATE_FIPS:
            raise ValueError("unsupported state/territory geography")
        svi = row.get("SVI_PERCENTILE")
        rucc = row.get("RUCC_2023")
        svi_valid = (
            isinstance(svi, (float, int))
            and not isinstance(svi, bool)
            and math.isfinite(svi)
            and 0 <= svi <= 1
        )
        rucc_valid = (
            isinstance(rucc, (float, int))
            and not isinstance(rucc, bool)
            and math.isfinite(rucc)
            and rucc == int(rucc)
            and 1 <= rucc <= 9
        )
        if not svi_valid or not rucc_valid:
            reason = (
                "both_invalid_or_missing"
                if not svi_valid and not rucc_valid
                else "svi_invalid_or_missing"
                if not svi_valid
                else "rucc_invalid_or_missing"
            )
            exclusions[reason] += 1
            missing_by_rucc[str(int(cast(float, rucc))) if rucc_valid else "unknown"] += 1
            continue
        eligible.append(County(fips, float(cast(float, svi)), int(cast(float, rucc))))
    return eligible, {
        "projection_rows": len(rows),
        "unique_counties": len(set(ids)),
        "eligible_counties": len(eligible),
        "excluded_counties": sum(exclusions.values()),
        "exclusions": dict(exclusions),
        "missing_by_rucc": dict(missing_by_rucc),
        "source_observation_rows": None,  # projection does not expose native source row N
    }


def grouped(counties: list[County], broad: bool = False) -> dict[int, list[float]]:
    groups: dict[int, list[float]] = defaultdict(list)
    for county in counties:
        group = (1 if county.rucc <= 3 else 2) if broad else county.rucc
        groups[group].append(county.svi)
    return dict(groups)


def analyze(counties: list[County], replicates: int = 2000) -> dict[str, Any]:
    if not 1 <= replicates <= 2000:
        raise ValueError("bootstrap replicates bounded to [1,2000]")
    groups = grouped(counties)
    summaries = {
        str(group): {
            "n": len(values),
            "mean": mean(values),
            "median": median(values),
            "q25": quantile(values, 0.25),
            "q75": quantile(values, 0.75),
            "min": min(values),
            "max": max(values),
        }
        for group, values in sorted(groups.items())
    }
    result: dict[str, Any] = {"groups": summaries, "posthoc": "not_performed"}
    if set(groups) != set(range(1, 10)) or min(map(len, groups.values())) < 20:
        return {**result, "status": "DESCRIPTIVE_ONLY", "reason": "group support below plan"}
    primary = omnibus(groups)
    result.update(status="ESTIMATED_DESCRIPTIVELY", omnibus=primary, iid_p_value=None)
    states: dict[str, list[County]] = defaultdict(list)
    for county in counties:
        states[county.fips[:2]].append(county)
    state_ids = sorted(states)
    rng = random.Random(SEED)
    effects = []
    skipped = 0
    for _ in range(replicates):
        sample = [
            county for state in rng.choices(state_ids, k=len(state_ids)) for county in states[state]
        ]
        sample_groups = grouped(sample)
        if set(sample_groups) != set(groups):
            skipped += 1
            continue
        try:
            effects.append(float(omnibus(sample_groups)["epsilon_squared"]))
        except ValueError:
            skipped += 1
    result["state_block_sensitivity"] = {
        "states": len(states),
        "seed": SEED,
        "replicates": replicates,
        "valid_replicates": len(effects),
        "skipped_replicates": skipped,
        "percentile_interval": [quantile(effects, 0.025), quantile(effects, 0.975)]
        if effects
        else None,
        "interpretation": "sensitivity interval, not a spatially validated confidence interval",
    }
    leave_one_out = [
        float(omnibus(grouped([c for c in counties if c.fips[:2] != state]))["epsilon_squared"])
        for state in state_ids
    ]
    result["leave_one_state_out_range"] = [min(leave_one_out), max(leave_one_out)]
    result["metro_nonmetro"] = {
        str(group): {
            "n": len(values),
            "mean": mean(values),
            "median": median(values),
            "q25": quantile(values, 0.25),
            "q75": quantile(values, 0.75),
        }
        for group, values in grouped(counties, broad=True).items()
    }
    return result
