# ML #196 peer-county lookup rerun: registered specification v1

- **Spec/version and owning issue:** `196-peer-county-rerun/v1`, [ML #196](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/196), program epic [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md). This is the bootstrap-gate rerun of [192-peer-county-lookup/v1](192-analysis-spec.md). Matthew Caraway's standing directive on 2026-10-25, sequenced by the orchestrator on 2026-10-26 as the second follow-up after #194, authorizes this rerun. This run does not authorize a Tier 1 change, a tier-policy change, a PROD write, an API, a pipeline, a UI, or a public score.
- **Question / decision / allowed interpretation:** Is the peer-county list stable when the county pool is redrawn, once the result is compared with what a perfectly stable list scores under the same resampling? Should the #192 method call (revise) change to keep, stay revise, or change to stop? "Similar" means similar on the listed context features only. It does not mean similar disease burden, similar risk, or a validated match. No ground truth exists. A neighbor list is a lookup aid. `No records` and `Unknown` are not negatives. A missing human floor is not zero. A published human count is a lower bound (CDC floor 5). Say published floor, not incidence.
- **Estimand:** The same lookup as #192, on the same embedding, the same k, and the same seeds. The only changed estimand is the bootstrap stability statistic. #192 scored the raw Jaccard between the in-sample Euclidean neighbor set and the neighbor set inside a bootstrap pool. This rerun scores the conditional retained-neighbor Jaccard defined below, and it applies the numeric keep line, floor, and interval rule in this spec. The raw Jaccard is still computed on the same draws and stored as a descriptive continuity number. It is not a keep gate.

## What was already known

The #192 result was already published when this gate was written. Issue #192 results comment, run `192-peer-county-lookup-20261026T1859Z`: raw bootstrap median Jaccard 0.49993562946807224 (reported 0.4999), interval 0.4857 to 0.5120, estimable, 0 failed replicates, second-seed median 0.5015, k=15 raw median 0.4749. The sole keep-gate miss was that median against the frozen line 0.50. Every other #192 keep gate passed, including leave-state-out type agreement 0.9394 versus 0.5004 for the other-state same-RUCC baseline, determinism 1.0, and prototype recovery 1.0. The #192 reviewer stated that a perfectly stable list scores about 0.4994 under that resampling, so the 0.50 line sat on the mechanical ceiling.

This gate is not a function of 0.4999, 0.4857, 0.5120, or 0.5015. Those numbers are disclosed so a reader can see that they were known. They are not inputs to the keep line, the floor, or the interval rule.

## Ceiling derivation

The #192 bootstrap draws n county indexes with replacement, n = 3144, and keeps the unique indexes as the pool. Self is not a neighbor. A county with fewer than k other counties in the pool is skipped. k = 5 for the gate.

The probability that one given county is in the pool is

π₁ = 1 − (1 − 1/n)^n = 0.6321790716.

That is about 0.632. The county and one given neighbor each have this marginal inclusion probability. They are not independent. The probability that a specific county and one specific other county are both in the pool is

π₂ = 1 − 2(1 − 1/n)^n + (1 − 2/n)^n = 0.3996073261.

A perfectly stable list means the distance order is fixed. The bootstrap neighbors are then the k pool members that rank first in that order. If R of the original k neighbors fall in the pool, all R of them are among the bootstrap neighbors, and the other k − R bootstrap neighbors are replacements. Raw Jaccard is

J = R / (2k − R).

R = 0 gives J = 0. R = k gives J = 1. The distribution of R for k specific other counties follows from the multinomial draw. For a specific set of t neighbors included and a disjoint set of m neighbors excluded,

P = Σ_{j=0}^{t} C(t, j) (−1)^j (1 − (m + j) / n)^n.

Then

E[J] = Σ_{r=0}^{k} C(k, r) P(specific r included and the other k − r excluded) × r / (2k − r).

For n = 3144 and k = 5, E[J] = 0.499415. For k = 15 the same formula gives 0.474395. The k = 5 value is the mechanical ceiling of the #192 statistic. A keep line of 0.50 sits on that ceiling. It cannot separate a stable list from an unstable one. The expectation above does not drop the rare replicate in which a county has fewer than k other counties in the pool. At this n the unique pool is about n × π₁ = 1,988 counties, so that skip barely moves the mean.

## Simulation that confirms the ceiling

The simulation uses no county features. It uses the #192 resampling only.

- n = 3144 and k = 5. County i has fixed neighbor order (i+1) mod n, (i+2) mod n, and so on.
- `numpy.random.Generator(numpy.random.PCG64(1962026))`.
- 2,000 replicates. Each replicate draws n indexes with replacement and keeps the unique indexes.
- A county contributes when the pool holds at least k other counties. R is how many of its first k fixed neighbors are in the pool. J = R / (2k − R).
- The replicate statistic is the mean of J. A replicate with fewer than 500 contributing counties is a failure. None failed.
- The median of the 2,000 replicate means is 0.499248. The mean of the replicate means is 0.499249.
- The same draws, scored as conditional retained-neighbor Jaccard, have median 1.0. That is the algebraic ceiling of the new statistic: every retained original neighbor stays a neighbor when the order is fixed.
- A 200-replicate run with the same seed has raw median 0.499017. Both sit on 0.4994, the rounded exact expectation 0.499415.

The simulation seed 1962026 is not a fit seed. The fit seeds stay 1922026 and 1922027.

## New bootstrap gate

Conditional retained-neighbor Jaccard, on the same pools as the raw statistic:

1. Build the in-sample Euclidean neighbor list exactly as #192.
2. Draw the bootstrap pool exactly as #192, on the fixed in-sample embedding. Do not refit the scaler inside the bootstrap.
3. Let N be the in-sample Euclidean neighbor set and B the Euclidean neighbor set inside the pool. Let R = N ∩ pool, self excluded.
4. If the county has fewer than k other counties in the pool, skip it, as #192 does.
5. If R is empty, skip it. The conditional ratio is undefined.
6. The county score is |N ∩ B| / |R|. Under a fixed order this score is 1 whenever it is defined.
7. The replicate statistic is the unweighted mean of the county scores. A replicate with fewer than 500 contributing counties is a failure.

The interval rule is unchanged from #192. Not estimable when failures exceed 5 percent of the 200 replicates or fewer than two replicates remain. Otherwise the endpoints are the #116 percentile: index (n − 1) × p with linear interpolation, p = 0.025 and p = 0.975. n here is the number of retained replicates.

| Check | Gate |
| --- | --- |
| Conditional bootstrap interval, Euclidean k = 5 | estimable, median at least 0.90, lower endpoint at least 0.80 |
| Absolute difference of the two conditional medians | at most 0.05 |

The median line 0.90 and the floor 0.80 are fractions of the algebraic ceiling 1. On a typical replicate, at least nine-tenths of the original neighbors that remain in the pool are still neighbors. The lower end of the stability band stays at or above four-fifths. A null that picks k counties uniformly from a pool of about 1,988 has expected conditional score about 5 / 1,988 = 0.0025, so these lines are stability fractions, not a null cutoff and not a rescaling of 0.4999.

k = 15 conditional median, primary seed only, is reported and cannot rescue a miss at k = 5. The raw k = 5 median, its interval, the raw second seed, and the raw k = 15 median are stored and are not keep gates.

## Gates that stay as in #192

Every keep gate below is copied from #192. Pass, fail, and the product call still use k = 5.

| Check | Gate |
| --- | --- |
| Determinism Jaccard of the two Euclidean k = 5 builds | 1.0 |
| Mean Jaccard of cosine k = 5 versus Euclidean k = 5 | at least 0.40 |
| Leave-state-out Euclidean k = 5 type agreement | estimable and at least 0.50 |
| That rate minus the leave-state-out same-RUCC type agreement | at least 0.10 |
| Leave-state-out Euclidean k = 5 neighbor-set mean Jaccard | at least 0.10 |
| Largest single-block mean Jaccard against the full list | below 0.60 |
| Smallest drop-one-block mean Jaccard | below 0.80 |
| Prototype-label silhouette | finite and at least 0 |
| Prototype recovery on the 810 | at least 0.95 |

**Method.** **stop** on the same data, pin, context, and runtime failures as #192. **keep** when every keep line in both tables holds. **revise** when the fit completes and any keep line fails.

**Product.** Unchanged from #192. **stop** when the method is stop. **advance** when the method is keep, the share of counties with at least one out-of-state Euclidean k = 5 neighbor is at least 0.50, the leave-state-out neighbor-set mean Jaccard is at least 0.20, and the in-sample Euclidean k = 5 type agreement exceeds the in-sample same-state same-RUCC type agreement by at least 0.05. **investigate** otherwise. Advance means the lists are stable enough to brief as a peer lookup in a later design story. It does not authorize a model, a rank, a production score, a UI, or an API.

## Cosine denominator

In the #192 `EDA.METRICS_LONG` row `type_agreement_cosine`, the denominator was the Euclidean type-agreement n, 770. The cosine rate's own estimable count on that run was 776. This run stores the cosine estimable count on that row. It does not copy the Euclidean n. The write-up reports the count this run computes. The expected value on this pin is 776. Leave-state-out cosine keeps the #192 denominator rule.

## Unit, cohort, and pin

One county on `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. The lookup cohort is the national extract, 3,144 counties. The resampling and holdout unit is the county, blocked by postal state when a whole state is held out (51 states, including the District of Columbia). This is one snapshot. It is not a change contrast and not a forecast. Human surveillance is calendar 2023. Population, social vulnerability, and uninsured share are the 2022 county layer. The rural-urban code is 2023. Tick species and pathogen statuses are cumulative through 2025-12-31. Those vintages are not one time base.

The context check on 2026-10-26, before this spec was frozen, returned `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. User `OH_LYME_ML_AGENT_SVC`, role `OH_LYME_ML_AGENT`, database `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`, schema `SCRATCH`, warehouse `OH_LYME_ML_LAB_XS_WH`.

Pin, read the same day from `PRESENTATION.CURRENT_RELEASE_V` before this spec was frozen: release `governed-2026-10-15-january-climate-prod`, schema `2.0.0`, methodology `semantic-2.0.0`, scope `US_COUNTIES`, bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`. The same session's aggregate read returned 3,144 counties, 3,144 distinct FIPS, 51 states, 651 published floors, and 2,493 counties with no county-linked human record. `EDA.GAP_COMMUNITY_ASSIGNMENTS_120` for run `120-gap-communities-20261026T1355Z` has 810 rows. That run id is the only #120 assignment source.

Objects and columns read are the #192 three queries in `sql/validation/192_peer_lookup.sql`, plus a read of `EDA.PEER_COUNTY_NEIGHBORS_192` for run `192-peer-county-lookup-20261026T1859Z` limited to `FIPS`, the k = 5 Euclidean neighbor list, and the k = 5 cosine neighbor list. No other column is selected. Do not select payload, part text, limitation text, geometry, either case floor, evidence completeness, land cover, a tier score, a #121 axis, or a latent-class label.

The #192 run and its Lab rows stay as they are. This run does not update them and does not delete them. Inserts are a new run id `196-peer-county-rerun-<UTC yyyymmddThhmmZ>`, issue number 196, insert-only and idempotent by run id. After the inserts, one `UPDATE` sets `REGISTRY.RUNS.FINISHED_AT` for this run id when it is still null.

If the recomputed Euclidean and cosine k = 5 lists match the stored #192 lists for every county, do not create a neighbor table. Refer to `EDA.PEER_COUNTY_NEIGHBORS_192` and that run id. If any list differs, insert `EDA.PEER_COUNTY_NEIGHBORS_196`, one row per county, same columns as the #192 table, and `GRANT SELECT` to `OH_LYME_PROD_READ` and `OH_LYME_ML_LAB_READ`. Record each grant. A failed grant is not retried as a stronger role.

## Features and the rest of the lookup

Unchanged from #192: seven #120 features, the unit rule, z-score with divisor n, frozen categorical levels, gamma 0.5, exact neighbor search, tie break toward the smaller FIPS inside 1e-12, k = 5 and sensitivity k = 15, same-state same-RUCC baseline, leave-state-out, nearest prototype from the stored #120 labels, exclusive #121 situation labels, ablation blocks, and silhouette. Seeds `1922026` and `1922027`. Neighbor search has no seed. Bootstrap replicates: 200. Determinism rebuilds the in-sample Euclidean k = 5 lists and requires Jaccard 1.0.

`EDA.FINDINGS` allows the disposition words keep, revise, stop, and follow-up. The statement and the disposition column use the same word. The method row uses keep, revise, or stop. The product row records advance as keep, investigate as follow-up, and stop as stop, and the statement uses that recorded word. The write-up and the pull-request body still say the product call as advance, investigate, or stop, and they name this mapping.

Small cells: a count from 1 to 10 is omitted from `EDA.METRICS_LONG`, experiment metrics, `EDA.FINDINGS` evidence, chart labels, and Drive files. A zero on a denominator of at least 11 is kept. The results write-up and the pull-request body may name counties and may give county-level numbers, including small counts. Charts do not.

## Charts

Aggregate PNGs under git-ignored `artifacts/charts/196/`, each under about 20 KB at about 64 dpi, with legible tick labels. No county name, state name, or FIPS on a chart. A chart that compares methods has a legend. The ablation chart uses a logarithmic count axis so the single-block bars, which were about 0.002 to 0.009 in #192, stay visible. Bins of the 5th-neighbor distance with a count from 1 to 10 are omitted.

File names: `method-agreement`, `stability`, `ablation`, `neighbor-distance`. Upload to Drive folder `issue-196` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`, from the file, with no re-encoding. Register a file only after the Drive byte size and SHA-256 match the local file and the PNG decodes. If they differ, stop uploading, leave the file unregistered, and report the local path, byte size, and SHA-256. A second artifact row with the same run id and file name is rejected.

- **Exploratory or confirmatory:** Confirmatory for the release pin, the counts 3,144 / 651 / 2,493 / 810, the conditional bootstrap gate, and the cosine denominator. The raw Jaccard is descriptive. Nothing in the results is used to move k, gamma, a seed, a level list, a threshold, or the feature list. The conditional keep line and floor were fixed in this document before the fit, with the #192 raw median already known, and they are justified by the ceiling derivation above.
- **Spatial / temporal dependence:** Counties in one state share reporting rules. The leave-state-out is the check for that block. It does not cover dependence that crosses a state line. No p-value and no county-independent interval are reported. The bootstrap interval is a stability band for the neighbor lists. It is not a confidence interval for a disease rate. The 2022, 2023, and 2025 vintages are not aligned.
- **Effect-size / uncertainty output:** Conditional bootstrap median and interval, both seeds, k = 15 conditional median, simulated raw ceiling 0.499415 and simulated median 0.499248, plus the unchanged #192 rates. Sample sizes sit next to each rate.
- **Key caveat / stop conditions:** Stop if the context check is not `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Do not read `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, `KNOWLEDGE_GRAPH`, historical CDC snapshots, or conformed history. Do not select payload, part text, limitation text, or geometry. A query still running at 10 minutes is cancelled and the method is stop. Do not change a keep line, a floor, or the interval rule after the fit. If a rule changes after this spec is frozen, the pull-request body says so.
- **Result disposition:** **PLANNED.** Apply the rules above after the fit without changing them.

## Reproduction / evidence

SQL remains `sql/validation/192_peer_lookup.sql`. Runner `scripts/eda_196_peer_lookup.py`. The #192 lookup code stays the source of the embedding, the neighbor search, and the raw bootstrap. The conditional score and the new gate live beside it and do not rewrite the #192 run. Narrative `docs/eda/196-peer-county-rerun.md`. Run id pattern `196-peer-county-rerun-<UTC yyyymmddThhmmZ>`. Fit seeds `1922026` and `1922027`. Ceiling simulation seed `1962026`, 2,000 replicates.

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_196_peer_lookup.py
uv run python scripts/verify.py
```
