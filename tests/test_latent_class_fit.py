import pytest

from lyme_gap_atlas_ml.latent_class_baseline import BASELINE_A, assert_baseline_cross_tab
from lyme_gap_atlas_ml.latent_class_fit import (
    ClassCountCandidate,
    FitConfig,
    choose_class_count,
    feature_levels,
    feature_names,
    observations,
    parameter_count,
    select_class_count,
)
from lyme_gap_atlas_ml.latent_class_inputs import (
    NATIONAL_COUNTY_COUNT,
    LatentClassInputError,
    SurveillanceCounty,
    build_counties,
)
from lyme_gap_atlas_ml.latent_class_result import build_result_document, render_selection_note

_FAST = FitConfig(
    class_counts=(2, 3),
    primary_seed=1192026,
    alternate_seeds=(1192027, 1192028),
    random_starts=6,
    minimum_median_ari=0.90,
    minimum_class_counties=40,
    bic_margin=6.0,
    max_iterations=80,
)


def _candidate(n_classes: int, bic: float, *, eligible: bool) -> ClassCountCandidate:
    return ClassCountCandidate(
        n_classes=n_classes,
        bic=bic,
        log_likelihood=0.0,
        median_adjusted_rand_index=1.0 if eligible else 0.0,
        adjusted_rand_indexes=(1.0, 1.0, 1.0, 1.0),
        minimum_class_counties=100 if eligible else 1,
        stable=eligible,
        eligible=eligible,
    )


def test_parameter_count_matches_the_declared_levels() -> None:
    assert parameter_count(2, (2, 4, 4, 3)) == 19
    assert parameter_count(3, (4, 4, 3)) == 26


def test_bic_margin_keeps_the_smallest_eligible_class_count() -> None:
    selected, reason = choose_class_count(
        (
            _candidate(2, 100.0, eligible=True),
            _candidate(3, 94.0, eligible=True),
            _candidate(4, 90.0, eligible=True),
            _candidate(5, 80.0, eligible=False),
        ),
        bic_margin=6.0,
    )
    assert reason is None
    assert selected == 3
    blocked, blocked_reason = choose_class_count(
        (_candidate(2, 10.0, eligible=False),), bic_margin=6.0
    )
    assert blocked is None
    assert blocked_reason == "no class count met the stability rule"


def test_blank_levels_are_retained_and_every_row_is_assigned() -> None:
    rows = [("no_county_linked_record", "Unknown", "Unknown", "Unknown")] * 50
    rows += [("published_count_floor", "No records", "No records", "No records")] * 50
    selection = select_class_count(
        rows,
        feature_levels("four-state"),
        feature_names("four-state"),
        _FAST,
    )
    model = selection.model
    assert model is not None
    assert len(model.hard_assignments) == len(rows)
    assert model.levels[1] == ("Established", "Reported", "No records", "Unknown")
    assert model.levels[3] == ("Present", "No records", "Unknown")
    for probability in model.probabilities:
        assert abs(sum(probability) - 1.0) < 1e-6


def test_same_seed_assigns_the_same_classes() -> None:
    rows = [("published_count_floor", "Established", "No records", "Present")] * 60
    rows += [("no_county_linked_record", "No records", "No records", "No records")] * 60
    levels = feature_levels("four-state")
    names = feature_names("four-state")
    first = select_class_count(rows, levels, names, _FAST)
    second = select_class_count(rows, levels, names, _FAST)
    assert first.model is not None
    assert second.model is not None
    assert first.model.hard_assignments == second.model.hard_assignments
    assert first.selected_classes == 2


def test_population_is_not_an_indicator() -> None:
    county = build_counties(
        [
            {
                "FIPS": "01001",
                "STATE": "AL",
                "HUMAN_STATUS": "no_county_linked_record",
                "SCAPULARIS_STATUS": "No records",
                "PACIFICUS_STATUS": "No records",
                "BURGDORFERI_STATUS": "No records",
                "POPULATION": 50,
            }
        ]
    )[0]
    assert observations([county], "four-state")[0] == county.estimand_a()
    assert "50" not in observations([county], "four-state")[0]


def test_unrecognized_level_fails_closed() -> None:
    with pytest.raises(LatentClassInputError, match="unrecognized"):
        select_class_count(
            [("no_county_linked_record", "Absent", "No records", "No records")],
            feature_levels("four-state"),
            feature_names("four-state"),
            _FAST,
        )


def test_baseline_table_sums_and_rejects_a_changed_cell() -> None:
    assert sum(count for _, count, _ in BASELINE_A) == NATIONAL_COUNTY_COUNT
    assert sum(people for _, _, people in BASELINE_A) == 331_097_593
    counties = _counties_from_baseline()
    assert_baseline_cross_tab(counties)
    changed = (
        SurveillanceCounty(
            fips="99999",
            state="WY",
            human_status="published_count_floor",
            scapularis_status="Unknown",
            pacificus_status="Unknown",
            burgdorferi_status="Unknown",
            population=1,
        ),
        *counties[1:],
    )
    with pytest.raises(LatentClassInputError, match="baseline"):
        assert_baseline_cross_tab(changed)


def test_selection_note_does_not_cite_the_follow_up_list() -> None:
    counties = _separated_counties()
    selection = select_class_count(
        observations(counties, "tick-pathogen"),
        feature_levels("tick-pathogen"),
        feature_names("tick-pathogen"),
        _FAST,
    )
    document = build_result_document(
        counties,
        {"four-state": selection, "tick-pathogen": selection},
        code_revision="abc",
        numpy_version="0",
        sklearn_version="0",
    )
    note = render_selection_note(document, code_revision="abc")
    assert "228-county" not in note
    assert "follow-up county list was not an input" in note
    estimands = document["estimands"]
    assert isinstance(estimands, dict)
    tick = estimands["tick-pathogen"]
    assert isinstance(tick, dict)
    assignments = tick["assignments"]
    assert isinstance(assignments, list)
    assert len(assignments) == len(counties)


def _separated_counties() -> tuple[SurveillanceCounty, ...]:
    rows = []
    for index in range(60):
        rows.append(
            SurveillanceCounty(
                fips=f"{index:05d}",
                state="AL",
                human_status="published_count_floor",
                scapularis_status="Established",
                pacificus_status="No records",
                burgdorferi_status="Present",
                population=100,
            )
        )
    for index in range(60, 120):
        rows.append(
            SurveillanceCounty(
                fips=f"{index:05d}",
                state="AL",
                human_status="no_county_linked_record",
                scapularis_status="No records",
                pacificus_status="No records",
                burgdorferi_status="No records",
                population=100,
            )
        )
    return tuple(rows)


def _counties_from_baseline() -> tuple[SurveillanceCounty, ...]:
    counties: list[SurveillanceCounty] = []
    serial = 0
    for cell, count, people in BASELINE_A:
        share, remainder = divmod(people, count)
        for offset in range(count):
            counties.append(
                SurveillanceCounty(
                    fips=f"{serial:05d}",
                    state="AK" if cell[1:] == ("Unknown", "Unknown", "Unknown") else "AL",
                    human_status=cell[0],
                    scapularis_status=cell[1],
                    pacificus_status=cell[2],
                    burgdorferi_status=cell[3],
                    population=share + (1 if offset < remainder else 0),
                )
            )
            serial += 1
    return tuple(counties)
