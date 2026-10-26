"""Issue 192 lookup rules. No live Snowflake connection."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from lyme_gap_atlas_ml.peer_lookup import (
    CATEGORY_SCALE,
    GAMMA,
    K_PRIMARY,
    RUCC_LEVELS,
    County,
    PeerLookupError,
    _neighbors,
    load_peer_queries,
    parse_clusters,
    parse_counties,
    score_counties,
)
from lyme_gap_atlas_ml.state_regimes import HUMAN_NONE, HUMAN_PUBLISHED

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "sql" / "validation" / "192_peer_lookup.sql"


def test_category_scale_matches_gamma() -> None:
    assert pytest.approx(0.5) == CATEGORY_SCALE
    assert pytest.approx(GAMMA) == 2 * CATEGORY_SCALE**2


def test_sql_file_has_the_three_registered_queries() -> None:
    queries = load_peer_queries(SQL.read_text(encoding="utf-8"))
    assert set(queries) == {"release_identity", "county_rows", "gap_clusters"}
    assert "GAP_COMMUNITY_ASSIGNMENTS_120" in queries["gap_clusters"]
    assert "CASE_COUNT" not in queries["county_rows"]
    assert "GEOMETRY" not in queries["county_rows"]


def test_national_gate_rejects_a_short_extract() -> None:
    with pytest.raises(PeerLookupError, match="3144"):
        parse_counties([_row(1)], release_id="governed-2026-10-15-january-climate-prod")


def test_assignment_gate_requires_810_rows() -> None:
    with pytest.raises(PeerLookupError, match="810"):
        parse_clusters([{"FIPS": "01001", "CLUSTER_ID": 1}, {"FIPS": "01003", "CLUSTER_ID": 2}])


def test_exclusive_situation_keeps_double_gap_out_of_wider_only() -> None:
    counties = _panel()
    clusters = {county.fips: 1 if index < 20 else 2 for index, county in enumerate(counties)}
    analysis = score_counties(counties, clusters, replicates=4, min_contributing=20)
    by_fips = {row.fips: row.situation for row in analysis.rows}
    assert by_fips["00001"] == "double_gap"
    assert by_fips["00002"] == "wider_gap_only"
    assert by_fips["00003"] == "aligned"
    assert by_fips["00004"] == "undocumented"
    for row in analysis.rows:
        neighbors = set(row.euclidean_neighbors.split(","))
        assert row.fips not in neighbors
        assert len(neighbors) == K_PRIMARY
    assert analysis.determinism_jaccard == pytest.approx(1.0)
    if analysis.method == "keep":
        assert analysis.failures == ()
    else:
        assert analysis.failures
    assert analysis.product in {"advance", "investigate"}


def test_tie_breaks_toward_the_smaller_index() -> None:
    embedding = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=float)
    indexes, _distances = _neighbors(embedding, np.arange(3), 2, "euclidean")
    assert list(indexes[0]) == [1, 2]


def _panel() -> tuple[County, ...]:
    rows = []
    for index in range(1, 41):
        if index == 1:
            human, tick, pathogen = HUMAN_NONE, "Established", "Present"
        elif index == 2:
            human, tick, pathogen = HUMAN_NONE, "Established", "No records"
        elif index == 3:
            human, tick, pathogen = HUMAN_PUBLISHED, "Established", "Present"
        elif index == 4:
            human, tick, pathogen = HUMAN_NONE, "No records", "No records"
        else:
            human, tick, pathogen = HUMAN_NONE, "Reported", "Unknown"
        rows.append(
            _county(
                index,
                state="AA" if index <= 20 else "BB",
                svi=index / 100,
                human=human,
                tick=tick,
                pathogen=pathogen,
            )
        )
    return tuple(rows)


def _county(
    index: int,
    *,
    state: str,
    svi: float = 0.2,
    human: str = HUMAN_NONE,
    tick: str = "No records",
    pathogen: str = "No records",
) -> County:
    return County(
        fips=f"{index:05d}",
        name=f"County {index}",
        state=state,
        population=1000.0 + index,
        svi=svi,
        uninsured=min(0.95, 0.05 + index / 80),
        rucc=(index % 9) + 1,
        human_status=human,
        scapularis="Established" if index % 2 == 0 else "No records",
        pacificus="No records",
        burgdorferi=pathogen,
        tick_status=tick,
    )


def _row(index: int) -> dict[str, object]:
    county = _county(index, state="AA")
    return {
        "FIPS": county.fips,
        "COUNTY": county.name,
        "STATE": county.state,
        "RELEASE_ID": "governed-2026-10-15-january-climate-prod",
        "POPULATION": county.population,
        "SVI_PERCENTILE": county.svi,
        "UNINSURED_PERCENTILE": county.uninsured,
        "RUCC_2023": county.rucc,
        "HUMAN_STATUS": county.human_status,
        "SCAPULARIS_STATUS": county.scapularis,
        "PACIFICUS_STATUS": county.pacificus,
        "BURGDORFERI_STATUS": county.burgdorferi,
        "TICK_STATUS": county.tick_status,
    }


def test_one_hot_levels_cover_the_frozen_rucc_list() -> None:
    assert RUCC_LEVELS[0] == "1"
    assert RUCC_LEVELS[-1] == "unlisted"
    assert np.isfinite(GAMMA)
