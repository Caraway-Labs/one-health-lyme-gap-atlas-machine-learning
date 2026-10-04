"""Interval identification and coverage reconciliation for ML #64; no inference."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CountInterval:
    """A source-supported count bound; None upper means no finite upper evidence."""

    lower: float
    upper: float | None

    def __post_init__(self) -> None:
        if not math.isfinite(self.lower) or self.lower < 0:
            raise ValueError("Count lower bound must be finite and nonnegative")
        if self.upper is not None and (not math.isfinite(self.upper) or self.upper < self.lower):
            raise ValueError("Finite upper bound must be at least the lower bound")


@dataclass(frozen=True)
class ChangeIdentification:
    lower: float
    upper: float
    direction: str
    exact_magnitude: bool


def identify_change(earlier: CountInterval, later: CountInterval) -> ChangeIdentification:
    """Identify later-minus-earlier change without replacing floors by totals.

    Marginal intervals alone support the Cartesian-product difference interval.
    Joint source constraints could tighten it, but must be separately evidenced.
    An identified sign does not authorize a paired test or establish comparability.
    """
    lower = later.lower - (earlier.upper if earlier.upper is not None else math.inf)
    upper = (later.upper if later.upper is not None else math.inf) - earlier.lower
    if lower > 0:
        direction = "INCREASE"
    elif upper < 0:
        direction = "DECREASE"
    elif lower == upper == 0:
        direction = "UNCHANGED"
    else:
        direction = "NOT_IDENTIFIED"
    return ChangeIdentification(lower, upper, direction, lower == upper)


@dataclass(frozen=True)
class PairCoverage:
    """Mutually exclusive availability states; pairs are not independent county N."""

    candidate_pairs: int
    neither_year: int
    earlier_only: int
    later_only: int
    both_years: int

    def __post_init__(self) -> None:
        values = (
            self.candidate_pairs,
            self.neither_year,
            self.earlier_only,
            self.later_only,
            self.both_years,
        )
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values
        ):
            raise ValueError("Coverage counts must be nonnegative integers")
        if sum(values[1:]) != self.candidate_pairs:
            raise ValueError("Availability exclusions do not reconcile to candidate pairs")

    @property
    def missing_either_year(self) -> int:
        return self.neither_year + self.earlier_only + self.later_only


def summarize_publisher_coverage(rows: Sequence[Mapping[str, str]]) -> dict[str, object]:
    """Reconcile source rows and numeric-FIPS coverage, never case totals.

    Input is the fixed year/FIPS/status COUNT(*) aggregate, without frequencies.
    Five-digit FIPS syntax does not certify historical geography compatibility.
    """
    if not rows or len(rows) >= 10_000:
        raise ValueError("Empty or possibly truncated publisher aggregate")
    seen: set[tuple[int, str, str]] = set()
    source_rows: Counter[int] = Counter()
    unallocated: Counter[tuple[int, str]] = Counter()
    categories: dict[tuple[int, str], set[str]] = {}
    for row in rows:
        year = int(row["year"])
        fips, category, count = row["fips"], row["case_status"], int(row["n"])
        if year not in range(2011, 2020) or category not in {"Confirmed", "Probable"} or count < 1:
            raise ValueError("Unexpected source year, category or observation count")
        key = (year, fips, category)
        if key in seen:
            raise ValueError("Duplicate source aggregate key")
        seen.add(key)
        source_rows[year] += count
        if re.fullmatch(r"[0-9]{5}", fips):
            categories.setdefault((year, fips), set()).add(category)
        else:
            unallocated[year, fips] += count
    windows = []
    for start, end, era in ((2011, 2016, "cdc_2011"), (2017, 2019, "cdc_2017")):
        observed = {
            year: {fips for y, fips in categories if y == year} for year in range(start, end + 1)
        }
        both_categories = {
            year: {
                fips
                for (y, fips), statuses in categories.items()
                if y == year and len(statuses) == 2
            }
            for year in observed
        }
        if any(not counties for counties in observed.values()):
            raise ValueError("An entire expected source year is absent")
        county_union = set().union(*observed.values())
        contrasts = []
        for year in range(start, end):
            a, b = observed[year], observed[year + 1]
            coverage = PairCoverage(
                len(county_union), len(county_union - (a | b)), len(a - b), len(b - a), len(a & b)
            )
            status_pairs = len(both_categories[year] & both_categories[year + 1])
            contrasts.append(
                {
                    "earlier_year": year,
                    "later_year": year + 1,
                    **coverage.__dict__,
                    "missing_either_year": coverage.missing_either_year,
                    "both_categories_in_both_years": status_pairs,
                    "observed_pairs_missing_either_category": coverage.both_years - status_pairs,
                }
            )
        windows.append(
            {
                "era": era,
                "unique_counties": len(county_union),
                "source_observation_rows": sum(source_rows[y] for y in observed),
                "published_county_years": sum(map(len, observed.values())),
                "all_years_observed_counties": len(set.intersection(*observed.values())),
                "year_coverage": [
                    {
                        "year": y,
                        "source_observation_rows": source_rows[y],
                        "published_county_years": len(observed[y]),
                        "both_categories_county_years": len(both_categories[y]),
                        "unallocated_source_rows": {
                            fips: n for (year, fips), n in unallocated.items() if year == y
                        },
                    }
                    for y in observed
                ],
                "contrasts": contrasts,
            }
        )
    return {
        "unique_counties_across_windows": len({fips for _, fips in categories}),
        "windows": windows,
        "statistical_tests_executed": False,
    }
