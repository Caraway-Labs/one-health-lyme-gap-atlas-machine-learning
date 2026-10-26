# ML #110 peer-county clusters: registered specification v1

- **Spec/version and owning issue:** `110-peer-county-clusters/v1`, [ML #110](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/110), parent [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md). Matthew Caraway authorized this story through the EDA queue on 2026-10-26. This run does not authorize a Tier 1 change, a PROD write, an API, a pipeline, a UI, or a public score.
- **Question / decision / allowed interpretation:** Do the four context-only clusters in epic #22 section 4.1 reproduce on the pinned release, are they stable enough to keep, and can multi-domain environmental, vector, human, and population features reveal stable peer-county groups? The cluster decision is keep, revise, or stop. The product decision is advance, investigate, or stop. A cluster is a descriptive grouping. It is not incidence, risk, causation, a hot spot, or a training label. `No records` and `Unknown` are not negatives. A missing human floor is not zero. No new production model, API, pipeline, or public-facing score.
- **Estimand:** On the pinned release, for each frozen slice below: K-means labels at k = 4, the cluster-size multiset, the Euclidean silhouette, the adjusted Rand index against the alternate seed, the #116 state-cluster and county-resample intervals of the assignment adjusted Rand index, the leave-one-Census-region and leave-one-state held-in adjusted Rand indexes, the Ward adjusted Rand index against K-means, the doubled-SVI-weight adjusted Rand index where that sensitivity is defined, Cramér's V of the labels against publishing-state membership and Census region, and the largest share of a cluster that sits in a non-publishing state. The October 13 comparison is the context-only size multiset, silhouette, and SVI-weight adjusted Rand index. County names and county-level numbers may appear in the lab cluster table, the results write-up, the pull-request body, and the issue comment. Charts, other Drive files, and lab aggregate tables stay aggregate and suppress a count from 1 to 10.
- **Unit / cohort / geography / time:** One county on `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. The expected county count is 3,144. Census region, from `coverage_audit.CENSUS_REGIONS`, is the state block. A county-adjacency table does not exist and is not used. This is one snapshot. It is not a change contrast and not a forecast. Human surveillance is calendar 2023. Population, social vulnerability, and uninsured context are the 2022 county layer. The rural-urban code is 2023. Tick and pathogen statuses are cumulative through 2025-12-31. Climate, when the aggregate returns, is the January 2025 county-day window already described by #109.

## Variables and slices

Pin `RELEASE_ID`, `SCHEMA_VERSION`, `BUNDLE_SHA256`, `METHODOLOGY_VERSION`, and `SCOPE` from `PRESENTATION.CURRENT_RELEASE_V` before the fit. The expected pin, read before this spec was frozen, is release `governed-2026-10-15-january-climate-prod`, schema `2.0.0`, methodology `semantic-2.0.0`, scope `US_COUNTIES`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`.

Objects read:

| Object | Columns |
| --- | --- |
| `PRESENTATION.CURRENT_RELEASE_V` | `RELEASE_ID`, `SCHEMA_VERSION`, `METHODOLOGY_VERSION`, `SCOPE`, `BUNDLE_SHA256` |
| `PRESENTATION.CURRENT_COUNTY_ATLAS_V` | `FIPS`, `COUNTY`, `STATE`, `POPULATION`, `SVI_PERCENTILE`, `UNINSURED_PERCENTILE`, `RUCC_2023`, `HUMAN_STATUS`, `TICK_STATUS`, `BURGDORFERI_STATUS`, `RELEASE_ID` |
| `PRESENTATION.CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V` | County aggregates only: `COUNTY_FIPS`, mean and day count of `VALUE_NATIVE_DOUBLE` for the two measures below, restricted to `VALUE_STATE` in `OBSERVED` or `ZERO` |
| `PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V` | Distinct county count where `MEASURE_ID` starts with `nlcd_` |

No other column is selected. Do not select payload, part text, limitation text, geometry, case floors, or incidence floors.

The October 13 fit is the prose in epic #22 section 4.1. This repository has no script, notebook, or parameter file for that fit. The recorded figures, which this spec compares and does not replace, are four context-only K-means clusters from social-vulnerability percentile and log population, sizes 703, 828, 461, and 1,152, silhouette 0.389, stable across seeds, and adjusted Rand index 0.365 after doubling the SVI weight.

Feature construction, in frozen order. Standardization is `sklearn.preprocessing.StandardScaler` (mean 0, standard deviation 1), fit on the rows of that fit only, after the unit rule. Distance is Euclidean in that standardized space.

| Feature | Construction | Slices |
| --- | --- | --- |
| `log_population` | Natural log of `POPULATION` | context, extended, multi-domain |
| `svi_percentile` | `SVI_PERCENTILE` after the unit rule | context, extended, multi-domain |
| `uninsured_percentile` | `UNINSURED_PERCENTILE` after the unit rule | extended, multi-domain |
| `rucc_2023` | `RUCC_2023` as an ordered integer, then standardized. Not one-hot | extended, multi-domain |
| `january_tavg_c` | County mean of `nclimgrid_tavg_county_day`, degrees Celsius | climate, multi-domain |
| `january_prcp_mm` | County mean of `nclimgrid_prcp_county_day`, millimeters | climate, multi-domain |
| `human_published` | 1 when `HUMAN_STATUS` is `published_count_floor`, else 0 when it is `no_county_linked_record` | coverage |
| `tick_established`, `tick_reported`, `tick_unknown` | One-hot of `TICK_STATUS`. `No records` is the omitted reference level | coverage |
| `pathogen_present`, `pathogen_unknown` | One-hot of `BURGDORFERI_STATUS`. `No records` is the omitted reference level | coverage |

Context-only is the reproduction slice: log population and SVI only. Extended context adds uninsured percentile and the ordered rural-urban code. Climate is the environment slice. Coverage is the surveillance-status slice and is never concatenated into context, extended, climate, or multi-domain. Multi-domain is extended context plus the two climate means, on the climate cohort. Vector evidence enters only as tick documentation status inside the coverage slice. No national vector-abundance column is on the allow-list. Maximum and minimum temperature are not features; they repeat the average-temperature contrast. Land cover is not a feature. The NLCD county count is reported. It is not clustered, including when the count is not national.

Unit rule, frozen before the fit: if the maximum of `SVI_PERCENTILE` or `UNINSURED_PERCENTILE` on the included rows of a slice is greater than 1.5, divide that column by 100 and record the column. Do not clip.

A non-publishing state is a state with zero counties whose human status is `published_count_floor`, judged on the full atlas cohort before slice exclusion.

- **Missingness rule:** Do not impute. Do not replace a gap with zero, Established, or Present. A recorded climate `ZERO` with a non-null native value is an observed zero and stays in the mean. A null native value is omitted from that county's mean and is not filled. A county needs at least 20 such days for each climate measure to enter the climate cohort. Context-only drops a county with null or non-positive population or null SVI. Extended context also drops null uninsured percentile or a rural-urban code that is not an integer from 1 through 9. Multi-domain uses the intersection of the extended-context rules and the climate cohort. Coverage drops a county only when a status is outside the allowed levels, and that event stops the fit rather than recoding the level to zero. The exclusion count of each slice is a result. A duplicate `FIPS`, a `FIPS` that is not five digits, or a state missing from the Census map stops the fit.
- **Exploratory or confirmatory:** Confirmatory for the release pin, the county count 3,144, and the comparison to the October 13 size multiset, silhouette, and SVI-weight adjusted Rand index. The stability intervals and the other slices are the prespecified descriptive results of the rules below. Nothing in those results changes a threshold, a seed, a weight, or a k after the fit. The October 13 fitting code is not in this repository, so a mismatch is reported. It is not tuned away.

## Method

Baselines first. K-means and Ward hierarchical clustering use the same standardized matrix. Density and mixture models run only if the justification gate opens. They are not used to pick k.

| Setting | Frozen value |
| --- | --- |
| Primary k | 4, matching the October 13 grouping |
| k grid | 2 through 8. The grid does not replace k = 4. It is a sensitivity |
| K-means | `sklearn.cluster.KMeans`, `init='k-means++'`, `algorithm='lloyd'`, `max_iter=300`. Primary, seed comparison, Ward comparison, weight, unscaled, k grid, and holdouts use `n_init=10`. Each #116 bootstrap replicate uses `n_init=1` so the replicate count stays the #116 count |
| Seeds | Primary `1102026`. Alternate `1102027`. Bootstrap streams use those seeds inside `test_selection.state_cluster_interval` and `test_selection.resample_interval` |
| Hierarchical | `AgglomerativeClustering`, `linkage='ward'`, k = 4, on the same standardized matrix. Ward has no seed |
| SVI weight | After standardization, multiply the SVI column by 2 and refit K-means at k = 4. Do not standardize again. Applied to context-only and multi-domain |
| Unscaled | K-means at k = 4 on the unstandardized slice matrix. Reported. It is not a keep bar except where a bar below names it |
| Silhouette | `sklearn.metrics.silhouette_score`, Euclidean, on the standardized matrix of the fit |
| Adjusted Rand | `sklearn.metrics.adjusted_rand_score` |
| State-cluster interval | `test_selection.state_cluster_interval` on context-only and multi-domain only. 2,000 replicates, percentiles 2.5 and 97.5, linear index `(n-1)*p`. The statistic refits the scaler and K-means on the drawn states and assigns every original county in the slice to the nearest bootstrap centroid. A draw that cannot fit k groups returns a failure |
| County interval | `test_selection.resample_interval` with the same assignment rule, context-only and multi-domain only. This is the dependence diagnostic |
| Region holdout | Drop one Census region, refit, adjusted Rand on the counties that stayed in, versus the full-sample labels. The bar uses the minimum of the four |
| State holdout | Drop one state, same held-in adjusted Rand. The bar uses the median across states that return an index. The minimum is reported |
| Association | `test_selection.cramers_v` for cluster by publishing-state indicator, Census region, human status, and tick status |
| Representatives | Three counties closest to the cluster mean in the standardized space. Ties break toward the smaller `FIPS`. Context-only, and multi-domain when that slice exists |
| Small cells | A count from 1 to 10 is not published in lab aggregate tables or charts. A zero on a denominator of at least 11 is kept |

Density gate, opened only for the context-only standardized matrix, and only when the k = 4 silhouette is below 0.25 or the smallest cluster's share of the slice is below 0.05. If the gate stays closed, Gaussian mixture, DBSCAN, and HDBSCAN are not fit.

| Method, only if the gate opens | Frozen setting |
| --- | --- |
| Gaussian mixture | `GaussianMixture`, 4 components, `covariance_type='diag'`, `n_init=3`, `max_iter=200`, `random_state=1102026` |
| DBSCAN | `eps=0.9`, `min_samples=40`, Euclidean. Label `-1` is noise. No second eps is tried |
| HDBSCAN | `min_cluster_size=80`, `min_samples=15`, `cluster_selection_method='eom'`, `random_state=1102026`. Label `-1` is noise |

There is no county-adjacency matrix. Spatial leakage is the state holdout and the Census-region holdout. Surveillance confounding is Cramér's V and the non-publishing share, not a feature inside the context slices.

- **Spatial / temporal dependence:** Counties in one state share reporting rules. The state-cluster interval resamples states. It does not cover dependence that crosses a state line. Region and state holdouts ask whether the labels are an artifact of one block. The windows above are not one time base. No p-value is reported.
- **Effect-size / uncertainty output:** Sizes, silhouette, adjusted Rand indexes, the two intervals on the two primary slices, holdout indexes, Cramér's V, non-publishing shares, standardized cluster means, and three representative counties per reported cluster. Histogram bins are not an estimand.
- **Key caveat / stop conditions:** Stop if the context check is not `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Stop if the live release id, schema, methodology, scope, or bundle SHA differs from the pin above. Stop if the county count is not 3,144, if `FIPS` are not unique five-digit ids, or if any state is outside the Census map. Stop if any human, tick, or pathogen status is outside the levels named above. Stop the context-only fit if fewer than two features remain or fewer than 500 counties remain. A climate query that fails or is still running at 9 minutes makes the climate and multi-domain slices not estimable. It does not by itself stop the context-only fit. Do not read `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, `KNOWLEDGE_GRAPH`, historical CDC snapshots, or any column other than the list above. A query still running at 10 minutes is cancelled. County rows may stay in memory. They are not written to a data extract, a chart, or Drive. Cluster assignments, including the county name, are inserted only into `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.COUNTY_CLUSTERS_110`.

## Result disposition

**PLANNED.** After the fit, apply this rule without changing it.

October 13 reproduction, context-only only:

- Sizes reproduce when the size multiset equals {461, 703, 828, 1152}.
- Silhouette reproduces when the absolute difference from 0.389 is at most 0.010.
- The SVI-weight result reproduces when the absolute difference from 0.365 is at most 0.020.

Context-only **keep** requires every line below. Otherwise the cluster decision is **revise**. The cluster decision is **stop** when a stop gate above fails or the context-only fit is not estimable.

- Sizes reproduce and silhouette reproduces.
- Silhouette is at least 0.25.
- Alternate-seed adjusted Rand index is at least 0.90.
- The state-cluster adjusted Rand interval is estimable and its lower endpoint is at least 0.80.
- The minimum leave-one-region held-in adjusted Rand index is at least 0.70.
- The median leave-one-state held-in adjusted Rand index is at least 0.90.
- Ward versus K-means adjusted Rand index is at least 0.50.
- Doubled-SVI-weight adjusted Rand index is at least 0.80.
- No k in 2 through 8 has silhouette at least 0.05 above the k = 4 silhouette.
- No cluster of at least 11 counties has 0.80 or more of its counties in non-publishing states.
- Publishing-state Cramér's V is either not estimable or below 0.50.
- Context-only exclusions are zero.

Census-region Cramér's V is reported. A value of 0.50 or more blocks product advance. It does not by itself block keep.

**Product call.** **stop** when the cluster decision is stop. **advance** when multi-domain is estimable, its climate cohort covers at least 0.90 of the 3,144 counties, and the multi-domain slice meets the same stability lines as keep (seed, state-cluster lower endpoint, region minimum, state median, Ward, SVI weight, k grid, surveillance bars, silhouette at least 0.25) and its Census-region Cramér's V is estimable and below 0.50. **investigate** otherwise. Advance authorizes a later design story for the text concept below. It does not authorize a model, a rank, or a public map.

The text concept, drafted with the results and not built: a reviewer chooses a county and sees the nearest counties in one frozen standardized space, with the distance and the cluster's aggregate profile. Surveillance status is displayed beside those peers as documentation. It is not part of the distance and it is not a risk score.

- **Reproduction / evidence:** SQL in `sql/validation/110_peer_clusters.sql`. Runner `scripts/eda_110_peer_clusters.py`. Fit logic `src/lyme_gap_atlas_ml/peer_clusters.py`. Lab writer `src/lyme_gap_atlas_ml/snowflake/peer_cluster_scores.py`, reusing `eda_writer.write_eda_results`, `eda_lab_writers.write_findings`, `eda_lab_writers.write_queries`, and the experiment insert shape from `anomaly_scores.py`. Run id pattern `110-peer-county-clusters-<UTC yyyymmddThhmmZ>`. Charts under git-ignored `artifacts/charts/110/`, uploaded to Drive folder `issue-110` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`. Durable narrative: `docs/eda/110-peer-county-clusters.md`. Writes are insert-only. A run id that already has a `REGISTRY.RUNS` row is not written again. The role cannot `DELETE`.

  ```text
  uv sync --locked --extra dev --extra snowflake
  uv run python scripts/check_ml_agent_context.py
  MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_110_peer_clusters.py
  uv run python scripts/verify.py
  ```
