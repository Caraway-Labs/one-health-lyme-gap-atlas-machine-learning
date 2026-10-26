# ML #123 state reporting regimes: registered specification v1

- **Spec/version and owning issue:** `123-state-reporting-regimes/v1`, [ML #123](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/123), parent epic [ML #118](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/118), program epic [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md). Matthew Caraway authorized this story through the EDA queue on 2026-10-26. This run does not authorize a Tier 1 change, a PROD write, an API, a pipeline, a UI, or a public score.
- **Question / decision / allowed interpretation:** Which states resemble each other in publication, tick documentation, and pathogen documentation? Which group contains high-publication Northeast states, and which group contains states with no published county floor? After publication rate is removed, which states still look alike on tick coverage, pathogen coverage, and rural mix? Which profile, if either, may a later county model use as a state effect? The method decision is keep, revise, or stop. The product decision is advance, investigate, or stop. A group is a descriptive partition of states. It is not a risk tier, an incidence tier, a hot spot, or a training label. `No records` and `Unknown` are not negatives. A missing published floor is not zero. No production score is published.
- **Estimand:** On the pinned release, two partitions of the 51 state rows (50 states and the District of Columbia). For each profile: the chosen group count, Euclidean silhouette, leave-one-state-out median and minimum adjusted Rand index, and the bootstrap adjusted Rand interval. Between profiles: the adjusted Rand index and the state-count contingency table. Also the count of states with a zero published-floor share and the sum of their county counts, compared with the #107 result (19 states, 1,437 counties). #109 supplies the status definitions (published floor, established tick, pathogen present, and the national unpublished count 2,493 of 3,144). #110 supplies Ward linkage, Euclidean silhouette, adjusted Rand, `StandardScaler`, and the #116 resample interval used for the bootstrap. This story does not refit the #110 county K-means.

## Unit, cohort, and pin

One state row, built from the counties on `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. The expected county count is 3,144 and the expected state count is 51. This is one snapshot. It is not a change contrast and not a forecast. Human surveillance is calendar 2023. The rural-urban code is 2023. Tick and pathogen statuses are cumulative through 2025-12-31.

Pin `RELEASE_ID`, `SCHEMA_VERSION`, `BUNDLE_SHA256`, `METHODOLOGY_VERSION`, and `SCOPE` from `PRESENTATION.CURRENT_RELEASE_V` before the fit. The pin, read before this spec was frozen, is release `governed-2026-10-15-january-climate-prod`, schema `2.0.0`, methodology `semantic-2.0.0`, scope `US_COUNTIES`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`.

Objects and columns read:

| Object | Columns |
| --- | --- |
| `PRESENTATION.CURRENT_RELEASE_V` | `RELEASE_ID`, `SCHEMA_VERSION`, `METHODOLOGY_VERSION`, `SCOPE`, `BUNDLE_SHA256` |
| `PRESENTATION.CURRENT_COUNTY_ATLAS_V` | `STATE`, `FIPS`, `RUCC_2023`, `HUMAN_STATUS`, `TICK_STATUS`, `BURGDORFERI_STATUS`, `INCIDENCE_FLOOR_2023`, `RELEASE_ID` |

No other column is selected. Do not select county name, payload, part text, limitation text, geometry, case floors, population, social vulnerability, or insurance. County rows may stay in memory. They are not written to git, to a chart, or to Drive.

## Variables

State rows are sorted by postal code before any fit. Shares use the state county count as the denominator. A share of zero is a real share. It is not an imputed floor.

| Feature | Construction | Profile |
| --- | --- | --- |
| `published_share` | Share of counties with `HUMAN_STATUS` = `published_count_floor` | descriptive only |
| `tick_established_share` | Share of counties with `TICK_STATUS` = `Established` | both |
| `pathogen_present_share` | Share of counties with `BURGDORFERI_STATUS` = `Present` | both |
| `median_published_floor` | Median of non-null `INCIDENCE_FLOOR_2023`. The displayed name is the published floor rate per 100,000. The source column keeps its warehouse name | descriptive only, and only as specified below |
| `rural_nonmetro_share` | Share of counties with `RUCC_2023` in {4, 5, 6, 7, 8, 9}. Codes 1–3 are metropolitan. This is the #116 USDA split | publication-free only |

Allowed levels, from the #109 and #110 reads of this pin: human `published_count_floor` or `no_county_linked_record`; tick `Established`, `Reported`, `No records`, or `Unknown`; pathogen `Present`, `No records`, or `Unknown`. Any other level stops the fit. `Reported`, `No records`, and `Unknown` stay in the denominator and out of the established-tick numerator. Pathogen `No records` and `Unknown` stay in the denominator and out of the present numerator.

### Missing median rule

The median uses `statistics.median` on the non-null published floors in the state (the mean of the two middle values when the count is even). If that count is zero, the stored median is missing. It is never stored as zero, and it is never filled with zero before the distance is built.

A state with `published_share` of zero and a non-null floor, or a state with a positive published share and no non-null floor, stops the fit.

Descriptive raw matrix, column order fixed, one row per state:

1. `published_share`
2. `tick_established_share`
3. `pathogen_present_share`
4. `median_observed`: 1 when the median exists, else 0
5. `median_coordinate`: `sklearn.preprocessing.StandardScaler` fit on the observed medians only. States with a missing median receive the product of `median_observed` and that scaled median, which is 0 because the indicator is 0. That coordinate is not written into the median field. A stored median of zero would mean a published floor rate of zero. This coordinate does not mean that.

One further `StandardScaler` is fit on all 51 rows and these five columns. Ward uses that jointly standardized matrix. If the observed medians have population standard deviation 0, `median_coordinate` is 0 for every state, the joint scaler leaves that column with no contrast, and `median_contrast` is recorded as false. The indicator column still separates states that have no published median. Those states stay in the descriptive partition.

The publication-free raw matrix is only `tick_established_share`, `pathogen_present_share`, and `rural_nonmetro_share`, jointly standardized. It does not include `published_share`, `median_observed`, `median_coordinate`, or the stored median.

## Method

Distance is Euclidean. Primary linkage is Ward, `sklearn.cluster.AgglomerativeClustering(linkage='ward')`, the same class #110 uses. Ward has no seed. The row order is the postal-code order.

The group count is not taken from #110 and is not chosen by eye. For each profile, and for each k in {2, 3, 4, 5, 6}:

- Fit Ward on the jointly standardized matrix.
- Euclidean silhouette from `sklearn.metrics.silhouette_score`, the same metric #110 uses. A failure makes that k inadmissible.
- Leave-one-state-out: drop one state, refit the scaler and Ward at the same k on the other 50, and take the adjusted Rand index against the full-sample labels of those 50. Record the median and the minimum. There is no seed.
- Bootstrap: `test_selection.resample_interval` with 2,000 replicates. The descriptive seed is `1232026`. The publication-free seed is `1232027`. Each replicate draws 51 states with replacement, refits the scaler and Ward, and assigns every original state to the nearest bootstrap centroid in that refit space. The interval is the #116 percentile interval (2.5 and 97.5, linear index `(n-1)*p`). A replicate that cannot form k centroids counts as a failure. The interval is not estimable when failures exceed 5 percent.

A k is admissible when the silhouette is finite, the leave-one-state-out median is at least 0.70, the bootstrap interval is estimable, and its lower endpoint is at least 0.40. Among admissible k, choose the largest silhouette. Ties break toward the higher leave-one-state-out median, then toward the smaller k. If no k is admissible, the same ordering still picks a reported cut and `cut_stable` is false.

Group ids are relabeled 1..k by descending size, then by the first postal code in the group. The display name is `group` plus that id. It is not a risk tier.

Alternatives are fit at the chosen k and are not used to choose k or to replace the Ward labels:

- average linkage and complete linkage on the same standardized matrix, adjusted Rand against Ward
- descriptive sensitivity that drops the two median columns and keeps the three shares, Ward, adjusted Rand against the primary descriptive labels

The dendrogram is the full Ward tree (`distance_threshold=0`). The drawn cut sits halfway between the merge that reached k groups and the next merge. Labels on that tree must match `n_clusters=k` with adjusted Rand 1. State labels on the image are postal codes. The image does not print share values, medians, or county counts, so a state with fewer than 11 counties is named and its suppressed shares are not printed.

- **Missingness rule:** Do not impute a floor, a tick status, or a pathogen status with zero, Established, or Present. The median rule above is the only missing-value coordinate, and it does not write a median. A null rural-urban code, or a code that is not an integer from 1 through 9, stops the fit. Do not drop a state to finish the partition.
- **Exploratory or confirmatory:** Confirmatory for the release pin, the county count 3,144, the state count 51, the #107 zero-published comparison (19 states, 1,437 counties), and the two acceptance rules below. The k grid is the prespecified search. Nothing in the results changes a threshold, a seed, a linkage, or a feature after the fit.

## Dependence, output, and stop conditions

- **Spatial / temporal dependence:** Counties in one state share a reporting rule, so the unit is the state. Leave-one-state-out and the state bootstrap do not cover dependence that crosses a state line. The windows above are not one time base. No p-value is reported.
- **Effect-size / uncertainty output:** Chosen k, silhouette, leave-one-state-out median and minimum, bootstrap interval, cross-profile adjusted Rand index, contingency counts, and group membership. A group summary lists every member state. Numeric group summaries use only member states with at least 11 counties, and only when at least 11 such states are in the group.
- **Key caveat / stop conditions:** Stop if the context check is not `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Stop if the live release id, schema, methodology, scope, or bundle SHA differs from the pin. Stop if the county count is not 3,144, if `FIPS` values are not unique five-digit ids, if the state count is not 51, if any status or rural-urban code is outside the levels above, or if publication and the floor column disagree. A query still running at 10 minutes is cancelled. Do not read `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, `KNOWLEDGE_GRAPH`, historical CDC snapshots, or any column other than the list above.

Small cells: a state with fewer than 11 counties stays in both partitions. In the lab assignment table, git files other than the `docs/eda/` write-up, and Drive charts, report the group and suppress the per-state shares, the stored median, the rural share, the county count, and the zero-published flag. The write-up and the issue comment may show the full state row, including a small count. A contingency cell whose state count is 1 to 10 is blank on the chart and suppressed in lab metrics. A zero cell on a denominator of 51 may be stated as zero in the write-up.

## Result disposition

**PLANNED.** After the fit, apply this rule without changing it.

Method **stop** when a stop gate fails or either profile cannot be fit. Method **keep** only when every line below holds for both profiles. Otherwise the method decision is **revise**.

- `cut_stable` is true.
- Silhouette is at least 0.25.
- Leave-one-state-out median adjusted Rand index is at least 0.80.
- The bootstrap interval is estimable and its lower endpoint is at least 0.50.
- Each of the 51 states is in exactly one group.
- Tree labels and `n_clusters=k` labels have adjusted Rand index 1.
- The publication-free matrix uses only the three publication-free features.
- Every state with `published_share` 0 is present in the descriptive partition, and its stored median is missing.
- The zero-published comparison matches #107: 19 states and 1,437 counties.

**Product call.** **stop** when the method decision is stop. **advance** when the method decision is keep and the adjusted Rand index between the two chosen partitions is below 0.50. **investigate** otherwise.

Feature rule, tied to that call: the publication-free group id may be used as a categorical state effect in a later county-model story only when the product call is advance. The descriptive group id is a briefing result and is not a county-model feature, because its matrix includes the publication share and the median coordinate. Advance does not fit a model, publish a score, or change a tier.

- **Reproduction / evidence:** SQL in `sql/validation/123_state_regimes.sql`. Runner `scripts/eda_123_state_regimes.py`. Fit logic `src/lyme_gap_atlas_ml/state_regimes.py`. Lab writer `src/lyme_gap_atlas_ml/snowflake/state_regime_groups.py`, reusing `eda_writer.write_eda_results`, `eda_lab_writers.write_findings`, `eda_lab_writers.write_queries`, and the experiment insert shape from `peer_cluster_scores.py`. Run id pattern `123-state-reporting-regimes-<UTC yyyymmddThhmmZ>`. Charts under git-ignored `artifacts/charts/123/`, each PNG kept under about 40 KB, uploaded to Drive folder `issue-123` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`. Durable narrative: `docs/eda/123-state-reporting-regimes.md`. Writes are insert-only. A run id that already has a `REGISTRY.RUNS` row is not written again. The role cannot `DELETE`. The writer attempts `GRANT SELECT` on the new lab table to `OH_LYME_PROD_READ` and records whether the grant succeeded.

  ```text
  uv sync --locked --extra dev --extra snowflake
  uv run python scripts/check_ml_agent_context.py
  MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_123_state_regimes.py
  uv run python scripts/verify.py
  ```
