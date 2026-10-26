"""Issue 110 peer-county clusters. No live warehouse connection."""

from __future__ import annotations

from pathlib import Path

from lyme_gap_atlas_ml.coverage_audit import PINNED_BUNDLE_SHA256, PINNED_RELEASE_ID
from lyme_gap_atlas_ml.peer_cluster_report import (
    build_findings,
    profile_frame,
    render_comment,
    stability_frame,
)
from lyme_gap_atlas_ml.peer_clusters import (
    CONTEXT_FEATURES,
    COVERAGE_FEATURES,
    OCT13_SIZES,
    SCHEMA_VERSION,
    SCOPE,
    SPEC_ID,
    Analysis,
    County,
    Decision,
    SliceFit,
    analyze,
    build_counties,
    decide,
    lab_metrics,
    load_peer_queries,
    release_matches,
)
from lyme_gap_atlas_ml.snowflake.eda_lab_writers import prepare_finding
from lyme_gap_atlas_ml.snowflake.peer_cluster_scores import (
    _CREATE_CLUSTERS,
    _GRANT,
    _INSERT_CLUSTERS,
    CLUSTER_TABLE,
    cluster_table_sql,
)

SQL_PATH = "sql/validation/110_peer_clusters.sql"
_STATES = ("ME", "NY", "PA", "OH", "IL", "WI", "VA", "GA", "TX", "CO", "CA", "WA")


def test_queries_do_not_impute_or_read_free_text() -> None:
    text = Path(SQL_PATH).read_text(encoding="utf-8")
    queries = load_peer_queries(text)
    climate = queries["climate_county"].upper()
    assert "VALUE_STATE IN ('OBSERVED', 'ZERO')" in climate
    assert "VALUE_NATIVE_DOUBLE IS NOT NULL" in climate
    assert "COALESCE" not in climate
    assert "ZEROIFNULL" not in climate
    joined = "\n".join(queries.values()).upper()
    for token in ("LIMITATIONS", "PART_TEXT", "PAYLOAD", "GEOMETRY_JSON", "CASE_COUNT_FLOOR"):
        assert token not in joined


def test_release_pin_matches_the_frozen_spec() -> None:
    ok, reasons = release_matches(
        {
            "RELEASE_ID": PINNED_RELEASE_ID,
            "SCHEMA_VERSION": SCHEMA_VERSION,
            "METHODOLOGY_VERSION": "semantic-2.0.0",
            "SCOPE": SCOPE,
            "BUNDLE_SHA256": PINNED_BUNDLE_SHA256,
        }
    )
    assert ok
    assert reasons == ()
    shifted, mismatch = release_matches(
        {
            "RELEASE_ID": "other",
            "SCHEMA_VERSION": SCHEMA_VERSION,
            "METHODOLOGY_VERSION": "semantic-2.0.0",
            "SCOPE": SCOPE,
            "BUNDLE_SHA256": PINNED_BUNDLE_SHA256,
        }
    )
    assert not shifted
    assert mismatch == ("release_id",)


def test_missing_svi_is_excluded_and_not_zero() -> None:
    rows = [_atlas(index) for index in range(3144)]
    rows[3]["SVI_PERCENTILE"] = None
    rows[4]["SVI_PERCENTILE"] = 250
    rows[5]["RUCC_2023"] = 0
    rows[6]["UNINSURED_PERCENTILE"] = None
    counties = list(build_counties(rows, _climate_rows()))
    counties[7] = _with_climate(counties[7], days=19)
    context = _qualified(counties, CONTEXT_FEATURES)
    assert counties[3].fips not in context
    assert counties[4].fips in context
    extended_features = (
        "log_population",
        "svi_percentile",
        "uninsured_percentile",
        "rucc_2023",
    )
    extended = _qualified(counties, extended_features)
    assert counties[5].fips not in extended
    assert counties[6].fips not in extended
    climate = _qualified(counties, ("january_tavg_c", "january_prcp_mm"))
    assert counties[7].fips not in climate
    assert "human_published" not in CONTEXT_FEATURES
    assert "human_published" in COVERAGE_FEATURES


def test_percentile_above_one_point_five_is_divided_by_100() -> None:
    counties = list(_blobs(n=600))
    high = counties[0]
    counties[0] = County(
        fips=high.fips,
        name=high.name,
        state=high.state,
        region=high.region,
        population=high.population,
        svi=180,
        uninsured=high.uninsured,
        rucc=high.rucc,
        human=high.human,
        tick=high.tick,
        pathogen=high.pathogen,
        tavg=high.tavg,
        tavg_days=high.tavg_days,
        prcp=high.prcp,
        prcp_days=high.prcp_days,
    )
    fitted = analyze(counties, climate_loaded=True, bootstrap=False, enforce_count=False)
    assert fitted.slice("context").percentile_divided == ("svi_percentile",)
    assert fitted.slice("context").excluded == 0
    assert fitted.slice("context").features == CONTEXT_FEATURES


def test_representatives_are_nearest_and_charts_have_no_names() -> None:
    fitted = analyze(_blobs(640), climate_loaded=True, bootstrap=False, enforce_count=False)
    context = fitted.slice("context")
    assert context.estimable
    assert context.representatives
    first = context.representatives[0]
    assert first.rank == 1
    assert first.name
    frame = profile_frame(fitted)
    assert frame
    assert all("name" not in row and "fips" not in row for row in frame)
    _names, columns, matrix = stability_frame(fitted)
    assert "county_low" in columns
    county_index = columns.index("county_low")
    assert all(row[county_index] is None for row in matrix)


def test_decision_rules() -> None:
    kept = _passing_slice("context", sizes=OCT13_SIZES, silhouette=0.389)
    multi = _passing_slice("multidomain", sizes=OCT13_SIZES, silhouette=0.389)
    decision = decide(kept, multi, 3144)
    assert decision.cluster == "keep"
    assert decision.product == "advance"
    fragile = _passing_slice("context", weight_ari=0.365, sizes=OCT13_SIZES, silhouette=0.389)
    revised = decide(fragile, _empty("multidomain"), 3144)
    assert revised.cluster == "revise"
    assert revised.product == "investigate"
    assert "svi_weight" in revised.reasons
    assert revised.weight_reproduced
    stopped = decide(_empty("context"), _empty("multidomain"), 3144)
    assert stopped.cluster == "stop"
    assert stopped.product == "stop"


def test_findings_stay_aggregate() -> None:
    fitted = analyze(_blobs(520), climate_loaded=False, bootstrap=False, enforce_count=False)
    findings = build_findings(fitted)
    assert len(findings) == 3
    for index, finding in enumerate(findings, start=1):
        prepare_finding(finding, finding_id=f"11011010-0000-4000-8000-{index:012d}")
    comment = render_comment(
        fitted,
        run_id="110-peer-county-clusters-20261026T0000Z",
        git_commit="abc",
        row_counts={"EDA.COUNTY_CLUSTERS_110": 520},
        drive_links=(),
        missing_charts=("cluster-profile.png",),
        grant_note="SELECT was not granted.",
    )
    assert "1. Question" in comment
    assert "5. Disposition" in comment
    assert SPEC_ID in comment
    assert "cluster-profile.png" not in "".join(row["cluster"] for row in profile_frame(fitted))


def test_small_cluster_composition_is_omitted() -> None:
    context = _passing_slice("context", sizes=(5, 100, 100, 100), silhouette=0.40)
    analysis = Analysis(
        counties=(),
        publishing_states=frozenset(),
        slices=(
            context,
            _empty("extended"),
            _empty("climate"),
            _empty("coverage"),
            _empty("multidomain"),
        ),
        decision=Decision(
            "revise",
            "investigate",
            ("sizes",),
            ("multidomain_not_estimable",),
            False,
            False,
            False,
        ),
        nlcd_counties=2,
        climate_loaded=False,
        experiments=(),
    )
    metrics = lab_metrics(analysis)
    assert all(metric.metric_name != "cluster_size" for metric in metrics)


def test_cluster_sql_is_insert_only_ml_lab() -> None:
    sql = cluster_table_sql()
    assert "ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.COUNTY_CLUSTERS_110" in sql
    assert "DELETE" not in sql.upper()
    assert CLUSTER_TABLE in _INSERT_CLUSTERS
    assert "GRANT SELECT" in _GRANT
    assert "OH_LYME_PROD_READ" in _GRANT
    assert "DELETE" not in _CREATE_CLUSTERS.upper()


def _qualified(counties: tuple[County, ...] | list[County], features: tuple[str, ...]) -> set[str]:
    from lyme_gap_atlas_ml.peer_clusters import _matrix

    mask, _raw, _divided = _matrix(counties, features)
    return {county.fips for county, keep in zip(counties, mask, strict=True) if keep}


def _atlas(index: int) -> dict[str, object]:
    state = _STATES[index % len(_STATES)]
    return {
        "FIPS": f"{index:05d}",
        "COUNTY": f"County {index}",
        "STATE": state,
        "POPULATION": 1000 + index,
        "SVI_PERCENTILE": (index % 100) / 100,
        "UNINSURED_PERCENTILE": ((index + 7) % 100) / 100,
        "RUCC_2023": (index % 9) + 1,
        "HUMAN_STATUS": "published_count_floor" if index % 5 == 0 else "no_county_linked_record",
        "TICK_STATUS": "Established" if index % 3 == 0 else "No records",
        "BURGDORFERI_STATUS": "Present" if index % 4 == 0 else "No records",
        "RELEASE_ID": PINNED_RELEASE_ID,
    }


def _climate_rows() -> list[dict[str, object]]:
    return [
        {
            "COUNTY_FIPS": f"{index:05d}",
            "TAVG_C": 0.1 * (index % 30),
            "TAVG_DAYS": 31,
            "PRCP_MM": float(index % 5),
            "PRCP_DAYS": 31,
        }
        for index in range(3144)
    ]


def _with_climate(county: County, *, days: int) -> County:
    return County(
        fips=county.fips,
        name=county.name,
        state=county.state,
        region=county.region,
        population=county.population,
        svi=county.svi,
        uninsured=county.uninsured,
        rucc=county.rucc,
        human=county.human,
        tick=county.tick,
        pathogen=county.pathogen,
        tavg=1.0,
        tavg_days=days,
        prcp=0.0,
        prcp_days=days,
    )


def _blobs(n: int) -> tuple[County, ...]:
    counties: list[County] = []
    for index in range(n):
        group = index % 4
        state = _STATES[index % len(_STATES)]
        population = (1000, 20000, 80000, 500000)[group] + index
        counties.append(
            County(
                fips=f"{index:05d}",
                name=f"County {index}",
                state=state,
                region=("Northeast", "Midwest", "South", "West")[_STATES.index(state) // 3],
                population=float(population),
                svi=(0.1, 0.3, 0.7, 0.9)[group],
                uninsured=(0.2, 0.4, 0.6, 0.8)[group],
                rucc=(1, 3, 6, 9)[group],
                human="published_count_floor" if group % 2 == 0 else "no_county_linked_record",
                tick="Established" if group == 0 else "No records",
                pathogen="Present" if group == 0 else "No records",
                tavg=(-5.0, 0.0, 8.0, 15.0)[group],
                tavg_days=31,
                prcp=(10.0, 40.0, 80.0, 120.0)[group],
                prcp_days=31,
            )
        )
    return tuple(counties)


def _passing_slice(
    name: str,
    *,
    weight_ari: float = 0.95,
    sizes: tuple[int, ...] = (800, 800, 800, 744),
    silhouette: float = 0.40,
) -> SliceFit:
    base = _empty(name)
    return SliceFit(
        name=name,
        estimable=True,
        note="fit",
        n=sum(sizes),
        excluded=0,
        features=("log_population", "svi_percentile"),
        percentile_divided=(),
        labels=(),
        silhouette=silhouette,
        sizes=sizes,
        seed_ari=0.97,
        ward_ari=0.80,
        weight_ari=weight_ari,
        unscaled_ari=0.40,
        k_silhouettes=((2, 0.20), (4, silhouette), (5, silhouette)),
        region_held_in=(),
        region_held_out=(),
        region_min=0.85,
        state_holdout_median=0.96,
        state_holdout_min=0.90,
        state_low=0.88,
        state_high=0.99,
        state_estimable=True,
        county_low=0.90,
        county_high=0.99,
        county_estimable=True,
        cramer_publishing=0.10,
        cramer_region=0.20,
        cramer_human=0.10,
        cramer_tick=0.10,
        max_nonpublish_share=0.20,
        max_nonpublish_count=160,
        centers=(),
        representatives=(),
        density=base.density,
    )


def _empty(name: str) -> SliceFit:
    from lyme_gap_atlas_ml.peer_clusters import _empty_slice

    return _empty_slice(name, 0, "not estimable")
