# ML #192 peer-county lookup: registered specification v1

- **Spec/version and owning issue:** `192-peer-county-lookup/v1`, [ML #192](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/192), program epic [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md). Matthew Caraway's standing directive on 2026-10-25, sequenced by the orchestrator on 2026-10-26, authorizes this unsupervised lookup after #188 and #190. This run does not authorize a Tier 1 change, a tier-policy change, a PROD write, an API, a pipeline, a UI, or a public score.
- **Question / decision / allowed interpretation:** For a county, which other counties are nearest on the #120 context features, and does that short list stay put across a second bootstrap seed, a feature-block drop, and a redraw of the county pool? When the county's own state is held out, do the remaining neighbors share its #120 type more often than a same-RUCC match, and does any of the original list survive? Do the lists line up with the #120 types and the #121 situation groups, or does one feature block rebuild the list by itself? The method decision is keep, revise, or stop. The product decision is advance, investigate, or stop. "Similar" means similar on the listed context features only. It does not mean similar disease burden, similar risk, or a validated match. No ground truth exists. A neighbor list is a lookup aid. `No records` and `Unknown` are not negatives. A missing human floor is not zero. A published human count is a lower bound (CDC floor 5). Say published floor, not incidence.
- **Estimand:** On the pinned release, for all 3,144 counties: the k nearest other counties under Euclidean distance and under cosine distance in one frozen embedding of the #120 feature set; the same-state and same-RUCC baseline peer set; nearest-prototype assignment to the two #120 types; leave-state-out type agreement; leave-state-out neighbor-set Jaccard; bootstrap Jaccard of the neighbor sets; silhouette of the prototype labels; feature-block ablation Jaccard; and agreement with the exclusive #121 situation label. #120 supplies the feature list, the mixed-distance weight, and the stored types. #121 supplies the situation predicates and is not a feature source. #110 supplies the question this lookup is allowed to answer and the warning that those clusters were not kept.

## Unit, cohort, and pin

One county on `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. The lookup cohort is the national extract, 3,144 counties. The #120 types exist only for the established-tick gap cohort inside that extract. The resampling and holdout unit is the county, blocked by postal state when a whole state is held out (51 states, including the District of Columbia). This is one snapshot. It is not a change contrast and not a forecast. Human surveillance is calendar 2023. Population, social vulnerability, and uninsured share are the 2022 county layer. The rural-urban code is 2023. Tick species and pathogen statuses are cumulative through 2025-12-31. Those vintages are not one time base.

The context check on 2026-10-26, before this spec was frozen, returned `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Role `OH_LYME_ML_AGENT`, warehouse `OH_LYME_ML_LAB_XS_WH`, database `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`.

Pin, read the same day from `PRESENTATION.CURRENT_RELEASE_V` before this spec was frozen: release `governed-2026-10-15-january-climate-prod`, schema `2.0.0`, methodology `semantic-2.0.0`, scope `US_COUNTIES`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`. The same session's aggregate read returned 3,144 counties, 3,144 distinct FIPS, 51 states, 651 published floors, 2,493 counties with no county-linked human record, 810 in the wider established-tick gap, and 228 in the double gap. Social-vulnerability and uninsured percentiles already sit on 0 to 1. No nulls in population, either percentile, rural-urban code, or the three species and pathogen statuses. `EDA.GAP_COMMUNITY_ASSIGNMENTS_120` for run `120-gap-communities-20261026T1355Z` has 810 rows. That run id is the only #120 assignment source.

Objects and columns read:

| Object | Columns |
| --- | --- |
| `PRESENTATION.CURRENT_RELEASE_V` | `RELEASE_ID`, `SCHEMA_VERSION`, `METHODOLOGY_VERSION`, `SCOPE`, `BUNDLE_SHA256` |
| `PRESENTATION.CURRENT_COUNTY_ATLAS_V` | `FIPS`, `COUNTY`, `STATE`, `RELEASE_ID`, `POPULATION`, `SVI_PERCENTILE`, `UNINSURED_PERCENTILE`, `RUCC_2023`, `HUMAN_STATUS`, `TICK_STATUS`, `SCAPULARIS_STATUS`, `PACIFICUS_STATUS`, `BURGDORFERI_STATUS` |
| `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.GAP_COMMUNITY_ASSIGNMENTS_120` | `FIPS`, `CLUSTER_ID` for run `120-gap-communities-20261026T1355Z` only |

No other column is selected. Do not select payload, part text, limitation text, geometry, either case floor, evidence completeness, land cover, a tier score, a #121 axis, or a latent-class label. `HUMAN_STATUS` and `TICK_STATUS` label the #121 situations and the national gates. They are not distance features. County rows may stay in memory. They are written only to `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.PEER_COUNTY_NEIGHBORS_192`. They are not written to git, to a chart, or to Drive.

## Features, scaling, and the two distances

Seven #120 features. Nothing else enters a distance.

| Feature | Role | Coding |
| --- | --- | --- |
| Social-vulnerability percentile | numeric | Unit rule, then z-score |
| Uninsured percentile | numeric | Same unit rule, then z-score |
| Log population | numeric | Natural log of population, then z-score |
| Rural-urban code | category | Codes 1 through 9, plus `blank` and `unlisted` |
| Blacklegged-tick status | category | Published level, unpooled, plus `blank` |
| Western-blacklegged-tick status | category | Published level, unpooled, plus `blank` |
| Pathogen status | category | Published level, unpooled, plus `blank` |

Unit rule, the #114 rule, applied separately to each percentile on the rows of that fit: if the maximum of that column is greater than 1.5, divide that column by 100. Do not clip. A value outside [0, 1] after that rule stops the fit.

Z-score: subtract the fit-set mean and divide by the population standard deviation (divisor n, `numpy.std` with `ddof=0`). The in-sample fit set is every county that passes the gates. A leave-state-out fit set is the counties outside the held-out state. A numeric column with standard deviation 0 stops that fit. Do not impute. A null percentile, a null population, a non-positive population, a null status, or a null rural-urban code stops the fit. A rural-urban code outside the integers 1 through 9 stops the fit on this pin; the embedding still reserves `blank` and `unlisted` so the column list does not depend on which codes appear.

Categorical levels, frozen, in this order:

| Feature | Levels |
| --- | --- |
| Rural-urban code | `1`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `blank`, `unlisted` |
| Blacklegged-tick status | `Established`, `Reported`, `No records`, `Unknown`, `blank` |
| Western-blacklegged-tick status | `Established`, `Reported`, `No records`, `Unknown`, `blank` |
| Pathogen status | `Present`, `No records`, `Unknown`, `blank` |

A level outside its list stops the fit. `blank` is not filled with `No records`.

The embedding makes squared Euclidean distance equal the #120 Huang mixed distance. Gamma is 0.5, the #120 value after a successful z-score. It is not refit. Each numeric coordinate is the z-score. Each categorical feature is a one-hot of its frozen levels, multiplied by `sqrt(gamma / 2) = 0.5`, so two different levels contribute gamma to the squared Euclidean distance and two equal levels contribute 0. Columns for levels that no county uses stay in the embedding as zeros.

Cosine distance is `1 - (u·v) / (||u|| ||v||)` on that same embedding. A zero vector stops the fit. Cosine is the alternative metric. Gower is not used: it is not in the pinned dependencies, and this story adds none.

Neighbor search is exact. There is no approximate index and no random initialization. For a query county, rank the other counties in the allowed pool by distance ascending. Ties at or inside `1e-12` break toward the smaller FIPS. Self is never a neighbor. k is 5 for the short list a steward would read, and 15 as a sensitivity. Pass, fail, and the product call use k = 5. k = 15 is reported and cannot rescue a miss at k = 5.

## Baseline, prototypes, and situation labels

The baseline peer set of a county is every other county in the same state with the same rural-urban code. The set size is not forced to k. A county with no such peer has an empty baseline. Under leave-state-out the same-state rule removes every baseline peer, so the baseline neighbor-set Jaccard against the in-sample baseline set is 0 for every county that had a peer. That 0 is the baseline stability number. It is not a missing computation.

The leave-state-out baseline for type agreement cannot use the same state. It is every other-state county with the same rural-urban code. The agreement rate uses that whole set. It is the comparator the lookup has to beat. It is not a second product baseline.

Nearest prototype uses the stored #120 labels, not a new clustering. On the 810 assigned counties, z-score the three numerics with the 810-county mean and population standard deviation, take the numeric prototype as the member mean, and take the categorical prototype as the mode. Mode ties break by Python string order, toward the label that sorts first. Gamma stays 0.5. Assign every national county, transformed with the 810-county scaler, to the nearer prototype. Distance ties break toward the smaller cluster id. Recovery is the share of the 810 whose assigned prototype equals the stored cluster id. Labels are not refit and k is not re-chosen.

The #121 situation label is one exclusive label per county, first match wins:

| Label | Rule |
| --- | --- |
| `aligned` | Published human floor, aggregate tick `Established`, pathogen `Present` |
| `double_gap` | No county-linked human record, aggregate tick `Established`, pathogen `Present` |
| `wider_gap_only` | No county-linked human record, aggregate tick `Established`, pathogen not `Present` |
| `human_ahead` | Published human floor, pathogen `No records` |
| `undocumented` | No county-linked human record, aggregate tick `No records`, pathogen `No records` |
| `other` | None of the above |

`double_gap` is inside the #121 wider gap. The exclusive label keeps it out of `wider_gap_only`, because the #190 review showed that overlapping predicates are not a partition. These labels are an agreement check. They are not distance features. Tick and pathogen documentation enter both the labels and the distance, so situation agreement is partly circular. Human status does not enter the distance. Say both facts with the number. Do not treat the agreement as validation.

## Metrics

Adjusted Rand is not the neighbor metric. Neighbor-set agreement is Jaccard of the two FIPS sets, `|A ∩ B| / |A ∪ B|`. Type agreement for one county is the share of neighbors that have a stored #120 type equal to the focal county's stored type, among neighbors that have a stored type. A county with no stored type, or with no typed neighbor, is not estimable for that rate. The reported rate is the unweighted mean over estimable counties. Situation agreement is the same rate using the exclusive label, and every county has a label.

| Quantity | Rule |
| --- | --- |
| In-sample neighbors | k = 5 and k = 15, Euclidean and cosine, pool = the other 3,143 counties, scaler fit on all 3,144 |
| Baseline peers | Same state and same rural-urban code, in sample |
| Cross-state share | Share of counties whose Euclidean k = 5 list contains at least one county in another state |
| Leave-state-out neighbors | For each state, refit the scaler on the other states, transform the held-out counties with that scaler, and take neighbors only from the other states |
| Leave-state-out stability | Mean Jaccard between the in-sample k = 5 Euclidean list and the leave-state-out k = 5 Euclidean list |
| Leave-state-out type agreement | Mean type agreement of the leave-state-out Euclidean k = 5 neighbors, and the same rate for cosine k = 5 |
| Leave-state-out baseline agreement | Mean type agreement of the other-state same-RUCC set |
| In-sample type agreement | Euclidean k = 5, cosine k = 5, nearest prototype (the prototype label versus the stored label, which is recovery on the 810 and the assigned label off it), and the same-state same-RUCC baseline |
| Bootstrap | 200 replicates. `numpy.random.Generator(np.random.PCG64(seed))` draws n indexes with replacement. The pool is the unique drawn counties. Self is excluded. A county with fewer than k other counties in the pool is skipped. The replicate statistic is the mean Jaccard between the in-sample Euclidean k = 5 list and the k list from that pool. A replicate with fewer than 500 contributing counties is a failure |
| Bootstrap interval | Same percentile formula as #116: index `(n - 1) * p` with linear interpolation, p = 0.025 and 0.975. Not estimable when failures exceed 5 percent or fewer than two replicates remain. The replicate count is 200, not the #116 count of 2,000, because each replicate rebuilds the neighbor graph |
| Seeds | Bootstrap seeds `1922026` and `1922027`. Neighbor search has no seed. The determinism check builds the in-sample Euclidean k = 5 lists twice and requires Jaccard 1.0 |
| Seed stability of the interval | The two bootstrap medians differ by at most 0.05 |
| Silhouette | `sklearn.metrics.silhouette_score`, Euclidean, on the in-sample embedding, labels = nearest-prototype cluster id. Finite and at least 0 is the bar. There is no 0.25 floor: that was a #110 K-means scale |
| Neighbor distances | Deciles of the distance to the 5th Euclidean neighbor and to the 5th cosine neighbor |
| Ablation | Drop one feature block, refit the numeric scaler on the blocks that remain, rebuild Euclidean k = 5, and record the mean Jaccard against the full list. Also fit each block alone. Blocks are `svi_percentile`, `uninsured_percentile`, `log_population`, `rucc`, `scapularis_status`, `pacificus_status`, and `burgdorferi_status` |
| k = 15 | Bootstrap median Jaccard and leave-state-out type agreement, reported only |

Small cells: a count from 1 to 10 is omitted from `EDA.METRICS_LONG`, experiment metrics, `EDA.FINDINGS` evidence, chart labels, and Drive files. A zero on a denominator of at least 11 is kept. The results write-up, the pull-request body, and the issue comment may name counties and may give county-level numbers, including small counts.

Three counties with the smallest 5th-neighbor Euclidean distance, and three with the largest, are examples. Ties break toward the smaller FIPS. Each example lists its five Euclidean neighbors. They may be named in the write-up and the pull-request body. They do not appear in chart titles, axis labels, Drive file names, `EDA.FINDINGS`, or `EDA.METRICS_LONG`.

## Disposition

**Method.** **stop** when the context check fails, the pin differs, the county count is not 3,144, the distinct FIPS count is not 3,144, the state count is not 51, the published-floor count is not 651, the no-county-linked count is not 2,493, a FIPS is not a unique five-digit id, a required field is null or illegal, a percentile falls outside [0, 1] after the unit rule, the #120 assignment table does not have exactly 810 rows for the pinned run, a distance fit has a zero numeric standard deviation or a zero embedding vector, or a query is still running at 10 minutes. **keep** when every line below holds. **revise** when the fit completes and any line fails.

| Check | Gate |
| --- | --- |
| Determinism Jaccard of the two Euclidean k = 5 builds | 1.0 |
| Bootstrap interval for Euclidean k = 5 mean Jaccard | estimable, median at least 0.50, lower endpoint at least 0.30 |
| Absolute difference of the two bootstrap medians | at most 0.05 |
| Mean Jaccard of cosine k = 5 versus Euclidean k = 5 | at least 0.40 |
| Leave-state-out Euclidean k = 5 type agreement | estimable and at least 0.50 |
| That rate minus the leave-state-out same-RUCC type agreement | at least 0.10 |
| Leave-state-out Euclidean k = 5 neighbor-set mean Jaccard | at least 0.10 |
| Largest single-block mean Jaccard against the full list | below 0.60 |
| Smallest drop-one-block mean Jaccard | below 0.80 |
| Prototype-label silhouette | finite and at least 0 |
| Prototype recovery on the 810 | at least 0.95 |

A single block at or above 0.60 means the short list is that block, not the profile. Every drop-one block at or above 0.80 means the list does not use the profile. Either one is revise.

**Product.** **stop** when the method is stop. **advance** when the method is keep, the share of counties with at least one out-of-state Euclidean k = 5 neighbor is at least 0.50, the leave-state-out neighbor-set mean Jaccard is at least 0.20, and the in-sample Euclidean k = 5 type agreement exceeds the in-sample same-state same-RUCC type agreement by at least 0.05. **investigate** otherwise. Advance means the lists are stable enough to brief as a peer lookup in a later design story. It does not authorize a model, a rank, a production score, a UI, or an API.

- **Exploratory or confirmatory:** Confirmatory for the release pin, the counts 3,144 / 651 / 2,493 / 810 / 228, and the 810 stored #120 rows. Exploratory for which counties appear on a short list. Nothing in the results is used to move k, gamma, a seed, a level list, a threshold, or the feature list.
- **Spatial / temporal dependence:** Counties in one state share reporting rules. The leave-state-out is the check for that block. It does not cover dependence that crosses a state line. No p-value and no county-independent interval are reported. The bootstrap interval is a stability band for the neighbor lists. It is not a confidence interval for a disease rate. The 2022, 2023, and 2025 vintages are not aligned.
- **Effect-size / uncertainty output:** Neighbor-set Jaccard, type-agreement rates, the bootstrap median and interval, silhouette, ablation Jaccard, cross-state share, and the 5th-neighbor distance deciles. Sample sizes sit next to each rate.
- **Key caveat / stop conditions:** Stop if the context check is not `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Do not read `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, `KNOWLEDGE_GRAPH`, historical CDC snapshots, or conformed history. Do not select payload, part text, limitation text, or geometry. A query still running at 10 minutes is cancelled and the method is stop.
- **Result disposition:** **PLANNED.** Apply the rules above after the fit without changing them.

## Reproduction / evidence

SQL in `sql/validation/192_peer_lookup.sql`. Runner `scripts/eda_192_peer_lookup.py`. Logic `src/lyme_gap_atlas_ml/peer_lookup.py`. Narrative `src/lyme_gap_atlas_ml/peer_lookup_report.py`. Lab writer `src/lyme_gap_atlas_ml/snowflake/peer_neighbors.py`, reusing `eda_writer.write_eda_results` and `eda_lab_writers.write_findings` / `write_queries`. Run id pattern `192-peer-county-lookup-<UTC yyyymmddThhmmZ>`. Seeds `1922026` and `1922027`.

`EDA.PEER_COUNTY_NEIGHBORS_192` is one row per county, keyed by `RUN_ID` and `FIPS`: county name, state, stored #120 cluster id when the county has one, exclusive situation label, prototype cluster id, the k = 5 Euclidean neighbor FIPS list, the k = 5 cosine neighbor FIPS list, the distance to the 5th Euclidean neighbor, the baseline peer count, and the leave-state-out type agreement when it is estimable. Inserts are insert-only. A second invocation with the same run id does not insert again. No `DELETE`. After the inserts, one `UPDATE` sets `REGISTRY.RUNS.FINISHED_AT` for that run id when it is still null. That is the only update. #188 and #190 granted `SELECT` on their new tables to `OH_LYME_PROD_READ` only. The ML Lead review of #190 could not see that table, because the lab reader role does not hold `OH_LYME_PROD_READ`. This session can see role `OH_LYME_ML_LAB_READ` and there is no role named `OH_LYME_ML_READER`. The writer attempts `GRANT SELECT` on the neighbor table to `OH_LYME_PROD_READ` and to `OH_LYME_ML_LAB_READ`, then reads the grants and records each result. A failed grant is recorded and is not retried as a stronger role.

Charts under git-ignored `artifacts/charts/192/`, each PNG under about 20 KB at about 64 dpi, with legible tick labels and a legend on every chart that compares methods: `method-agreement`, `stability`, `ablation`, `neighbor-distance`. Upload to Drive folder `issue-192` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`. Register each file with `register_artifact` only after the Drive byte size and SHA-256 match the local file and the PNG decodes. Durable narrative: `docs/eda/192-peer-county-lookup.md`.

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_192_peer_lookup.py
uv run python scripts/verify.py
```
