# Production release: exhaustive descriptive EDA

- Issue: none. Unscoped read-only exploration of `ONE_HEALTH_LYME_GAP_ATLAS_PROD`, requested as a checklist pass over the visible production catalog.
- Question / intended use: describe every consumer-visible object, then apply a standard EDA checklist (overview, missingness, univariate shape, bivariate association, outlier rules, correlation, skewness, and feature relationships) to the county release. The record can support a later analysis spec. It does not approve a target, a training run, a public interpretation, or model promotion.
- Data: views visible to `OH_LYME_PROD_READ` in `ONE_HEALTH_LYME_GAP_ATLAS_PROD`. Current release `governed-2026-10-06-nlcd-demo-cohort`, schema `1.0.0`, method `semantic-1.0.0`, bundle SHA-256 `603afb135a1a5c958d1d56d48d580d9942c67eb38986caf8b4b3acf69fcde2c9`, generated 2026-10-05, loaded 2026-10-10, scope `US_COUNTIES`.
- Cohort: 3,144 unique five-digit county FIPS and 51 state codes, including the District of Columbia. Connecticut contributes 9 planning-region FIPS. Human measures are calendar year 2023. Population, SVI, and uninsured context are the 2022 county layer (ACS 2018–2022). RUCC is 2023. Tick and pathogen status are cumulative through 2025-12-31. NLCD land cover is calendar year 2025 for FIPS `09110` and `51013` only.

## Material conclusion

The analytic table is `PRESENTATION.CURRENT_COUNTY_ATLAS_V`: one row per county, one release, and no duplicate FIPS. Human case and incidence values are privacy-protected floors for 651 counties (20.7% of counties, 47.9% of the 331,097,593 people on the atlas). The other 2,493 counties are an explicit no-county-linked-record state, and their floors are null. That null is structural. Tick status is a clean rollup of two non-overlapping species, *I. scapularis* in the East and *I. pacificus* in the West. Pathogen presence concentrates inside established *I. scapularis* counties. Published incidence is right-skewed, heaped at the case floor of 5, and strongly clustered by state (34% of its variance is between state means).

`EVIDENCE_COMPLETENESS` is a deterministic recode of those surveillance flags on this release, and the uninsured percent and uninsured percentile are the same ranking. The September tier view is a percentile bin of an existing score, aligned with current human status, and pinned to an older release id. Daily climate and both intelligence feeds are empty. Land cover exists for two geographies. Those three surfaces cannot support a distributional model.

## Method and assumptions

Exploratory checklist, applied after the catalog was inspected. Results below are descriptive. County rows are spatially dependent, so Pearson correlation, Spearman rank correlation, Cramér's V, and the between-state variance share are association summaries. No p-values are reported. No model was fit. No holdout labels were used. No missing numeric value was replaced with zero.

Spec, recorded with the execution because this pass had no prior issue spec:

- Estimand: the joint distribution of the current consumer county release, plus row counts and grain of every other visible view.
- Unit: county, except state-unallocated human records, which are a state-level constant repeated on county rows, and lineage, which is a release-measure-county row.
- Missingness rule: `no_county_linked_record`, `No records`, `Unknown`, observation `MISSING`, and observation `ZERO` stay distinct. Climate and intelligence feeds have no rows, so their missingness rate is not estimable. Unselected counties are absent from NLCD, which is different from a zero share.
- Dependence: state and census-region tables, plus the share of published-incidence variance lying between state means. No spatial-weights matrix was built.
- Stop conditions: a claim of complete incidence, biological absence, causation, individual risk, or a license to train. The tier score and `EVIDENCE_COMPLETENESS` are not available as labels or as extra predictors beside the flags that define them.

Context at read time, 2026-10-15: user `MATTHEWCARAWAY`, role `OH_LYME_PROD_READ`, database `ONE_HEALTH_LYME_GAP_ATLAS_PROD`, schema `PRESENTATION`, warehouse `COMPUTE_WH`, secondary roles empty. The named connection had no default schema or warehouse; both were selected for the session. The warehouse is the one this role can use for the production read. Statement timeouts were 120–300 seconds. Every aggregate below finished inside that bound.

Skewness is reported two ways. The checklist moment is the average of cubed population-standardized deviations. `SKEW()` is Snowflake's bias-adjusted sample skewness. On these sizes the two agree to two decimals except where shown. `KURTOSIS()` is excess kurtosis. Pearson correlations use `CORR`. Spearman correlations are Pearson correlations of ranks. Outlier fences use `PERCENTILE_CONT` quartiles and the 1.5-IQR rule. Z-scores use the sample standard deviation. Counts are exact. Correlations and skew in the narrative are rounded to two decimals.

Census region is the standard four-region assignment of the 50 states and the District of Columbia. It is a label for the state table, not a source variable.

## 1. Data overview

The read role sees four schemas: `GOVERNANCE`, `INFORMATION_SCHEMA`, `LINEAGE_AUDIT`, and `PRESENTATION`. Outside `INFORMATION_SCHEMA` there are 14 views, 268 columns, and no base tables. Internal semantic and raw tables were not visible and were not queried.

| Object | Rows | Columns | Role in this pass |
| --- | ---: | ---: | --- |
| `PRESENTATION.CURRENT_COUNTY_ATLAS_V` | 3,144 | 21 | National county product and the EDA table |
| `PRESENTATION.CURRENT_COUNTY_OBSERVATIONS_V` | 9,446 | 29 | Long human measures for every county, plus NLCD for two |
| `PRESENTATION.CURRENT_TIER1_COUNTY_REVIEW_V` | 3,144 | 20 | Existing September-pinned score, read as an output |
| `LINEAGE_AUDIT.SEMANTIC_LINEAGE_AUDIT_V` | 88,046 | 27 | Match-kind audit for two retained releases |
| `PRESENTATION.CURRENT_RELEASE_V` | 1 | 9 | Release, bundle, score defaults, limitations |
| `PRESENTATION.CURRENT_INDICATOR_METADATA_V` | 7 | 8 | Indicator dictionary |
| `PRESENTATION.CURRENT_MEASURE_METADATA_V` | 21 | 17 | Measure dictionary and missingness semantics |
| `PRESENTATION.CURRENT_SOURCE_METADATA_V` | 6 | 12 | Source vintage and notes |
| `PRESENTATION.CURRENT_METHODOLOGY_METADATA_V` | 3 | 7 | Human-floor methodology |
| `GOVERNANCE.V_USER_FEEDBACK_ANALYST` | 4 | 9 | Analyst-visible feedback census |
| `PRESENTATION.CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V` | 0 | 45 | Daily climate shell, empty |
| `PRESENTATION.CURRENT_CLIMATE_MEASURE_METADATA_V` | 0 | 14 | Climate dictionary, empty |
| `PRESENTATION.INTELLIGENCE_FEED_V` | 0 | 24 | Text feed, empty |
| `PRESENTATION.INTELLIGENCE_FEED_V2` | 0 | 26 | Text feed, empty |

The atlas grain is one row per FIPS. All 3,144 FIPS match `^[0-9]{5}$`. There are 51 state codes, one release id, no duplicate FIPS, and no duplicate county name within a state. Geometry is present for every county: 2,965 `Polygon` and 179 `MultiPolygon`. Population is a positive integer for every county and sums to 331,097,593. The smallest population is 50 and the largest is 9,936,690.

The release limitation says this is a deterministic surveillance follow-up priority release. Published human values are privacy-protected floors. `No records` is a documentation state. Human rows whose state geography is unavailable stay in source provenance and are not allocated to a county. NLCD is limited to 2025 TIGER geographies `09110` (Capitol Planning Region, Connecticut, with no historical county crosswalk) and `51013` (Arlington County, Virginia). Unselected counties are omitted. Land cover is descriptive context and is not automatic ML admission.

`SCORE_DEFAULTS` on the release row is an object, not a county column. It sets community share 0.35 (rurality 0.2, SVI 0.5, uninsured percentile 0.3), ecological share 0.65 (tick status 0.6, *B. burgdorferi* 0.4), a low-incidence breakpoint of 10 per 100,000, and a missing-human-signal weakness of 75. This pass did not find that mix materialized on the county table.

Long observations contain three human measures for every county (9,432 rows) and seven NLCD measures for two counties (14 rows). Observation ids are unique. Tick, pathogen, population, SVI, uninsured, and RUCC are wide-atlas fields. They are not rows in the observations view. The two NLCD counties also have the three human rows, so their observation count is 10 and every other county has 3.

## 2. Missing values

On the atlas, SQL nulls are confined to the two human floors, and those nulls line up exactly with human status.

| Column | Null counties | Share | What the null means here |
| --- | ---: | ---: | --- |
| `CASE_COUNT_FLOOR_2023` | 2,493 | 79.3% | No county-linked published value |
| `INCIDENCE_FLOOR_2023` | 2,493 | 79.3% | Same counties as the case floor |
| Population, either species status, SVI, both uninsured fields, RUCC, state-unallocated records, geometry | 0 | 0% | Present for every county |

Categorical gaps are stored as values, not SQL nulls. Tick and pathogen `Unknown` cover the same 35 counties: Alaska 30 and Hawaii 5. Those are exactly the counties with `IN_CONTIGUOUS_TICK_SCOPE = FALSE`. No in-scope county is `Unknown`. `No records` is a third status, used for 1,215 tick counties and 2,420 pathogen counties.

Quality checks on the non-null values all passed: a published floor always has both case and incidence; an unpublished county never has either; no case floor is below 5; no incidence is negative or zero; SVI and the uninsured percentile lie in `[0, 1]`; the uninsured percent lies in `[0, 100]`; RUCC lies in 1–9. The uninsured percent is a percent (median 8.4, maximum 45.1), while its companion percentile is a 0–1 rank.

In the observations view the same human gap is `VALUE_STATE = 'MISSING'` with a null value for 2,493 counties, and `VALUE_STATE = 'OBSERVED'` for 651. Human status uses `NO_COUNTY_LINKED_RECORD` versus `OBSERVED`, and the stored status text matches the atlas status on every county. NLCD uses `ZERO` for Arlington agriculture (the value is 0) and `OBSERVED` otherwise. Unselected counties have no NLCD row.

State-unallocated 2023 records are present for every county, constant within each state, and sum to 1,944 when taken once per state. The largest state totals are Virginia 293 and Wisconsin 209. Summing the county column would multiply each state total by its number of counties.

Empty views do not have a missingness rate. `CURRENT_CLIMATE_COUNTY_DAY_OBSERVATIONS_V`, `CURRENT_CLIMATE_MEASURE_METADATA_V`, `INTELLIGENCE_FEED_V`, and `INTELLIGENCE_FEED_V2` returned zero rows. A daily climate series, a climate histogram, and a text corpus are not estimable from this release. Filling those views with zeros would invent data.

The pathogen source note says 33 absent canonical counties are classified as unknown source coverage. The consumer view has 35 `Unknown` counties, all in Alaska and Hawaii. This pass did not resolve 33 versus 35.

## 3. Univariate analysis

Human status has two levels: `published_count_floor` 651 counties and 158,701,707 people, and `no_county_linked_record` 2,493 counties and 172,395,886 people.

| Status | Counties | People |
| --- | ---: | ---: |
| Tick established | 1,404 | 230,033,329 |
| Tick no records | 1,215 | 57,438,899 |
| Tick reported | 490 | 41,439,955 |
| Tick unknown | 35 | 2,185,410 |
| *I. scapularis* established | 1,307 | — |
| *I. scapularis* reported | 475 | — |
| *I. scapularis* no records | 1,327 | — |
| *I. pacificus* established | 97 | — |
| *I. pacificus* reported | 15 | — |
| *I. pacificus* no records | 2,997 | — |
| Pathogen present | 689 | 123,261,641 |
| Pathogen no records | 2,420 | 205,650,542 |
| Pathogen unknown | 35 | 2,185,410 |

Species unknown is 35 for both species, the same Alaska and Hawaii counties. No county has both species established. Tick status is exactly the species rollup: Established if either species is established (1,307 + 97 = 1,404), otherwise Reported if either is reported (475 + 15 = 490), otherwise Unknown when both are unknown (35), otherwise No records (1,215). Inconsistent combinations returned zero rows.

`EVIDENCE_COMPLETENESS` takes four values only: 50 (1,224 counties), 67 (1,050), 83 (426), and 100 (444). The numeric labels match 3/6, 4/6, 5/6, and 6/6 rounded to integers. On this release the moving part is the count of three surveillance signals: a published human floor, a tick status of Established or Reported, and pathogen Present. Unknown and No records do not add a signal. The 12 status combinations map onto those four scores with no leftover county, so the column is a recode of the three flags. The 3/6 baseline is the arithmetic of the labels; the producing expression was not read from upstream code.

RUCC 2023 is an ordinal code from 1 (largest metro) through 9 (most rural). County counts are 443, 385, 358, 201, 76, 379, 247, 466, and 589. Code 5 is a small cell.

Published floors, n = 651:

| Variable | Min | P25 | Median | Mean | P75 | P90 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Case floor | 5 | 14 | 49 | 134.4 | 147.5 | 337 | 3,262 |
| Incidence floor per 100,000 | 0.15 | 22.8 | 80.9 | 139.2 | 207.2 | 346.7 | 1,640.46 |

There are 249 distinct case-floor values. The mode is 5, with 46 counties (7.1% of published counties). The next values are 6 (22 counties), 11 (19), 7 (17), and 13 (15). Case bins are 46 at exactly 5, 58 from 6 to 9, 226 from 10 to 49, 95 from 50 to 99, 189 from 100 to 499, and 37 at 500 or above. Incidence has 639 distinct values among 651 counties, so a mode is not a useful summary.

Incidence bins among the 651 published counties:

| Incidence per 100,000 | Counties | People |
| --- | ---: | ---: |
| Under 10 | 103 | 71,154,429 |
| 10 to under 50 | 152 | 35,806,190 |
| 50 to under 100 | 106 | 22,980,998 |
| 100 to under 200 | 118 | 17,141,662 |
| 200 to under 500 | 145 | 10,604,090 |
| 500 or above | 27 | 1,014,338 |

The 103 low-incidence published counties hold 44.8% of the people who live in a published-floor county. The 290 counties at or above 100 per 100,000 hold 28,760,090 people.

For every published county, incidence equals `CASE_COUNT_FLOOR_2023 / POPULATION * 100000` within 0.05 per 100,000 (median absolute residual 0.03). The atlas population is the incidence denominator. It is the 2022 SVI population, so the 2023 floor is cases from one year over an ACS 2018–2022 population.

Context distributions, all 3,144 counties:

| Variable | Min | P25 | Median | Mean | P75 | Max | Moment skew |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Population | 50 | 10,836 | 25,785 | 105,311 | 68,080 | 9,936,690 | 13.17 |
| Log population | 3.91 | 9.29 | 10.16 | 10.27 | 11.13 | 16.11 | 0.26 |
| SVI percentile | 0 | 0.25 | 0.50 | 0.50 | 0.75 | 1 | 0.00 |
| Uninsured percentile | 0 | 0.245 | 0.500 | 0.497 | 0.748 | 1 | 0.01 |
| Uninsured percent | 0 | 5.8 | 8.4 | 9.5 | 12.0 | 45.1 | 1.51 |
| RUCC | 1 | 2 | 6 | 5.25 | 8 | 9 | −0.12 |
| Evidence completeness | 50 | 50 | 67 | 67.2 | 83 | 100 | 0.68 |

SVI and the uninsured percentile look like uniforms: excess kurtosis is about −1.20, the uniform value. Population excess kurtosis is 290. Case-floor excess kurtosis is 46.2 and incidence excess kurtosis is 14.3.

NLCD is a two-geography demonstration, not a national distribution. Shares below are the entire layer. Changed area and mean impervious are overlays. The other five are area shares. Arlington's five-class sum is 1.000. The Connecticut planning region's five-class sum is 0.989, so about 1.1 percentage points sit in classes this measure set does not carry. Arlington agriculture is a true zero (`VALUE_STATE = 'ZERO'`).

| Geography | FIPS | Agriculture | Developed | Forest | Open water | Wetland | Changed | Impervious |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Capitol Planning Region, CT | 09110 | 0.079 | 0.372 | 0.428 | 0.016 | 0.095 | 0.005 | 0.105 |
| Arlington County, VA | 51013 | 0 | 0.967 | 0.027 | 0.004 | 0.002 | 0.0002 | 0.422 |

With two points, a land-cover correlation, a skewness coefficient, and an outlier fence are not estimable.

## 4. Bivariate analysis

The 12 human × tick × pathogen cells partition the 3,144 counties and the full population.

| Human status | Tick | Pathogen | Counties | People |
| --- | --- | --- | ---: | ---: |
| No county floor | No records | No records | 1,189 | 54,861,634 |
| No county floor | Established | No records | 582 | 60,507,583 |
| Published floor | Established | Present | 443 | 98,184,384 |
| No county floor | Reported | No records | 442 | 30,879,405 |
| No county floor | Established | Present | 228 | 22,704,146 |
| Published floor | Established | No records | 151 | 48,637,216 |
| No county floor | Unknown | Unknown | 35 | 2,185,410 |
| Published floor | Reported | No records | 31 | 8,207,299 |
| Published floor | No records | No records | 25 | 2,557,405 |
| No county floor | Reported | Present | 16 | 1,237,848 |
| Published floor | Reported | Present | 1 | 1,115,403 |
| No county floor | No records | Present | 1 | 19,860 |

Reading the margins: 594 of 1,404 established-tick counties have a published floor (42.3%), against 32 of 490 reported (6.5%) and 25 of 1,215 with no tick record (2.1%). Pathogen present is 671 of 1,404 established counties (47.8%), 17 of 490 reported (3.5%), and 1 of 1,215 with no tick record. Established tick and no human floor covers 810 counties and 83,211,729 people. That is 57.7% of established-tick counties and 36.2% of the people who live in an established-tick county, because the unpublished established counties are smaller. All three signals together cover 443 counties. A published floor with no pathogen record covers 207 counties. The two singleton cells are left unnamed.

Cramér's V, computed from these counts and interpreted only as a descriptive association, is 0.48 for human status × tick status, 0.57 for human status × pathogen status, and 0.81 for tick status × pathogen status. The last figure is high partly because Unknown aligns across tick and pathogen and because pathogen presence sits inside established tick counties. The chi-square statistics (726, 1,030, and 4,132) are not tests. Counties inside a state are dependent, and several cells are structural.

Median context shifts with human status:

| Human status | Counties | Median population | Median SVI | Median uninsured percentile | Median RUCC |
| --- | ---: | ---: | ---: | ---: | ---: |
| Published floor | 651 | 73,802 | 0.37 | 0.24 | 3 |
| No county floor | 2,493 | 20,228 | 0.55 | 0.57 | 6 |

Pathogen-present counties have median population 52,624, median SVI 0.37, and median uninsured percentile 0.26. Counties with no pathogen record have median population 20,778, median SVI 0.55, and median uninsured percentile 0.57. Established-tick counties sit between them. These location shifts are the same regional pattern seen below, not a separated effect of vulnerability or rurality.

Publication rises with population size:

| Population | Counties | Published counties | Published share |
| --- | ---: | ---: | ---: |
| Under 10,000 | 735 | 32 | 4.4% |
| 10,000 to under 50,000 | 1,413 | 222 | 15.7% |
| 50,000 to under 100,000 | 390 | 121 | 31.0% |
| 100,000 to under 500,000 | 464 | 192 | 41.4% |
| 500,000 or more | 142 | 84 | 59.2% |

RUCC is not a smooth gradient. Published share is highest in the largest metro code and lowest in the most rural code, with a break at the small code-5 cell. Median incidence among published counties generally rises toward more rural codes. Code 5 has only eight published counties, so its median and its within-code correlations are unstable.

| RUCC | Counties | Published | Published share | Median incidence if published | Pearson, incidence vs SVI | Pearson, incidence vs log population |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 443 | 168 | 37.9% | 31.8 | −0.32 | −0.32 |
| 2 | 385 | 103 | 26.8% | 52.7 | −0.30 | −0.35 |
| 3 | 358 | 106 | 29.6% | 59.1 | −0.20 | −0.23 |
| 4 | 201 | 58 | 28.9% | 125.8 | 0.03 | −0.13 |
| 5 | 76 | 8 | 10.5% | 24.2 | unstable | unstable |
| 6 | 379 | 66 | 17.4% | 139.0 | −0.09 | 0.18 |
| 7 | 247 | 34 | 13.8% | 173.6 | −0.39 | −0.20 |
| 8 | 466 | 70 | 15.0% | 217.0 | −0.17 | 0.05 |
| 9 | 589 | 38 | 6.5% | 265.1 | −0.23 | −0.45 |

SVI percentile buckets of width 0.2, plus the one county whose percentile is exactly 1 and falls in an extra width-bucket:

| SVI range | Counties | Published | Published share | Median incidence if published |
| --- | ---: | ---: | ---: | ---: |
| 0.00–0.20 | 629 | 169 | 26.9% | 111.7 |
| 0.20–0.40 | 629 | 187 | 29.7% | 102.1 |
| 0.40–0.60 | 628 | 166 | 26.4% | 76.2 |
| 0.60–0.80 | 629 | 89 | 14.1% | 29.9 |
| 0.80–1.00, excluding 1 | 628 | 40 | 6.4% | 21.8 |
| Exactly 1 | 1 | 0 | — | — |

The upper two SVI buckets have a lower published share and, among published counties, a lower median incidence. Buckets 1 and 2 are close to each other. This is the same selected, regionally clustered subset as the correlations below.

Census region, with Alaska and Hawaii in the West:

| Region | Counties | People | Published counties | Established tick | Pathogen present | Median published incidence |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Midwest | 1,055 | 68,857,396 | 238 | 504 | 324 | 44.8 |
| Northeast | 218 | 57,312,797 | 217 | 218 | 200 | 159.2 |
| South | 1,422 | 126,499,924 | 184 | 585 | 132 | 43.4 |
| West | 449 | 78,427,476 | 12 | 97 | 33 | 0.69 |

The Northeast is 6.9% of counties and 33.3% of published-floor counties. Every Northeast county has established *I. scapularis*. The West's 97 established-tick counties are all *I. pacificus*. One western county is *I. scapularis* reported. The West's published-incidence median of 0.69 is the median of 12 counties, several of them large, so a small case floor becomes a very small rate. It is a description of the published subset.

Species geography:

| Region | *I. scapularis* established | *I. scapularis* reported | *I. pacificus* established | *I. pacificus* reported | Both no records | Both unknown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Midwest | 504 | 131 | 0 | 0 | 420 | 0 |
| Northeast | 218 | 0 | 0 | 0 | 0 | 0 |
| South | 585 | 343 | 0 | 0 | 494 | 0 |
| West | 0 | 1 | 97 | 15 | 301 | 35 |

Among the 651 published counties, 34% of incidence-floor variance lies between state means (eta-squared from the county-weighted state means and the population variance). The other two-thirds is within states. For the 12 states with at least 15 published counties, the within-state Pearson correlation of incidence with log population is negative in every state, from −0.35 in Minnesota to −0.80 in Florida. The within-state correlation with SVI is negative in 10 of those states, about zero in Wisconsin (0.00), and positive in Ohio (0.14). Pooled national coefficients mix a strong between-region pattern with a size gradient that also appears inside these reporting states.

State counts use one row per state. "Established, no floor" counts established-tick counties without a published human floor. "All three no-record" counts counties with no human floor, tick No records, and pathogen No records. Alaska and Hawaii are Unknown, so they contribute 0 to that column. "State-unallocated" is the state-level human record, not a county sum.

| State | Counties | Population | Published counties | Established, no floor | Pathogen present | All three signals | All three no-record | State-unallocated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AK | 30 | 734,821 | 0 | 0 | 0 | 0 | 0 | 0 |
| AL | 67 | 5,028,092 | 1 | 35 | 0 | 0 | 12 | 29 |
| AR | 75 | 3,018,669 | 0 | 31 | 0 | 0 | 22 | 0 |
| AZ | 15 | 7,172,282 | 1 | 1 | 0 | 0 | 13 | 6 |
| CA | 58 | 39,356,104 | 6 | 49 | 29 | 5 | 2 | 43 |
| CO | 64 | 5,770,790 | 0 | 0 | 0 | 0 | 64 | 29 |
| CT | 9 | 3,611,317 | 9 | 0 | 9 | 9 | 0 | 9 |
| DC | 1 | 670,587 | 1 | 0 | 1 | 1 | 0 | 0 |
| DE | 3 | 993,635 | 3 | 0 | 3 | 3 | 0 | 24 |
| FL | 67 | 21,634,529 | 16 | 43 | 0 | 0 | 0 | 59 |
| GA | 159 | 10,722,325 | 0 | 39 | 2 | 0 | 77 | 17 |
| HI | 5 | 1,450,589 | 0 | 0 | 0 | 0 | 0 | 0 |
| IA | 99 | 3,188,836 | 8 | 43 | 17 | 1 | 22 | 77 |
| ID | 44 | 1,854,109 | 0 | 0 | 0 | 0 | 44 | 11 |
| IL | 102 | 12,757,634 | 13 | 50 | 51 | 13 | 13 | 46 |
| IN | 92 | 6,784,403 | 10 | 80 | 88 | 10 | 0 | 163 |
| KS | 105 | 2,935,922 | 0 | 4 | 0 | 0 | 78 | 8 |
| KY | 120 | 4,502,935 | 2 | 48 | 15 | 2 | 40 | 108 |
| LA | 64 | 4,640,546 | 0 | 19 | 1 | 0 | 26 | 14 |
| MA | 14 | 6,984,205 | 14 | 0 | 6 | 6 | 0 | 33 |
| MD | 24 | 6,161,707 | 24 | 0 | 10 | 10 | 0 | 66 |
| ME | 16 | 1,366,949 | 16 | 0 | 15 | 15 | 0 | 0 |
| MI | 83 | 10,057,921 | 44 | 16 | 40 | 30 | 12 | 67 |
| MN | 87 | 5,695,292 | 52 | 16 | 34 | 34 | 15 | 51 |
| MO | 115 | 6,154,422 | 0 | 23 | 0 | 0 | 82 | 15 |
| MS | 82 | 2,958,846 | 0 | 40 | 0 | 0 | 0 | 0 |
| MT | 56 | 1,091,840 | 0 | 0 | 0 | 0 | 55 | 6 |
| NC | 100 | 10,470,214 | 14 | 51 | 18 | 5 | 23 | 73 |
| ND | 53 | 776,874 | 0 | 7 | 2 | 0 | 44 | 12 |
| NE | 93 | 1,958,939 | 0 | 3 | 1 | 0 | 84 | 0 |
| NH | 10 | 1,379,610 | 10 | 0 | 10 | 10 | 0 | 9 |
| NJ | 21 | 9,249,063 | 21 | 0 | 20 | 20 | 0 | 118 |
| NM | 33 | 2,112,463 | 0 | 0 | 0 | 0 | 33 | 8 |
| NV | 17 | 3,104,817 | 1 | 0 | 0 | 0 | 15 | 8 |
| NY | 62 | 19,994,379 | 62 | 0 | 59 | 59 | 0 | 51 |
| OH | 88 | 11,774,683 | 40 | 37 | 49 | 30 | 6 | 77 |
| OK | 77 | 3,970,497 | 0 | 28 | 0 | 0 | 22 | 0 |
| OR | 36 | 4,229,374 | 3 | 15 | 1 | 0 | 14 | 37 |
| PA | 67 | 12,989,208 | 67 | 0 | 67 | 67 | 0 | 0 |
| RI | 5 | 1,094,250 | 5 | 0 | 1 | 1 | 0 | 0 |
| SC | 46 | 5,142,750 | 2 | 21 | 3 | 1 | 7 | 42 |
| SD | 66 | 890,342 | 0 | 4 | 1 | 0 | 58 | 5 |
| TN | 95 | 6,923,772 | 2 | 27 | 6 | 0 | 38 | 39 |
| TX | 254 | 29,243,342 | 0 | 28 | 0 | 0 | 182 | 27 |
| UT | 29 | 3,283,809 | 1 | 5 | 0 | 0 | 20 | 7 |
| VA | 133 | 8,624,511 | 65 | 28 | 47 | 31 | 25 | 293 |
| VT | 14 | 643,816 | 13 | 1 | 13 | 13 | 0 | 6 |
| WA | 39 | 7,688,549 | 0 | 17 | 3 | 0 | 17 | 25 |
| WI | 72 | 5,882,128 | 71 | 1 | 41 | 41 | 0 | 209 |
| WV | 55 | 1,792,967 | 54 | 0 | 26 | 26 | 1 | 17 |
| WY | 23 | 577,929 | 0 | 0 | 0 | 0 | 23 | 0 |
| Total | 3,144 | 331,097,593 | 651 | 810 | 689 | 443 | 1,189 | 1,944 |

Nineteen states have no published county floor: Alaska, Arkansas, Colorado, Georgia, Hawaii, Idaho, Kansas, Louisiana, Missouri, Mississippi, Montana, Nebraska, New Mexico, North Dakota, Oklahoma, South Dakota, Texas, Washington, and Wyoming. The largest established-tick gaps on the county count are Indiana 80, North Carolina 51, Illinois 50, California 49, Kentucky 48, Florida 43, Iowa 43, Mississippi 40, Georgia 39, and Ohio 37. Florida has published floors in 16 counties and pathogen present in none.

## 5. Outlier detection

The 1.5-IQR rule and the |z| > 3 rule were applied as screens, then compared with the log scale. They flag skew and censoring. They do not identify rows to drop.

| Variable | n | Above the upper 1.5-IQR fence | Below the lower fence | Absolute z > 3 |
| --- | ---: | ---: | ---: | ---: |
| Case floor | 651 | 63 | 0 | 16 |
| Incidence floor | 651 | 30 | 0 | 10 |
| Log case floor | 651 | 0 | 0 | 0 |
| Log incidence floor | 651 | 0 | 12 | 4 |
| Population | 3,144 | 440 | 0 | 41 |
| Log population | 3,144 | 42 | 20 | 10 |
| Uninsured percent | 3,144 | 91 | 0 | 41 |
| SVI percentile | 3,144 | 0 | 0 | 0 |
| Uninsured percentile | 3,144 | 0 | 0 | 0 |

The case-floor upper fence is 347.8 and the incidence upper fence is 483.8. Both lower fences fall below the data, so the IQR rule cannot see the left censoring at 5 cases. Population flags 440 of 3,144 counties, which is the right skew of city size rather than a set of bad populations. Log population brings that screen down to 62 counties. Log case counts bring the case-floor screen to zero. Log incidence moves the screen to the other tail: 12 published counties fall below the lower fence because rates near the minimum of 0.15 become large negative logs. A log is a reasonable variance stabilizer for population and case floors. For incidence it trades a long right tail for a left tail of large, low-rate counties.

SVI and the uninsured percentile have no IQR outliers because they are bounded percentiles. The uninsured percent, which is the skewed companion of that percentile, flags 91 counties above 21.3%.

## 6. Correlation

Associations below are Pearson unless noted. The published-floor block uses the 651 counties with a positive incidence floor. The all-county block uses indicator coding: published floor, established tick, and pathogen present are 1 or 0.

Published floors, n = 651:

| Pair | Pearson | Spearman |
| --- | ---: | ---: |
| Incidence, log population | −0.41 | −0.50 |
| Incidence, RUCC | 0.42 | 0.46 |
| Incidence, SVI percentile | −0.22 | −0.27 |
| Incidence, uninsured percentile | −0.11 | −0.18 |
| Case floor, log population | 0.38 | 0.31 |
| Case floor, incidence | 0.23 | 0.61 |
| Case floor, uninsured percentile | −0.26 | — |
| Case floor, RUCC | −0.25 | — |
| Case floor, SVI percentile | 0.01 | — |
| Log incidence, log population | −0.56 | — |
| Log incidence, RUCC | 0.46 | — |
| Log incidence, SVI percentile | −0.32 | — |
| SVI percentile, uninsured percentile | 0.48 | 0.45 |
| Log population, RUCC | −0.76 | −0.77 |
| Uninsured percentile, uninsured percent | 0.92 | 1.00 |

Case counts and incidence move together in rank (Spearman 0.61) and only weakly in the raw Pearson correlation (0.23), which is what the skew and the rate-versus-count distinction produce. Larger published counties have higher case floors and lower incidence floors. More rural RUCC codes have higher incidence floors in the pooled published subset, and they also have much smaller populations (log population with RUCC is −0.76). SVI and uninsured percentile move together moderately. SVI and case floors do not (0.01).

All counties, n = 3,144:

| Pair | Pearson |
| --- | ---: |
| Published floor, pathogen present | 0.57 |
| Published floor, established tick | 0.48 |
| Published floor, any tick record | 0.38 |
| Published floor, log population | 0.37 |
| Published floor, uninsured percentile | −0.37 |
| Published floor, RUCC | −0.25 |
| Published floor, SVI percentile | −0.20 |
| Established tick, pathogen present | 0.56 |
| SVI percentile, uninsured percentile | 0.58 |
| Log population, RUCC | −0.73 |

On all 3,144 counties the Spearman correlation between uninsured percent and uninsured percentile is 1.00. The percentile adds no rank information beyond the percent. Pearson is lower wherever it was computed on the published subset (0.92) because the percent is right-skewed and the percentile is flat.

`EVIDENCE_COMPLETENESS` correlates 0.79 with the published-floor indicator. That number is mechanical: the score counts the published floor as one of its inputs. It is reported so it is not mistaken for a discovered association.

The September-pinned tier score correlates 0.41 with the current published incidence floor, 0.26 with log population, and −0.16 with SVI, on the same 651 counties. See the tier section for why this is not a model evaluation.

## 7. Distribution and skewness

Moment skew and the sample `SKEW()` agree at two decimals for every variable below.

| Variable | Cohort | Moment skew | After natural log |
| --- | --- | ---: | ---: |
| Population | 3,144 counties | 13.17 | 0.26 |
| Uninsured percent | 3,144 counties | 1.51 | — |
| Case floor | 651 published | 5.33 | 0.18 |
| Incidence floor | 651 published | 2.73 | −0.87 |
| Evidence completeness | 3,144 counties | 0.68 | discrete, log not applied |
| Log population already | 3,144 counties | 0.26 | — |
| RUCC | 3,144 counties | −0.12 | ordinal, log not applied |
| Uninsured percentile | 3,144 counties | 0.01 | already a rank |
| SVI percentile | 3,144 counties | 0.00 | already a rank |

Positive skew of population and of the case floor is strong, and the log removes most of it. Incidence skew is also positive. The log overshoots (skew −0.87, and the mean of the log, 4.04, falls below the median of the log, 4.39) because the left side of the incidence distribution reaches 0.15. Evidence completeness is four atoms, so its skew describes that mix. RUCC skew near zero does not make the code symmetric in a substantive sense: mass sits at both the metro and rural ends.

## 8. Feature relationships

What a later feature set can treat as separate information, based on this release:

- Human status and the two floors are one fact. The floors are null exactly where status is `no_county_linked_record`, and incidence is the case floor divided by atlas population, rounded to two decimals.
- The case floor is left-censored at 5. Forty-six published counties sit on that point. A model that treats the floor as a complete count compresses everything below 5.
- Tick status, *I. scapularis* status, and *I. pacificus* status are one rollup plus a geography split. The species ranges do not overlap on this release. A single tick code pools an eastern and a western species.
- Pathogen status is dependent on that tick rollup and is still not a duplicate: 733 established-tick counties have no pathogen record, and one county has pathogen present with tick No records.
- `EVIDENCE_COMPLETENESS` duplicates the three surveillance flags. Using it beside those flags double-counts them.
- Uninsured percent and uninsured percentile are one ranking. SVI is a different percentile and correlates 0.58 with the uninsured percentile nationally, 0.48 inside the published subset.
- RUCC and log population are strongly aligned (−0.73 nationally). Both still have a relationship with publication and with incidence, and those relationships are entangled with region.
- State-unallocated records are a state attribute. They are constant on county rows and are not a county outcome.
- Geometry is complete and was not used as a predictor here.
- NLCD shares are real for two geographies only. They cannot enter a national feature matrix. A zero for an unselected county would be false.
- The release `SCORE_DEFAULTS` mix is metadata. It is not a county feature column.

The tier view is an existing output, not a new measurement. All 3,144 FIPS match the atlas in both directions. The view is pinned to release `governed-2026-09-18-unknown-coverage`, model `tier1-statistical-reference-v1`, features `tier1-county-features-v2`, evaluation `tier1-selection-evaluation-v1`, tier policy `tier1-review-percentile-v1`, one run, generated 2026-10-07T02:14:24Z. The current atlas release is the October NLCD cohort. Human evidence state matches current human status exactly: sufficient lines up with the 651 published floors, and insufficient lines up with the 2,493 other counties. SVI, RUCC, and incidence were not compared value-by-value with the September bundle in this pass.

| Tier | Counties | Who is in it | Score min, median, max | Percentile range |
| --- | ---: | --- | --- | --- |
| HIGH | 315 | All sufficient, all published floors | 1.65, 1.85, 2.54 | 90.0–100 |
| MEDIUM | 628 | 336 published floors and 292 without a floor | 0.97, 1.21, 1.65 | 70.0–90.0 |
| LOW | 2,201 | All insufficient, all without a floor | 0.44, 0.63, 0.97 | 0–70.0 |

The score ranges abut: LOW ends at 0.970 and MEDIUM begins at 0.970; MEDIUM ends at 1.647 and HIGH begins at 1.647. The empirical percentiles fall in 0–70, 70–90, and 90–100. HIGH is the top tenth of the 3,144-county ranking (315 counties), MEDIUM the next fifth (628), and LOW the rest (2,201). The labels are percentile bins of that score. Within-tier skew is mild (0.30 to 0.79). The score's correlation with current published incidence is a cross-release description of a selected subset. It is not an evaluation, and the score is not available as a label for a new model.

Lineage retains both releases: 44,016 rows for `governed-2026-09-18-unknown-coverage` and 44,030 for the current release. The 14-row difference is the seven NLCD measures on two counties. Temporal windows are `2022 (2018-2022 ACS)` (6 measures), `2023` (5 measures, including RUCC and the human measures), `through 2025-12-31` (3 measures: both tick species and pathogen), and `2025` (the 14 NLCD rows). County FIPS and match kind are never null.

| Match kind | Where it appears |
| --- | --- |
| `LEGACY_CONFORMED` | County id, geometry, population, SVI, both uninsured fields, and RUCC, for all 3,144 counties on both releases |
| `RESTRICTED_CDC_CONFORMED` | Both tick species and pathogen, for 3,109 in-scope counties on both releases |
| `UNMATCHED` | Every human measure, including state-unallocated records, for all 3,144 counties on both releases; also the 35 Alaska and Hawaii tick and pathogen rows |
| `IMMUTABLE_REVISION` | The 14 current-release NLCD rows |

The 210 null artifact hashes are exactly those 35 counties × 3 vector/pathogen measures × 2 releases. Human `UNMATCHED` rows still have artifact hashes. The human match-kind gap is present on both retained releases while the atlas continues to publish the human values with CDC 2023 source metadata. Whether that `UNMATCHED` result is expected is a data-owner question.

Analyst-visible feedback is four rows from 2026-09-26 through 2026-10-01: three `general` / `new`, and one `usability` / `reviewed`. One general row has no state and no county. Four rows can be counted. They cannot support a distribution.

## 9. Checklist outcome and questions the release can support

| Checklist step | Result on this release |
| --- | --- |
| Overview | 14 views, one national county table of 3,144 × 21, long observations of 9,446, lineage of 88,046, four empty or census-only surfaces |
| Missing values | Human floors are structurally null for 79.3% of counties; Unknown is a real status for 35 counties; climate and text feeds have no rows to call missing |
| Univariate | Two human states, four tick states, three pathogen states, four-level evidence score, right-skewed floors, uniform percentiles |
| Bivariate | Publication, tick establishment, and pathogen presence move together and concentrate in the Northeast; size and RUCC move with publication |
| Outliers | Right-tail flags on the raw floors and on population; the log changes which tail is flagged; nothing here is a drop rule |
| Correlation | Moderate associations inside a selected, state-clustered subset; uninsured percent and percentile are redundant; evidence score is mechanical |
| Skewness | Log stabilizes population and case floors; log incidence becomes left-skewed |
| Feature relationships | Species split, censoring at 5, and the deterministic evidence score are the feature constraints |
| Workflow close | Descriptive typology is estimable. Climate, text, national land cover, change over time, complete incidence, and a tier-supervised model are not |

Questions worth a later spec, and questions this release cannot carry:

| Question | What the data can do | Disposition |
| --- | --- | --- |
| Where do human floors, tick establishment, and pathogen records agree or diverge? | Full 3,144-county cross-tab and state table | Answered here, as description |
| How selected is the published-floor subset? | Size, RUCC, region, and within-state size gradients | Answered here, as description |
| Do the floors need a transform before a later model? | Skew, heaping at 5, and the log comparison | Answered as a preprocessing fact, not as feature admission |
| Which unlabeled counties resemble published-floor counties? | County features exist; the unlabeled state is censored documentation, and states are dependent | FOLLOW_UP. Needs a frozen spec, leave-one-state-out evaluation, an explicit missingness rule, species stratification, and a ban on using the tier score or evidence completeness as a label or extra predictor |
| Is SVI associated with incidence inside reporting states? | Within-state signs disagree (Ohio positive, Wisconsin about zero, ten states negative) | Already outside this unscoped pass. A confirmatory claim needs its own prespecified cohort |
| Can land cover explain county differences? | Two 2025 geographies | NOT_ESTIMABLE |
| Can daily climate or seasonality be described? | Climate observation and metadata views exist and contain zero rows | NOT_ESTIMABLE. Do not impute |
| Can text or news intelligence be described? | Both feed views contain zero rows | NOT_ESTIMABLE |
| Can change over time be estimated? | One human year, cumulative tick and pathogen status, one RUCC vintage, one SVI layer | NOT_ESTIMABLE |
| Can the tier score supervise or validate a new model? | The score is a percentile bin of a September-pinned reference | REJECT for that use |

## Decision

FOLLOW_UP. The published county release can support a descriptive typology and, after a frozen spec, a censored-floor or positive-unlabeled question about surveillance follow-up. It cannot support a national land-cover model, a climate model, a text model, a time-series model, a claim of complete incidence, or a claim about individual risk.

Smallest next step: write one analysis spec that ranks unlabeled counties by resemblance to published-floor counties, with leave-one-state-out evaluation, species kept distinct, and no use of the tier score or `EVIDENCE_COMPLETENESS` as an input or a label. Before that rank is treated as operational, ask the data owner whether human `UNMATCHED` lineage is expected and whether the pathogen note's 33 unknown-coverage counties are the same set as the 35 Alaska and Hawaii counties on the consumer view. The empty climate views are a load question, not an imputation task.

## Reproduction and retained evidence

- Code revision at read time: `024bbbf74a7da8e54566bd60e8e762d85a51e24f`. This document is uncommitted relative to that revision.
- Objects read: the 14 views in the overview table, `INFORMATION_SCHEMA.SCHEMATA`, `INFORMATION_SCHEMA.TABLES`, and `INFORMATION_SCHEMA.COLUMNS`. No base table was visible. No object was written.
- Session: `snow sql` as the verified read role, database, schema, and `COMPUTE_WH`, with `STATEMENT_TIMEOUT_IN_SECONDS` of 120 to 300. Connection selection stays in the local environment and is not recorded here.
- Headline county partition:

```sql
SELECT HUMAN_STATUS, TICK_STATUS, BURGDORFERI_STATUS,
       COUNT(*) AS N_COUNTIES, SUM(POPULATION) AS POPULATION
FROM PRESENTATION.CURRENT_COUNTY_ATLAS_V
GROUP BY 1, 2, 3
ORDER BY N_COUNTIES DESC;
```

- The same session produced the release row, per-column null counts, species-rollup checks, the incidence-versus-population residual, percentile and `SKEW` / `KURTOSIS` summaries, 1.5-IQR and z-score screens, `CORR` and rank correlations, RUCC and state and region tables, the observations-to-atlas match, the NLCD value census, the tier join, and the lineage match-kind and temporal-window counts. Definitions are in the method section.
- Lifecycle / review: exploratory description only. The tier view was read as an existing output and was not re-scored.
- Transient artifacts intentionally not committed: ignored `outputs/eda-prod-exhaustive/` query files and JSON aggregates.
- Snowflake writes: none.
