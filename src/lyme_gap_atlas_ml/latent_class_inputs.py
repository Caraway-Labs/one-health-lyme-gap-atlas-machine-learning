"""Admitted categorical inputs for story 119 latent class analysis.

The builder keeps blanks as categories. It does not impute, and it refuses any
column that is not in the admitted set.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

RELEASE_ID = "governed-2026-10-06-nlcd-demo-cohort"
BUNDLE_SHA256 = "603afb135a1a5c958d1d56d48d580d9942c67eb38986caf8b4b3acf69fcde2c9"
DATASET_ID = "surveillance-latent-class-counties"
DATASET_VERSION = "v1"
FEATURE_SET_ID = "surveillance-latent-class-indicators"
FEATURE_SET_VERSION = "v1"
NATIONAL_COUNTY_COUNT = 3144

IDENTITY_COLUMNS = ("FIPS", "STATE")
ESTIMAND_A_COLUMNS = (
    "HUMAN_STATUS",
    "SCAPULARIS_STATUS",
    "PACIFICUS_STATUS",
    "BURGDORFERI_STATUS",
)
ESTIMAND_B_COLUMNS = ("SCAPULARIS_STATUS", "PACIFICUS_STATUS", "BURGDORFERI_STATUS")
DENOMINATOR_COLUMN = "POPULATION"
ADMITTED_COLUMNS = frozenset((*IDENTITY_COLUMNS, *ESTIMAND_A_COLUMNS, DENOMINATOR_COLUMN))

HUMAN_LEVELS = frozenset({"published_count_floor", "no_county_linked_record"})
TICK_LEVELS = frozenset({"Established", "Reported", "No records", "Unknown"})
PATHOGEN_LEVELS = frozenset({"Present", "No records", "Unknown"})
LEVELS = {
    "HUMAN_STATUS": HUMAN_LEVELS,
    "SCAPULARIS_STATUS": TICK_LEVELS,
    "PACIFICUS_STATUS": TICK_LEVELS,
    "BURGDORFERI_STATUS": PATHOGEN_LEVELS,
}


class LatentClassInputError(ValueError):
    """A county row is outside the admitted latent-class contract."""


@dataclass(frozen=True)
class SurveillanceCounty:
    """One county in the latent-class cohort.

    Population is the reporting denominator. The estimand methods omit it.
    """

    fips: str
    state: str
    human_status: str
    scapularis_status: str
    pacificus_status: str
    burgdorferi_status: str
    population: int

    def estimand_a(self) -> tuple[str, str, str, str]:
        """Four-state surveillance situation indicators."""
        return (
            self.human_status,
            self.scapularis_status,
            self.pacificus_status,
            self.burgdorferi_status,
        )

    def estimand_b(self) -> tuple[str, str, str]:
        """Tick-and-pathogen indicators, without human status."""
        return (self.scapularis_status, self.pacificus_status, self.burgdorferi_status)


def assert_admitted_release(release_id: str, bundle_sha256: str) -> None:
    """Fail closed unless the caller verified the pinned release identity."""
    if release_id != RELEASE_ID or bundle_sha256 != BUNDLE_SHA256:
        raise LatentClassInputError("release identity does not match the admitted snapshot")


def build_counties(rows: Sequence[Mapping[str, object]]) -> tuple[SurveillanceCounty, ...]:
    """Return counties sorted by FIPS, with blanks retained and duplicates rejected."""
    counties = [_county(row) for row in rows]
    counties.sort(key=lambda county: county.fips)
    fips = [county.fips for county in counties]
    if len(fips) != len(set(fips)):
        raise LatentClassInputError("duplicate county FIPS")
    return tuple(counties)


def require_national_cohort(
    counties: Sequence[SurveillanceCounty],
    *,
    release_id: str,
    bundle_sha256: str,
) -> tuple[SurveillanceCounty, ...]:
    """Require the full admitted release, not a convenience subset."""
    assert_admitted_release(release_id, bundle_sha256)
    if len(counties) != NATIONAL_COUNTY_COUNT:
        raise LatentClassInputError(
            f"expected {NATIONAL_COUNTY_COUNT} counties, found {len(counties)}"
        )
    return tuple(counties)


def _county(row: Mapping[str, object]) -> SurveillanceCounty:
    extra = set(row) - ADMITTED_COLUMNS
    if extra:
        names = ", ".join(sorted(extra))
        raise LatentClassInputError(f"column is not an admitted latent-class input: {names}")
    missing = ADMITTED_COLUMNS - set(row)
    if missing:
        names = ", ".join(sorted(missing))
        raise LatentClassInputError(f"admitted column is missing: {names}")
    fips = row["FIPS"]
    state = row["STATE"]
    if not isinstance(fips, str) or len(fips) != 5 or not fips.isdigit():
        raise LatentClassInputError("FIPS must be a five-digit string")
    if (
        not isinstance(state, str)
        or len(state) != 2
        or not state.isalpha()
        or state != state.upper()
    ):
        raise LatentClassInputError("STATE must be a two-letter code")
    statuses = {column: _level(column, row[column]) for column in ESTIMAND_A_COLUMNS}
    return SurveillanceCounty(
        fips=fips,
        state=state,
        human_status=statuses["HUMAN_STATUS"],
        scapularis_status=statuses["SCAPULARIS_STATUS"],
        pacificus_status=statuses["PACIFICUS_STATUS"],
        burgdorferi_status=statuses["BURGDORFERI_STATUS"],
        population=_population(row[DENOMINATOR_COLUMN]),
    )


def _level(column: str, value: object) -> str:
    if not isinstance(value, str) or value not in LEVELS[column]:
        raise LatentClassInputError(f"unrecognized {column}")
    return value


def _population(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise LatentClassInputError("POPULATION must be a positive integer")
    return value
