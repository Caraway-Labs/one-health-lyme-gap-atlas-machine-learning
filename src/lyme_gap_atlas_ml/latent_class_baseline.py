"""Identity check against the published story 119 cross-classification.

This table is the baseline the extract must match. It is not an input to the
class-count rule.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from lyme_gap_atlas_ml.latent_class_inputs import LatentClassInputError, SurveillanceCounty

BASELINE_A: tuple[tuple[tuple[str, str, str, str], int, int], ...] = (
    (("no_county_linked_record", "No records", "No records", "No records"), 1189, 54861634),
    (("no_county_linked_record", "Established", "No records", "No records"), 523, 42167012),
    (("published_count_floor", "Established", "No records", "Present"), 438, 83910033),
    (("no_county_linked_record", "Reported", "No records", "No records"), 428, 29569755),
    (("no_county_linked_record", "Established", "No records", "Present"), 200, 10486999),
    (("published_count_floor", "Established", "No records", "No records"), 146, 42924965),
    (("no_county_linked_record", "No records", "Established", "No records"), 59, 18340571),
    (("no_county_linked_record", "Unknown", "Unknown", "Unknown"), 35, 2185410),
    (("published_count_floor", "Reported", "No records", "No records"), 30, 5941373),
    (("no_county_linked_record", "No records", "Established", "Present"), 28, 12217147),
    (("published_count_floor", "No records", "No records", "No records"), 25, 2557405),
    (("no_county_linked_record", "Reported", "No records", "Present"), 16, 1237848),
    (("no_county_linked_record", "No records", "Reported", "No records"), 14, 1309650),
    (("published_count_floor", "No records", "Established", "No records"), 5, 5712251),
    (("published_count_floor", "No records", "Established", "Present"), 5, 14274351),
    (("published_count_floor", "Reported", "No records", "Present"), 1, 1115403),
    (("published_count_floor", "No records", "Reported", "No records"), 1, 2265926),
    (("no_county_linked_record", "No records", "No records", "Present"), 1, 19860),
)


def assert_baseline_cross_tab(counties: Sequence[SurveillanceCounty]) -> None:
    """Refuse an extract whose four-state cells differ from the published baseline."""
    observed: Counter[tuple[str, str, str, str]] = Counter()
    population: Counter[tuple[str, str, str, str]] = Counter()
    for county in counties:
        cell = county.estimand_a()
        observed[cell] += 1
        population[cell] += county.population
    expected = {cell: (count, people) for cell, count, people in BASELINE_A}
    if observed.keys() != expected.keys() or any(
        (observed[cell], population[cell]) != expected[cell] for cell in expected
    ):
        raise LatentClassInputError("county extract does not match the published baseline table")
