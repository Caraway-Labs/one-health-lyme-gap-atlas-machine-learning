# ML #106 state-relative county anomaly screen: registered specification v1

- **Spec/version and owning issue:** `106-state-relative-anomaly/v1`, [ML #106](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/106), parent [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Follows [analysis-spec v1](../methodology/analysis-spec-v1.md). Matthew Caraway authorized #106 on 2026-10-25 as discovery only: a written recommendation and no changes to the tiers. This spec does not authorize a Tier 1 change, a PROD write, a tier-policy change, an API change, or a UI change.
- **Question / decision / allowed interpretation:** Which counties are unusual compared with peers inside the same state, and does a state-relative baseline make statistical sense given small and uneven state sample sizes? The decision is proceed, revise, or defer for a surveillance-review flag kept separate from the HIGH/MEDIUM/LOW tiers. A score is a data-quality or surveillance-review flag. It is not incidence, risk, causation, a hot spot, or a training label. `No records` and `Unknown` are not negatives. A missing human floor is not zero. A published human count is a lower bound. Do not train on the Tier 1 score or on latent-class membership.
- **Estimand:** On the pinned release, for each county with complete context features, the state-relative robust-z flag under the peer rule below; the agreement of that flag with the same rule fit nationally; the share of state-relative flags whose state has fewer than 40 counties; the median absolute rank shift between the national and state-relative max absolute z; and whether an isolation forest or local outlier factor, fit only in states with at least 80 counties, is stable enough to add a review set. Uncertainty for the state-relative flag rate is a state-cluster bootstrap percentile interval. County names and county-level numbers may appear in the lab score table, the results write-up, the pull-request body, and the issue comment. Charts, other Drive files, and lab aggregate tables stay aggregate and suppress a count from 1 to 10.
- **Unit / cohort / geography / time:** One county on the pinned release. Census region comes from `coverage_audit.CENSUS_REGIONS`. This is one snapshot. It is not a change contrast and not a forecast. See temporal feasibility below.
- **Exploratory or confirmatory:** Confirmatory for the release pin, the county count 3,144, the published human floor 651, the no-county-linked human record 2,493, the established-tick / pathogen-present / no-human-floor count 228, and the per-state inventory in this file. Flag rates, agreement, rank shift, and detector stability are the prespecified descriptive results of the rules below. Epic #22 section 4.1 did not record a state-relative anomaly count. Nothing in that section is used to change a threshold, a seed, or a contamination setting after the fit.

## Data feasibility inventory

Read on 2026-10-25 after `scripts/check_ml_agent_context.py` returned `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Role `OH_LYME_ML_AGENT`, warehouse `OH_LYME_ML_LAB_XS_WH`, database `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB`. Objects read: `PRESENTATION.CURRENT_RELEASE_V`, `PRESENTATION.CURRENT_SOURCE_METADATA_V`, and aggregate queries on `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. No county feature extract was written to a file.

Pinned release, matching the #109 pin:

| Field | Value |
| --- | --- |
| `RELEASE_ID` | `governed-2026-10-15-january-climate-prod` |
| `SCHEMA_VERSION` | `2.0.0` |
| `METHODOLOGY_VERSION` | `semantic-2.0.0` |
| `SCOPE` | `US_COUNTIES` |
| `BUNDLE_SHA256` | `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d` |

National integrity: 3,144 rows, 3,144 distinct five-digit FIPS, one release id, 51 state codes (the District of Columbia is included). Context fields have no incomplete rows: population is positive, SVI percentile and uninsured percentile are non-null with maxima 1.0, and the rural-urban code is an integer from 1 through 9. Human status nulls are 0. Published human floor 651. No county-linked human record 2,493. Case-floor nulls 2,493. Incidence-floor nulls 2,493. Established tick 1,404. Pathogen present 689. The double-gap predicate is 228.

Source vintages on `CURRENT_SOURCE_METADATA_V`: human `2023`; tick `through 2025-12-31`; pathogen `through 2025-12-31`; SVI `2022 (2018-2022 ACS)`; RUCC `2023`; NLCD `C1V2-2025`. These are not one time base.

### Temporal feasibility

Temporal anomaly detection is not feasible on this pin. The atlas view has one row per FIPS and one release id. Human surveillance is a single calendar year, 2023. Tick and pathogen status are cumulative through 2025-12-31, not a year panel. Epic #22 section 4.1 item 6 already recorded time patterns as not estimable with one annual human year. This spec does not read `CONFORMED.CONFORMED_CDC_LYME_QTBI_XD4I`, `CDC_HISTORICAL_VALIDATED_SNAPSHOTS`, or any other history object. No temporal detector is fit. A later temporal story needs a governed multi-year county panel that does not exist in this release.

### Per-state inventory

`N` is the county count. Context features are complete in every state (`CONTEXT_INCOMPLETE` was 0 for all 51 and is omitted). Human floor, established tick, and pathogen present are surveillance counts, not features by themselves. A state can support a within-state surveillance-status contrast only under the rule in the method section.

| State | N | Band | Human floor | Established tick | Pathogen present |
| --- | ---: | --- | ---: | ---: | ---: |
| DC | 1 | fallback | 1 | 1 | 1 |
| DE | 3 | fallback | 3 | 3 | 3 |
| HI | 5 | fallback | 0 | 0 | 0 |
| RI | 5 | fallback | 5 | 5 | 1 |
| CT | 9 | fallback | 9 | 9 | 9 |
| NH | 10 | fallback | 10 | 10 | 10 |
| MA | 14 | fallback | 14 | 14 | 6 |
| VT | 14 | fallback | 13 | 14 | 13 |
| AZ | 15 | shrunk | 1 | 1 | 0 |
| ME | 16 | shrunk | 16 | 16 | 15 |
| NV | 17 | shrunk | 1 | 0 | 0 |
| NJ | 21 | shrunk | 21 | 21 | 20 |
| WY | 23 | shrunk | 0 | 0 | 0 |
| MD | 24 | shrunk | 24 | 22 | 10 |
| UT | 29 | shrunk | 1 | 6 | 0 |
| AK | 30 | shrunk | 0 | 0 | 0 |
| NM | 33 | shrunk | 0 | 0 | 0 |
| OR | 36 | shrunk | 3 | 18 | 1 |
| WA | 39 | shrunk | 0 | 17 | 3 |
| ID | 44 | state | 0 | 0 | 0 |
| SC | 46 | state | 2 | 23 | 3 |
| ND | 53 | state | 0 | 7 | 2 |
| WV | 55 | state | 54 | 48 | 26 |
| MT | 56 | state | 0 | 0 | 0 |
| CA | 58 | state | 6 | 55 | 29 |
| NY | 62 | state | 62 | 62 | 59 |
| CO | 64 | state | 0 | 0 | 0 |
| LA | 64 | state | 0 | 19 | 1 |
| SD | 66 | state | 0 | 4 | 1 |
| AL | 67 | state | 1 | 36 | 0 |
| FL | 67 | state | 16 | 55 | 0 |
| PA | 67 | state | 67 | 67 | 67 |
| WI | 72 | state | 71 | 61 | 41 |
| AR | 75 | state | 0 | 31 | 0 |
| OK | 77 | state | 0 | 28 | 0 |
| MS | 82 | forest | 0 | 40 | 0 |
| MI | 83 | forest | 44 | 56 | 40 |
| MN | 87 | forest | 52 | 66 | 34 |
| OH | 88 | forest | 40 | 76 | 49 |
| IN | 92 | forest | 10 | 90 | 88 |
| NE | 93 | forest | 0 | 3 | 1 |
| TN | 95 | forest | 2 | 29 | 6 |
| IA | 99 | forest | 8 | 51 | 17 |
| NC | 100 | forest | 14 | 63 | 18 |
| IL | 102 | forest | 13 | 63 | 51 |
| KS | 105 | forest | 0 | 4 | 0 |
| MO | 115 | forest | 0 | 23 | 0 |
| KY | 120 | forest | 2 | 50 | 15 |
| VA | 133 | forest | 65 | 70 | 47 |
| GA | 159 | forest | 0 | 39 | 2 |
| TX | 254 | forest | 0 | 28 | 0 |

Bands, frozen with the thresholds below: fallback is `N < 15` (8 states, 61 counties), shrunk is `15 <= N < 40` (11 states, 283 counties), state is `N >= 40` (32 states, 2,800 counties). Forest eligibility is the subset `N >= 80` (16 states, 1,807 counties).

Census-region county counts: Northeast 218, Midwest 1,055, South 1,422, West 449. Region by tick status, used only as a class-peer candidate:

| Region | Tick status | Counties |
| --- | --- | ---: |
| Midwest | Established | 504 |
| Midwest | No records | 420 |
| Midwest | Reported | 131 |
| Northeast | Established | 218 |
| South | Established | 585 |
| South | No records | 494 |
| South | Reported | 343 |
| West | No records | 301 |
| West | Established | 97 |
| West | Unknown | 35 |
| West | Reported | 16 |

West × Unknown (35) and West × Reported (16) are below the class-peer minimum of 40. A fallback county in those cells uses the Census region, not the class cell. Northeast has only Established, so its class peer and its region peer are the same 218 counties.

Evidence sufficiency: every state has complete population, SVI percentile, uninsured percentile, and rural-urban code, so the continuous baseline is feasible everywhere the peer rule allows a scale. Human, tick, and pathogen contrasts are not feasible in states that do not vary, including states with no published human floor (Texas, Georgia, Missouri, and others in the table) and states where every county shares one tick status (Pennsylvania, New York, and the small northeastern states). Case and incidence floors are missing on the same 2,493 counties as `no_county_linked_record`. They are not modeled. Missing is not zero.

## Variables

The only county table read for the fit is `PRESENTATION.CURRENT_COUNTY_ATLAS_V`. Columns: `FIPS`, `COUNTY`, `STATE`, `RELEASE_ID`, `POPULATION`, `SVI_PERCENTILE`, `UNINSURED_PERCENTILE`, `RUCC_2023`, `HUMAN_STATUS`, `TICK_STATUS`, `BURGDORFERI_STATUS`. `COUNTY` is the display name. It is not a feature. No other column is selected. Case floors, incidence floors, evidence-completeness, species statuses, geometry, payload, part text, and limitation text are not selected.

Continuous features, in this order:

| Feature | Construction |
| --- | --- |
| `log_population` | Natural log of `POPULATION` |
| `svi_percentile` | `SVI_PERCENTILE` after the unit rule |
| `uninsured_percentile` | `UNINSURED_PERCENTILE` after the unit rule |
| `rucc_2023` | `RUCC_2023` as an ordered number |

Unit rule, the same rule as #122: if the cohort maximum of a percentile column is greater than 1.5, divide that column by 100 and record it. Do not clip. The inventory maxima are 1.0, so the expected scaled-column list is empty. Do not change the rule if the live maximum differs. Record the columns that were scaled.

Surveillance-signal features are not median/MAD features. A 0/1 status has median absolute deviation 0 unless the peer group is split exactly in half, so robust z on these statuses is not a real scale. The surveillance rule is the percentile-style rule in the method section. `CASE_COUNT_FLOOR_2023` and `INCIDENCE_FLOOR_2023` stay out. A missing floor is not zero, and the CDC floor of 5 means a present value is a lower bound.

## Missingness rule

Do not impute. Do not replace a gap with zero, Established, or Present. A row is excluded when population is null or not positive, when either percentile or the rural-urban code is null, or when the rural-urban code is not an integer from 1 through 9. The inventory exclusion count is 0. An exclusion at fit time is a data-quality result and forces disposition revise. A duplicate FIPS, a FIPS that is not five digits, or a state missing from the Census map stops the fit.

## Peer rule

Thresholds are frozen before the fit. They are not revised after seeing flag lists.

| State county count | Peer | What is fit |
| --- | --- | --- |
| `N >= 40` | `state_native` | State median and state MAD. Percentile rule, robust-covariance distance, and, when `N >= 80`, isolation forest and LOF. |
| `15 <= N < 40` | `state_shrunk` | State median. Scale is a shrinkage blend toward the leave-state-out Census-region MAD. No percentile rule, no distance, no forest, no LOF. |
| `N < 15` | `class_peer` if the Census-region × tick-status cell has at least 40 counties; otherwise `region_peer` | Median and MAD of that peer group. Percentile rule and robust-covariance distance use that peer group. No forest and no LOF. |

Shrinkage, for each continuous feature in a shrunk state: let `n` be the state count, `n0 = 40`, and `w = n / (n + n0)`. Blended MAD is `w * state_MAD + (1 - w) * leave_state_out_region_MAD`. The robust scale is `1.482602218505602 * blended_MAD`, the same constant as #122. Location stays the state median, so the county is still compared with its state, with a scale that does not collapse in a small state. If the state MAD is 0, use the leave-state-out region MAD only. If that region remainder has fewer than 40 counties or MAD 0, use the full-region MAD. If the scale is still 0, drop the feature for that state.

A county in a fallback state is not described as unusual for its state. The peer label names the region or the region-and-tick-status class.

Class peers are the surveillance situation implied by `TICK_STATUS` inside the Census region. They are not the #119 latent-class model and not a new class fit.

## Method

Baselines first. #122 showed that an isolation forest on 1,404 established-tick counties had seed Jaccard 0.82, below the frozen 0.90 bar, and that robust z and robust-covariance agreed poorly with it (matched-count Jaccard about 0.20). Interpretable baselines are the primary screen. A detector is reported only where the stability bar below is met. A stop or defer call is an accepted outcome.

| Rule | Setting |
| --- | --- |
| Robust z | Median and MAD inside the assigned peer group, or the shrunk scale above. Scale constant `1.482602218505602`. Flag when the largest absolute z on the continuous features that have a positive scale exceeds 3.5. |
| Dominant feature | The continuous feature with the largest absolute state-relative z. `tie` when the top two are within 1e-12. `joint` when the largest absolute z is below 2.5. Reuse `class_anomaly.dominant_label`. |
| Percentile | Continuous features only. Applied only when the peer group has at least 40 counties, so a 2.5 percent tail is at least one county. Empirical percentile is the average rank divided by the peer count, ranks starting at 1, ties averaged. Flag when that percentile is at most 0.025 or at least 0.975 on any continuous feature. |
| Surveillance signal | Separate from robust z. For human published vs not, tick Established vs not, and pathogen Present vs not: the peer group must have at least 44 counties, both levels must have count at least 11, and the minority share must be at most 0.25. Counties in the minority level are flagged. If the minority share is above 0.25, the rule runs and flags nobody. If either level is below 11, the signal is not estimable in that peer group. The same rule is also fit once nationally, for the side-by-side comparison only. |
| Robust distance | `MinCovDet`, `support_fraction=0.8`, `random_state=1062026`, on the continuous features with a positive MAD in that peer group. At least two such features are required. Flag when squared Mahalanobis distance exceeds the chi-square 0.975 quantile for that dimension count, using the #122 quantiles for 1 to 4 features. On failure, record the failure. Do not substitute the classical covariance. Fit inside each state-native state, inside each fallback peer group, and once nationally. Do not fit inside a shrunk state. |
| Isolation forest | Only in states with `N >= 80`. `IsolationForest`, 200 trees, `max_samples='auto'`, `bootstrap=False`, `n_jobs=1`, on the raw continuous features. Do not z-score before the forest. The population scaling is the log. Contamination 0.02, 0.05, and 0.10. Seeds `1062026` and `1062027`. The stored score is the negation of `decision_function`. The flag is `predict == -1`. Primary is seed `1062026` at contamination 0.05. |
| LOF | Only in those same states. `LocalOutlierFactor`, `n_neighbors=20`, `n_jobs=1`, contamination 0.02, 0.05, and 0.10. LOF has no seed. The stored score is the negation of `negative_outlier_factor_`, so a larger score is more unusual. Nested stability is the Jaccard between the contamination-0.02 flags and the top-k primary scores, where k is the 0.02 flag count. |
| Detector bar | A state counts as forest-stable only when both seeds flag at least one county and the seed Jaccard at contamination 0.05 is at least 0.90. The forest is defensible only when at least 8 states are forest-stable and, in at least half of those states, the matched-count Jaccard versus that state's robust-z flags is below 0.80. LOF is defensible only when at least 8 eligible states have nested Jaccard at least 0.90 and matched-count Jaccard versus robust z below 0.80. If the bar is missed, the detector is not a recommended screen. That miss does not by itself change the baseline disposition. |
| National comparison | The national robust z uses the same four continuous features, the national median and MAD, and the same 3.5 cutoff. Agreement with the state-relative robust-z flags is Jaccard. Matched-count Jaccard takes as many highest national max-absolute-z counties as the state-relative rule flagged, ties broken by FIPS. Rank 1 is the largest max absolute z. Ties break by FIPS ascending. Rank shift is national rank minus state-relative rank. Material movement is a median absolute rank shift of at least 100 among the union of the two flag sets. Spearman correlation of the two max-absolute-z values is descriptive. |
| Urban concentration | Metro is rural-urban code 1, 2, or 3. Compare the metro share of state-relative robust-z flags with the metro share of the fit cohort. The contrast is suppressed when either the metro or the non-metro flag count is from 1 to 10. A gap of at least 0.25, when both sides are publishable, forces disposition revise. |
| Small-state share | Share of state-relative robust-z flags whose state has `N < 40`, and the share whose state has `N < 15`. A share above 0.10 forces revise. |
| Uncertainty | 400 state-cluster bootstrap draws, seed `1062026`, percentile 2.5 and 97.5, for the state-relative robust-z flag rate. A draw with no flags is skipped. If fewer than 100 draws remain, the interval is not estimable. The interval resamples states. It is not a causal interval. |
| Small cells | Lab aggregate tables and charts omit a count from 1 to 10 and a composition whose omitted remainder is from 1 to 10. A zero on a denominator of at least 11 is kept. `EDA.FINDINGS` stays aggregate and cannot contain a five-digit token. The writer vocabulary is keep, revise, stop, or follow-up. This spec's proceed is stored as follow-up. This spec's defer is stored as revise, and the statement text says defer. |

Plain-language reason, for a state-relative robust-z flag: name the dominant feature, the direction from the peer median, the county value, the peer median, the robust z, the peer label, and the peer count. When the label is joint, say that no single feature reaches 2.5 robust z units. A fallback county's sentence names the region or class peer, not the state as the peer.

What a user would see, frozen as copy and not as a shipped surface: "Exploratory state-relative signal, separate from the HIGH, MEDIUM, and LOW tiers. This county is unusual compared with {peer label} (n={peer count}) because {reason}. This is a surveillance-review flag. It is not a tier, an incidence, a risk, or a hot spot." No tier label changes. No API field is added by this story.

## Spatial and temporal dependence

Counties in one state share reporting rules. The bootstrap resamples states. No p-value is reported. Population, SVI, insurance, rural-urban code, human year, and tick or pathogen cumulative status are not one time base. Temporal detection is not estimable, as recorded above.

## Effect-size and uncertainty output

Flag counts and rates, Jaccard values, rank-shift median, Spearman correlation, urban shares, small-state shares, per-state seed Jaccard summarized in bins, detector pass or fail, surveillance-rule counts, and the bootstrap interval. Histogram bins for the seed-Jaccard chart are 0, 0.5, 0.7, 0.8, 0.9, and 1.01. State-size chart bands are the four peer bands above.

## Key caveat and stop conditions

Stop if the context check is not `prod_select` pass, `scratch_write` pass, and `prod_write_denied` pass. Stop if the live release id or bundle SHA differs from the pin in this file. Stop if the county count is not 3,144, if distinct FIPS is not 3,144, if five-digit FIPS is not 3,144, if the release id count is not 1, if the published human floor is not 651, if the no-county-linked count is not 2,493, or if the double-gap predicate is not 228. Stop on a duplicate FIPS or a state outside the Census map. Do not read `RESTRICTED_CDC_*`, `RAW`, `GOVERNANCE`, `KNOWLEDGE_GRAPH`, historical CDC snapshots, or any column other than the list above. Do not select payload, part text, limitation text, or geometry. A query still running at 10 minutes is cancelled. County feature rows may stay in memory for the fit. They are not written to a data extract, a chart, or Drive. County scores, including the county name, are inserted only into `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.EDA.COUNTY_STATE_ANOMALY_106`.

The existing lab writers do not grant `SELECT` to another role. This story does not add a grant. The ML Lead's usual read role `OH_LYME_PROD_READ` cannot count the new table unless an owner grants it. The pull request states that limit.

## Result disposition

**PLANNED.** After the fit, apply this rule without changing it.

**stop** when a gate above fails.

Otherwise, in this order:

1. **defer** when the state-relative robust-z flag count is 0, or the Jaccard with the national robust-z flags is at least 0.80, or the median absolute rank shift on the union of those two flag sets is under 100. A detector that misses its bar is noted and does not override defer.
2. **revise** when the state-relative flag count is from 1 to 10, or the share of those flags from states with `N < 40` is above 0.10, or any state-native state keeps fewer than two continuous features, or robust distance fails in more than half of the state-native states, or the publishable metro share of flags exceeds the cohort metro share by at least 0.25.
3. **proceed** otherwise. Proceed recommends a follow-on design for the interpretable baseline only. It does not change tiers, the Tier 1 model, PROD batch, or the API. Isolation forest and LOF are in that follow-on only when their own bar is met. When the bar is missed, the follow-on excludes them.

Code-only slice versus protected slice, decided before the fit: log population and the rural-urban code are statistical and geographic codes. Social-vulnerability percentile and uninsured percentile describe community vulnerability and coverage. Surveillance status is a third slice. It can explain a pattern. It is not an outreach rank. A later review column, if one is authorized, may use the code-only pair. Vulnerability and insurance percentiles stay in a protected slice.

Follow-on story outlines are written in the results record only when the disposition is proceed. They are not opened as GitHub issues by this run. Each outline names the business question, model family, baseline, evaluation, and Snowflake persistence, and is marked code-only or protected.

## Reproduction and evidence

SQL in `sql/validation/106_state_anomaly.sql`. Runner `scripts/eda_106_state_anomaly.py`. Fit logic `src/lyme_gap_atlas_ml/state_anomaly.py`. Lab score writer `src/lyme_gap_atlas_ml/snowflake/state_anomaly_scores.py`, reusing `eda_writer.write_eda_results`, `eda_lab_writers.write_findings` / `write_queries`, and the robust-z, Jaccard, and distance helpers from the #122 modules. Run id pattern `106-state-relative-anomaly-<UTC yyyymmddThhmmZ>`. Charts under git-ignored `artifacts/charts/106/`, uploaded to Drive folder `issue-106` under `1b8dkHIpE8cxSi17FJP9nmTSDn1TBYvhM`. Durable narrative: `docs/eda/106-state-relative-anomaly.md`.

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_106_state_anomaly.py
uv run python scripts/verify.py
```
