# 110: Do stable peer-county groups exist on the pinned release?

- Issue: [#110](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/110); parent [#22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Question: do the four context-only clusters reproduce, are they stable enough to keep, and can multi-domain features reveal stable peer groups?
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`, county means from `CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V`, and an NLCD county count from `CURRENT_COUNTY_OBSERVATIONS_V`. Release `governed-2026-10-15-january-climate-prod`.
- Cohort: the 3,144-county atlas. Context-only uses complete log population and SVI. Climate and multi-domain use counties with at least 20 observed-or-zero January days for average temperature and precipitation. Coverage statuses are a separate slice.

## Method and assumptions

Spec [110-peer-county-clusters/v1](110-analysis-spec.md), frozen before the fit. Context-only exclusions 0. Percentile columns divided by 100: none. No missing value was replaced with zero. Cluster decision revise. Product call investigate.

## Material findings and limits

1. Question

Do the four context-only clusters in epic #22 section 4.1 reproduce on the pinned release, are they stable enough to keep, and can multi-domain environmental, vector, human, and population features reveal stable peer-county groups?

2. Method (and why; link the spec)

Spec [110-peer-county-clusters/v1](docs/eda/110-analysis-spec.md), frozen before the fit. The October 13 fitting code is not in this repository. The recorded groups used social-vulnerability percentile and log population. This run repeats that pair as the context-only slice, with z-score standardization and Euclidean K-means at k=4, because that is the simplest distance baseline that can be compared with the recorded silhouette and the doubled-SVI-weight adjusted Rand index. Ward clustering is the second baseline on the same matrix. Coverage statuses stay in their own slice so a peer group is not defined by reporting behavior. Climate means enter only the climate and multi-domain slices, and a missing day is left out of the county mean. Seeds 1102026 and 1102027. State-cluster and county-resample intervals use the #116 helpers on the context-only and multi-domain slices.

3. Key findings with numbers

Context-only: n=3144, excluded 0, silhouette 0.3886, sizes 1152/828/703/461, seed adjusted Rand 0.9990, state-cluster interval 0.3899 to 0.9641 (estimable True), county-resample interval 0.3821 to 0.9837 (estimable True), region-holdout minimum 0.7906, state-holdout median 0.9890 (minimum 0.9228), Ward adjusted Rand 0.3753, SVI-weight adjusted Rand 0.3648, unscaled adjusted Rand 0.2532. Standardized means: group 1 (n=1152: log_population -0.2821, svi_percentile 0.9130); group 2 (n=828: log_population 0.4469, svi_percentile -0.8144); group 3 (n=703: log_population -1.0787, svi_percentile -0.9234); group 4 (n=461: log_population 1.5472, svi_percentile 0.5894).

October 13 reference: sizes 703, 828, 461, and 1152; silhouette 0.389; SVI-weight adjusted Rand 0.365. This run: sizes 1152/828/703/461; silhouette 0.3886; SVI-weight adjusted Rand 0.3648. Sizes reproduced: True. Silhouette reproduced: True. Weight result reproduced: True. The epic text says the groups were stable across seeds and that doubling the SVI weight changed membership. Seed adjusted Rand on this pin is 0.9990. A difference from 0.389 or 0.365 is left as a difference: the original seed, scaler, and library version are not in the repository, and the pinned release is governed-2026-10-15-january-climate-prod.

Extended context: n=3144, excluded 0, silhouette 0.3013, sizes 871/853/752/668, seed adjusted Rand 0.9991, state-cluster interval not estimable to not estimable (estimable False), county-resample interval not estimable to not estimable (estimable False), region-holdout minimum 0.5842, state-holdout median 0.9956 (minimum 0.9348), Ward adjusted Rand 0.6868, SVI-weight adjusted Rand 0.6780, unscaled adjusted Rand 0.3034. Standardized means: group 1 (n=871: log_population -0.5242, svi_percentile 0.7835, uninsured_percentile 0.9440, rucc_2023 0.7612); group 2 (n=853: log_population -0.7185, svi_percentile -0.7596, uninsured_percentile -0.6081, rucc_2023 0.8651); group 3 (n=752: log_population 0.6891, svi_percentile -0.7376, uninsured_percentile -0.8844, rucc_2023 -1.0316); group 4 (n=668: log_population 0.8252, svi_percentile 0.7787, uninsured_percentile 0.5412, rucc_2023 -0.9359).

Climate: not estimable (complete case is below the frozen minimum). Excluded 3144. A follow-up county aggregate on this pin, using the frozen rule that a day counts only when VALUE_STATE is OBSERVED or ZERO and VALUE_NATIVE_DOUBLE is non-null, counted 3144 counties, 0 counties with at least 20 usable days for both measures, usable average-temperature days from 0 to 1, usable precipitation days from 0 to 6, and 3143 counties with a null temperature mean. No day was zero-imputed and no other value column was substituted.

Coverage: n=3144, excluded 0, silhouette 0.6678, sizes 1797/822/490/35, seed adjusted Rand 1.0000, state-cluster interval not estimable to not estimable (estimable False), county-resample interval not estimable to not estimable (estimable False), region-holdout minimum 0.5745, state-holdout median 1.0000 (minimum 1.0000), Ward adjusted Rand 0.7551, SVI-weight adjusted Rand not estimable, unscaled adjusted Rand 0.5912. Standardized means: group 1 (n=1797: human_published -0.4767, tick_established -0.2468, tick_reported -0.4297, tick_unknown -0.1061, pathogen_present -0.5284, pathogen_unknown -0.1061); group 2 (n=822: human_published 1.2724, tick_established 1.1132, tick_reported -0.4297, tick_unknown -0.1061, pathogen_present 1.4436, pathogen_unknown -0.1061); group 3 (n=490: human_published -0.3498, tick_established -0.8983, tick_reported 2.3273, tick_unknown -0.1061, pathogen_present -0.4459, pathogen_unknown -0.1061); group 4 (n=35: human_published -0.5110, tick_established -0.8983, tick_reported -0.4297, tick_unknown 9.4249, pathogen_present -0.5298, pathogen_unknown 9.4249).

Multi-domain: not estimable (complete case is below the frozen minimum). Excluded 3144. It uses the same January temperature and precipitation complete-case rule as the climate slice, so it is not estimable for the same reason.

Surveillance check, context-only: publishing-state Cramér's V 0.3488; Census-region Cramér's V 0.3023; human-status Cramér's V 0.4104; tick-status Cramér's V 0.2328; largest non-publishing share 0.6088 (count 428). Multi-domain Census-region Cramér's V not estimable.

The density gate stayed closed, so Gaussian mixture, DBSCAN, and HDBSCAN were not fit.

Find similar counties, as text only: a reviewer would pick a county and see the nearest counties in one frozen standardized space, with the distance and that cluster's aggregate profile (size, social-vulnerability percentile, uninsured percentile, rural-urban code, and January temperature and precipitation when the county is in the climate cohort). Surveillance status would be shown beside the peers as documentation. It would not be a distance feature, a risk score, or a priority rank. This run does not build that view.

Representative counties are the three nearest the cluster mean in standardized space.

| Slice | Group | Rank | County | State | Distance | Population | SVI | RUCC | Human | Tick | Pathogen |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |
| context | 1 | 1 | Covington County | MS | 0.0224 | 18323 | 0.7674 | 8 | no_county_linked_record | Reported | No records |
| context | 1 | 2 | McIntosh County | OK | 0.0391 | 19159 | 0.7528 | 8 | no_county_linked_record | Reported | No records |
| context | 1 | 3 | Wright County | MO | 0.0523 | 18475 | 0.7490 | 8 | no_county_linked_record | No records | No records |
| context | 2 | 1 | Autauga County | AL | 0.0234 | 58761 | 0.2663 | 2 | no_county_linked_record | Established | No records |
| context | 2 | 2 | La Plata County | CO | 0.0253 | 55983 | 0.2580 | 6 | no_county_linked_record | No records | No records |
| context | 2 | 3 | Sandusky County | OH | 0.0259 | 58885 | 0.2622 | 4 | no_county_linked_record | Established | No records |
| context | 3 | 1 | Norton County | KS | 0.0439 | 5431 | 0.2230 | 9 | no_county_linked_record | No records | No records |
| context | 3 | 2 | Sullivan County | PA | 0.0469 | 5880 | 0.2444 | 8 | published_count_floor | Established | Present |
| context | 3 | 3 | Atchison County | MO | 0.0539 | 5270 | 0.2249 | 9 | no_county_linked_record | No records | No records |
| context | 4 | 1 | Durham County | NC | 0.0763 | 325101 | 0.6860 | 2 | published_count_floor | Established | No records |
| context | 4 | 2 | Leon County | FL | 0.0876 | 294128 | 0.6952 | 2 | no_county_linked_record | Established | No records |
| context | 4 | 3 | Luzerne County | PA | 0.0990 | 325396 | 0.6942 | 2 | published_count_floor | Established | Present |

4. Caveats

Counts are surveillance signals. A published human floor is a lower bound (CDC floor 5), not incidence or risk. No records and Unknown are not negatives. Missing is not zero. The context fields, the rural-urban code, tick status, and the January 2025 climate window are not one time base. State-cluster intervals do not cover dependence that crosses a state line. No county-adjacency table was used. The October 13 seed, standardization, and scikit-learn version were not recorded, so a numeric difference can come from those choices or from the release pin. Land cover is not a national feature on this run (NLCD county count 2). Density methods ran only if the frozen gate opened. January climate on this pin does not supply a national VALUE_NATIVE_DOUBLE series under the frozen 20-day rule, so environmental peer groups were not estimated.

5. Disposition: advance / investigate / stop (or keep / revise / stop)

Cluster decision: revise. Product call: investigate.

Do not keep these groups as peer counties. The context-only partition missed state_bootstrap, ward, svi_weight. The October 13 note already treated the SVI-weight change as material, and this pin is held to that same kind of bar. Multi-domain features did not clear the product bar either. Investigate only if a later story freezes a different peer definition. Do not build a similarity score, and do not change the tiers.

6. Artifacts

run_id: 110-peer-county-clusters-20261026T0644Z
Snowflake row counts: REGISTRY.RUNS=1, EDA.METRICS_LONG=118, EDA.FINDINGS=3, REGISTRY.QUERIES=5, EXPERIMENTS.EXPERIMENTS=5, EXPERIMENTS.MODEL_METRICS=34, EDA.COUNTY_CLUSTERS_110=3144.
Drive: Missing charts: cluster-profile.png, stability-heatmap.png
SELECT on EDA.COUNTY_CLUSTERS_110 was granted to OH_LYME_PROD_READ.
Doc: docs/eda/110-peer-county-clusters.md
Spec: docs/eda/110-analysis-spec.md

7. Reproducibility

Commit: 21df201b870680eeb92de735cc582ff11d8956cb
Release: governed-2026-10-15-january-climate-prod
Seeds: primary 1102026, alternate 1102027. Bootstrap uses those seeds inside the #116 helpers. Primary fits use n_init=10. Each bootstrap replicate uses n_init=1.
Commands:
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_110_peer_clusters.py
uv run python scripts/verify.py

County-level cluster rows were not written to git or Drive. Transient chart PNG files under artifacts/charts/110 were uploaded or listed as missing and were not committed.


## Decision

INCONCLUSIVE. The groups are descriptive at most. The product call is investigate or the cluster decision is revise, so no similarity view should be built from this fit.

## Reproduction and retained evidence

- Code revision: `21df201b870680eeb92de735cc582ff11d8956cb`. Run `110-peer-county-clusters-20261026T0644Z`. Spec `110-peer-county-clusters/v1`.
- Entry points: `sql/validation/110_peer_clusters.sql`, `scripts/eda_110_peer_clusters.py`, `src/lyme_gap_atlas_ml/peer_clusters.py`.
- Commands: `uv run python scripts/check_ml_agent_context.py` and `MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_110_peer_clusters.py`.
- Lifecycle: descriptive EDA only. No Tier 1 change and no promotion review.
- Transient artifacts intentionally not committed: county-level frames, `outputs/110-run-id.txt`, and `artifacts/charts/110/*.png`.
