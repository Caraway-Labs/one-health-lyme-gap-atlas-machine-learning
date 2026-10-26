# ML #120 established-tick gap communities: registered specification v1

- **Spec/version and owning issue:** `120-gap-communities/v1`, [ML #120](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/120), parent epic [ML #118](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/118), program epic [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md). Matthew Caraway authorized this story through the EDA queue on 2026-10-26. This run does not authorize a Tier 1 change, a PROD write, an API, a pipeline, a UI, or a public score.
- **Question / decision / allowed interpretation:** Inside the established-tick gap, which counties resemble each other on vulnerability, insurance, rurality, population, and surveillance status? What is a plain-language profile of each community type? Which type contains the most people, and which type is the most rural? Do the 228 double-gap counties concentrate in one type? The method decision is keep, revise, or stop. The product decision is advance, investigate, or stop. Cluster membership is not disease risk and not a production score. A status is a surveillance signal. It is not incidence, risk, or causation. `No records` and `Unknown` are not negatives. A missing human floor is not zero. A published human count is a lower bound (CDC floor 5). Say published floor, not incidence.
- **Estimand:** On the pinned release, for the established-tick gap cohort: pre-clustering distributions of population, social-vulnerability percentile, uninsured percentile, and rural-urban code; a k-prototypes partition whose k is chosen by the stability rule below; cluster sizes, population totals, and numeric medians; the second-seed adjusted Rand index, the #116 county-resample interval of adjusted Rand, and the mixed-distance silhouette at every candidate k; the minimum mixed distance between prototypes; and the count of double-gap counties in each reported cluster. #109 supplies the status levels. #110 supplies the second-seed adjusted Rand, the silhouette role, and the county-resample stability pattern. #114 supplies the social-vulnerability unit rule. #121 supplies the situation predicates below. #121 axis scores are not features. No latent-class label is a feature.

## Unit, cohort, and pin

One county on `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. The national extract is 3,144 counties. This is one snapshot. It is not a change contrast and not a forecast. Human surveillance is calendar 2023. Population, social vulnerability, and uninsured share are the 2022 county layer. The rural-urban code is 2023. Tick species and pathogen statuses are cumulative through 2025-12-31. Those vintages are not one time base.

Pin `RELEASE_ID`, `SCHEMA_VERSION`, `BUNDLE_SHA256`, `METHODOLOGY_VERSION`, and `SCOPE` from `PRESENTATION.CURRENT_RELEASE_V` before the fit. The pin, the same pin as #109 and #121, is release `governed-2026-10-15-january-climate-prod`, schema `2.0.0`, methodology `semantic-2.0.0`, scope `US_COUNTIES`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`.

The cohort is the #121 wider established-tick gap: `HUMAN_STATUS = no_county_linked_record` and `TICK_STATUS = Established`. The October reference is 810. The double-gap subset inside it is the same human and tick rule plus `BURGDORFERI_STATUS = Present`. The October reference is 228. If a live count differs, report the live count. That mismatch does not stop the fit and does not change k. It makes the method disposition revise.

Objects and columns read:

| Object | Columns |
| --- | --- |
| `PRESENTATION.CURRENT_RELEASE_V` | `RELEASE_ID`, `SCHEMA_VERSION`, `METHODOLOGY_VERSION`, `SCOPE`, `BUNDLE_SHA256` |
| `PRESENTATION.CURRENT_COUNTY_ATLAS_V` | `FIPS`, `COUNTY`, `STATE`, `RELEASE_ID`, `POPULATION`, `SVI_PERCENTILE`, `UNINSURED_PERCENTILE`, `RUCC_2023`, `HUMAN_STATUS`, `TICK_STATUS`, `SCAPULARIS_STATUS`, `PACIFICUS_STATUS`, `BURGDORFERI_STATUS` |

No other column is selected. Do not select payload, part text, limitation text, geometry, the raw uninsured percent, either case floor, evidence completeness, land cover, a tier score, a #121 axis, or a latent-class label. County rows may stay in memory. They are not written to git, to a chart, or to Drive. County-to-cluster assignments are inserted only into `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.GAP_COMMUNITY_ASSIGNMENTS_120`.

## Features, scaling, and blanks

Seven features. Nothing else enters the distance.

| Feature | Role | Coding |
| --- | --- | --- |
| Social-vulnerability percentile | numeric | Unit rule, then z-score |
| Uninsured percentile | numeric | Same unit rule, then z-score |
| Log population | numeric | Natural log of population, then z-score |
| Rural-urban code | category | Codes 1 through 9 as categories |
| Blacklegged-tick status | category | Published level, unpooled |
| Western-blacklegged-tick status | category | Published level, unpooled |
| Pathogen status | category | Published level, unpooled |

Unit rule, the #114 rule, applied separately to each percentile before the z-score: if the maximum of that column on the national extract is greater than 1.5, divide that column by 100. Do not clip. A value outside [0, 1] after that rule stops the fit.

Z-score: subtract the cohort mean and divide by the population standard deviation (divisor n, the same divisor as `numpy.std` and scikit-learn `StandardScaler`). The mean and standard deviation are computed on the clustering cohort only. A numeric column with standard deviation 0 stops the fit.

A null or empty blacklegged-tick status, western-blacklegged-tick status, or pathogen status is the category `blank`. It is not filled with `No records`, a mode, Established, or Present. A null or empty rural-urban code is `blank`. A rural-urban code outside the integers 1 through 9 is `unlisted`. Do not impute. A null percentile, a null population, or a population that is not positive excludes that county from the distance matrix. The exclusion count is reported. It is not coded as zero.

The national gate still stops when the release pin differs, the county count is not 3,144, the published-floor count is not 651, the no-county-linked count is not 2,493, FIPS values are not unique five-digit ids, human status is outside the two #109 levels, aggregate tick status is outside the four #109 levels, a percentile or population fails the rules above, or a rural-urban code is outside 1 through 9. Those fields define the cohort and the #109 integrity checks. Species and pathogen blanks do not, by themselves, stop the gate.

## Distance and the gamma rule

The `kmodes` package is not a pinned dependency. Runtime dependencies in `pyproject.toml` are numpy, scikit-learn, and joblib. Do not add a package for this story. The fit is Huang k-prototypes, the distance implemented by `kmodes` (Huang 1997; squared Euclidean numeric part, simple-matching categorical part), written in `src/lyme_gap_atlas_ml/gap_communities.py`.

For a county and a prototype, the mixed distance is the sum of squared differences on the three scaled numeric features, plus gamma times the number of categorical mismatches. A mismatch is 1 when the categories differ and 0 when they match. `blank` mismatches `No records`.

Gamma, the kmodes automatic rule, applied after the z-score so that log population does not set the weight:

```text
gamma = 0.5 * mean(column standard deviations of the scaled numeric matrix)
```

The standard deviation is the population divisor used in the z-score. On a successful z-score this gamma is 0.5. Higher gamma would give more weight to the categorical block. Gamma is computed. It is not chosen after looking at the clusters.

Initialization copies both the scaled numeric values and the categorical values from k distinct cohort rows drawn without replacement by `numpy.random.Generator` at the stated seed. That is an observed-row start. It is not the kmodes Cao start, and it is not the kmodes random start's normal draw for the numeric centers. One start per seed. `n_init` is 1 so the second seed is a real rerun rather than one of several starts that are then picked by cost.

Update step: the numeric prototype is the mean; the categorical prototype is the mode. Mode ties break by Python string order, toward the label that sorts first. Assignment ties break toward the lower pre-relabel cluster index. An empty cluster receives the farthest member of the largest cluster, ties broken by the smallest row index, for at most k repairs. Maximum iterations: 50. A fit that still moves, or that still has an empty cluster, has not converged.

After convergence, cluster ids are relabeled 1..k by size descending. Ties break by the smallest FIPS in the cluster. Adjusted Rand uses the labels before that cosmetic relabel; the index is unchanged by a relabel.

## Choosing k

Candidate k values are 2, 3, 4, 5, and 6. Seeds: primary `1202026`, second seed `1202027`, bootstrap `1202028`. The bootstrap seed is passed to the #116 `resample_interval` helper (2,000 replicates, percentiles 2.5 and 97.5), the same helper #110 uses for a county resample. Each replicate draws n counties with replacement, refits k-prototypes at the primary seed on that draw, and assigns every original county to the nearest bootstrap prototype. The statistic is the adjusted Rand index against the primary labels. A replicate that does not converge is dropped. The interval is not estimable when more than 5 percent of replicates fail or fewer than two remain, which is the #116 rule.

For each k, record the second-seed adjusted Rand index, the mixed-distance silhouette (`sklearn.metrics.silhouette_score` on the precomputed mixed-distance matrix), the bootstrap interval, the cluster sizes, and whether the primary fit converged.

Minimum cluster size is `max(30, ceil(0.05 * n))` on the clustering cohort. At n = 810 this is 41.

A candidate passes only when all of these hold:

| Check | Gate |
| --- | --- |
| Primary fit converged, and the second seed converged | required |
| Second-seed adjusted Rand index | at least 0.80 |
| Bootstrap interval | estimable, and the lower endpoint is at least 0.70 |
| Mixed-distance silhouette | finite |
| Smallest cluster | at least the minimum cluster size |

Among candidates that pass, choose the highest silhouette. If another passing k is within 0.01 silhouette of the leader, choose the smaller k. The double-gap table, the population totals, and the narrative profiles are not inputs to this choice.

Silhouette has no separate floor. #110's 0.25 floor is a Euclidean K-means scale. This silhouette is on the mixed distance, and it is the ranking score among candidates that already passed the stability gates.

If no k passes, the reported partition is the converged candidate with the highest second-seed adjusted Rand index, then the highest silhouette, then the smallest k. That partition is a diagnostic. It is not a chosen typology. Method is revise and product is stop.

## What counts as a distinguishable community type

A reported cluster is a distinguishable community type when its prototype's mixed distance to every other prototype is at least 1.0. At gamma 0.5, that is two categorical mismatches, or a one-standard-deviation squared gap on one numeric feature plus one categorical mismatch, or a larger numeric gap. A cluster closer than that to another cluster is not a separate type. This check is applied after k is chosen. It does not choose k. If any chosen cluster fails it, the method disposition is revise.

Plain-language profiles use the original units: median population, median social-vulnerability percentile, median uninsured percentile, the modal rural-urban code, and the modal level of each surveillance status. The most rural type is the one with the highest median rural-urban code. Ties break toward the higher share of codes 7, 8, and 9, then the smaller cluster id. The type with the most people is the one with the largest population total. Ties break toward the smaller cluster id. Three example counties per cluster are the ones with the smallest mixed distance to that prototype, ties broken by FIPS. They may be named in the write-up, the pull-request body, and the issue comment. They do not appear in chart titles, axis labels, Drive files, `EDA.FINDINGS`, or `EDA.METRICS_LONG`.

Pre-clustering frequency exhibits, not clustering inputs, use the #121 finer population edges (10, 25, 50, 100, 250, and 500 thousand, and 1 million) and percentile tenths from 0.1 through 0.9 for social vulnerability and for the uninsured percentile. Rural-urban codes stay unbinned.

## Disposition

**Method.** **stop** when the context check fails, the pin differs, the national county count is not 3,144, the published-floor count is not 651, the no-county-linked count is not 2,493, or a required national field is illegal. **revise** when the fit completes and the cohort count is not 810, the double-gap count is not 228, a double-gap county falls outside the cohort, a cohort county is excluded for a missing numeric, no k passes the stability rule, or a chosen cluster is not distinguishable. **keep** otherwise.

**Product.** **stop** when the method is stop, or when no k passes the stability rule. **advance** when the method is keep, the most-populous type and the most-rural type are both defined, and no cluster holds 70 percent or more of the cohort counties. **investigate** otherwise. Advance means the types are stable enough to brief as separate outreach descriptions. It does not authorize a model, a rank, a production score, or a public risk map.

- **Exploratory or confirmatory:** Confirmatory for the release pin, the counts 3,144 / 651 / 2,493, and the cohort counts 810 and 228 as reproduction checks. Exploratory for the names of the types. Nothing in the results is used to move gamma, a seed, a k gate, the minimum cluster size, the prototype-distance threshold, or the feature list.
- **Spatial / temporal dependence:** Counties in one state share reporting rules. No p-value and no county-independent interval are reported. The second seed and the county resample are the stability evidence. The 2022, 2023, and 2025 vintages are not aligned.
- **Effect-size / uncertainty output:** Sizes, population totals, numeric medians, modal categories, silhouette, second-seed adjusted Rand, the bootstrap interval, and the prototype distances. The bootstrap interval is a stability band for the partition. It is not a confidence interval for a disease rate.
- **Key caveat / stop conditions:** Stop if the context check is not `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Do not read `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, `KNOWLEDGE_GRAPH`, historical CDC snapshots, or conformed history. Do not select payload, part text, limitation text, or geometry. A query still running at 10 minutes is cancelled. Small cells: a count from 1 to 10 is omitted from `EDA.METRICS_LONG`, experiment metrics, `EDA.FINDINGS` evidence, chart labels, and Drive files. The results write-up, the pull-request body, and the issue comment may name counties and may give county-level numbers, including small counts.
- **Result disposition:** **PLANNED.** Apply the rules above after the fit without changing them.
- **Reproduction / evidence:** SQL in `sql/validation/120_gap_communities.sql`. Runner `scripts/eda_120_gap_communities.py`. Logic `src/lyme_gap_atlas_ml/gap_communities.py`. Lab assignment writer `src/lyme_gap_atlas_ml/snowflake/gap_community_assignments.py`, reusing `eda_writer.write_eda_results` and `eda_lab_writers.write_findings` / `write_queries`. Run id pattern `120-gap-communities-<UTC yyyymmddThhmmZ>`. Seeds `1202026`, `1202027`, and `1202028`. Charts under git-ignored `artifacts/charts/120/`, each PNG under 40 KB: `cohort-distributions`, `cluster-sizes`, `numeric-medians`. Upload to Drive folder `issue-120` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`. Durable narrative: `docs/eda/120-gap-communities.md`. Inserts are insert-only. A second invocation with the same run id does not insert again. No `DELETE`. `GRANT SELECT` on the new assignment table to `OH_LYME_PROD_READ` is attempted once; a failed grant is recorded and is not retried as a stronger role.

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_120_gap_communities.py
uv run python scripts/verify.py
```
